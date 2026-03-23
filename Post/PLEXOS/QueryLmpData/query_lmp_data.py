"""
Query generation-weighted LMP data from the PLEXOS solution database.

Focused script — LMP analysis only. Reads solution views set up by
configure_duck_db_views.py, joins with technology lookup and memberships CSVs,
calculates generation-weighted LMPs by zone, and stages results to output_path.

Chain after configure_duck_db_views.py (to ensure solution views exist) and
after any script that produces the memberships CSV in output_path.

Environment variables used:
    duck_db_path     – required; path to the DuckDB solution database
    output_path      – required; working directory for output files
    simulation_path  – optional; base directory for resolving relative CSV paths
"""
import argparse
import datetime
import os
import sys
from pathlib import Path
from urllib.parse import unquote

import duckdb
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe in cloud containers
import matplotlib.pyplot as plt


# Required env vars — fail fast with a clear message
try:
    DUCK_DB_PATH = os.environ["duck_db_path"]
except KeyError:
    print("Error: Missing required environment variable: duck_db_path")
    sys.exit(1)

try:
    OUTPUT_PATH = os.environ["output_path"]
except KeyError:
    print("Error: Missing required environment variable: output_path")
    sys.exit(1)

# Optional env vars — use sensible defaults
SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def _resolve_file_path(value: str, base_dir: str) -> str:
    """
    Resolve a file path. If value is a plain filename (no separators), joins it
    with base_dir. Otherwise treats it as an absolute or relative path as-is.

    Args:
        value:    File path or plain filename from CLI arg.
        base_dir: Base directory to prepend for plain filenames.

    Returns:
        Resolved file path string.
    """
    p = Path(_decode_path(value))
    if not p.is_absolute() and len(p.parts) == 1:
        return str(Path(base_dir) / p)
    return str(p)


def _esc(value: str) -> str:
    """Escape single quotes for use in DuckDB SQL string literals."""
    return value.replace("'", "''")


