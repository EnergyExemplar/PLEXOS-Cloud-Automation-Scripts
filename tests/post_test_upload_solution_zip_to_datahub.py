"""
Unit tests for Post/PLEXOS/UploadSolutionZipToDatahub/upload_solution_zip_to_datahub.py

Tests the ZipSolutionUploader class and main() entry point.
All CloudSDK calls are mocked — no real cloud services are contacted.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module


MOD = get_module("upload_solution_zip_to_datahub")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sdk_response(results: list[dict]):
    """Build a mock SDKBase.get_response_data return value."""
    mock_results = []
    for r in results:
        m = MagicMock()
        m.Success = r.get("Success", True)
        m.RelativeFilePath = r.get("RelativeFilePath", "model.zip")
        m.LocalFilePath = r.get("LocalFilePath", "/local/model.zip")
        m.FailureReason = r.get("FailureReason", None)
        mock_results.append(m)

    mock_data = MagicMock()
    mock_data.DatahubResourceResults = mock_results
    return mock_data


def _make_uploader():
    with patch("upload_solution_zip_to_datahub.CloudSDK"):
        return MOD.ZipSolutionUploader(cli_path="mock_cli")


def _write_mapping(path, entries):
    path.write_text(json.dumps(entries))


# ---------------------------------------------------------------------------
# _decode_path helper
# ---------------------------------------------------------------------------

class TestDecodePathHelper:
    def test_decodes_percent_encoded_spaces(self):
        assert MOD._decode_path("My%20Model") == "My Model"

    def test_strips_single_quotes(self):
        assert MOD._decode_path("'/some/path'") == "/some/path"

    def test_strips_double_quotes(self):
        assert MOD._decode_path('"/some/path"') == "/some/path"

    def test_plain_string_unchanged(self):
        assert MOD._decode_path("MyModel") == "MyModel"


# ---------------------------------------------------------------------------
# ModelData
# ---------------------------------------------------------------------------

class TestModelData:
    def test_attributes(self):
        md = MOD.ModelData(model_id="m1", solution_path="/sim/m1")
        assert md.id == "m1"
        assert md.solution_path == "/sim/m1"


# ---------------------------------------------------------------------------
# ZipSolutionUploader._resolve_mapping_file
# ---------------------------------------------------------------------------

class TestResolveMappingFile:
    def test_returns_env_path_when_exists(self, tmp_path):
        f = tmp_path / "mapping.json"
        f.write_text("[]")
        uploader = _make_uploader()
        assert uploader._resolve_mapping_file(str(f)) == str(f)

    def test_raises_when_neither_path_exists(self, tmp_path):
        uploader = _make_uploader()
        with patch("upload_solution_zip_to_datahub.os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                uploader._resolve_mapping_file(str(tmp_path / "nonexistent.json"))

    def test_raises_when_env_path_empty_and_default_missing(self):
        uploader = _make_uploader()
        with patch("upload_solution_zip_to_datahub.os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                uploader._resolve_mapping_file("")


# ---------------------------------------------------------------------------
# ZipSolutionUploader._read_mapping
# ---------------------------------------------------------------------------

class TestReadMapping:
    def test_returns_first_entry_with_path(self, tmp_path):
        mapping = [
            {"Name": "ModelA", "Id": "m1", "Path": "/sim/m1"},
            {"Name": "ModelB", "Id": "m2", "Path": "/sim/m2"},
        ]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)
        uploader = _make_uploader()
        result = uploader._read_mapping(str(f))
        assert result.id == "m1"
        assert result.solution_path == "/sim/m1"

    def test_skips_entries_without_path(self, tmp_path):
        mapping = [
            {"Name": "ModelA", "Id": "m1"},
            {"Name": "ModelB", "Id": "m2", "Path": "/sim/m2"},
        ]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)
        uploader = _make_uploader()
        result = uploader._read_mapping(str(f))
        assert result.id == "m2"
        assert result.solution_path == "/sim/m2"

    def test_decodes_percent_encoded_path(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": "/sim/My%20Model"}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)
        uploader = _make_uploader()
        result = uploader._read_mapping(str(f))
        assert result.solution_path == "/sim/My Model"

    def test_raises_on_empty_json(self, tmp_path):
        f = tmp_path / "mapping.json"
        f.write_text("[]")
        uploader = _make_uploader()
        with pytest.raises(ValueError, match="empty"):
            uploader._read_mapping(str(f))

    def test_raises_when_no_entry_has_path(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1"}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)
        uploader = _make_uploader()
        with pytest.raises(ValueError, match="Path"):
            uploader._read_mapping(str(f))

    def test_raises_when_id_missing(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "", "Path": "/sim/m1"}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)
        uploader = _make_uploader()
        with pytest.raises(ValueError, match="Id"):
            uploader._read_mapping(str(f))

    def test_raises_when_root_is_not_a_list(self, tmp_path):
        f = tmp_path / "mapping.json"
        f.write_text('{"Name": "ModelA", "Id": "m1", "Path": "/sim/m1"}')
        uploader = _make_uploader()
        with pytest.raises(ValueError, match="empty or not properly formatted"):
            uploader._read_mapping(str(f))

    def test_raises_when_entry_is_not_a_dict(self, tmp_path):
        f = tmp_path / "mapping.json"
        f.write_text('["not-a-dict"]')
        uploader = _make_uploader()
        with pytest.raises(ValueError, match="non-object entry"):
            uploader._read_mapping(str(f))


# ---------------------------------------------------------------------------
# ZipSolutionUploader.upload
# ---------------------------------------------------------------------------

class TestZipSolutionUploaderUpload:
    def _setup(self, mapping_file):
        """Return (uploader, mock_sdk) with _resolve_mapping_file patched to return mapping_file."""
        with patch("upload_solution_zip_to_datahub.CloudSDK") as mock_sdk_cls:
            uploader = MOD.ZipSolutionUploader(cli_path="mock_cli")
            uploader.sdk = mock_sdk_cls.return_value
        uploader._resolve_mapping_file = lambda _: str(mapping_file)
        return uploader, uploader.sdk

    def test_upload_success_returns_true(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                   return_value=_make_sdk_response([{"Success": True, "RelativeFilePath": "sol.zip"}])):
            result = uploader.upload("Eagles/ZipSolutions", "exec-123")

        assert result is True

    def test_upload_constructs_correct_remote_path(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                   return_value=_make_sdk_response([{"Success": True}])):
            uploader.upload("Eagles/ZipSolutions", "exec-123")

        _, kwargs = mock_sdk.datahub.upload.call_args
        assert kwargs["remote_folder"] == "Eagles/ZipSolutions/exec-123/m1"

    def test_upload_passes_correct_sdk_params(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                   return_value=_make_sdk_response([{"Success": True}])):
            uploader.upload("Eagles/ZipSolutions", "exec-123", patterns=["**/*.zip"])

        _, kwargs = mock_sdk.datahub.upload.call_args
        assert kwargs["local_folder"] == str(tmp_path)
        assert kwargs["glob_patterns"] == ["**/*.zip"]
        assert kwargs["is_versioned"] is False
        assert kwargs["print_message"] is False

    def test_upload_default_pattern_is_zip(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                   return_value=_make_sdk_response([{"Success": True}])):
            uploader.upload("Eagles/ZipSolutions", "exec-123")

        _, kwargs = mock_sdk.datahub.upload.call_args
        assert kwargs["glob_patterns"] == ["**/*.zip"]

    def test_upload_strips_trailing_slash_from_remote_base(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                   return_value=_make_sdk_response([{"Success": True}])):
            uploader.upload("Eagles/ZipSolutions/", "exec-123")

        _, kwargs = mock_sdk.datahub.upload.call_args
        assert "//" not in kwargs["remote_folder"]
        assert kwargs["remote_folder"] == "Eagles/ZipSolutions/exec-123/m1"

    def test_upload_returns_false_on_failed_files(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                   return_value=_make_sdk_response([
                       {"Success": False, "RelativeFilePath": "sol.zip", "FailureReason": "Timeout"},
                   ])):
            result = uploader.upload("Eagles/ZipSolutions", "exec-123")

        assert result is False

    def test_upload_treats_identical_file_as_success(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                   return_value=_make_sdk_response([
                       {"Success": False, "FailureReason": "File is identical to the remote file"},
                   ])):
            result = uploader.upload("Eagles/ZipSolutions", "exec-123")

        assert result is True

    def test_upload_returns_false_when_response_data_is_none(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        uploader, mock_sdk = self._setup(f)
        mock_sdk.datahub.upload.return_value = MagicMock()

        with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data", return_value=None):
            result = uploader.upload("Eagles/ZipSolutions", "exec-123")

        assert result is False


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMainFunction:
    def _run_main(self, argv, mapping_file, tmp_path, upload_results=None):
        if upload_results is None:
            upload_results = [{"Success": True, "RelativeFilePath": "sol.zip"}]

        with patch("sys.argv", argv):
            with patch("upload_solution_zip_to_datahub.CloudSDK") as mock_sdk_cls:
                mock_sdk = mock_sdk_cls.return_value
                mock_sdk.datahub.upload.return_value = MagicMock()

                with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                           return_value=_make_sdk_response(upload_results)):
                    with patch.object(MOD, "CLOUD_CLI_PATH", "mock_cli"):
                        with patch.object(MOD, "EXECUTION_ID", "exec-001"):
                            with patch.object(MOD, "DIRECTORY_MAP_PATH", str(mapping_file)):
                                return MOD.main()

    def test_main_returns_0_on_success(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        exit_code = self._run_main(
            ["upload_solution_zip_to_datahub.py", "-r", "Eagles/ZipSolutions"],
            f, tmp_path,
        )
        assert exit_code == 0

    def test_main_returns_1_on_upload_failure(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        exit_code = self._run_main(
            ["upload_solution_zip_to_datahub.py", "-r", "Eagles/ZipSolutions"],
            f, tmp_path,
            upload_results=[{"Success": False, "FailureReason": "Server error"}],
        )
        assert exit_code == 1

    def test_main_returns_1_when_no_path_in_mapping(self, tmp_path):
        """When mapping has no entry with a Path field, main returns 1."""
        mapping = [{"Name": "ModelA", "Id": "m1"}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        exit_code = self._run_main(
            ["upload_solution_zip_to_datahub.py", "-r", "Eagles/ZipSolutions"],
            f, tmp_path,
        )
        assert exit_code == 1

    def test_main_passes_custom_pattern(self, tmp_path):
        mapping = [{"Name": "ModelA", "Id": "m1", "Path": str(tmp_path)}]
        f = tmp_path / "mapping.json"
        _write_mapping(f, mapping)

        with patch("sys.argv", ["upload_solution_zip_to_datahub.py", "-r", "Eagles/ZipSolutions", "-p", "*.zip"]):
            with patch("upload_solution_zip_to_datahub.CloudSDK") as mock_sdk_cls:
                mock_sdk = mock_sdk_cls.return_value
                mock_sdk.datahub.upload.return_value = MagicMock()
                with patch("upload_solution_zip_to_datahub.SDKBase.get_response_data",
                           return_value=_make_sdk_response([{"Success": True}])):
                    with patch.object(MOD, "CLOUD_CLI_PATH", "mock_cli"):
                        with patch.object(MOD, "EXECUTION_ID", "exec-001"):
                            with patch.object(MOD, "DIRECTORY_MAP_PATH", str(f)):
                                MOD.main()

        _, kwargs = mock_sdk.datahub.upload.call_args
        assert kwargs["glob_patterns"] == ["*.zip"]
