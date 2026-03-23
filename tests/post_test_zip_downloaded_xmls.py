"""
Unit tests for Post/PLEXOS/ZipDiagnostics/zip_downloaded_xmls.py

Tests the DiagnosticsZipper.process_diagnostics method and main() entry point.
All CloudSDK calls are mocked — no real cloud services are contacted.
"""
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module


MOD = get_module("zip_downloaded_xmls")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_download_response(results: list[dict]):
    """Build a mock SDKBase.get_response_data return value for download."""
    mock_results = []
    for r in results:
        m = MagicMock()
        m.Success = r.get("Success", True)
        m.LocalFilePath = r.get("LocalFilePath", "/output/test.xml")
        m.RelativeFilePath = r.get("RelativeFilePath", "unknown.xml")
        m.FailureReason = r.get("FailureReason", None)
        mock_results.append(m)

    mock_data = MagicMock()
    mock_data.DatahubResourceResults = mock_results
    return mock_data


def _make_upload_response(success=True, identical=False):
    """Build a mock SDKBase.get_response_data return value for upload."""
    mock_results = []
    m = MagicMock()
    m.RelativeFilePath = "Base_diagnostics.zip"
    
    if success:
        m.Success = True
        m.FailureReason = None
    elif identical:
        m.Success = False
        m.FailureReason = "File is identical to the remote file"
    else:
        m.Success = False
        m.FailureReason = "Upload failed"
    
    mock_results.append(m)
    
    mock_data = MagicMock()
    mock_data.DatahubResourceResults = mock_results
    return mock_data


# ---------------------------------------------------------------------------
# _decode_path helper
# ---------------------------------------------------------------------------

class TestDecodePathHelper:
    """Tests for the _decode_path helper (URL-decode + quote-strip)."""

    def test_decodes_percent_encoded_spaces(self):
        assert MOD._decode_path("Project/My%20Study") == "Project/My Study"

    def test_strips_single_quotes(self):
        assert MOD._decode_path("'Project/Study'") == "Project/Study"

    def test_strips_double_quotes(self):
        assert MOD._decode_path('"Project/Study"') == "Project/Study"

    def test_plain_path_unchanged(self):
        assert MOD._decode_path("Project/Study/diagnostics") == "Project/Study/diagnostics"


# ---------------------------------------------------------------------------
# DiagnosticsZipper.process_diagnostics
# ---------------------------------------------------------------------------

