"""
Unit tests for Post/PLEXOS/UploadToDataHub/upload_to_datahub.py

Tests the standalone DataHub upload script (upload only, no conversion).
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from .conftest import get_module


MOD = get_module("upload_to_datahub")


class TestUploadFolder:
    """Test the upload_folder function."""

    def test_upload_with_mocked_sdk(self, tmp_dir):
        """Test successful upload with mocked CloudSDK."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("mock data")

        # Mock the CloudSDK response
        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "test.parquet"
        mock_result.FailureReason = None

        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            mock_sdk_instance = MockSDK.return_value
            mock_sdk_instance.datahub.upload.return_value = MagicMock()
            
            with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_response_data
                
                success = MOD.upload_folder(
                    str(tmp_dir),
                    "Project/Study/Results",
                    patterns=["**/*"],
                    is_versioned=True
                )

        assert success is True
        assert MockSDK.called
        assert mock_sdk_instance.datahub.upload.called

    def test_upload_handles_no_response_data(self, tmp_dir):
        """Test upload failure when SDKBase returns None."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("mock data")

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            mock_sdk_instance = MockSDK.return_value
            mock_sdk_instance.datahub.upload.return_value = MagicMock()
            
            with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = None
                
                success = MOD.upload_folder(
                    str(tmp_dir),
                    "Project/Study/Results"
                )

        assert success is False

    def test_upload_handles_unexpected_response_structure(self, tmp_dir):
        """Test upload failure with unexpected response structure."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("mock data")

        mock_response_data = MagicMock(spec=[])  # No DatahubResourceResults attribute

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            mock_sdk_instance = MockSDK.return_value
            mock_sdk_instance.datahub.upload.return_value = MagicMock()
            
            with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_response_data
                
                success = MOD.upload_folder(
                    str(tmp_dir),
                    "Project/Study/Results"
                )

        assert success is False

    def test_upload_handles_failures(self, tmp_dir):
        """Test upload with some failed files."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("mock data")

        mock_failed_result = MagicMock()
        mock_failed_result.Success = False
        mock_failed_result.RelativeFilePath = "test.parquet"
        mock_failed_result.FailureReason = "Network error"

        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_failed_result]

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            mock_sdk_instance = MockSDK.return_value
            mock_sdk_instance.datahub.upload.return_value = MagicMock()
            
            with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_response_data
                
                success = MOD.upload_folder(
                    str(tmp_dir),
                    "Project/Study/Results"
                )

        assert success is False

    def test_upload_handles_skipped_identical_files(self, tmp_dir):
        """Test that skipped (identical) files count as success."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("mock data")

        mock_skipped_result = MagicMock()
        mock_skipped_result.Success = False
        mock_skipped_result.RelativeFilePath = "test.parquet"
        mock_skipped_result.FailureReason = "File is identical to the remote file"

        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_skipped_result]

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            mock_sdk_instance = MockSDK.return_value
            mock_sdk_instance.datahub.upload.return_value = MagicMock()
            
            with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_response_data
                
                success = MOD.upload_folder(
                    str(tmp_dir),
                    "Project/Study/Results"
                )

        # Should succeed because identical files are treated as success
        assert success is True

    def test_upload_exception_handling(self, tmp_dir):
        """Test upload handles SDK exceptions gracefully."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("mock data")

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            MockSDK.side_effect = Exception("SDK initialization failed")
            
            success = MOD.upload_folder(
                str(tmp_dir),
                "Project/Study/Results"
            )

        assert success is False

    def test_upload_sdk_called_with_correct_params(self, tmp_dir):
        """CloudSDK.datahub.upload must use local_folder, remote_folder, glob_patterns, is_versioned, and print_message=False."""
        (tmp_dir / "result.parquet").write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "result.parquet"
        mock_result.FailureReason = None

        mock_data = MagicMock()
        mock_data.DatahubResourceResults = [mock_result]

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()
            with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                MOD.upload_folder(str(tmp_dir), "Project/Study/Results", is_versioned=False)

        call_kwargs = mock_instance.datahub.upload.call_args.kwargs
        # Correct param names (per CloudSDK.md)
        assert "local_folder" in call_kwargs, "SDK upload must use 'local_folder'"
        assert "remote_folder" in call_kwargs, "SDK upload must use 'remote_folder'"
        assert "glob_patterns" in call_kwargs, "SDK upload must use 'glob_patterns'"
        # glob_patterns must be a list
        assert isinstance(call_kwargs["glob_patterns"], list)
        # is_versioned must be forwarded correctly
        assert call_kwargs.get("is_versioned") is False
        # print_message must always be False (never let SDK print its own output)
        assert call_kwargs.get("print_message") is False, "print_message must be False"

    def test_upload_multiple_patterns_reach_sdk(self, tmp_dir):
        """Both patterns are forwarded to CloudSDK.datahub.upload as glob_patterns."""
        (tmp_dir / "result.csv").write_text("a,b")
        (tmp_dir / "result.parquet").write_bytes(b"PAR1")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "result.csv"
        mock_result.FailureReason = None

        mock_data = MagicMock()
        mock_data.DatahubResourceResults = [mock_result]

        with patch("upload_to_datahub.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()
            with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                MOD.upload_folder(str(tmp_dir), "Project/Study/Results", patterns=["*.csv", "*.parquet"])

        call_kwargs = mock_instance.datahub.upload.call_args.kwargs
        assert call_kwargs["glob_patterns"] == ["*.csv", "*.parquet"]


class TestMainFunction:
    """Test the main function with argument parsing."""

    def test_main_missing_required_args(self):
        """Main should fail when required arguments are missing."""
        with patch("sys.argv", ["upload_to_datahub.py"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            # argparse exits with code 2 for missing required arguments
            assert exc.value.code == 2

    def test_main_with_valid_args(self, tmp_dir):
        """Main should execute successfully with valid arguments."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "test.parquet"

        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", str(tmp_dir),
            "-r", "Project/Study/Results"
        ]):
            with patch("upload_to_datahub.CloudSDK"):
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_response_data
                    
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_main_with_pattern_arg(self, tmp_dir):
        """Main should respect pattern argument."""
        (tmp_dir / "file1.parquet").write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "file1.parquet"

        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", str(tmp_dir),
            "-r", "Project/Study/Results",
            "-p", "*.parquet"
        ]):
            with patch("upload_to_datahub.CloudSDK"):
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_response_data
                    
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_main_upload_failure(self, tmp_dir):
        """Main should return non-zero exit code on upload failure."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("data")

        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", str(tmp_dir),
            "-r", "Project/Study/Results"
        ]):
            with patch("upload_to_datahub.CloudSDK"):
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = None  # Simulate failure
                    
                    exit_code = MOD.main()

        assert exit_code == 1

    def test_main_with_no_versioning(self, tmp_dir):
        """Main should respect -v false flag."""
        test_file = tmp_dir / "test.parquet"
        test_file.write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "test.parquet"

        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", str(tmp_dir),
            "-r", "Project/Study/Results",
            "-v", "false"
        ]):
            with patch("upload_to_datahub.CloudSDK") as MockSDK:
                mock_sdk_instance = MockSDK.return_value
                
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_response_data
                    
                    exit_code = MOD.main()

        assert exit_code == 0
        # Verify upload was called with is_versioned=False
        call_kwargs = mock_sdk_instance.datahub.upload.call_args.kwargs
        assert call_kwargs["is_versioned"] is False

    def test_url_encoded_remote_path_is_decoded(self, tmp_dir):
        """URL-encoded %20 spaces in -r are decoded before being passed to the SDK."""
        (tmp_dir / "file.parquet").write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "file.parquet"
        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", str(tmp_dir),
            "-r", "Kavitha/Study%203/Output%20Folder",
        ]):
            with patch("upload_to_datahub.CloudSDK") as MockSDK:
                mock_sdk_instance = MockSDK.return_value
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_response_data
                    exit_code = MOD.main()

        assert exit_code == 0
        call_kwargs = mock_sdk_instance.datahub.upload.call_args.kwargs
        assert call_kwargs["remote_folder"] == "Kavitha/Study 3/Output Folder"
        assert "%20" not in call_kwargs["remote_folder"]

    def test_url_encoded_local_folder_is_decoded(self, tmp_dir):
        """URL-encoded %20 spaces in -l are decoded so the folder is found on disk."""
        # create a subfolder whose name contains a space
        spaced = tmp_dir / "My Results"
        spaced.mkdir()
        (spaced / "data.parquet").write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "data.parquet"
        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        encoded = str(spaced).replace(" ", "%20")
        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", encoded,
            "-r", "Project/Study/Results",
        ]):
            with patch("upload_to_datahub.CloudSDK") as MockSDK:
                mock_sdk_instance = MockSDK.return_value
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_response_data
                    exit_code = MOD.main()

        assert exit_code == 0
        call_kwargs = mock_sdk_instance.datahub.upload.call_args.kwargs
        assert " " in call_kwargs["local_folder"]
        assert "%20" not in call_kwargs["local_folder"]

    def test_surrounding_quotes_stripped_from_args(self, tmp_dir):
        """Single quotes around -l or -r (from the task runner) are stripped."""
        (tmp_dir / "file.csv").write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "file.csv"
        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", f"'{tmp_dir}'",
            "-r", "'Project/Study/Results'",
        ]):
            with patch("upload_to_datahub.CloudSDK") as MockSDK:
                mock_sdk_instance = MockSDK.return_value
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_response_data
                    exit_code = MOD.main()

        assert exit_code == 0
        call_kwargs = mock_sdk_instance.datahub.upload.call_args.kwargs
        assert "'" not in call_kwargs["local_folder"]
        assert "'" not in call_kwargs["remote_folder"]

    def test_main_multiple_patterns_via_cli(self, tmp_dir):
        """Two space-separated -p values are both forwarded to the SDK as glob_patterns."""
        (tmp_dir / "file.csv").write_text("data")

        mock_result = MagicMock()
        mock_result.Success = True
        mock_result.RelativeFilePath = "file.csv"
        mock_response_data = MagicMock()
        mock_response_data.DatahubResourceResults = [mock_result]

        with patch("sys.argv", [
            "upload_to_datahub.py",
            "-l", str(tmp_dir),
            "-r", "Project/Study/Results",
            "-p", "*.csv", "*.parquet",
        ]):
            with patch("upload_to_datahub.CloudSDK") as MockSDK:
                mock_sdk_instance = MockSDK.return_value
                with patch("upload_to_datahub.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_response_data
                    exit_code = MOD.main()

        assert exit_code == 0
        call_kwargs = mock_sdk_instance.datahub.upload.call_args.kwargs
        assert call_kwargs["glob_patterns"] == ["*.csv", "*.parquet"]
