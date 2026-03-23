"""
Unit tests for Post/PLEXOS/ExtractDiagnosticsXML/extract_diag_xml.py

Tests the upload_diagnostics function and main() entry point.
All CloudSDK calls are mocked — no real cloud services are contacted.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module

MOD = get_module("extract_diag_xml")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sdk_response(results: list[dict]):
    """Build a mock SDKBase.get_response_data return value."""
    mock_results = []
    for r in results:
        m = MagicMock()
        m.Success = r.get("Success", True)
        m.RelativeFilePath = r.get("RelativeFilePath", "Model Solution/Diagnostics.xml")
        m.LocalFilePath = r.get("LocalFilePath", "/simulation/Diagnostics.xml")
        m.FailureReason = r.get("FailureReason", None)
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
# upload_diagnostics
# ---------------------------------------------------------------------------

class TestUploadDiagnostics:
    """Test the upload_diagnostics function."""

    def test_successful_upload(self):
        """Successful upload returns True and prints summary."""
        mock_data = _make_sdk_response([
            {"Success": True, "RelativeFilePath": "Model Solution/STDiagnostics.xml"},
        ])

        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data

                success = MOD.upload_diagnostics(
                    remote_base="Project/Study/diagnostics",
                    model_name="ModelA",
                )

        assert success is True

    def test_upload_no_response_data(self):
        """Returns False when SDK returns None."""
        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = None

                success = MOD.upload_diagnostics(
                    remote_base="Project/Study/diagnostics",
                    model_name="ModelA",
                )

        assert success is False

    def test_upload_unexpected_response_structure(self):
        """Returns False when response has no DatahubResourceResults."""
        mock_data = MagicMock(spec=[])  # No DatahubResourceResults

        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data

                success = MOD.upload_diagnostics(
                    remote_base="Project/Study/diagnostics",
                    model_name="ModelA",
                )

        assert success is False

    def test_upload_handles_failed_files(self):
        """Returns False when one or more files fail to upload."""
        mock_data = _make_sdk_response([
            {"Success": False, "RelativeFilePath": "STDiagnostics.xml",
             "FailureReason": "Permission denied"},
        ])

        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data

                success = MOD.upload_diagnostics(
                    remote_base="Project/Study/diagnostics",
                    model_name="ModelA",
                )

        assert success is False

    def test_upload_handles_skipped_identical_files(self):
        """Identical files are treated as success."""
        mock_data = _make_sdk_response([
            {"Success": False, "RelativeFilePath": "STDiagnostics.xml",
             "FailureReason": "File is identical to the remote file"},
        ])

        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data

                success = MOD.upload_diagnostics(
                    remote_base="Project/Study/diagnostics",
                    model_name="ModelA",
                )

        assert success is True

    def test_upload_no_matching_files(self):
        """Returns True with a warning when no files match."""
        mock_data = MagicMock()
        mock_data.DatahubResourceResults = []

        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data

                success = MOD.upload_diagnostics(
                    remote_base="Project/Study/diagnostics",
                    model_name="ModelA",
                )

        assert success is True

    def test_sdk_called_with_correct_params(self):
        """Verify datahub.upload uses the correct parameter names per CloudSDK.md."""
        mock_data = _make_sdk_response([
            {"Success": True, "RelativeFilePath": "Diagnostics.xml"},
        ])

        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data

                MOD.upload_diagnostics(
                    remote_base="Project/Study/diagnostics",
                    model_name="ModelA",
                    pattern="**/*ST*Diagnostics.xml",
                    is_versioned=True,
                )

        call_kwargs = mock_instance.datahub.upload.call_args.kwargs

        assert "local_folder" in call_kwargs, "SDK upload must use 'local_folder'"
        assert "remote_folder" in call_kwargs, "SDK upload must use 'remote_folder'"
        assert "glob_patterns" in call_kwargs, "SDK upload must use 'glob_patterns'"
        assert isinstance(call_kwargs["glob_patterns"], list), "glob_patterns must be a list"
        assert call_kwargs["glob_patterns"] == ["**/*ST*Diagnostics.xml"]
        assert call_kwargs.get("is_versioned") is True
        assert call_kwargs.get("print_message") is False, "print_message must be False"

    def test_remote_path_built_correctly(self):
        """Verify the remote path includes model name, execution ID, and simulation ID."""
        mock_data = _make_sdk_response([
            {"Success": True, "RelativeFilePath": "Diagnostics.xml"},
        ])

        with patch("extract_diag_xml.CloudSDK") as MockSDK:
            mock_instance = MockSDK.return_value
            mock_instance.datahub.upload.return_value = MagicMock()

            with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                mock_get_data.return_value = mock_data
                with patch.object(MOD, "EXECUTION_ID", "exec_123"), \
                     patch.object(MOD, "SIMULATION_ID", "sim_456"):
                    MOD.upload_diagnostics(
                        remote_base="Project/Study/diagnostics",
                        model_name="ModelA",
                    )

        call_kwargs = mock_instance.datahub.upload.call_args.kwargs
        remote = call_kwargs["remote_folder"]
        assert "ModelA" in remote
        assert "exec_123" in remote
        assert "sim_456" in remote
        assert remote == "Project/Study/diagnostics/ModelA/exec_123/diagnostics/sim_456"


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMainFunction:
    """Test the main function with argument parsing."""

    def test_main_missing_required_args(self):
        """Main should fail when required arguments are missing."""
        with patch("sys.argv", ["extract_diag_xml.py"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            assert exc.value.code == 2

    def test_main_fails_when_mapping_not_found(self):
        """Main returns 1 when the directory mapping file cannot be resolved."""
        with patch("sys.argv", ["extract_diag_xml.py", "-r", "Project/Study/diagnostics"]):
            with patch("extract_diag_xml._get_model_name_from_mapping",
                       side_effect=FileNotFoundError("Mapping file not found")):
                exit_code = MOD.main()
        assert exit_code == 1

    def test_main_fails_when_simulation_id_missing(self):
        """Main returns 1 when simulation_id env var is empty."""
        with patch("sys.argv", [
            "extract_diag_xml.py",
            "-r", "Project/Study/diagnostics",
        ]):
            with patch("extract_diag_xml._get_model_name_from_mapping", return_value="ModelA"), \
                 patch.object(MOD, "SIMULATION_ID", ""), \
                 patch.object(MOD, "EXECUTION_ID", "exec_001"):
                exit_code = MOD.main()
        assert exit_code == 1

    def test_main_fails_when_execution_id_missing(self):
        """Main returns 1 when execution_id env var is empty."""
        with patch("sys.argv", [
            "extract_diag_xml.py",
            "-r", "Project/Study/diagnostics",
        ]):
            with patch("extract_diag_xml._get_model_name_from_mapping", return_value="ModelA"), \
                 patch.object(MOD, "EXECUTION_ID", ""), \
                 patch.object(MOD, "SIMULATION_ID", "sim_001"):
                exit_code = MOD.main()
        assert exit_code == 1

    def test_main_successful_run(self):
        """Main returns 0 on successful upload."""
        mock_data = _make_sdk_response([
            {"Success": True, "RelativeFilePath": "Diagnostics.xml"},
        ])

        with patch("sys.argv", [
            "extract_diag_xml.py",
            "-r", "Project/Study/diagnostics",
        ]):
            with patch("extract_diag_xml._get_model_name_from_mapping", return_value="ModelA"), \
                 patch("extract_diag_xml.CloudSDK"):
                with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_main_with_custom_pattern(self):
        """Main respects the --pattern argument."""
        mock_data = _make_sdk_response([
            {"Success": True, "RelativeFilePath": "STDiagnostics.xml"},
        ])

        with patch("sys.argv", [
            "extract_diag_xml.py",
            "-r", "Project/Study/diagnostics",
            "-pt", "**/*ST*Diagnostics.xml",
        ]):
            with patch("extract_diag_xml._get_model_name_from_mapping", return_value="ModelA"), \
                 patch("extract_diag_xml.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.upload.return_value = MagicMock()

                with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    exit_code = MOD.main()

        assert exit_code == 0
        call_kwargs = mock_instance.datahub.upload.call_args.kwargs
        assert call_kwargs["glob_patterns"] == ["**/*ST*Diagnostics.xml"]

    def test_main_with_versioned_true(self):
        """Main passes is_versioned=True when -v true is given."""
        mock_data = _make_sdk_response([
            {"Success": True, "RelativeFilePath": "Diagnostics.xml"},
        ])

        with patch("sys.argv", [
            "extract_diag_xml.py",
            "-r", "Project/Study/diagnostics",
            "-v", "true",
        ]):
            with patch("extract_diag_xml._get_model_name_from_mapping", return_value="ModelA"), \
                 patch("extract_diag_xml.CloudSDK") as MockSDK:
                mock_instance = MockSDK.return_value
                mock_instance.datahub.upload.return_value = MagicMock()

                with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = mock_data
                    exit_code = MOD.main()

        assert exit_code == 0
        call_kwargs = mock_instance.datahub.upload.call_args.kwargs
        assert call_kwargs["is_versioned"] is True

    def test_main_upload_failure_returns_1(self):
        """Main returns 1 when upload fails."""
        with patch("sys.argv", [
            "extract_diag_xml.py",
            "-r", "Project/Study/diagnostics",
        ]):
            with patch("extract_diag_xml._get_model_name_from_mapping", return_value="ModelA"), \
                 patch("extract_diag_xml.CloudSDK"):
                with patch("extract_diag_xml.SDKBase.get_response_data") as mock_get_data:
                    mock_get_data.return_value = None
                    exit_code = MOD.main()

        assert exit_code == 1

    def test_main_handles_exception(self):
        """Main returns 1 when an unhandled exception occurs."""
        with patch("sys.argv", [
            "extract_diag_xml.py",
            "-r", "Project/Study/diagnostics",
        ]):
            with patch("extract_diag_xml._get_model_name_from_mapping", return_value="ModelA"), \
                 patch("extract_diag_xml.CloudSDK") as MockSDK:
                MockSDK.side_effect = Exception("SDK init failed")
                exit_code = MOD.main()

        assert exit_code == 1


# ---------------------------------------------------------------------------
# _resolve_mapping_file
# ---------------------------------------------------------------------------

class TestResolveMappingFile:
    """Tests for _resolve_mapping_file helper."""

    def test_uses_env_path_when_it_exists(self, tmp_path):
        """Returns env_path when it exists."""
        mapping = tmp_path / "directorymapping.json"
        mapping.write_text("[]")
        result = MOD._resolve_mapping_file(str(mapping))
        assert result == str(mapping)

    def test_falls_back_to_simulation_splits(self, tmp_path):
        """Falls back to /simulation/splits/directorymapping.json when env_path is absent."""
        fallback = "/simulation/splits/directorymapping.json"
        with patch("os.path.exists", side_effect=lambda p: p == fallback):
            result = MOD._resolve_mapping_file("")
        assert result == fallback

    def test_raises_when_no_mapping_found(self):
        """Raises FileNotFoundError when neither path exists."""
        with patch("os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                MOD._resolve_mapping_file("")


# ---------------------------------------------------------------------------
# _get_model_name_from_mapping
# ---------------------------------------------------------------------------

class TestGetModelNameFromMapping:
    """Tests for _get_model_name_from_mapping helper."""

    def _write_mapping(self, tmp_path, data) -> str:
        mapping = tmp_path / "directorymapping.json"
        mapping.write_text(json.dumps(data))
        return str(mapping)

    def test_returns_name_from_first_parquet_entry(self, tmp_path):
        """Returns Name from the first entry that has a ParquetPath."""
        path = self._write_mapping(tmp_path, [
            {"Name": "ModelA", "Id": "1", "ParquetPath": "/sim/parquet"},
        ])
        with patch("extract_diag_xml._resolve_mapping_file", return_value=path):
            result = MOD._get_model_name_from_mapping("")
        assert result == "ModelA"

    def test_skips_entries_without_parquet_path(self, tmp_path):
        """Skips entries without ParquetPath and returns Name of matching entry."""
        path = self._write_mapping(tmp_path, [
            {"Name": "Other", "Id": "0"},
            {"Name": "ModelB", "Id": "2", "ParquetPath": "/sim/parquet"},
        ])
        with patch("extract_diag_xml._resolve_mapping_file", return_value=path):
            result = MOD._get_model_name_from_mapping("")
        assert result == "ModelB"

    def test_raises_when_no_parquet_entry(self, tmp_path):
        """Raises ValueError when no entry has ParquetPath."""
        path = self._write_mapping(tmp_path, [{"Name": "ModelA", "Id": "1"}])
        with patch("extract_diag_xml._resolve_mapping_file", return_value=path):
            with pytest.raises(ValueError, match="No entry with 'ParquetPath'"):
                MOD._get_model_name_from_mapping("")

    def test_raises_when_name_is_empty(self, tmp_path):
        """Raises ValueError when ParquetPath entry has an empty Name."""
        path = self._write_mapping(tmp_path, [
            {"Name": "", "Id": "1", "ParquetPath": "/sim/parquet"},
        ])
        with patch("extract_diag_xml._resolve_mapping_file", return_value=path):
            with pytest.raises(ValueError, match="non-empty 'Name'"):
                MOD._get_model_name_from_mapping("")

    def test_raises_for_empty_mapping(self, tmp_path):
        """Raises ValueError when JSON is an empty list."""
        path = self._write_mapping(tmp_path, [])
        with patch("extract_diag_xml._resolve_mapping_file", return_value=path):
            with pytest.raises(ValueError):
                MOD._get_model_name_from_mapping("")