class TestDiagnosticsZipper:
    """Test the DiagnosticsZipper class."""

    def test_successful_workflow(self, tmp_dir):
        """Successful download, zip, and upload returns True."""
        # Create mock downloaded file
        xml_file = tmp_dir / "test_diagnostics.xml"
        xml_file.write_text("<diagnostics/>")
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.side_effect = [mock_download_data, mock_upload_data]

                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                success = zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "test_sim_001")

        assert success is True
        assert mock_instance.datahub.download.called
        assert mock_instance.datahub.upload.called
        # Verify ZIP was created
        assert (tmp_dir / "Base_diagnostics.zip").exists()

    def test_download_returns_no_data(self, tmp_dir):
        """Raises RuntimeError when download returns None."""
        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = None

                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                
                with pytest.raises(RuntimeError, match="Failed to download"):
                    zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "test_sim_001")

    def test_download_no_files_matched(self, tmp_dir):
        """Raises RuntimeError when no files match the download pattern."""
        mock_download_data = MagicMock()
        mock_download_data.DatahubResourceResults = []

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_download_data

                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                
                with pytest.raises(RuntimeError, match="Failed to download"):
                    zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "test_sim_001")

    def test_partial_download_failure_still_zips_successes(self, tmp_dir):
        """When some files fail to download, successfully downloaded ones are still archived."""
        xml_file = tmp_dir / "ok.xml"
        xml_file.write_text("<diagnostics/>")

        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
            {"Success": False, "LocalFilePath": "", "RelativeFilePath": "missing.xml", "FailureReason": "Not found"},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.side_effect = [mock_download_data, mock_upload_data]
                
                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                success = zipper.process_diagnostics("Base", "Project/Study", "exec_001", "sim_001")

        assert success is True
        assert (tmp_dir / "Base_diagnostics.zip").exists()

    def test_upload_failure_returns_false(self, tmp_dir):
        """Returns False when upload fails."""
        xml_file = tmp_dir / "test.xml"
        xml_file.write_text("<diagnostics/>")
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=False)

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.side_effect = [mock_download_data, mock_upload_data]

                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                success = zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "test_sim_001")

        assert success is False

    def test_empty_execution_id_raises_error(self, tmp_dir):
        """Raises ValueError when execution_id is empty."""
        zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
        
        with pytest.raises(ValueError, match="execution_id is required"):
            zipper.process_diagnostics("Base", "Project/Study", "", "test_sim_001")
    
    def test_empty_simulation_id_raises_error(self, tmp_dir):
        """Raises ValueError when simulation_id is empty."""
        zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
        
        with pytest.raises(ValueError, match="simulation_id is required"):
            zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "")

    def test_file_outside_output_path_raises_error(self, tmp_dir):
        """Raises RuntimeError when a downloaded file path is outside output_path."""
        # SDK returns a path outside our output_path (e.g. wrong temp dir)
        import shutil
        import tempfile
        other_dir = Path(tempfile.mkdtemp())
        try:
            outside_file = other_dir / "outside.xml"
            outside_file.write_text("<diagnostics/>")
            mock_download_data = _make_download_response([
                {"Success": True, "LocalFilePath": str(outside_file)},
            ])
            mock_upload_data = _make_upload_response(success=True)

            with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.download.return_value = MagicMock()
                mock_instance.datahub.upload.return_value = MagicMock()

                with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.side_effect = [mock_download_data, mock_upload_data]

                    zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                    with pytest.raises(RuntimeError, match="outside output path"):
                        zipper.process_diagnostics("Base", "Project/Study", "exec_001", "sim_001")
        finally:
            shutil.rmtree(other_dir, ignore_errors=True)

    def test_download_sdk_called_with_correct_params(self, tmp_dir):
        """Verify datahub.download uses the correct parameter names per CloudSDK.md."""
        xml_file = tmp_dir / "test.xml"
        xml_file.write_text("<diagnostics/>")
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.side_effect = [mock_download_data, mock_upload_data]

                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "test_sim_001", pattern="**/*ST*Diagnostics.xml")

        download_call_kwargs = mock_instance.datahub.download.call_args.kwargs
        
        # Verify required parameters
        assert "remote_glob_patterns" in download_call_kwargs, "SDK download must use 'remote_glob_patterns'"
        assert "output_directory" in download_call_kwargs, "SDK download must use 'output_directory'"
        assert isinstance(download_call_kwargs["remote_glob_patterns"], list), "remote_glob_patterns must be a list"
        
        # Verify print_message=False is passed
        assert download_call_kwargs.get("print_message") is False, "SDK download must use print_message=False"
        
        # Verify no undocumented/invalid kwargs are used
        valid_download_params = {"remote_glob_patterns", "output_directory", "print_message"}
        actual_params = set(download_call_kwargs.keys())
        invalid_params = actual_params - valid_download_params
        assert not invalid_params, f"SDK download has invalid parameters: {invalid_params}"

    def test_upload_sdk_called_with_correct_params(self, tmp_dir):
        """Verify datahub.upload uses the correct parameter names per CloudSDK.md."""
        xml_file = tmp_dir / "test.xml"
        xml_file.write_text("<diagnostics/>")
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.side_effect = [mock_download_data, mock_upload_data]

                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "test_sim_001")

        upload_call_kwargs = mock_instance.datahub.upload.call_args.kwargs
        
        assert "local_folder" in upload_call_kwargs, "SDK upload must use 'local_folder'"
        assert "remote_folder" in upload_call_kwargs, "SDK upload must use 'remote_folder'"
        assert "glob_patterns" in upload_call_kwargs, "SDK upload must use 'glob_patterns'"
        assert isinstance(upload_call_kwargs["glob_patterns"], list), "glob_patterns must be a list"
        assert upload_call_kwargs.get("print_message") is False, "print_message must be False"

    def test_remote_path_built_correctly(self, tmp_dir):
        """Verify the remote glob pattern includes model name and execution ID."""
        xml_file = tmp_dir / "test.xml"
        xml_file.write_text("<diagnostics/>")
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.side_effect = [mock_download_data, mock_upload_data]
                
                with patch.object(MOD, "EXECUTION_ID", "exec_123"):
                    zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                    zipper.process_diagnostics("ModelA", "Project/Study/diagnostics", "exec_123", "sim_456")

        download_call_kwargs = mock_instance.datahub.download.call_args.kwargs
        remote_pattern = download_call_kwargs["remote_glob_patterns"][0]
        
        assert "ModelA" in remote_pattern
        assert "exec_123" in remote_pattern
        assert "Project/Study/diagnostics" in remote_pattern

    def test_zip_file_contains_downloaded_files(self, tmp_dir):
        """Verify ZIP file is created with correct contents."""
        xml_file = tmp_dir / "test_diagnostics.xml"
        xml_file.write_text("<diagnostics>content</diagnostics>")
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.download.return_value = MagicMock()
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.side_effect = [mock_download_data, mock_upload_data]

                zipper = MOD.DiagnosticsZipper("mock_cli_path", str(tmp_dir))
                success = zipper.process_diagnostics("Base", "Project/Study", "test_exec_001", "test_sim_001")

        assert success is True
        
        # Verify ZIP file exists and contains the XML
        zip_path = tmp_dir / "Base_diagnostics.zip"
        assert zip_path.exists()
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            assert len(zipf.namelist()) > 0
            assert any("test_diagnostics.xml" in name for name in zipf.namelist())


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMainFunction:
    """Test the main function with argument parsing."""

    def test_main_fails_when_mapping_missing(self, tmp_dir):
        """Main should fail when directory mapping file is not found."""
        with patch("sys.argv", ["zip_downloaded_xmls.py", "-r", "Project/Study"]):
            with patch.object(MOD, "DIRECTORY_MAP_PATH", "/nonexistent/mapping.json"), \
                 patch("zip_downloaded_xmls.os.path.exists", return_value=False):
                exit_code = MOD.main()
        
        assert exit_code == 1

    def test_main_fails_when_mapping_has_no_name(self, tmp_dir):
        """Main should fail when directory mapping JSON lacks a valid Name field."""
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text('[{"ParquetPath": "some/path"}]')  # Missing "Name"
        
        with patch("sys.argv", ["zip_downloaded_xmls.py", "-r", "Project/Study"]):
            with patch.object(MOD, "DIRECTORY_MAP_PATH", str(mapping_file)):
                exit_code = MOD.main()
        
        assert exit_code == 1

    def test_main_successful_run(self, tmp_dir):
        """Main returns 0 on successful workflow."""
        xml_file = tmp_dir / "test.xml"
        xml_file.write_text("<diagnostics/>")
        
        # Create mock directory mapping file
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text('[{"Name": "TestModel", "Id": "test-id", "ParquetPath": "some/path"}]')
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("sys.argv", [
            "zip_downloaded_xmls.py",
            "-r", "Project/Study",
        ]):
            with patch("zip_downloaded_xmls.CloudSDK"):
                with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.side_effect = [mock_download_data, mock_upload_data]
                    
                    with patch.object(MOD, "EXECUTION_ID", "exec_001"), \
                         patch.object(MOD, "SIMULATION_ID", "sim_001"), \
                         patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)), \
                         patch.object(MOD, "DIRECTORY_MAP_PATH", str(mapping_file)):
                        exit_code = MOD.main()

        assert exit_code == 0

    def test_main_with_custom_pattern(self, tmp_dir):
        """Main respects the -pt argument."""
        xml_file = tmp_dir / "ST_diagnostics.xml"
        xml_file.write_text("<diagnostics/>")
        
        # Create mock directory mapping file
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text('[{"Name": "TestModel", "Id": "test-id", "ParquetPath": "some/path"}]')
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("sys.argv", [
            "zip_downloaded_xmls.py",
            "-r", "Project/Study",
            "-pt", "**/*ST*Diagnostics.xml",
        ]):
            with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.download.return_value = MagicMock()
                mock_instance.datahub.upload.return_value = MagicMock()

                with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.side_effect = [mock_download_data, mock_upload_data]
                    
                    with patch.object(MOD, "EXECUTION_ID", "exec_001"), \
                         patch.object(MOD, "SIMULATION_ID", "sim_001"), \
                         patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)), \
                         patch.object(MOD, "DIRECTORY_MAP_PATH", str(mapping_file)):
                        exit_code = MOD.main()

        assert exit_code == 0
        download_call_kwargs = mock_instance.datahub.download.call_args.kwargs
        assert "**/*ST*Diagnostics.xml" in download_call_kwargs["remote_glob_patterns"][0]

    def test_main_workflow_failure_returns_1(self, tmp_dir):
        """Main returns 1 when workflow fails."""
        # Create mock directory mapping file
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text('[{"Name": "TestModel", "Id": "test-id", "ParquetPath": "some/path"}]')
        
        with patch("sys.argv", [
            "zip_downloaded_xmls.py",
            "-r", "Project/Study",
        ]):
            with patch("zip_downloaded_xmls.CloudSDK"):
                with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = None
                    
                    with patch.object(MOD, "EXECUTION_ID", "exec_001"), \
                         patch.object(MOD, "SIMULATION_ID", "sim_001"), \
                         patch.object(MOD, "DIRECTORY_MAP_PATH", str(mapping_file)):
                        exit_code = MOD.main()

        assert exit_code == 1

    def test_main_handles_exception(self, tmp_dir):
        """Main returns 1 when an unhandled exception occurs."""
        # Create mock directory mapping file
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text('[{"Name": "TestModel", "Id": "test-id", "ParquetPath": "some/path"}]')
        
        with patch("sys.argv", [
            "zip_downloaded_xmls.py",
            "-r", "Project/Study",
        ]):
            with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
                MockSDK.side_effect = Exception("SDK init failed")
                
                with patch.object(MOD, "EXECUTION_ID", "exec_001"), \
                     patch.object(MOD, "SIMULATION_ID", "sim_001"), \
                     patch.object(MOD, "DIRECTORY_MAP_PATH", str(mapping_file)):
                    exit_code = MOD.main()

        assert exit_code == 1

    def test_url_encoded_paths_are_decoded(self, tmp_dir):
        """URL-encoded %20 spaces in arguments are decoded."""
        xml_file = tmp_dir / "test.xml"
        xml_file.write_text("<diagnostics/>")
        
        # Create mock directory mapping file
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text('[{"Name": "Model A", "Id": "model-a-id", "ParquetPath": "some/path"}]')
        
        mock_download_data = _make_download_response([
            {"Success": True, "LocalFilePath": str(xml_file)},
        ])
        mock_upload_data = _make_upload_response(success=True)

        with patch("sys.argv", [
            "zip_downloaded_xmls.py",
            "-r", "Project/My%20Study",
        ]):
            with patch("zip_downloaded_xmls.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.download.return_value = MagicMock()
                mock_instance.datahub.upload.return_value = MagicMock()

                with patch("zip_downloaded_xmls.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.side_effect = [mock_download_data, mock_upload_data]
                    
                    with patch.object(MOD, "EXECUTION_ID", "exec_001"), \
                         patch.object(MOD, "SIMULATION_ID", "sim_001"), \
                         patch.object(MOD, "OUTPUT_PATH", str(tmp_dir)), \
                         patch.object(MOD, "DIRECTORY_MAP_PATH", str(mapping_file)):
                        exit_code = MOD.main()

        assert exit_code == 0
        # Verify decoded paths were used
        download_call_kwargs = mock_instance.datahub.download.call_args.kwargs
        remote_pattern = download_call_kwargs["remote_glob_patterns"][0]
        assert "Model A" in remote_pattern
        assert "%20" not in remote_pattern
