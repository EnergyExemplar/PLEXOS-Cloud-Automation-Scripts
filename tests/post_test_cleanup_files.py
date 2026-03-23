"""
Unit tests for Post/PLEXOS/CleanupFiles/cleanup_files.py

Tests the cleanup script for deleting files/folders matching patterns.
"""
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest

from .conftest import get_module


MOD = get_module("cleanup_files")


class TestCleanupFiles:
    """Test the cleanup_files function."""

    def test_cleanup_empty_directory(self, tmp_dir):
        """Cleanup should handle empty directories gracefully."""
        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "*.csv",
            recursive=False,
            dry_run=False
        )

        assert files_deleted == 0
        assert folders_deleted == 0

    def test_cleanup_single_file(self, tmp_dir):
        """Delete a single CSV file."""
        test_file = tmp_dir / "test.csv"
        test_file.write_text("data")

        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "*.csv",
            recursive=False,
            dry_run=False
        )

        assert files_deleted == 1
        assert folders_deleted == 0
        assert not test_file.exists()

    def test_cleanup_multiple_files(self, tmp_dir):
        """Delete multiple files matching pattern."""
        (tmp_dir / "file1.csv").write_text("data")
        (tmp_dir / "file2.csv").write_text("data")
        (tmp_dir / "file3.parquet").write_text("data")  # should not be deleted

        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "*.csv",
            recursive=False,
            dry_run=False
        )

        assert files_deleted == 2
        assert folders_deleted == 0
        assert (tmp_dir / "file3.parquet").exists()
        assert not (tmp_dir / "file1.csv").exists()
        assert not (tmp_dir / "file2.csv").exists()

    def test_cleanup_folder(self, tmp_dir):
        """Delete folders matching pattern."""
        analysis_dir = tmp_dir / "Analysis_2024"
        analysis_dir.mkdir()
        (analysis_dir / "results.csv").write_text("data")

        other_dir = tmp_dir / "Other"
        other_dir.mkdir()

        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "Analysis_*",
            recursive=False,
            dry_run=False
        )

        assert files_deleted == 0
        assert folders_deleted == 1
        assert not analysis_dir.exists()
        assert other_dir.exists()

    def test_cleanup_recursive(self, tmp_dir):
        """Delete files recursively in subdirectories."""
        sub_dir = tmp_dir / "subdir"
        sub_dir.mkdir()
        (tmp_dir / "root.csv").write_text("data")
        (sub_dir / "nested.csv").write_text("data")
        (sub_dir / "keep.parquet").write_text("data")

        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "*.csv",
            recursive=True,
            dry_run=False
        )

        assert files_deleted == 2
        assert not (tmp_dir / "root.csv").exists()
        assert not (sub_dir / "nested.csv").exists()
        assert (sub_dir / "keep.parquet").exists()

    def test_cleanup_dry_run(self, tmp_dir):
        """Dry run should not delete anything."""
        (tmp_dir / "file1.csv").write_text("data")
        (tmp_dir / "file2.csv").write_text("data")

        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "*.csv",
            recursive=False,
            dry_run=True
        )

        # Counts should be 0 in dry-run mode
        assert files_deleted == 0
        assert folders_deleted == 0
        # Files should still exist
        assert (tmp_dir / "file1.csv").exists()
        assert (tmp_dir / "file2.csv").exists()

    def test_cleanup_nonexistent_path(self):
        """Cleanup should handle nonexistent paths gracefully."""
        files_deleted, folders_deleted = MOD.cleanup_files(
            "/nonexistent/path",
            "*.csv",
            recursive=False,
            dry_run=False
        )

        assert files_deleted == 0
        assert folders_deleted == 0

    def test_cleanup_no_matches(self, tmp_dir):
        """Cleanup should handle no matches gracefully."""
        (tmp_dir / "file.parquet").write_text("data")

        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "*.csv",
            recursive=False,
            dry_run=False
        )

        assert files_deleted == 0
        assert folders_deleted == 0
        assert (tmp_dir / "file.parquet").exists()

    def test_cleanup_mixed_files_and_folders(self, tmp_dir):
        """Delete both files and folders matching pattern."""
        (tmp_dir / "temp_file.csv").write_text("data")
        temp_dir = tmp_dir / "temp_folder"
        temp_dir.mkdir()
        (temp_dir / "data.txt").write_text("data")

        files_deleted, folders_deleted = MOD.cleanup_files(
            str(tmp_dir),
            "temp_*",
            recursive=False,
            dry_run=False
        )

        assert files_deleted == 1
        assert folders_deleted == 1
        assert not (tmp_dir / "temp_file.csv").exists()
        assert not temp_dir.exists()

    def test_cleanup_preserves_other_files(self, tmp_dir):
        """Cleanup should not affect files that don't match pattern."""
        (tmp_dir / "delete_me.csv").write_text("data")
        (tmp_dir / "keep_me.parquet").write_text("data")
        keep_dir = tmp_dir / "keep_this"
        keep_dir.mkdir()

        MOD.cleanup_files(
            str(tmp_dir),
            "*.csv",
            recursive=False,
            dry_run=False
        )

        assert not (tmp_dir / "delete_me.csv").exists()
        assert (tmp_dir / "keep_me.parquet").exists()
        assert keep_dir.exists()


