"""
Unit tests for Post/PLEXOS/DatahubSolParquetUploader/datahub_solparquet_uploader.py

Tests the DatahubSolParquetUploader class and main() function.
All CloudSDK calls are mocked — no real cloud services are contacted.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module


MOD = get_module("solparquet_uploader")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sdk_response(results: list[dict]):
    """Build a mock SDKBase.get_response_data return value."""
    mock_results = []
    for r in results:
        m = MagicMock()
        m.Success = r.get("Success", True)
        m.RelativeFilePath = r.get("RelativeFilePath", "file.parquet")
        m.LocalFilePath = r.get("LocalFilePath", "/local/file.parquet")
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
        assert MOD._decode_path("/simulation/My%20Model/parquet") == "/simulation/My Model/parquet"

    def test_decodes_other_percent_encoded_chars(self):
        assert MOD._decode_path("path%2Fwith%2Fslashes") == "path/with/slashes"

    def test_strips_single_quotes(self):
        assert MOD._decode_path("'/some/path'") == "/some/path"

    def test_strips_double_quotes(self):
        assert MOD._decode_path('"/some/path"') == "/some/path"

    def test_plain_path_unchanged(self):
        assert MOD._decode_path("/some/plain/path") == "/some/plain/path"


# ---------------------------------------------------------------------------
# ModelData
# ---------------------------------------------------------------------------

class TestModelData:
    def test_attributes(self):
        md = MOD.ModelData(model_id="abc", parquet_path="/data/abc")
        assert md.id == "abc"
        assert md.parquet_path == "/data/abc"


# ---------------------------------------------------------------------------
# DatahubSolParquetUploader._read_mapping
# ---------------------------------------------------------------------------

class TestReadMapping:
    def _uploader(self):
        with patch("datahub_solparquet_uploader.CloudSDK"):
            return MOD.DatahubSolParquetUploader(cli_path="mock_cli")

    def test_returns_first_entry_with_parquet_path(self, tmp_path):
        mapping = [
            {"Id": "m1", "ParquetPath": "/data/m1"},
            {"Id": "m2", "ParquetPath": "/data/m2"},
        ]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        uploader = self._uploader()
        result = uploader._read_mapping(str(f))

        assert result.id == "m1"
        assert result.parquet_path == "/data/m1"

    def test_skips_entries_without_parquet_path(self, tmp_path):
        mapping = [
            {"Id": "m1", "Name": "NoParquet"},
            {"Id": "m2", "ParquetPath": "/data/m2"},
        ]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        uploader = self._uploader()
        result = uploader._read_mapping(str(f))

        assert result.id == "m2"
        assert result.parquet_path == "/data/m2"

    def test_raises_on_empty_json(self, tmp_path):
        f = tmp_path / "mapping.json"
        f.write_text("[]")

        uploader = self._uploader()
        with pytest.raises(ValueError, match="empty"):
            uploader._read_mapping(str(f))

    def test_raises_when_no_parquet_path_entry(self, tmp_path):
        mapping = [{"Id": "m1", "Name": "NoParquet"}]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        uploader = self._uploader()
        with pytest.raises(ValueError, match="ParquetPath"):
            uploader._read_mapping(str(f))

    def test_raises_on_missing_file(self):
        uploader = self._uploader()
        with pytest.raises(FileNotFoundError):
            uploader._read_mapping("/nonexistent/mapping.json")

    def test_raises_when_id_is_missing(self, tmp_path):
        """Entries with a ParquetPath but no Id field raise ValueError."""
        mapping = [{"ParquetPath": "/data/m1"}]  # no Id key
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        uploader = self._uploader()
        with pytest.raises(ValueError, match="'Id'"):
            uploader._read_mapping(str(f))

    def test_raises_when_id_is_empty_string(self, tmp_path):
        """Entries with an empty Id raise ValueError."""
        mapping = [{"Id": "", "ParquetPath": "/data/m1"}]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        uploader = self._uploader()
        with pytest.raises(ValueError, match="'Id'"):
            uploader._read_mapping(str(f))

    def test_decodes_url_encoded_parquet_path(self, tmp_path):
        """ParquetPath values with URL-encoded spaces are decoded."""
        mapping = [{"Id": "m1", "ParquetPath": "/simulation/My%20Model/parquet"}]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        uploader = self._uploader()
        result = uploader._read_mapping(str(f))

        assert result.parquet_path == "/simulation/My Model/parquet"


# ---------------------------------------------------------------------------
# DatahubSolParquetUploader._resolve_mapping_file
# ---------------------------------------------------------------------------

class TestResolveMappingFile:
    def _uploader(self):
        with patch("datahub_solparquet_uploader.CloudSDK"):
            return MOD.DatahubSolParquetUploader(cli_path="mock_cli")

    def test_uses_env_path_when_exists(self, tmp_path):
        f = tmp_path / "mymap.json"
        f.write_text("[]")

        uploader = self._uploader()
        result = uploader._resolve_mapping_file(str(f))
        assert result == str(f)

    def test_falls_back_to_split_path(self):
        split_path = "/simulation/splits/directorymapping.json"
        with patch("datahub_solparquet_uploader.os.path.exists",
                   side_effect=lambda p: p == split_path):
            uploader = self._uploader()
            result = uploader._resolve_mapping_file("")
        assert result == split_path

    def test_raises_when_neither_path_exists(self):
        with patch("datahub_solparquet_uploader.os.path.exists", return_value=False):
            uploader = self._uploader()
            with pytest.raises(FileNotFoundError, match="Mapping file not found"):
                uploader._resolve_mapping_file("")


# ---------------------------------------------------------------------------
# DatahubSolParquetUploader.upload  — SDK parameter contract
# ---------------------------------------------------------------------------

class TestUploadSDKParams:
    """Assert the correct SDK parameter names are used (most common source of runtime errors)."""

    def _run_upload(self, tmp_path, sdk_response_data):
        mapping = [{"Id": "sol1", "ParquetPath": str(tmp_path / "parquet")}]
        map_file = tmp_path / "mapping.json"
        map_file.write_text(json.dumps(mapping))
        (tmp_path / "parquet").mkdir()

        with patch("datahub_solparquet_uploader.CloudSDK") as MockSDK, \
             patch("datahub_solparquet_uploader.SDKBase.get_response_data") as mock_get_data, \
             patch("datahub_solparquet_uploader.DIRECTORY_MAP_PATH", str(map_file)), \
             patch("datahub_solparquet_uploader.os.path.exists", return_value=True):

            mock_sdk_instance = MockSDK.return_value
            mock_sdk_instance.datahub.upload.return_value = MagicMock()
            mock_get_data.return_value = sdk_response_data

            uploader = MOD.DatahubSolParquetUploader(cli_path="mock_cli")

            result = uploader.upload(remote_base="Project/Solutions")

        return result, mock_sdk_instance

    def test_upload_uses_correct_param_names(self, tmp_path):
        """Verify local_folder, remote_folder, glob_patterns, is_versioned, print_message."""
        sdk_data = _make_sdk_response([{"Success": True, "RelativeFilePath": "a.parquet"}])
        _, mock_sdk = self._run_upload(tmp_path, sdk_data)

        call_kwargs = mock_sdk.datahub.upload.call_args.kwargs
        assert "local_folder"   in call_kwargs, "local_folder param missing"
        assert "remote_folder"  in call_kwargs, "remote_folder param missing"
        assert "glob_patterns"  in call_kwargs, "glob_patterns param missing"
        assert "is_versioned"   in call_kwargs, "is_versioned param missing"
        assert "print_message"  in call_kwargs, "print_message param missing"
        assert call_kwargs["print_message"] is False, "print_message must be False"
        assert call_kwargs["is_versioned"] is True
        assert call_kwargs["glob_patterns"] == ["**/*.parquet"]

    def test_upload_remote_folder_contains_model_id(self, tmp_path):
        """Remote folder must include model ID."""
        sdk_data = _make_sdk_response([{"Success": True, "RelativeFilePath": "a.parquet"}])
        _, mock_sdk = self._run_upload(tmp_path, sdk_data)

        remote = mock_sdk.datahub.upload.call_args.kwargs["remote_folder"]
        assert "sol1" in remote

    def test_upload_success(self, tmp_path):
        sdk_data = _make_sdk_response([{"Success": True, "RelativeFilePath": "a.parquet"}])
        result, _ = self._run_upload(tmp_path, sdk_data)
        assert result is True

    def test_upload_treats_identical_file_as_success(self, tmp_path):
        sdk_data = _make_sdk_response([{
            "Success": False,
            "RelativeFilePath": "a.parquet",
            "FailureReason": "File is identical to the remote file",
        }])
        result, _ = self._run_upload(tmp_path, sdk_data)
        assert result is True

    def test_upload_fails_on_real_error(self, tmp_path):
        sdk_data = _make_sdk_response([{
            "Success": False,
            "RelativeFilePath": "a.parquet",
            "FailureReason": "Permission denied",
        }])
        result, _ = self._run_upload(tmp_path, sdk_data)
        assert result is False

    def test_upload_fails_when_no_response_data(self, tmp_path):
        result, _ = self._run_upload(tmp_path, None)
        assert result is False

    def test_upload_raises_when_mapping_file_missing(self, tmp_path):
        """upload() raises FileNotFoundError when neither mapping path exists."""
        with patch("datahub_solparquet_uploader.CloudSDK"), \
             patch("datahub_solparquet_uploader.DIRECTORY_MAP_PATH", ""), \
             patch("datahub_solparquet_uploader.os.path.exists", return_value=False):
            uploader = MOD.DatahubSolParquetUploader(cli_path="mock_cli")
            with pytest.raises(FileNotFoundError, match="Mapping file not found"):
                uploader.upload(remote_base="Project/Solutions")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_returns_0_on_success(self):
        with patch.object(MOD.DatahubSolParquetUploader, "__init__", return_value=None), \
             patch.object(MOD.DatahubSolParquetUploader, "upload", return_value=True), \
             patch("sys.argv", ["script", "-r", "Project/Solutions"]):
            code = MOD.main()
        assert code == 0

    def test_main_returns_1_on_failure(self):
        with patch.object(MOD.DatahubSolParquetUploader, "__init__", return_value=None), \
             patch.object(MOD.DatahubSolParquetUploader, "upload", return_value=False), \
             patch("sys.argv", ["script", "-r", "Project/Solutions"]):
            code = MOD.main()
        assert code == 1

    def test_main_returns_1_on_exception(self):
        with patch.object(MOD.DatahubSolParquetUploader, "__init__", return_value=None), \
             patch.object(MOD.DatahubSolParquetUploader, "upload", side_effect=RuntimeError("boom")), \
             patch("sys.argv", ["script", "-r", "Project/Solutions"]):
            code = MOD.main()
        assert code == 1

    def test_main_url_encoded_remote_path_is_decoded(self):
        """Spaces encoded as %20 in -r are decoded before being passed to upload()."""
        captured = {}

        def fake_upload(remote_base):
            captured["remote_base"] = remote_base
            return True

        with patch.object(MOD.DatahubSolParquetUploader, "__init__", return_value=None), \
             patch.object(MOD.DatahubSolParquetUploader, "upload", side_effect=fake_upload), \
             patch("sys.argv", ["script", "-r", "Project/My%20Solutions"]):
            MOD.main()

        assert captured["remote_base"] == "Project/My Solutions"
