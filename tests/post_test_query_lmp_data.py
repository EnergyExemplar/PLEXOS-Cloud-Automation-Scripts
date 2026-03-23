"""
Unit tests for Post/PLEXOS/QueryLmpData/query_lmp_data.py

Tests use pytest's tmp_path fixture and create temporary CSV files and
DuckDB databases under that directory. Solution views (fullkeyinfo, data,
period, object, category) are created as real DuckDB views backed by minimal
in-memory parquet data to exercise the pipeline end-to-end.
"""
import argparse
import datetime
import json
from pathlib import Path
from unittest.mock import patch

import duckdb
import pandas as pd
import pytest

from .conftest import get_module


MOD = get_module("query_lmp_data")


# ---------------------------------------------------------------------------
# Helpers — fixture data builders
# ---------------------------------------------------------------------------

def _write_tech_lookup(tmp_path: Path) -> Path:
    """Write a minimal technology classification CSV."""
    f = tmp_path / "tech_lookup.csv"
    f.write_text("PLEXOS,PSO\nCoalCat,Coal\nGasCat,Gas\nRenCat,Renewables\n")
    return f


def _write_memberships(tmp_path: Path) -> Path:
    """Write a minimal memberships CSV linking generators → nodes → zones."""
    f = tmp_path / "memberships.csv"
    f.write_text(
        "parent_class,parent_object,child_class,child_object\n"
        "Generator,GenCoal1,Node,Node1\n"
        "Generator,GenGas1,Node,Node2\n"
        "Node,Node1,Region,ZoneA\n"
        "Node,Node2,Region,ZoneA\n"
    )
    return f