class TestMainFunction:
    """Test the main function with argument parsing."""

    def test_main_missing_required_args(self):
        """Main should fail when -p is missing (the only required argument)."""
        with patch("sys.argv", ["cleanup_files.py"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            # argparse exits with code 2 for missing required arguments
            assert exc.value.code == 2

    def test_main_default_pattern_deletes_all(self, tmp_dir):
        """Omitting -pt defaults to '**/*' and deletes all files including subdirectories."""
        sub = tmp_dir / "subdir"
        sub.mkdir()
        (tmp_dir / "file.csv").write_text("data")
        (tmp_dir / "file.parquet").write_bytes(b"data")
        (sub / "nested.csv").write_text("data")

        with patch("sys.argv", ["cleanup_files.py", "-p", str(tmp_dir)]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert not (tmp_dir / "file.csv").exists()
        assert not (tmp_dir / "file.parquet").exists()
        assert not (sub / "nested.csv").exists()

    def test_main_with_valid_args(self, tmp_dir):
        """Main should execute successfully with valid arguments."""
        (tmp_dir / "test.csv").write_text("data")

        with patch("sys.argv", [
            "cleanup_files.py",
            "-p", str(tmp_dir),
            "-pt", "*.csv"
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert not (tmp_dir / "test.csv").exists()

    def test_main_with_recursive_flag(self, tmp_dir):
        """Main should respect recursive flag."""
        sub_dir = tmp_dir / "subdir"
        sub_dir.mkdir()
        (tmp_dir / "root.csv").write_text("data")
        (sub_dir / "nested.csv").write_text("data")

        with patch("sys.argv", [
            "cleanup_files.py",
            "-p", str(tmp_dir),
            "-pt", "*.csv",
            "-r"
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert not (tmp_dir / "root.csv").exists()
        assert not (sub_dir / "nested.csv").exists()

    def test_main_with_dry_run(self, tmp_dir):
        """Main should respect dry-run flag."""
        (tmp_dir / "test.csv").write_text("data")

        with patch("sys.argv", [
            "cleanup_files.py",
            "-p", str(tmp_dir),
            "-pt", "*.csv",
            "--dry-run"
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        # File should still exist after dry-run
        assert (tmp_dir / "test.csv").exists()

    def test_main_with_output_path_env_var(self, tmp_dir):
        """Main should resolve output_path environment variable."""
        (tmp_dir / "test.csv").write_text("data")

        with patch("sys.argv", [
            "cleanup_files.py",
            "-p", "output_path",
            "-pt", "*.csv"
        ]):
            with patch.dict("os.environ", {"output_path": str(tmp_dir)}):
                exit_code = MOD.main()

        assert exit_code == 0
        assert not (tmp_dir / "test.csv").exists()

    def test_main_output_path_not_set(self):
        """Main should fail gracefully if output_path env var is not set."""
        with patch("sys.argv", [
            "cleanup_files.py",
            "-p", "output_path",
            "-pt", "*.csv"
        ]):
            with patch.dict("os.environ", {}, clear=True):
                # Re-set the required env vars for module import
                with patch.dict("os.environ", {
                    "cloud_cli_path": "mock",
                    "simulation_path": "mock",
                }):
                    exit_code = MOD.main()

        assert exit_code == 1

    def test_main_wildcard_pattern(self, tmp_dir):
        """Main should handle wildcard patterns correctly."""
        (tmp_dir / "file1.csv").write_text("data")
        (tmp_dir / "file2.txt").write_text("data")
        (tmp_dir / "file3.csv").write_text("data")

        with patch("sys.argv", [
            "cleanup_files.py",
            "-p", str(tmp_dir),
            "-pt", "*.csv"
        ]):
            exit_code = MOD.main()

        assert exit_code == 0
        assert not (tmp_dir / "file1.csv").exists()
        assert not (tmp_dir / "file3.csv").exists()
        assert (tmp_dir / "file2.txt").exists()
