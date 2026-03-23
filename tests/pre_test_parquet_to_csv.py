"""
Unit tests for Pre/PLEXOS/ParquetToCsv/convert_parquet_to_csv.py

Tests the standalone Parquet→CSV conversion script (conversion only, no DataHub download).
"""
import os
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest

from .conftest import get_module


MOD = get_module("new_parquet_to_csv")

_MOD_NAME = "convert_parquet_to_csv_new"


def _write_parquet(path: Path, rows: int = 20) -> None:
    """Write a small valid Parquet file to path."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=rows, freq="h"),
        "value_a":   range(rows),
        "value_b":   [x * 1.5 for x in range(rows)],
    })
    df.to_parquet(path, index=False)


class TestConvertSingleParquetToCsv:
    """Test the convert_single_parquet_to_csv function."""

    def test_converts_parquet_to_csv_and_deletes_source(self, tmp_dir):
        """Parquet is converted to CSV in-place; source Parquet is deleted on success."""
        parquet_path = tmp_dir / "data.parquet"
        _write_parquet(parquet_path)

        result_path, success, error = MOD.convert_single_parquet_to_csv(str(parquet_path))

        assert success is True
        assert error is None
        csv_path = parquet_path.with_suffix(".csv")
        assert csv_path.exists(), "CSV file should be created"
        assert not parquet_path.exists(), "Source Parquet should be deleted after successful conversion"

    def test_converted_csv_has_correct_row_count(self, tmp_dir):
        """Row count in CSV matches the source Parquet."""
        parquet_path = tmp_dir / "data.parquet"
        _write_parquet(parquet_path, rows=50)

        MOD.convert_single_parquet_to_csv(str(parquet_path))

        df = pd.read_csv(parquet_path.with_suffix(".csv"))
        assert len(df) == 50

    def test_converted_csv_has_correct_columns(self, tmp_dir):
        """Column names are preserved during conversion."""
        parquet_path = tmp_dir / "data.parquet"
        _write_parquet(parquet_path)

        MOD.convert_single_parquet_to_csv(str(parquet_path))

        df = pd.read_csv(parquet_path.with_suffix(".csv"))
        assert "value_a" in df.columns
        assert "value_b" in df.columns

    def test_returns_false_for_nonexistent_file(self, tmp_dir):
        """Non-existent Parquet path returns (path, False, error_msg)."""
        ghost = str(tmp_dir / "ghost.parquet")
        result_path, success, error = MOD.convert_single_parquet_to_csv(ghost)

        assert success is False
        assert error is not None

    def test_returns_false_when_duckdb_raises(self, tmp_dir):
        """If DuckDB raises during conversion the function returns failure."""
        parquet_file = tmp_dir / "data.parquet"
        _write_parquet(parquet_file)

        with patch(f"{_MOD_NAME}.duckdb.connect") as mock_connect:
            mock_connect.side_effect = Exception("DuckDB error")
            result_path, success, error = MOD.convert_single_parquet_to_csv(str(parquet_file))

        assert success is False
        assert error is not None

    def test_result_path_matches_input(self, tmp_dir):
        """The returned path is always the input Parquet path."""
        parquet_path = tmp_dir / "data.parquet"
        _write_parquet(parquet_path)

        result_path, _, _ = MOD.convert_single_parquet_to_csv(str(parquet_path))

        assert result_path == str(parquet_path)


class TestConvertFolder:
    """Test the convert_folder function."""

    def test_converts_all_parquets_in_folder(self, tmp_dir):
        """All Parquet files in the folder are converted to CSV."""
        for name in ("a.parquet", "b.parquet", "c.parquet"):
            _write_parquet(tmp_dir / name)

        success = MOD.convert_folder(str(tmp_dir))

        assert success is True
        for name in ("a.csv", "b.csv", "c.csv"):
            assert (tmp_dir / name).exists()
        # Source Parquet files should be gone
        for name in ("a.parquet", "b.parquet", "c.parquet"):
            assert not (tmp_dir / name).exists()

    def test_converts_parquets_in_subdirectories(self, tmp_dir):
        """Conversion is recursive — Parquet files in subdirectories are also converted."""
        sub = tmp_dir / "subdir"
        sub.mkdir()
        _write_parquet(tmp_dir / "root.parquet")
        _write_parquet(sub / "nested.parquet")

        success = MOD.convert_folder(str(tmp_dir))

        assert success is True
        assert (tmp_dir / "root.csv").exists()
        assert (sub / "nested.csv").exists()

    def test_returns_true_when_no_parquets_found(self, tmp_dir):
        """Folder with no Parquet files is not an error."""
        (tmp_dir / "data.csv").write_text("a,b\n1,2\n")

        success = MOD.convert_folder(str(tmp_dir))

        assert success is True

    def test_non_parquet_files_are_not_touched(self, tmp_dir):
        """CSV and text files that exist before conversion are left intact."""
        _write_parquet(tmp_dir / "convert_me.parquet")
        existing_csv = tmp_dir / "keep.csv"
        existing_csv.write_text("a,b\n1,2\n")
        keep_txt = tmp_dir / "readme.txt"
        keep_txt.write_text("notes")

        MOD.convert_folder(str(tmp_dir))

        assert existing_csv.exists()
        assert keep_txt.exists()

    def test_returns_false_on_any_conversion_failure(self, tmp_dir):
        """If at least one file fails, convert_folder returns False."""
        _write_parquet(tmp_dir / "good.parquet")
        bad = tmp_dir / "bad.parquet"
        bad.write_bytes(b"\x00\xff" * 100)  # unreadable

        success = MOD.convert_folder(str(tmp_dir))

        assert success is False


class TestMainFunction:
    """Test the main() entry point with argument parsing."""

    def test_main_missing_required_args(self):
        """main() exits with code 2 when -d is not supplied."""
        with patch("sys.argv", ["convert_parquet_to_csv.py"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            assert exc.value.code == 2

    def test_main_with_nonexistent_folder(self, tmp_dir):
        """main() returns 1 when the target folder does not exist."""
        with patch("sys.argv", [
            "convert_parquet_to_csv.py",
            "-d", str(tmp_dir / "does_not_exist"),
        ]):
            exit_code = MOD.main()

        assert exit_code == 1

    def test_main_with_valid_folder(self, tmp_dir):
        """main() returns 0 after successfully converting all Parquet files."""
        _write_parquet(tmp_dir / "data.parquet")

        with patch("sys.argv", [
            "convert_parquet_to_csv.py",
            "-d", str(tmp_dir),
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "data.csv").exists()

    def test_main_resolves_simulation_path_env_var(self, tmp_dir):
        """Passing 'simulation_path' as -d resolves to the SIMULATION_PATH env var."""
        _write_parquet(tmp_dir / "data.parquet")

        with patch(f"{_MOD_NAME}.SIMULATION_PATH", str(tmp_dir)):
            with patch("sys.argv", [
                "convert_parquet_to_csv.py",
                "-d", "simulation_path",
            ]):
                exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "data.csv").exists()

    def test_main_respects_workers_arg(self, tmp_dir):
        """--workers argument is accepted and forwarded to convert_folder."""
        for name in ("a.parquet", "b.parquet"):
            _write_parquet(tmp_dir / name)

        with patch("sys.argv", [
            "convert_parquet_to_csv.py",
            "-d", str(tmp_dir),
            "-w", "1",
        ]):
            exit_code = MOD.main()

        assert exit_code == 0

    def test_main_returns_1_on_failure(self, tmp_dir):
        """main() returns 1 when convert_folder reports failure."""
        bad = tmp_dir / "bad.parquet"
        bad.write_bytes(b"\x00\xff" * 100)

        with patch("sys.argv", [
            "convert_parquet_to_csv.py",
            "-d", str(tmp_dir),
        ]):
            exit_code = MOD.main()

        assert exit_code == 1

    def test_main_url_encoded_folder_is_decoded(self, tmp_dir):
        """Spaces encoded as %20 in the -d arg are decoded before resolving the folder."""
        _write_parquet(tmp_dir / "data.parquet")

        encoded = str(tmp_dir).replace(" ", "%20")
        with patch("sys.argv", [
            "convert_parquet_to_csv.py",
            "-d", encoded,
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "data.csv").exists(), "URL-encoded path must be decoded before use"


class TestDecodePathHelper:
    """Tests for the _decode_path helper (URL-decode + quote-strip)."""

    def test_decodes_percent_encoded_spaces(self):
        assert MOD._decode_path("My%20Folder/Data") == "My Folder/Data"

    def test_decodes_other_percent_encoded_chars(self):
        assert MOD._decode_path("path%2Fwith%2Fslashes") == "path/with/slashes"

    def test_strips_single_quotes(self):
        assert MOD._decode_path("'/some/path'") == "/some/path"

    def test_strips_double_quotes(self):
        assert MOD._decode_path('"/some/path"') == "/some/path"

    def test_plain_path_unchanged(self):
        assert MOD._decode_path("/some/plain/path") == "/some/plain/path"
