"""
Unit tests for Pre/PLEXOS/DownloadFromDataHub/download_from_datahub.py

Tests the standalone DataHub download script (download only, no conversion).
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import pytest

from .conftest import get_module


MOD = get_module("pre_download")

# Module name used as patch target (matches the name registered in sys.modules by load_script)
_MOD_NAME = "pre_download_from_datahub"


class TestDownloadFiles:
    """Test the download_files function."""

    def _make_result(self, success: bool, path: str, reason: str = None) -> MagicMock:
        r = MagicMock()
        r.Success = success
        r.RelativeFilePath = path
        r.FailureReason = reason
        return r

    def _make_response(self, results: list) -> MagicMock:
        data = MagicMock()
        data.DatahubResourceResults = results
        return data

    def test_download_success(self, tmp_dir):
        """Successful download returns True and reports downloaded file."""
        mock_data = self._make_response([
            self._make_result(True, "inputs/baseline.csv"),
        ])

        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                success = MOD.download_files(["Project/Study/inputs/**"], str(tmp_dir))

        assert success is True

    def test_download_multiple_remote_paths(self, tmp_dir):
        """Each remote path is downloaded independently; all succeeding returns True."""
        mock_data = self._make_response([
            self._make_result(True, "baseline.csv"),
        ])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                success = MOD.download_files(
                    ["Project/Study/baseline.csv", "Project/Study/forecast.csv"],
                    str(tmp_dir),
                )

        assert success is True

    def test_download_handles_no_response_data(self, tmp_dir):
        """Returns False when SDKBase returns None for a remote path."""
        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = None
                success = MOD.download_files(["Project/Study/inputs/**"], str(tmp_dir))

        assert success is False

    def test_download_handles_failed_result(self, tmp_dir):
        """Returns False when any DatahubResourceResult has Success=False."""
        mock_data = self._make_response([
            self._make_result(False, "inputs/missing.csv", "File not found"),
        ])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                success = MOD.download_files(["Project/Study/inputs/**"], str(tmp_dir))

        assert success is False

    def test_download_partial_failure(self, tmp_dir):
        """Returns False when at least one file in the result set failed."""
        mock_data = self._make_response([
            self._make_result(True,  "inputs/a.csv"),
            self._make_result(False, "inputs/b.csv", "Permission denied"),
        ])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                success = MOD.download_files(["Project/Study/inputs/**"], str(tmp_dir))

        assert success is False

    def test_download_empty_results(self, tmp_dir):
        """Returns False when DatahubResourceResults is empty (nothing downloaded)."""
        mock_data = self._make_response([])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                success = MOD.download_files(["Project/Study/empty/**"], str(tmp_dir))

        assert success is False

    def test_download_creates_local_directory(self, tmp_dir):
        """Local directory is created if it does not yet exist."""
        nested = tmp_dir / "deep" / "nested"
        assert not nested.exists()

        mock_data = self._make_response([self._make_result(True, "file.csv")])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                MOD.download_files(["Project/Study/file.csv"], str(nested))

        assert nested.exists()

    def test_download_exception_handling(self, tmp_dir):
        """Returns False gracefully when CloudSDK raises an exception."""
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            MockSDK.side_effect = Exception("SDK init failed")
            success = MOD.download_files(["Project/Study/inputs/**"], str(tmp_dir))

        assert success is False

    def test_download_sdk_called_with_correct_params(self, tmp_dir):
        """CloudSDK.datahub.download must use remote_glob_patterns, output_directory, and print_message=False."""
        mock_data = self._make_response([self._make_result(True, "file.csv")])

        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                MOD.download_files(["Project/Study/file.csv"], str(tmp_dir))

        call_kwargs = mock_instance.datahub.download.call_args.kwargs
        assert call_kwargs.get("print_message") is False
        # Must use the correct parameter names (not the old remote_folder / local_folder)
        assert "remote_glob_patterns" in call_kwargs, "SDK call must use remote_glob_patterns"
        assert "output_directory" in call_kwargs, "SDK call must use output_directory"
        assert "remote_folder" not in call_kwargs, "Old 'remote_folder' param must not be used"
        assert "local_folder" not in call_kwargs, "Old 'local_folder' param must not be used"
        # remote_glob_patterns must be a list
        assert isinstance(call_kwargs["remote_glob_patterns"], list)


class TestDecodePathHelper:
    """Tests for the _decode_path helper (URL-decode + quote-strip)."""

    def test_url_decodes_spaces(self):
        assert MOD._decode_path("Project/Study/Gas%20Demand%20NRT.csv") == "Project/Study/Gas Demand NRT.csv"

    def test_url_decodes_other_chars(self):
        assert MOD._decode_path("path%2Fwith%2Fencoded%2Fslashes") == "path/with/encoded/slashes"

    def test_strips_single_quotes(self):
        assert MOD._decode_path("'Project/Study/file.csv'") == "Project/Study/file.csv"

    def test_strips_double_quotes(self):
        assert MOD._decode_path('"Project/Study/file.csv"') == "Project/Study/file.csv"

    def test_strips_leading_quote_only(self):
        """Task runner may strip the trailing quote but leave the leading one."""
        assert MOD._decode_path("'Project/Study/Gas") == "Project/Study/Gas"

    def test_plain_path_unchanged(self):
        assert MOD._decode_path("Project/Study/file.csv") == "Project/Study/file.csv"


class TestMainFunction:
    """Test the main() entry point with argument parsing."""

    def test_main_missing_remote_path_and_env_var_returns_1(self):
        """main() returns 1 when -r is not supplied."""
        with patch("sys.argv", ["download_from_datahub.py"]):
            exit_code = MOD.main()
        assert exit_code == 1

    def test_main_success(self, tmp_dir):
        """main() returns 0 on a successful download."""
        mock_data = MagicMock()
        mock_data.DatahubResourceResults = [
            MagicMock(Success=True, RelativeFilePath="file.csv", FailureReason=None)
        ]

        with patch("sys.argv", [
            "download_from_datahub.py",
            "-r", "Project/Study/inputs/**",
            "-l", str(tmp_dir),
        ]):
            with patch(f"{_MOD_NAME}.CloudSDK"):
                with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_main_defaults_local_folder_to_output_path(self, tmp_dir):
        """Omitting -l resolves to OUTPUT_PATH."""
        mock_data = MagicMock()
        mock_data.DatahubResourceResults = [
            MagicMock(Success=True, RelativeFilePath="file.csv", FailureReason=None)
        ]

        with patch("sys.argv", ["download_from_datahub.py", "-r", "Project/Study/file.csv"]):
            with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.download.return_value = MagicMock()
                with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    MOD.main()

        call_kwargs = mock_instance.datahub.download.call_args.kwargs
        assert call_kwargs["output_directory"] == MOD.OUTPUT_PATH

    def test_main_download_failure_returns_1(self, tmp_dir):
        """main() returns 1 when download_files reports failure."""
        with patch("sys.argv", [
            "download_from_datahub.py",
            "-r", "Project/Study/inputs/**",
            "-l", str(tmp_dir),
        ]):
            with patch(f"{_MOD_NAME}.CloudSDK"):
                with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = None  # triggers failure
                    exit_code = MOD.main()

        assert exit_code == 1

    def test_main_multiple_remote_paths(self, tmp_dir):
        """main() accepts multiple -r flags and passes them as a list."""
        mock_data = MagicMock()
        mock_data.DatahubResourceResults = [
            MagicMock(Success=True, RelativeFilePath="a.csv", FailureReason=None)
        ]

        with patch("sys.argv", [
            "download_from_datahub.py",
            "-r", "Project/Study/a.csv",
            "-r", "Project/Study/b.csv",
            "-l", str(tmp_dir),
        ]):
            with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.download.return_value = MagicMock()
                with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    exit_code = MOD.main()

        # SDK should have been called twice (once per remote path)
        assert mock_instance.datahub.download.call_count == 2
        assert exit_code == 0

    def test_main_url_encoded_path_is_decoded(self, tmp_dir):
        """Spaces encoded as %20 in the -r arg are decoded before being sent to the SDK."""
        mock_data = MagicMock()
        mock_data.DatahubResourceResults = [
            MagicMock(Success=True, RelativeFilePath="Gas Demand NRT.csv", FailureReason=None)
        ]

        with patch("sys.argv", [
            "download_from_datahub.py",
            "-r", "Project/Study/Gas%20Demand%20NRT.csv",
            "-l", str(tmp_dir),
        ]):
            with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.download.return_value = MagicMock()
                with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    MOD.main()

        patterns = mock_instance.datahub.download.call_args.kwargs["remote_glob_patterns"]
        assert patterns == ["Project/Study/Gas Demand NRT.csv"], (
            "URL-encoded spaces must be decoded before being passed to the SDK"
        )

    def test_main_quotes_stripped_from_cli_args(self, tmp_dir):
        """Leading/trailing quotes left by a non-shell task runner are stripped from path values."""
        mock_data = MagicMock()
        mock_data.DatahubResourceResults = [
            MagicMock(Success=True, RelativeFilePath="file.csv", FailureReason=None)
        ]

        with patch("sys.argv", [
            "download_from_datahub.py",
            "-r", "'Project/Study/file.csv'",   # literal quotes as passed by task runner
            "-l", str(tmp_dir),
        ]):
            with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.download.return_value = MagicMock()
                with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    MOD.main()

        patterns = mock_instance.datahub.download.call_args.kwargs["remote_glob_patterns"]
        assert patterns == ["Project/Study/file.csv"], (
            "Surrounding single quotes must be stripped from -r values"
        )


