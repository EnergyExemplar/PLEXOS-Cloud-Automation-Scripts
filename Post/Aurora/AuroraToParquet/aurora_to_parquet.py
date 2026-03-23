"""
Convert Aurora solution tables to Parquet files.

Focused script — conversion only. No upload or analysis.
Chain with UploadToDataHub if you need to push results to DataHub.

Attaches the Aurora .xdb SQLite database in read-only mode (no lock or
journal files created) and exports every table as a Parquet file with an
appended SimulationId column. Because /simulation is read-only in post
tasks, read-only mode lets DuckDB read the .xdb directly without copying it.

Environment variables used:
    simulation_id   - required; identifies the current simulation run
    simulation_path - root path for study files (read-only in post tasks)
    output_path     - working directory; files here are auto-uploaded
"""
import argparse
import os
import sys
from pathlib import Path

import duckdb

# Platform-provided — injected automatically. Do not set these manually.
try:
    SIMULATION_ID = os.environ["simulation_id"]
except KeyError:
    print("Error: Missing required environment variable: simulation_id")
    sys.exit(1)

SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")
OUTPUT_PATH = os.environ.get("output_path", "/output")


class AuroraToParquetConverter:
    """Converts Aurora solution tables from an .xdb SQLite database to Parquet."""

    def __init__(self, simulation_id: str, simulation_path: str, output_path: str):
        """
        Args:
            simulation_id:   The current simulation run identifier.
            simulation_path: Root path containing the Aurora .xdb file.
            output_path:     Working directory for output files.
        """
        self.simulation_id = simulation_id
        self.simulation_path = simulation_path
        self.output_path = output_path
        self.parquet_path = os.path.join(output_path, "parquet")

    def convert(self, xdb_filename: str | None = None) -> bool:
        """
        Attach the Aurora .xdb database and export all tables as Parquet files.

        Args:
            xdb_filename: Name of the .xdb file (without path). Defaults to
                          <simulation_id>.xdb.

        Returns:
            True if all tables converted successfully.
            False if the expected .xdb file cannot be found.

        Raises:
            duckdb.Error: If an error occurs while attaching the database
                          or exporting tables.
        """
        xdb_name = xdb_filename or f"{self.simulation_id}.xdb"
        xdb_path = os.path.join(self.simulation_path, xdb_name)

        if not os.path.exists(xdb_path):
            print(f"[FAIL] Cannot find Aurora solution data: {xdb_path}")
            return False

        print(f"[OK] Found Aurora database: {xdb_path}")

        Path(self.parquet_path).mkdir(parents=True, exist_ok=True)
        print(f"[OK] Parquet output directory: {self.parquet_path}")

        table_count = self._export_tables(xdb_path)
        print(f"[OK] {table_count} table(s) converted to Parquet")
        return True

    def _export_tables(self, xdb_path: str) -> int:
        """
        Attach the Aurora SQLite database in read-only mode and export each table.

        Args:
            xdb_path: Absolute path to the .xdb SQLite file.

        Returns:
            Number of tables exported.
        """
        with duckdb.connect() as con:
            try:
                con.execute("LOAD sqlite;")
            except duckdb.Error:
                con.execute("INSTALL sqlite;")
                con.execute("LOAD sqlite;")
            safe_xdb_path = xdb_path.replace("'", "''")
            con.execute(f"ATTACH '{safe_xdb_path}' AS aurora (TYPE sqlite, READ_ONLY true);")
            con.execute("USE aurora;")

            tables = con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = 'aurora' AND table_schema = 'main'"
            ).fetchall()

            for (table_name,) in tables:
                safe_table = table_name.replace('"', '""')
                out_file = os.path.join(self.parquet_path, f"{table_name}.parquet")
                safe_out_file = out_file.replace("'", "''")
                con.execute(
                    f"COPY (SELECT *, ? AS SimulationId FROM \"{safe_table}\") "
                    f"TO '{safe_out_file}' (FORMAT 'parquet');",
                    [self.simulation_id],
                )
                print(f"  Converted: {table_name}")

        return len(tables)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Aurora .xdb solution tables to Parquet files."
    )
    parser.add_argument(
        "--xdb-filename",
        default=None,
        help="Name of the .xdb file (default: <simulation_id>.xdb).",
    )
    args = parser.parse_args()

    try:
        converter = AuroraToParquetConverter(
            simulation_id=SIMULATION_ID,
            simulation_path=SIMULATION_PATH,
            output_path=OUTPUT_PATH,
        )
        success = converter.convert(xdb_filename=args.xdb_filename)
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