class LmpQueryWorker:
    """
    Queries generation-weighted LMP data from PLEXOS solution views and
    stages output CSV files and an optional chart to output_path.
    """

    def __init__(self, duck_db_path: str, output_path: str) -> None:
        """
        Args:
            duck_db_path: Path to the DuckDB solution database.
            output_path:  Directory where output files are written.
        """
        self.duck_db_path = duck_db_path
        self.output_path = output_path

    def _load_csv_views(self, con: duckdb.DuckDBPyConnection, tech_lookup_path: str, memberships_path: str) -> None:
        """
        Create DuckDB views backed by technology lookup and memberships CSV files.

        Args:
            con:               Active DuckDB connection.
            tech_lookup_path:  Path to the technology classification CSV.
            memberships_path:  Path to the memberships CSV.

        Raises:
            FileNotFoundError: If either CSV file does not exist.
        """
        for label, path in [("tech_lookup_file", tech_lookup_path), ("memberships_file", memberships_path)]:
            if not Path(path).exists():
                raise FileNotFoundError(f"{label} not found: {path}")

        con.execute(f"CREATE OR REPLACE VIEW df_tech_lu AS SELECT * FROM read_csv_auto('{_esc(tech_lookup_path)}');")
        con.execute(f"CREATE OR REPLACE VIEW memberships AS SELECT * FROM read_csv_auto('{_esc(memberships_path)}');")
        print(f"[OK] Loaded tech lookup: {tech_lookup_path}")
        print(f"[OK] Loaded memberships: {memberships_path}")

    def _build_pipeline(self, con: duckdb.DuckDBPyConnection, period_type: str, phase: str) -> None:
        """
        Build all intermediate query views for the LMP analysis pipeline.

        Steps (mirroring the pipeline in the original query_lmp_data.py):
          1. Filter fullkeyinfo for Generation, Price Received, Installed Capacity
          2. Join with data parquet using SeriesId filter
          3. Join SeriesId data with object names and categories
          4. Join with period to get StartDate
          5. Pivot PropertyName to columns
          6. Add Technology classification from tech lookup
          7. Calculate revenue and time-based fields
          8. Map generators to nodes and zones via memberships
          9. Calculate generation-weighted LMPs by zone

        Args:
            con:         Active DuckDB connection.
            period_type: PeriodTypeName filter value (e.g. 'Interval').
            phase:       PhaseName filter value (e.g. 'ST').
        """
        period_esc = _esc(period_type)
        phase_esc = _esc(phase)

        print("[OK] Step 1: Filter fullkeyinfo for relevant properties")
        con.execute(f"""
            CREATE OR REPLACE VIEW relevant_series AS
            SELECT
                key.SeriesId,
                key.DataFileId,
                key.ChildObjectName,
                cat_child.Name AS ChildObjectCategoryName,
                cat_parent.Name AS ParentObjectCategoryName,
                key.PropertyName
            FROM fullkeyinfo AS key
            LEFT JOIN object AS obj_child ON key.ChildObjectId = obj_child.ObjectId
            LEFT JOIN category AS cat_child ON obj_child.CategoryId = cat_child.CategoryId
            LEFT JOIN object AS obj_parent ON key.ParentObjectId = obj_parent.ObjectId
            LEFT JOIN category AS cat_parent ON obj_parent.CategoryId = cat_parent.CategoryId
            WHERE
                key.PeriodTypeName = '{period_esc}' AND
                key.PhaseName      = '{phase_esc}' AND
                key.TimesliceName  = 'All Periods' AND
                key.PropertyName   IN ('Generation', 'Price Received', 'Installed Capacity') AND
                key.ParentClassName IN ('System') AND
                key.CollectionName  IN ('Generators', 'Batteries') AND
                key.ChildClassName  IN ('Generator', 'Battery');
        """)

        print("[OK] Step 2: Read data from relevant series")
        con.execute("""
            CREATE OR REPLACE VIEW all_data AS
            SELECT * FROM data
            WHERE SeriesId IN (SELECT SeriesId FROM relevant_series);
        """)

        print("[OK] Step 3: Join data with object names and categories")
        con.execute("""
            CREATE OR REPLACE VIEW combined_data AS
            SELECT
                d.SeriesId,
                d.PeriodId,
                d.Value,
                s.ChildObjectName,
                s.ChildObjectCategoryName,
                s.ParentObjectCategoryName,
                s.PropertyName
            FROM all_data AS d
            JOIN relevant_series AS s ON d.SeriesId = s.SeriesId;
        """)

        print("[OK] Step 4: Join with period to get dates")
        con.execute("""
            CREATE OR REPLACE VIEW combined_data_with_dates AS
            SELECT
                cd.*,
                p.StartDate
            FROM combined_data AS cd
            JOIN period AS p ON cd.PeriodId = p.PeriodId;
        """)

        print("[OK] Step 5: Pivot PropertyName to columns")
        con.execute("""
            CREATE OR REPLACE VIEW pivoted_data AS
            SELECT
                ChildObjectName,
                ChildObjectCategoryName,
                ParentObjectCategoryName,
                StartDate,
                MAX(CASE WHEN PropertyName = 'Generation'         THEN Value END) AS Generation,
                MAX(CASE WHEN PropertyName = 'Price Received'     THEN Value END) AS Price_Received,
                MAX(CASE WHEN PropertyName = 'Installed Capacity' THEN Value END) AS Installed_Capacity
            FROM combined_data_with_dates
            GROUP BY 1, 2, 3, 4;
        """)

        print("[OK] Step 6: Add Technology classification")
        con.execute("""
            CREATE OR REPLACE VIEW final_data AS
            SELECT
                pd.*,
                COALESCE(t.PSO, 'Unknown') AS Technology
            FROM pivoted_data AS pd
            LEFT JOIN df_tech_lu AS t ON pd.ChildObjectCategoryName = t.PLEXOS;
        """)

        print("[OK] Step 7: Calculate revenue and time fields")
        con.execute("""
            CREATE OR REPLACE VIEW enriched_data AS
            SELECT
                fd.*,
                fd.Generation * fd.Price_Received AS revenue_est,
                hour(fd.StartDate) AS hour,
                weekday(fd.StartDate) AS day_of_week,
                CASE WHEN weekday(fd.StartDate) IN (5, 6) THEN 'yes' ELSE 'no' END AS weekend,
                CASE
                    WHEN weekday(fd.StartDate) IN (5, 6) THEN 'offpeak'
                    WHEN hour(fd.StartDate) BETWEEN 8 AND 23 THEN 'peak'
                    ELSE 'offpeak'
                END AS peak
            FROM final_data AS fd;
        """)

        print("[OK] Step 8: Map generators to nodes and zones")
        con.execute("""
            CREATE OR REPLACE VIEW gen_node AS
            SELECT DISTINCT
                m.parent_object AS ChildObjectName,
                m.child_object  AS Node
            FROM memberships AS m
            WHERE
                (m.parent_class = 'Generator' OR m.parent_class = 'Battery') AND
                m.child_class = 'Node';
        """)
        con.execute("""
            CREATE OR REPLACE VIEW node_area AS
            SELECT DISTINCT
                m.parent_object AS Node,
                m.child_object  AS Zone
            FROM memberships AS m
            WHERE
                m.parent_class = 'Node' AND
                m.child_class  = 'Region';
        """)
        con.execute("""
            CREATE OR REPLACE VIEW area_data AS
            SELECT
                ed.*,
                na.Zone
            FROM enriched_data AS ed
            JOIN gen_node AS gn ON ed.ChildObjectName = gn.ChildObjectName
            JOIN node_area AS na ON gn.Node = na.Node;
        """)

        print("[OK] Step 9: Calculate generation-weighted LMPs")
        con.execute("""
            CREATE OR REPLACE VIEW gen_weighted_prices AS
            SELECT
                StartDate AS date,
                Zone,
                SUM(Generation)   AS Generation,
                SUM(revenue_est)  AS revenue_est,
                (SUM(revenue_est) / NULLIF(SUM(Generation), 0)) AS LMP_dollar_per_MWh
            FROM area_data
            GROUP BY 1, 2
            ORDER BY 1, 2;
        """)

    def _export_reports(self, con: duckdb.DuckDBPyConnection) -> tuple[str, str]:
        """
        Export analysis results to CSV files in output_path.

        Returns:
            Tuple of (lmp_csv_path, generation_csv_path).
        """
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        lmp_csv = str(Path(self.output_path) / f"gen_weighted_lmp_{ts}.csv")
        gen_csv = str(Path(self.output_path) / f"generation_by_generator_{ts}.csv")

        con.execute(
            f"COPY (SELECT * FROM gen_weighted_prices) "
            f"TO '{_esc(lmp_csv)}' WITH (HEADER, DELIMITER ',');"
        )
        con.execute(
            f"COPY ("
            f"SELECT ChildObjectName AS Name, StartDate, SUM(Generation) AS Generation "
            f"FROM pivoted_data GROUP BY ChildObjectName, StartDate ORDER BY StartDate"
            f") TO '{_esc(gen_csv)}' WITH (HEADER, DELIMITER ',');"
        )

        print(f"[OK] Exported LMP report      : {lmp_csv}")
        print(f"[OK] Exported generation report: {gen_csv}")
        return lmp_csv, gen_csv

    def _generate_chart(self, con: duckdb.DuckDBPyConnection, graph_date: str) -> None:
        """
        Generate an hourly generation-by-fuel chart for the given date.

        The chart uses the pre-computed Technology column from the pipeline
        (derived from the tech lookup CSV) to group generators by fuel type.
        Technology categories with no data are omitted automatically.

        Args:
            con:        Active DuckDB connection.
            graph_date: Date string in YYYY-MM-DD format.
        """
        graph_date_esc = _esc(graph_date)
        next_date = (datetime.date.fromisoformat(graph_date) + datetime.timedelta(days=1)).isoformat()

        graph_query = f"""
            SELECT
                Technology AS Fuel,
                hour(StartDate) AS Hour,
                SUM(Generation) AS Generation
            FROM final_data
            WHERE StartDate >= '{graph_date_esc}' AND StartDate < '{_esc(next_date)}'
            GROUP BY Technology, hour(StartDate)
            ORDER BY Hour, Fuel;
        """

        result = con.execute(graph_query).fetchdf()

        if result.empty:
            print(f"[WARN] No generation data found for date '{graph_date}' — chart skipped")
            return

        pivot_df = result.pivot(index="Hour", columns="Fuel", values="Generation")

        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        pivot_df.plot(kind="line", ax=ax)
        ax.set_title(f"Generation by Fuel — {graph_date}")
        ax.set_xlabel("Hour")
        ax.set_ylabel("Generation (MW)")
        ax.legend(title="Fuel")

        chart_path = str(Path(self.output_path) / f"gen_by_fuel_{graph_date}.png")
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[OK] Chart saved: {chart_path}")

    def run(
        self,
        tech_lookup_path: str,
        memberships_path: str,
        period_type: str = "Interval",
        phase: str = "ST",
        graph_date: str | None = None,
    ) -> bool:
        """
        Execute the full LMP query pipeline and write outputs to output_path.

        Args:
            tech_lookup_path: Path to the technology classification CSV.
            memberships_path: Path to the memberships CSV (in output_path).
            period_type:      PeriodTypeName filter (default: 'Interval').
            phase:            PhaseName filter (default: 'ST').
            graph_date:       Optional date (YYYY-MM-DD) for hourly chart generation.

        Returns:
            True on success, False on failure.
        """
        try:
            Path(self.output_path).mkdir(parents=True, exist_ok=True)

            with duckdb.connect(self.duck_db_path) as con:
                self._load_csv_views(con, tech_lookup_path, memberships_path)
                self._build_pipeline(con, period_type, phase)
                self._export_reports(con)
                if graph_date:
                    self._generate_chart(con, graph_date)

            print("[OK] LMP query pipeline completed.")
            return True

        except FileNotFoundError as e:
            print(f"[FAIL] {e}")
            return False
        except duckdb.Error as e:
            print(f"[FAIL] DuckDB error: {e}")
            return False
        except Exception as e:
            print(f"[FAIL] Unexpected error: {e}")
            return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query generation-weighted LMP data from the PLEXOS solution database.",
        epilog=(
            "Examples:\n\n"
            "  Minimum — required CSV inputs:\n"
            "    python3 query_lmp_data.py \\\n"
            "      -t plexos_pso_tech_lookup.csv \\\n"
            "      -m memberships_data.csv\n\n"
            "  With chart for a specific date:\n"
            "    python3 query_lmp_data.py \\\n"
            "      -t plexos_pso_tech_lookup.csv \\\n"
            "      -m memberships_data.csv \\\n"
            "      --graph-date 2024-01-15\n\n"
            "  Explicit period type and phase:\n"
            "    python3 query_lmp_data.py \\\n"
            "      -t /simulation/tech_lookup.csv \\\n"
            "      -m /output/memberships_data.csv \\\n"
            "      --period-type Interval --phase ST"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-t", "--tech-lookup-file",
        required=True,
        help=(
            "Path to the technology classification CSV. "
            "A plain filename is resolved relative to simulation_path; "
            "an absolute path is used as-is. "
            "Expected columns: PLEXOS (generator category), PSO (technology label)."
        ),
    )
    parser.add_argument(
        "-m", "--memberships-file",
        default="memberships_data.csv",
        help=(
            "Filename of the memberships CSV in output_path, or an absolute path. "
            "Expected columns: parent_class, parent_object, child_class, child_object. "
            "Default: memberships_data.csv"
        ),
    )
    parser.add_argument(
        "--period-type",
        default="Interval",
        help="PeriodTypeName filter value (default: Interval).",
    )
    parser.add_argument(
        "--phase",
        default="ST",
        help="PhaseName filter value (default: ST).",
    )
    parser.add_argument(
        "--graph-date",
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Date for the hourly generation-by-fuel chart (format: YYYY-MM-DD). "
            "If omitted, no chart is generated."
        ),
    )
    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    print(f"[OK] Args interpreted: {args}\n")

    if args.graph_date:
        try:
            datetime.date.fromisoformat(args.graph_date)
        except ValueError:
            print(f"[FAIL] Invalid --graph-date: '{args.graph_date}' — expected format YYYY-MM-DD")
            return 1

    tech_lookup_path = _resolve_file_path(args.tech_lookup_file, SIMULATION_PATH)
    memberships_path = _resolve_file_path(args.memberships_file, OUTPUT_PATH)

    worker = LmpQueryWorker(duck_db_path=DUCK_DB_PATH, output_path=OUTPUT_PATH)
    success = worker.run(
        tech_lookup_path=tech_lookup_path,
        memberships_path=memberships_path,
        period_type=args.period_type,
        phase=args.phase,
        graph_date=args.graph_date,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
