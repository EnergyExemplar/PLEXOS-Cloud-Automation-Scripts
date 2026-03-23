"""
Unit tests for Post/PLEXOS/WriteReportedProperties/write_reported_properties.py

Tests the ReportedPropertiesExporter.export method and main() entry point.
DuckDB is mocked — no real database files are required.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from .conftest import get_module


MOD = get_module("write_reported_properties")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_connection(write_parquet_creates_file=True, fetchall_rows=None, row_count=2):
    """
    Build a mock DuckDB connection context manager.

    - con.sql(main_query).write_parquet(path) creates a stub file when
      write_parquet_creates_file is True.
    - con.sql(read_parquet_query) returns a mock with .columns and .fetchall().
    - con.execute(count_query).fetchone() returns [row_count].
    """
    if fetchall_rows is None:
        fetchall_rows = [
            (1, 1, "Gen1", "Generator", "Region", "Price"),
            (2, 1, "Gen2", "Generator", "Region", "Demand"),
        ]

    created_files = []

    # Relation mock — returned by con.sql(main_query)
    mock_relation = MagicMock()

    def write_parquet_side_effect(path):
        if write_parquet_creates_file:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"PAR1")  # stub parquet bytes
            created_files.append(p)

    mock_relation.write_parquet.side_effect = write_parquet_side_effect

    # Preview result — returned by con.sql(SELECT * FROM read_parquet(...))
    mock_preview = MagicMock()
    mock_preview.columns = [
        "SeriesId", "DataFileId", "ChildObjectName",
        "ChildObjectCategoryName", "ParentObjectCategoryName", "PropertyName",
    ]
    mock_preview.fetchall.return_value = fetchall_rows

    # COUNT result
    count_mock = MagicMock()
    count_mock.fetchone.return_value = [row_count]

    def sql_side_effect(query_str):
        if "read_parquet" in query_str:
            return mock_preview
        return mock_relation

    mock_con = MagicMock()
    mock_con.sql.side_effect = sql_side_effect
    mock_con.execute.return_value = count_mock
    mock_con.__enter__ = MagicMock(return_value=mock_con)
    mock_con.__exit__ = MagicMock(return_value=None)

    return mock_con, created_files


# ---------------------------------------------------------------------------
# ReportedPropertiesExporter.export
# ---------------------------------------------------------------------------

class TestReportedPropertiesExporter:

    def test_export_success_returns_true(self, tmp_dir):
        """Successful export returns True."""
        out_dir = tmp_dir / "output"
        out_dir.mkdir()
        mock_con, _ = _make_mock_connection()

        with patch("write_reported_properties.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(out_dir))
            result = exporter.export("flattened_data.parquet")

        assert result is True

    def test_export_calls_write_parquet_with_correct_path(self, tmp_dir):
        """write_parquet creates the output file at the expected absolute path."""
        out_dir = tmp_dir / "output"
        out_dir.mkdir()
        mock_con, created_files = _make_mock_connection()

        with patch("write_reported_properties.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(out_dir))
            exporter.export("results.parquet")

        # write_parquet side_effect created a stub file at the expected path
        assert len(created_files) == 1
        assert created_files[0] == out_dir / "results.parquet"

    def test_export_connects_to_duck_db_path(self, tmp_dir):
        """duckdb.connect is called with the provided duck_db_path."""
        out_dir = tmp_dir / "output"
        out_dir.mkdir()
        duck_db = str(tmp_dir / "solution_views.ddb")
        mock_con, _ = _make_mock_connection()

        with patch("write_reported_properties.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.ReportedPropertiesExporter(duck_db, str(out_dir))
            exporter.export()

        mock_duckdb.connect.assert_called_once_with(duck_db)

    def test_export_rejects_absolute_path(self, tmp_dir):
        """Absolute path in --output-file is rejected with False."""
        exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(tmp_dir))
        assert exporter.export("/etc/evil.parquet") is False

    def test_export_rejects_forward_slash_in_filename(self, tmp_dir):
        """Filename containing '/' is rejected with False."""
        exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(tmp_dir))
        assert exporter.export("sub/dir.parquet") is False

    def test_export_rejects_backslash_in_filename(self, tmp_dir):
        """Filename containing '\\' is rejected with False."""
        exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(tmp_dir))
        assert exporter.export("sub\\dir.parquet") is False

    def test_export_rejects_path_traversal(self, tmp_dir):
        """Path traversal (../evil.parquet) is rejected with False."""
        exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(tmp_dir))
        assert exporter.export("../evil.parquet") is False

    def test_export_creates_output_directory(self, tmp_dir):
        """When output_path does not exist it is created automatically."""
        out_dir = tmp_dir / "nonexistent" / "nested"
        assert not out_dir.exists()

        mock_con, _ = _make_mock_connection()

        with patch("write_reported_properties.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(out_dir))
            result = exporter.export("out.parquet")

        assert result is True
        assert out_dir.exists()

    def test_export_mkdir_oserror_returns_false(self, tmp_dir):
        """When mkdir raises OSError the export returns False."""
        out_dir = tmp_dir / "output"

        with patch("write_reported_properties.Path.mkdir", side_effect=OSError("Permission denied")):
            exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(out_dir))
            result = exporter.export("out.parquet")

        assert result is False

    def test_export_duckdb_exception_returns_false(self, tmp_dir):
        """When DuckDB raises an exception the export returns False."""
        out_dir = tmp_dir / "output"
        out_dir.mkdir()

        mock_con = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)
        mock_con.sql.side_effect = Exception("View not found")

        with patch("write_reported_properties.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(out_dir))
            result = exporter.export("out.parquet")

        assert result is False

    def test_export_empty_data_preview(self, tmp_dir):
        """When the query returns no rows, export still succeeds."""
        out_dir = tmp_dir / "output"
        out_dir.mkdir()
        mock_con, _ = _make_mock_connection(fetchall_rows=[], row_count=0)

        with patch("write_reported_properties.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(out_dir))
            result = exporter.export("out.parquet")

        assert result is True

    def test_export_does_not_query_twice(self, tmp_dir):
        """The main query runs once via write_parquet; preview uses read_parquet."""
        out_dir = tmp_dir / "output"
        out_dir.mkdir()
        mock_con, _ = _make_mock_connection()
        sql_calls = []

        original_side_effect = mock_con.sql.side_effect

        def tracking_sql(q):
            sql_calls.append(q)
            return original_side_effect(q)

        mock_con.sql.side_effect = tracking_sql

        with patch("write_reported_properties.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.ReportedPropertiesExporter(str(tmp_dir / "views.ddb"), str(out_dir))
            exporter.export("out.parquet")

        main_query_calls = [q for q in sql_calls if "fullkeyinfo" in q]
        preview_calls = [q for q in sql_calls if "read_parquet" in q]
        assert len(main_query_calls) == 1, "Main JOIN query should be executed exactly once"
        assert len(preview_calls) == 1, "Preview should read from the written Parquet file"


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMainFunction:

    def test_main_default_output_file(self, tmp_dir):
        """Main runs successfully with the default output filename."""
        mock_con, _ = _make_mock_connection()

        with patch("sys.argv", ["write_reported_properties.py"]):
            with patch("write_reported_properties.duckdb") as mock_duckdb:
                mock_duckdb.connect.return_value = mock_con
                with patch.object(MOD, "DUCK_DB_PATH", str(tmp_dir / "views.ddb")):
                    with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                        exit_code = MOD.main()

        assert exit_code == 0

    def test_main_custom_output_file(self, tmp_dir):
        """Main respects -o / --output-file argument."""
        mock_con, created_files = _make_mock_connection()

        with patch("sys.argv", ["write_reported_properties.py", "-o", "custom.parquet"]):
            with patch("write_reported_properties.duckdb") as mock_duckdb:
                mock_duckdb.connect.return_value = mock_con
                with patch.object(MOD, "DUCK_DB_PATH", str(tmp_dir / "views.ddb")):
                    with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                        exit_code = MOD.main()

        assert exit_code == 0
        assert any("custom.parquet" in str(f) for f in created_files)

    def test_main_returns_1_on_export_failure(self, tmp_dir):
        """Main returns 1 when the export fails."""
        mock_con = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)
        mock_con.sql.side_effect = Exception("View not found")

        with patch("sys.argv", ["write_reported_properties.py"]):
            with patch("write_reported_properties.duckdb") as mock_duckdb:
                mock_duckdb.connect.return_value = mock_con
                with patch.object(MOD, "DUCK_DB_PATH", str(tmp_dir / "views.ddb")):
                    with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                        exit_code = MOD.main()

        assert exit_code == 1

    def test_main_returns_1_for_invalid_output_file(self, tmp_dir):
        """Main returns 1 when --output-file contains a path separator."""
        with patch("sys.argv", ["write_reported_properties.py", "-o", "../evil.parquet"]):
            with patch.object(MOD, "DUCK_DB_PATH", str(tmp_dir / "views.ddb")):
                with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                    exit_code = MOD.main()

        assert exit_code == 1
