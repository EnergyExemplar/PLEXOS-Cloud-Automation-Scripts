"""
Unit tests for Post/PLEXOS/QueryWriteMemberships/query_write_memberships.py

Tests the MembershipExporter.export_memberships method and main() entry point.
DuckDB and SQLite are mocked — no real database files are required.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module


MOD = get_module("query_write_memberships")


# ---------------------------------------------------------------------------
# MembershipExporter.export_memberships
# ---------------------------------------------------------------------------

class TestMembershipExporter:
    """Test the MembershipExporter class."""

    def test_export_memberships_success_writes_csv(self, tmp_dir):
        """Successful export creates CSV file and returns True."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"SQLite placeholder")
        out_path = tmp_dir / "output"
        out_path.mkdir()

        def mock_execute(sql):
            if "COPY" in sql and "TO '" in sql:
                match = re.search(r"TO '([^']+)'", sql)
                if match:
                    path = Path(match.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        "parent_class,child_class,collection,parent_object,child_object\n"
                        "Region,Generator,Generators,North,G1\n"
                    )

        mock_con = MagicMock()
        mock_con.execute = MagicMock(side_effect=mock_execute)
        mock_con.execute.return_value = None
        mock_con.sql.return_value = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("query_write_memberships.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            # SELECT COUNT(*) returns a mock with fetchone() -> [2]
            call_count = [0]

            def execute_side_effect(sql):
                if "COPY" in sql and "TO '" in sql:
                    match = re.search(r"TO '([^']+)'", sql)
                    if match:
                        path = Path(match.group(1))
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(
                            "parent_class,child_class,collection,parent_object,child_object\n"
                            "Region,Generator,Generators,North,G1\n"
                        )
                elif "SELECT COUNT" in sql:
                    call_count[0] += 1
                    # Return a mock that has fetchone() returning [row_count]
                    fetch_mock = MagicMock()
                    fetch_mock.fetchone.return_value = [2]
                    return fetch_mock

            mock_con.execute.side_effect = execute_side_effect

            exporter = MOD.MembershipExporter(str(tmp_dir), str(out_path))
            success = exporter.export_memberships("memberships_data.csv")

        assert success is True
        assert (out_path / "memberships_data.csv").exists()
        content = (out_path / "memberships_data.csv").read_text()
        assert "parent_class" in content
        assert "child_class" in content

    def test_export_memberships_missing_db_returns_false(self, tmp_dir):
        """When reference.db does not exist, returns False."""
        (tmp_dir / "output").mkdir()
        exporter = MOD.MembershipExporter(str(tmp_dir), str(tmp_dir / "output"))
        success = exporter.export_memberships("out.csv")
        assert success is False

    def test_export_memberships_calls_duckdb_install_load_attach(self, tmp_dir):
        """DuckDB connection executes INSTALL sqlite, LOAD sqlite, ATTACH, USE."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        out_dir = tmp_dir / "out"
        out_dir.mkdir()

        execute_calls = []

        def capture_execute(sql):
            execute_calls.append(sql)
            if "COPY" in sql and "TO '" in sql:
                match = re.search(r"TO '([^']+)'", sql)
                if match:
                    path = Path(match.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("parent_class,child_class,collection,parent_object,child_object\n")
            elif "SELECT COUNT" in sql:
                fetch_mock = MagicMock()
                fetch_mock.fetchone.return_value = [0]
                return fetch_mock

        mock_con = MagicMock()
        mock_con.execute = MagicMock(side_effect=capture_execute)
        mock_con.sql.return_value = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("query_write_memberships.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.MembershipExporter(str(tmp_dir), str(out_dir))
            exporter.export_memberships("out.csv")

        assert any("LOAD sqlite" in c for c in execute_calls)
        assert not any("INSTALL sqlite" in c for c in execute_calls), "INSTALL should not be called when LOAD succeeds"
        assert any("ATTACH" in c and "reference.db" in c and "AS reference" in c and "READ_ONLY true" in c for c in execute_calls)
        assert any("USE reference" in c for c in execute_calls)
        assert any("COPY" in c for c in execute_calls)

    def test_export_memberships_duckdb_query_exception_returns_false(self, tmp_dir):
        """When DuckDB query fails, returns False and logs error."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        out_dir = tmp_dir / "out"
        out_dir.mkdir()

        mock_con = MagicMock()
        mock_con.execute.side_effect = Exception("SQL syntax error")
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("query_write_memberships.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.MembershipExporter(str(tmp_dir), str(out_dir))
            success = exporter.export_memberships("out.csv")

        assert success is False

    def test_export_memberships_empty_data_preview(self, tmp_dir):
        """When query returns no rows, preview shows 'No data to preview'."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        out_dir = tmp_dir / "out"
        out_dir.mkdir()

        def execute_handler(sql):
            if "COPY" in sql:
                match = re.search(r"TO '([^']+)'", sql)
                if match:
                    path = Path(match.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("parent_class,child_class,collection,parent_object,child_object\n")
            elif "SELECT COUNT" in sql:
                m = MagicMock()
                m.fetchone.return_value = [0]
                return m

        mock_con = MagicMock()
        mock_con.execute = MagicMock(side_effect=execute_handler)
        
        # Mock sql() to return empty result
        mock_result = MagicMock()
        mock_result.columns = ["parent_class", "child_class", "collection"]
        mock_result.fetchall.return_value = []  # No rows
        mock_con.sql.return_value = mock_result
        
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("query_write_memberships.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.MembershipExporter(str(tmp_dir), str(out_dir))
            success = exporter.export_memberships("out.csv")

        assert success is True
        # No assertion on print output, but code path is covered

    def test_export_memberships_installs_sqlite_if_load_fails(self, tmp_dir):
        """When LOAD sqlite raises duckdb.Error, INSTALL is called then LOAD is retried."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        out_dir = tmp_dir / "out"
        out_dir.mkdir()

        execute_calls = []
        load_call_count = [0]

        def capture_execute(sql):
            execute_calls.append(sql)
            if "LOAD sqlite" in sql:
                load_call_count[0] += 1
                if load_call_count[0] == 1:
                    raise Exception("Extension not found")  # simulates duckdb.Error on first LOAD
            if "COPY" in sql and "TO '" in sql:
                match = re.search(r"TO '([^']+)'", sql)
                if match:
                    path = Path(match.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("parent_class,child_class,collection,parent_object,child_object\n")
            elif "SELECT COUNT" in sql:
                m = MagicMock()
                m.fetchone.return_value = [0]
                return m

        mock_con = MagicMock()
        mock_con.execute = MagicMock(side_effect=capture_execute)
        mock_con.sql.return_value = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("query_write_memberships.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            mock_duckdb.Error = Exception  # make except duckdb.Error catch our simulated error
            exporter = MOD.MembershipExporter(str(tmp_dir), str(out_dir))
            success = exporter.export_memberships("out.csv")

        assert success is True
        assert any("INSTALL sqlite" in c for c in execute_calls)
        assert execute_calls.count("LOAD sqlite;") == 2

    def test_export_memberships_creates_output_directory(self, tmp_dir):
        """When output_path does not exist, it is created automatically."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        out_dir = tmp_dir / "nonexistent" / "nested"  # Does not exist yet

        def copy_to_file(sql):
            if "COPY" in sql and "TO '" in sql:
                match = re.search(r"TO '([^']+)'", sql)
                if match:
                    path = Path(match.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("parent_class,child_class,collection,parent_object,child_object\n")
            elif "SELECT COUNT" in sql:
                m = MagicMock()
                m.fetchone.return_value = [0]
                return m

        mock_con = MagicMock()
        mock_con.execute = MagicMock(side_effect=copy_to_file)
        mock_con.sql.return_value = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("query_write_memberships.duckdb") as mock_duckdb:
            mock_duckdb.connect.return_value = mock_con
            exporter = MOD.MembershipExporter(str(tmp_dir), str(out_dir))
            success = exporter.export_memberships("out.csv")

        assert success is True
        assert out_dir.exists()

    def test_export_memberships_rejects_invalid_filename(self, tmp_dir):
        """output_filename with path separators or absolute paths is rejected."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        out_dir = tmp_dir / "out"
        out_dir.mkdir()

        exporter = MOD.MembershipExporter(str(tmp_dir), str(out_dir))
        for invalid_name in ["../evil.csv", "/etc/evil.csv", "sub/dir.csv", "sub\\dir.csv"]:
            success = exporter.export_memberships(invalid_name)
            assert success is False, f"Expected False for filename {invalid_name!r}"


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMainFunction:
    """Test the main function with argument parsing."""

    def test_main_missing_output_dir_uses_env_default(self, tmp_dir):
        """Main runs with default output file when no -o given."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")

        def copy_to_file(sql):
            if "COPY" in sql and "TO '" in sql:
                match = re.search(r"TO '([^']+)'", sql)
                if match:
                    path = Path(match.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("parent_class,child_class,collection,parent_object,child_object\n")
            elif "SELECT COUNT" in sql:
                m = MagicMock()
                m.fetchone.return_value = [0]
                return m

        mock_con = MagicMock()
        mock_con.execute = MagicMock(side_effect=copy_to_file)
        mock_con.sql.return_value = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("sys.argv", ["query_write_memberships.py"]):
            with patch("query_write_memberships.duckdb") as mock_duckdb:
                mock_duckdb.connect.return_value = mock_con
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                    with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                        exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "memberships_data.csv").exists()

    def test_main_custom_output_file(self, tmp_dir):
        """Main respects -o / --output-file argument."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")

        def copy_to_file(sql):
            if "COPY" in sql and "TO '" in sql:
                match = re.search(r"TO '([^']+)'", sql)
                if match:
                    path = Path(match.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("parent_class,child_class,collection,parent_object,child_object\n")
            elif "SELECT COUNT" in sql:
                m = MagicMock()
                m.fetchone.return_value = [0]
                return m

        mock_con = MagicMock()
        mock_con.execute = MagicMock(side_effect=copy_to_file)
        mock_con.sql.return_value = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=None)

        with patch("sys.argv", ["query_write_memberships.py", "-o", "custom_memberships.csv"]):
            with patch("query_write_memberships.duckdb") as mock_duckdb:
                mock_duckdb.connect.return_value = mock_con
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                    with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                        exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "custom_memberships.csv").exists()

    def test_main_returns_1_when_export_fails(self, tmp_dir):
        """Main returns 1 when reference.db is missing."""
        (tmp_dir / "out").mkdir()
        with patch("sys.argv", ["query_write_memberships.py"]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir / "out")):
                    exit_code = MOD.main()
        assert exit_code == 1

    def test_main_handles_keyboard_interrupt(self, tmp_dir):
        """Main returns 130 when user cancels with Ctrl+C."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        
        with patch("sys.argv", ["query_write_memberships.py"]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                    with patch.object(MOD, "MembershipExporter") as MockExporter:
                        MockExporter.return_value.export_memberships.side_effect = KeyboardInterrupt()
                        exit_code = MOD.main()
        
        assert exit_code == 130

    def test_main_handles_unexpected_exception(self, tmp_dir):
        """Main returns 1 when unexpected exception occurs."""
        ref_db = tmp_dir / "reference.db"
        ref_db.write_bytes(b"x")
        
        with patch("sys.argv", ["query_write_memberships.py"]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                with patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)):
                    with patch.object(MOD, "MembershipExporter") as MockExporter:
                        MockExporter.return_value.export_memberships.side_effect = RuntimeError("Unexpected error")
                        exit_code = MOD.main()
        
        assert exit_code == 1