def _build_solution_views(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    """
    Create fullkeyinfo, object, category, data, and period views in the
    given DuckDB connection, mirroring the structure of a PLEXOS solution.
    Uses DuckDB COPY to write parquet files (no pyarrow dependency).
    """
    cat_path = str(tmp_path / "category.parquet").replace("\\", "/")
    con.execute(
        f"COPY (SELECT 1 AS CategoryId, 'CoalCat' AS Name "
        f"UNION ALL SELECT 2, 'GasCat' "
        f"UNION ALL SELECT 3, 'RenCat') "
        f"TO '{cat_path}' (FORMAT PARQUET);"
    )
    con.execute(f"CREATE OR REPLACE VIEW category AS SELECT * FROM read_parquet('{cat_path}');")

    obj_path = str(tmp_path / "object.parquet").replace("\\", "/")
    con.execute(
        f"COPY (SELECT 10 AS ObjectId, 1 AS CategoryId, 'GenCoal1' AS Name "
        f"UNION ALL SELECT 20, 2, 'GenGas1' "
        f"UNION ALL SELECT 99, 99, 'System') "
        f"TO '{obj_path}' (FORMAT PARQUET);"
    )
    con.execute(f"CREATE OR REPLACE VIEW object AS SELECT * FROM read_parquet('{obj_path}');")

    fk_path = str(tmp_path / "fullkeyinfo.parquet").replace("\\", "/")
    con.execute(
        f"COPY (SELECT * FROM (VALUES"
        f"  (1, 1, 10, 99, 'GenCoal1', 'Generation',      'Generators', 'Generator', 'System', 'Interval', 'ST', 'All Periods'),"
        f"  (2, 1, 20, 99, 'GenGas1',  'Generation',      'Generators', 'Generator', 'System', 'Interval', 'ST', 'All Periods'),"
        f"  (3, 1, 10, 99, 'GenCoal1', 'Price Received',  'Generators', 'Generator', 'System', 'Interval', 'ST', 'All Periods')"
        f") t(SeriesId, DataFileId, ChildObjectId, ParentObjectId, ChildObjectName,"
        f"    PropertyName, CollectionName, ChildClassName, ParentClassName,"
        f"    PeriodTypeName, PhaseName, TimesliceName)) "
        f"TO '{fk_path}' (FORMAT PARQUET);"
    )
    con.execute(f"CREATE OR REPLACE VIEW fullkeyinfo AS SELECT * FROM read_parquet('{fk_path}');")

    period_path = str(tmp_path / "period.parquet").replace("\\", "/")
    con.execute(
        f"COPY (SELECT * FROM (VALUES"
        f"  (100, TIMESTAMP '2024-01-01 00:00:00'),"
        f"  (101, TIMESTAMP '2024-01-01 01:00:00')"
        f") t(PeriodId, StartDate)) "
        f"TO '{period_path}' (FORMAT PARQUET);"
    )
    con.execute(f"CREATE OR REPLACE VIEW period AS SELECT * FROM read_parquet('{period_path}');")

    data_path = str(tmp_path / "data.parquet").replace("\\", "/")
    con.execute(
        f"COPY (SELECT * FROM (VALUES"
        f"  (1, 100, 100.0),"
        f"  (1, 101, 120.0),"
        f"  (2, 100,  80.0),"
        f"  (2, 101,  90.0),"
        f"  (3, 100,  50.0),"
        f"  (3, 101,  55.0)"
        f") t(SeriesId, PeriodId, Value)) "
        f"TO '{data_path}' (FORMAT PARQUET);"
    )
    con.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM read_parquet('{data_path}');")


def _worker(tmp_path: Path) -> MOD.LmpQueryWorker:
    return MOD.LmpQueryWorker(duck_db_path=":memory:", output_path=str(tmp_path))


# ---------------------------------------------------------------------------
# _decode_path
# ---------------------------------------------------------------------------

class TestDecodePath:
    def test_strips_single_quotes(self):
        assert MOD._decode_path("'/simulation/file.csv'") == "/simulation/file.csv"

    def test_strips_double_quotes(self):
        assert MOD._decode_path('"/simulation/file.csv"') == "/simulation/file.csv"

    def test_url_decodes_spaces(self):
        assert MOD._decode_path("My%20File.csv") == "My File.csv"

    def test_plain_string_unchanged(self):
        assert MOD._decode_path("file.csv") == "file.csv"


# ---------------------------------------------------------------------------
# _resolve_file_path
# ---------------------------------------------------------------------------

class TestResolveFilePath:
    def test_plain_filename_joined_with_base(self):
        result = MOD._resolve_file_path("lookup.csv", "/simulation")
        assert result == str(Path("/simulation") / "lookup.csv")

    def test_absolute_path_returned_as_is(self, tmp_path):
        abs_path = str(tmp_path / "lookup.csv")
        assert MOD._resolve_file_path(abs_path, "/simulation") == abs_path

    def test_relative_path_with_separator_returned_as_is(self):
        result = MOD._resolve_file_path("subdir/lookup.csv", "/simulation")
        # Path normalisation may convert / to \ on Windows — compare using Path
        assert Path(result) == Path("subdir/lookup.csv")

    def test_url_decoded_before_resolution(self):
        result = MOD._resolve_file_path("my%20lookup.csv", "/base")
        assert "my lookup.csv" in result


# ---------------------------------------------------------------------------
# LmpQueryWorker._load_csv_views
# ---------------------------------------------------------------------------

class TestLoadCsvViews:
    def test_creates_views_for_valid_files(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _worker(tmp_path)._load_csv_views(con, str(tech_path), str(mem_path))
            views = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            assert "df_tech_lu" in views
            assert "memberships" in views

    def test_raises_for_missing_tech_lookup(self, tmp_path):
        mem_path = _write_memberships(tmp_path)
        with pytest.raises(FileNotFoundError, match="tech_lookup_file"):
            with duckdb.connect() as con:
                _worker(tmp_path)._load_csv_views(
                    con,
                    "/nonexistent/tech.csv",
                    str(mem_path),
                )

    def test_raises_for_missing_memberships(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        with pytest.raises(FileNotFoundError, match="memberships_file"):
            with duckdb.connect() as con:
                _worker(tmp_path)._load_csv_views(
                    con,
                    str(tech_path),
                    "/nonexistent/mem.csv",
                )


# ---------------------------------------------------------------------------
# LmpQueryWorker._build_pipeline
# ---------------------------------------------------------------------------

class TestBuildPipeline:
    def test_builds_all_views_successfully(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")

            # Verify key intermediate views exist
            tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            for expected in ("relevant_series", "all_data", "pivoted_data", "gen_weighted_prices"):
                assert expected in tables, f"Missing view: {expected}"

    def test_relevant_series_filters_by_period_and_phase(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))

            # Use a phase that matches no data — relevant_series should be empty
            worker._build_pipeline(con, period_type="Interval", phase="LT")
            count = con.execute("SELECT COUNT(*) FROM relevant_series").fetchone()[0]
            assert count == 0

    def test_gen_weighted_prices_calculated(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")

            rows = con.execute("SELECT * FROM gen_weighted_prices").fetchall()
            # GenCoal1 and GenGas1 both map to ZoneA via Node1/Node2 → ZoneA
            assert len(rows) > 0
            zones = {row[1] for row in rows}
            assert "ZoneA" in zones

    def test_unmatched_category_gets_unknown_technology(self, tmp_path):
        """Generators whose category is absent from tech lookup get Technology = 'Unknown'."""
        # Tech lookup has no entry for 'UnknownCat'
        tech_path = tmp_path / "tech_no_match.csv"
        tech_path.write_text("PLEXOS,PSO\nCoalCat,Coal\n")
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")

            # GenGas1 has category GasCat which is NOT in the lookup above
            techs = {
                row[0]
                for row in con.execute(
                    "SELECT DISTINCT Technology FROM final_data WHERE ChildObjectName = 'GenGas1'"
                ).fetchall()
            }
            assert "Unknown" in techs, "Unmatched generator should have Technology = 'Unknown'"
            assert "Battery" not in techs, "Unmatched generator must NOT fall back to 'Battery'"

    def test_weekends_are_always_offpeak(self, tmp_path):
        """Weekend hours 8-23 must be classified as offpeak, not peak."""
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        # Build a DB with timestamps covering a weekend midday hour
        # 2024-01-13 is a Saturday
        db_path = str(tmp_path / "weekend.ddb")
        with duckdb.connect(db_path) as con:
            cat_path = str(tmp_path / "cat_wk.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT 1 AS CategoryId, 'CoalCat' AS Name) "
                f"TO '{cat_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW category AS SELECT * FROM read_parquet('{cat_path}');")

            obj_path = str(tmp_path / "obj_wk.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT 10 AS ObjectId, 1 AS CategoryId, 'GenCoal1' AS Name "
                f"UNION ALL SELECT 99, 99, 'System') "
                f"TO '{obj_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW object AS SELECT * FROM read_parquet('{obj_path}');")

            fk_path = str(tmp_path / "fk_wk.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT * FROM (VALUES"
                f"  (1, 1, 10, 99, 'GenCoal1', 'Generation',     'Generators', 'Generator', 'System', 'Interval', 'ST', 'All Periods'),"
                f"  (2, 1, 10, 99, 'GenCoal1', 'Price Received', 'Generators', 'Generator', 'System', 'Interval', 'ST', 'All Periods')"
                f") t(SeriesId, DataFileId, ChildObjectId, ParentObjectId, ChildObjectName,"
                f"    PropertyName, CollectionName, ChildClassName, ParentClassName,"
                f"    PeriodTypeName, PhaseName, TimesliceName)) "
                f"TO '{fk_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW fullkeyinfo AS SELECT * FROM read_parquet('{fk_path}');")

            # Saturday 2024-01-13 12:00 (midday — normally 'peak' hour on a weekday)
            period_path = str(tmp_path / "period_wk.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT * FROM (VALUES"
                f"  (100, TIMESTAMP '2024-01-13 12:00:00')"
                f") t(PeriodId, StartDate)) "
                f"TO '{period_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW period AS SELECT * FROM read_parquet('{period_path}');")

            data_path = str(tmp_path / "data_wk.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT * FROM (VALUES (1, 100, 100.0), (2, 100, 40.0)) "
                f"t(SeriesId, PeriodId, Value)) "
                f"TO '{data_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM read_parquet('{data_path}');")

            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")

            peaks = {
                row[0]
                for row in con.execute("SELECT DISTINCT peak FROM enriched_data").fetchall()
            }
            assert peaks == {"offpeak"}, "Saturday midday must be 'offpeak', not 'peak'"


# ---------------------------------------------------------------------------
# LmpQueryWorker._export_reports
# ---------------------------------------------------------------------------

class TestExportReports:
    def test_exports_csv_files_to_output_path(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")
            lmp_csv, gen_csv = worker._export_reports(con)

        assert Path(lmp_csv).exists(), "LMP CSV not created"
        assert Path(gen_csv).exists(), "Generation CSV not created"

    def test_lmp_csv_contains_zone_column(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")
            lmp_csv, _ = worker._export_reports(con)

        df = pd.read_csv(lmp_csv)
        assert "Zone" in df.columns
        assert "LMP_dollar_per_MWh" in df.columns

    def test_generation_csv_contains_expected_columns(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")
            _, gen_csv = worker._export_reports(con)

        df = pd.read_csv(gen_csv)
        assert "Name" in df.columns
        assert "Generation" in df.columns


# ---------------------------------------------------------------------------
# LmpQueryWorker._generate_chart
# ---------------------------------------------------------------------------

class TestGenerateChart:
    def test_skips_chart_with_warn_when_no_matching_data(self, tmp_path, capsys):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        with duckdb.connect() as con:
            _build_solution_views(con, tmp_path)
            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")
            # Use a date with no data
            worker._generate_chart(con, graph_date="2000-01-01")

        captured = capsys.readouterr()
        assert "[WARN]" in captured.out
        # No chart file should be created for a missing date
        pngs = list(tmp_path.glob("*.png"))
        assert len(pngs) == 0

    def test_generates_chart_file_when_data_exists(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        # Coal1 generator maps to Node1 → ZoneA
        mem_path = tmp_path / "mem.csv"
        mem_path.write_text(
            "parent_class,parent_object,child_class,child_object\n"
            "Generator,Coal1,Node,Node1\n"
            "Node,Node1,Region,ZoneA\n"
        )

        with duckdb.connect() as con:
            cat_path = str(tmp_path / "category.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT 1 AS CategoryId, 'CoalCat' AS Name) "
                f"TO '{cat_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW category AS SELECT * FROM read_parquet('{cat_path}');")

            obj_path = str(tmp_path / "object.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT * FROM (VALUES (10, 1, 'Coal1'), (99, 99, 'System')) "
                f"t(ObjectId, CategoryId, Name)) TO '{obj_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW object AS SELECT * FROM read_parquet('{obj_path}');")

            fk_path = str(tmp_path / "fullkeyinfo.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT * FROM (VALUES"
                f"  (1, 1, 10, 99, 'Coal1', 'Generation',     'Generators', 'Generator', 'System', 'Interval', 'ST', 'All Periods'),"
                f"  (2, 1, 10, 99, 'Coal1', 'Price Received', 'Generators', 'Generator', 'System', 'Interval', 'ST', 'All Periods')"
                f") t(SeriesId, DataFileId, ChildObjectId, ParentObjectId, ChildObjectName,"
                f"    PropertyName, CollectionName, ChildClassName, ParentClassName,"
                f"    PeriodTypeName, PhaseName, TimesliceName)) "
                f"TO '{fk_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW fullkeyinfo AS SELECT * FROM read_parquet('{fk_path}');")

            period_path = str(tmp_path / "period.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT * FROM (VALUES"
                f"  (100, TIMESTAMP '2024-01-15 00:00:00'),"
                f"  (101, TIMESTAMP '2024-01-15 01:00:00')"
                f") t(PeriodId, StartDate)) TO '{period_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW period AS SELECT * FROM read_parquet('{period_path}');")

            data_path = str(tmp_path / "data.parquet").replace("\\", "/")
            con.execute(
                f"COPY (SELECT * FROM (VALUES"
                f"  (1, 100, 150.0), (1, 101, 160.0),"
                f"  (2, 100,  45.0), (2, 101,  50.0)"
                f") t(SeriesId, PeriodId, Value)) TO '{data_path}' (FORMAT PARQUET);"
            )
            con.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM read_parquet('{data_path}');")

            worker = _worker(tmp_path)
            worker._load_csv_views(con, str(tech_path), str(mem_path))
            worker._build_pipeline(con, period_type="Interval", phase="ST")
            worker._generate_chart(con, graph_date="2024-01-15")

        charts = list(tmp_path.glob("gen_by_fuel_*.png"))
        assert len(charts) == 1, "Expected one chart PNG file"


# ---------------------------------------------------------------------------
# LmpQueryWorker.run
# ---------------------------------------------------------------------------

class TestRunMethod:
    def test_returns_true_on_success(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        db_path = str(tmp_path / "test.ddb")
        with duckdb.connect(db_path) as con:
            _build_solution_views(con, tmp_path)

        worker = MOD.LmpQueryWorker(duck_db_path=db_path, output_path=str(tmp_path))
        result = worker.run(str(tech_path), str(mem_path))
        assert result is True

    def test_returns_false_for_missing_tech_lookup(self, tmp_path):
        mem_path = _write_memberships(tmp_path)

        db_path = str(tmp_path / "test.ddb")
        with duckdb.connect(db_path) as con:
            _build_solution_views(con, tmp_path)

        worker = MOD.LmpQueryWorker(duck_db_path=db_path, output_path=str(tmp_path))
        result = worker.run("/nonexistent/tech.csv", str(mem_path))
        assert result is False

    def test_returns_false_for_missing_memberships(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)

        db_path = str(tmp_path / "test.ddb")
        with duckdb.connect(db_path) as con:
            _build_solution_views(con, tmp_path)

        worker = MOD.LmpQueryWorker(duck_db_path=db_path, output_path=str(tmp_path))
        result = worker.run(str(tech_path), "/nonexistent/mem.csv")
        assert result is False

    def test_creates_output_files(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        db_path = str(tmp_path / "test.ddb")
        with duckdb.connect(db_path) as con:
            _build_solution_views(con, tmp_path)

        output_dir = tmp_path / "output"
        worker = MOD.LmpQueryWorker(duck_db_path=db_path, output_path=str(output_dir))
        worker.run(str(tech_path), str(mem_path))

        lmp_files = list(output_dir.glob("gen_weighted_lmp_*.csv"))
        gen_files = list(output_dir.glob("generation_by_generator_*.csv"))
        assert len(lmp_files) == 1, "Expected one LMP CSV"
        assert len(gen_files) == 1, "Expected one generation CSV"

    def test_partial_failure_missing_views_returns_false(self, tmp_path):
        """Returns False when DuckDB views (e.g. fullkeyinfo) are not present."""
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        # Use an empty DB — no solution views set up
        db_path = str(tmp_path / "empty.ddb")
        duckdb.connect(db_path).close()

        worker = MOD.LmpQueryWorker(duck_db_path=db_path, output_path=str(tmp_path))
        result = worker.run(str(tech_path), str(mem_path))
        assert result is False


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain:
    def _run(self, argv: list[str]) -> int:
        with patch("sys.argv", ["query_lmp_data.py"] + argv):
            return MOD.main()

    def test_missing_required_arg_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["query_lmp_data.py"]):
                MOD.main()
        assert exc_info.value.code != 0

    def test_invalid_graph_date_returns_1(self, tmp_path):
        tech = tmp_path / "t.csv"
        tech.write_text("PLEXOS,PSO\n")
        code = self._run(["-t", str(tech), "--graph-date", "not-a-date"])
        assert code == 1

    def test_success_run_returns_0(self, tmp_path):
        tech_path = _write_tech_lookup(tmp_path)
        mem_path = _write_memberships(tmp_path)

        db_path = str(tmp_path / "test.ddb")
        with duckdb.connect(db_path) as con:
            _build_solution_views(con, tmp_path)

        with (
            patch.dict("os.environ", {
                "duck_db_path": db_path,
                "output_path": str(tmp_path),
                "simulation_path": str(tmp_path),
            }),
            patch.object(MOD, "DUCK_DB_PATH", db_path),
            patch.object(MOD, "OUTPUT_PATH", str(tmp_path)),
            patch.object(MOD, "SIMULATION_PATH", str(tmp_path)),
        ):
            code = self._run(["-t", str(tech_path), "-m", str(mem_path)])
        assert code == 0
