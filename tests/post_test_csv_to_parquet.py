"""
Unit tests for Post/PLEXOS/CsvToParquet/convert_csv_to_parquet.py

Tests the standalone CSV→Parquet conversion script (conversion only, no DataHub upload).
"""
import os
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest

from .conftest import get_module


MOD = get_module("new_csv_to_parquet")

_MOD_NAME = "convert_csv_to_parquet_new"


def _write_csv(path: Path, rows: int = 20) -> None:
    """Write a small valid CSV to path."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=rows, freq="h"),
        "value_a":   range(rows),
        "value_b":   [x * 1.5 for x in range(rows)],
    })
    df.to_csv(path, index=False)


class TestConvertSingleCsvToParquet:
    """Test the convert_single_csv_to_parquet function."""

    def test_converts_csv_to_parquet_and_deletes_source(self, tmp_dir):
        """CSV is converted to Parquet in-place; source CSV is deleted on success."""
        csv_path = tmp_dir / "data.csv"
        _write_csv(csv_path)

        result_path, success, error = MOD.convert_single_csv_to_parquet(str(csv_path))

        assert success is True
        assert error is None
        parquet_path = csv_path.with_suffix(".parquet")
        assert parquet_path.exists(), "Parquet file should be created"
        assert not csv_path.exists(), "Source CSV should be deleted after successful conversion"

    def test_converted_parquet_has_correct_row_count(self, tmp_dir):
        """Row count in Parquet matches the source CSV."""
        csv_path = tmp_dir / "data.csv"
        _write_csv(csv_path, rows=50)

        MOD.convert_single_csv_to_parquet(str(csv_path))

        df = pd.read_parquet(csv_path.with_suffix(".parquet"))
        assert len(df) == 50

    def test_converted_parquet_has_correct_columns(self, tmp_dir):
        """Column names are preserved during conversion."""
        csv_path = tmp_dir / "data.csv"
        _write_csv(csv_path)

        MOD.convert_single_csv_to_parquet(str(csv_path))

        df = pd.read_parquet(csv_path.with_suffix(".parquet"))
        assert "value_a" in df.columns
        assert "value_b" in df.columns

    def test_returns_false_for_nonexistent_file(self, tmp_dir):
        """Non-existent CSV path returns (path, False, error_msg)."""
        ghost = str(tmp_dir / "ghost.csv")
        result_path, success, error = MOD.convert_single_csv_to_parquet(ghost)

        assert success is False
        assert error is not None

    def test_returns_false_when_duckdb_raises(self, tmp_dir):
        """If DuckDB raises during conversion the function returns failure."""
        from unittest.mock import patch, MagicMock
        csv_file = tmp_dir / "data.csv"
        _write_csv(csv_file)

        with patch(f"{_MOD_NAME}.duckdb.connect") as mock_connect:
            mock_connect.side_effect = Exception("DuckDB error")
            result_path, success, error = MOD.convert_single_csv_to_parquet(str(csv_file))

        assert success is False
        assert error is not None

    def test_result_path_matches_input(self, tmp_dir):
        """The returned path is always the input CSV path."""
        csv_path = tmp_dir / "data.csv"
        _write_csv(csv_path)

        result_path, _, _ = MOD.convert_single_csv_to_parquet(str(csv_path))

        assert result_path == str(csv_path)


class TestConvertFolder:
    """Test the convert_folder function."""

    def test_converts_all_csvs_in_folder(self, tmp_dir):
        """All CSV files in the folder are converted to Parquet."""
        for name in ("a.csv", "b.csv", "c.csv"):
            _write_csv(tmp_dir / name)

        success = MOD.convert_folder(str(tmp_dir))

        assert success is True
        for name in ("a.parquet", "b.parquet", "c.parquet"):
            assert (tmp_dir / name).exists()
        # Source CSVs should be gone
        for name in ("a.csv", "b.csv", "c.csv"):
            assert not (tmp_dir / name).exists()

    def test_converts_csvs_in_subdirectories(self, tmp_dir):
        """Conversion is recursive — CSV files in subdirectories are also converted."""
        sub = tmp_dir / "subdir"
        sub.mkdir()
        _write_csv(tmp_dir / "root.csv")
        _write_csv(sub / "nested.csv")

        success = MOD.convert_folder(str(tmp_dir))

        assert success is True
        assert (tmp_dir / "root.parquet").exists()
        assert (sub / "nested.parquet").exists()

    def test_returns_true_when_no_csvs_found(self, tmp_dir):
        """Folder with no CSV files is not an error."""
        (tmp_dir / "data.parquet").write_bytes(b"not-a-real-parquet-but-ignored")

        success = MOD.convert_folder(str(tmp_dir))

        assert success is True

    def test_non_csv_files_are_not_touched(self, tmp_dir):
        """Parquet and text files that exist before conversion are left intact."""
        _write_csv(tmp_dir / "convert_me.csv")
        existing_parquet = tmp_dir / "keep.parquet"
        existing_parquet.write_bytes(b"existing")
        keep_txt = tmp_dir / "readme.txt"
        keep_txt.write_text("notes")

        MOD.convert_folder(str(tmp_dir))

        assert existing_parquet.exists()
        assert keep_txt.exists()

    def test_returns_false_on_any_conversion_failure(self, tmp_dir):
        """If at least one file fails, convert_folder returns False."""
        _write_csv(tmp_dir / "good.csv")
        bad = tmp_dir / "bad.csv"
        bad.write_bytes(b"\x00\xff" * 100)  # unreadable

        success = MOD.convert_folder(str(tmp_dir))

        assert success is False


class TestMainFunction:
    """Test the main() entry point with argument parsing."""

    def test_main_missing_required_args(self):
        """main() exits with code 2 when -r is not supplied."""
        with patch("sys.argv", ["convert_csv_to_parquet.py"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            assert exc.value.code == 2

    def test_main_with_nonexistent_folder(self, tmp_dir):
        """main() returns 1 when the target folder does not exist."""
        with patch("sys.argv", [
            "convert_csv_to_parquet.py",
            "-r", str(tmp_dir / "does_not_exist"),
        ]):
            exit_code = MOD.main()

        assert exit_code == 1

    def test_main_with_valid_folder(self, tmp_dir):
        """main() returns 0 after successfully converting all CSV files."""
        _write_csv(tmp_dir / "data.csv")

        with patch("sys.argv", [
            "convert_csv_to_parquet.py",
            "-r", str(tmp_dir),
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "data.parquet").exists()

    def test_main_resolves_output_path_env_var(self, tmp_dir):
        """Passing 'output_path' as -r resolves to the OUTPUT_PATH env var."""
        _write_csv(tmp_dir / "data.csv")

        with patch(f"{_MOD_NAME}.OUTPUT_PATH", str(tmp_dir)):
            with patch("sys.argv", [
                "convert_csv_to_parquet.py",
                "-r", "output_path",
            ]):
                exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "data.parquet").exists()

    def test_main_respects_workers_arg(self, tmp_dir):
        """--workers argument is accepted and forwarded to convert_folder."""
        for name in ("a.csv", "b.csv"):
            _write_csv(tmp_dir / name)

        with patch("sys.argv", [
            "convert_csv_to_parquet.py",
            "-r", str(tmp_dir),
            "-w", "1",
        ]):
            exit_code = MOD.main()

        assert exit_code == 0

    def test_main_returns_1_on_failure(self, tmp_dir):
        """main() returns 1 when convert_folder reports failure."""
        bad = tmp_dir / "bad.csv"
        bad.write_bytes(b"\x00\xff" * 100)

        with patch("sys.argv", [
            "convert_csv_to_parquet.py",
            "-r", str(tmp_dir),
        ]):
            exit_code = MOD.main()

        assert exit_code == 1

    def test_main_respects_compression_arg(self, tmp_dir):
        """--compression argument is accepted and produces a valid Parquet file."""
        _write_csv(tmp_dir / "data.csv")

        with patch("sys.argv", [
            "convert_csv_to_parquet.py",
            "-r", str(tmp_dir),
            "-c", "snappy",
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "data.parquet").exists()

    def test_main_invalid_compression_arg(self):
        """--compression with an unsupported value exits with code 2."""
        with patch("sys.argv", [
            "convert_csv_to_parquet.py",
            "-r", "/some/folder",
            "-c", "unsupported",
        ]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            assert exc.value.code == 2

    def test_main_url_encoded_root_folder_is_decoded(self, tmp_dir):
        """Spaces encoded as %20 in the -r arg are decoded before resolving the folder."""
        _write_csv(tmp_dir / "data.csv")

        encoded = str(tmp_dir).replace(" ", "%20")
        with patch("sys.argv", [
            "convert_csv_to_parquet.py",
            "-r", encoded,
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert (tmp_dir / "data.parquet").exists(), "URL-encoded path must be decoded before use"


class TestDecodePathHelper:
    """Tests for the _decode_path helper (URL-decode + quote-strip)."""

    def test_decodes_percent_encoded_spaces(self):
        assert MOD._decode_path("My%20Folder/Results") == "My Folder/Results"

    def test_decodes_other_percent_encoded_chars(self):
        assert MOD._decode_path("path%2Fwith%2Fslashes") == "path/with/slashes"

    def test_strips_single_quotes(self):
        assert MOD._decode_path("'/some/path'") == "/some/path"

    def test_strips_double_quotes(self):
        assert MOD._decode_path('"/some/path"') == "/some/path"

    def test_plain_path_unchanged(self):
        assert MOD._decode_path("/some/plain/path") == "/some/plain/path"
