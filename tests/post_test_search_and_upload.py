"""
Unit tests for Post/PLEXOS/SearchAndUpload/search_and_upload.py

Tests file discovery (filesystem and ZIP), staging, CSV→Parquet conversion,
DataHub upload, and main() integration.
eecloud SDK is mocked in conftest.py.
"""
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module

MOD = get_module("search_and_upload")


# ── find_file tests ───────────────────────────────────────────────────────────

class TestFindFile:
    def test_finds_file_in_first_path(self, tmp_dir):
        (tmp_dir / "results.csv").write_text("data")
        found = MOD.find_file("results.csv", [str(tmp_dir)])
        assert found == str(tmp_dir / "results.csv")

    def test_returns_none_when_not_found(self, tmp_dir):
        assert MOD.find_file("missing.csv", [str(tmp_dir)]) is None

    def test_prefers_first_matching_path(self, tmp_dir):
        first = tmp_dir / "first"
        second = tmp_dir / "second"
        first.mkdir()
        second.mkdir()
        (first / "results.csv").write_text("data")
        (second / "results.csv").write_text("other")
        found = MOD.find_file("results.csv", [str(first), str(second)])
        assert found == str(first / "results.csv")

    def test_falls_through_to_second_path_when_not_in_first(self, tmp_dir):
        first = tmp_dir / "empty"
        second = tmp_dir / "with_file"
        first.mkdir()
        second.mkdir()
        (second / "results.csv").write_text("data")
        found = MOD.find_file("results.csv", [str(first), str(second)])
        assert found == str(second / "results.csv")

    def test_searches_recursively(self, tmp_dir):
        subdir = tmp_dir / "a" / "b"
        subdir.mkdir(parents=True)
        (subdir / "deep.csv").write_text("data")
        found = MOD.find_file("deep.csv", [str(tmp_dir)])
        assert found == str(subdir / "deep.csv")

    def test_supports_glob_pattern(self, tmp_dir):
        (tmp_dir / "report_2024.csv").write_text("data")
        found = MOD.find_file("report_*.csv", [str(tmp_dir)])
        assert found is not None
        assert "report_2024.csv" in found

    def test_skips_nonexistent_paths(self, tmp_dir):
        nonexistent = str(tmp_dir / "does_not_exist")
        assert MOD.find_file("results.csv", [nonexistent]) is None

    def test_returns_none_for_empty_path_list(self, tmp_dir):
        assert MOD.find_file("results.csv", []) is None


# ── find_in_zips tests ────────────────────────────────────────────────────────

class TestFindInZips:
    def _make_zip(self, zip_path: Path, entries: dict[str, str]):
        """Create a ZIP file with the given {name: content} entries."""
        with zipfile.ZipFile(zip_path, "w") as zf:
            for name, content in entries.items():
                zf.writestr(name, content)

    def test_finds_file_inside_zip(self, tmp_dir):
        self._make_zip(tmp_dir / "archive.zip", {"results.csv": "a,b\n1,2"})
        found = MOD.find_in_zips("results.csv", [str(tmp_dir)], str(tmp_dir))
        assert found is not None
        assert Path(found).name == "results.csv"
        assert Path(found).exists()

    def test_returns_none_when_entry_not_in_zip(self, tmp_dir):
        self._make_zip(tmp_dir / "archive.zip", {"other.csv": "a"})
        found = MOD.find_in_zips("missing.csv", [str(tmp_dir)], str(tmp_dir))
        assert found is None

    def test_returns_none_when_no_zips_present(self, tmp_dir):
        assert MOD.find_in_zips("results.csv", [str(tmp_dir)], str(tmp_dir)) is None

    def test_flattens_subdirectory_in_zip(self, tmp_dir):
        self._make_zip(tmp_dir / "archive.zip", {"sub/dir/deep.csv": "data"})
        found = MOD.find_in_zips("deep.csv", [str(tmp_dir)], str(tmp_dir))
        assert found is not None
        assert Path(found).parent == tmp_dir  # no subdirectory retained

    def test_supports_glob_pattern(self, tmp_dir):
        self._make_zip(tmp_dir / "archive.zip", {"report_2024.csv": "data"})
        found = MOD.find_in_zips("report_*.csv", [str(tmp_dir)], str(tmp_dir))
        assert found is not None

    def test_rejects_path_traversal_entry(self, tmp_dir):
        extract_dir = tmp_dir / "extract"
        extract_dir.mkdir()
        self._make_zip(tmp_dir / "evil.zip", {"../../evil.csv": "bad", "safe.csv": "good"})
        # The traversal entry must be skipped; the safe entry is still found
        found = MOD.find_in_zips("safe.csv", [str(tmp_dir)], str(extract_dir))
        assert found is not None
        # Must not have written outside extract_dir
        assert not (tmp_dir.parent / "evil.csv").exists()

    def test_rejects_absolute_path_entry(self, tmp_dir):
        extract_dir = tmp_dir / "extract"
        extract_dir.mkdir()
        # zipfile allows writing absolute paths into the archive
        zip_path = tmp_dir / "abs.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("/etc/passwd", "root:x:0:0")
            zf.writestr("legit.csv", "a,b")
        found = MOD.find_in_zips("legit.csv", [str(tmp_dir)], str(extract_dir))
        assert found is not None
        assert not Path("/etc/passwd_injected").exists()  # absolute entry was skipped

    def test_skips_bad_zip_and_continues(self, tmp_dir):
        (tmp_dir / "bad.zip").write_bytes(b"not a zip")
        good = tmp_dir / "good"
        good.mkdir()
        self._make_zip(good / "archive.zip", {"target.csv": "data"})
        found = MOD.find_in_zips("target.csv", [str(tmp_dir), str(good)], str(tmp_dir))
        assert found is not None


# ── convert_csv_to_parquet tests ──────────────────────────────────────────────

class TestConvertCsvToParquet:
    def test_creates_parquet_file(self, tmp_dir, sample_csv):
        parquet_path, success = MOD.convert_csv_to_parquet(str(sample_csv))
        assert success
        assert Path(parquet_path).exists()
        assert parquet_path.endswith(".parquet")

    def test_deletes_source_csv_on_success(self, tmp_dir, sample_csv):
        MOD.convert_csv_to_parquet(str(sample_csv))
        assert not sample_csv.exists()

    def test_returns_parquet_path_on_success(self, tmp_dir, sample_csv):
        expected = str(sample_csv.with_suffix(".parquet"))
        parquet_path, success = MOD.convert_csv_to_parquet(str(sample_csv))
        assert success
        assert parquet_path == expected

    def test_returns_failure_on_invalid_csv(self, tmp_dir):
        bad_csv = tmp_dir / "bad.csv"
        bad_csv.write_bytes(b"\xff\xfe malformed content \x00")
        parquet_path, success = MOD.convert_csv_to_parquet(str(bad_csv))
        assert not success
        assert parquet_path == ""

    def test_parquet_extension_matches_stem(self, tmp_dir, sample_csv):
        parquet_path, _ = MOD.convert_csv_to_parquet(str(sample_csv))
        assert Path(parquet_path).stem == sample_csv.stem


# ── stage_file tests ──────────────────────────────────────────────────────────

class TestStageFile:
    def test_moves_file_to_output_path(self, tmp_dir):
        src_dir = tmp_dir / "src"
        out_dir = tmp_dir / "out"
        src_dir.mkdir()
        out_dir.mkdir()
        src = src_dir / "file.csv"
        src.write_text("data")

        result = MOD.stage_file(str(src), str(out_dir), str(tmp_dir / "sim"))

        assert result is not None
        assert result.exists()
        assert result.parent == out_dir
        assert not src.exists()  # moved, not copied

    def test_copies_when_source_is_in_simulation_path(self, tmp_dir):
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()
        src = sim_dir / "file.csv"
        src.write_text("data")

        result = MOD.stage_file(str(src), str(out_dir), str(sim_dir))

        assert result is not None
        assert result.exists()
        assert src.exists()  # original preserved

    def test_returns_path_unchanged_when_already_in_output(self, tmp_dir):
        out_dir = tmp_dir / "output"
        out_dir.mkdir()
        src = out_dir / "file.csv"
        src.write_text("data")

        result = MOD.stage_file(str(src), str(out_dir), str(tmp_dir / "sim"))

        assert result == src.resolve()

    def test_creates_output_dir_if_missing(self, tmp_dir):
        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        out_dir = tmp_dir / "new_out"
        src = src_dir / "file.csv"
        src.write_text("data")

        result = MOD.stage_file(str(src), str(out_dir), str(tmp_dir / "sim"))

        assert out_dir.exists()
        assert result is not None

    def test_returns_none_on_error(self, tmp_dir):
        result = MOD.stage_file(
            str(tmp_dir / "nonexistent.csv"), str(tmp_dir / "out"), str(tmp_dir / "sim")
        )
        assert result is None


# ── upload_to_datahub tests ───────────────────────────────────────────────────

def _make_upload_response(success=True, failure_reason=None):
    """Build a mock CloudSDK upload response."""
    result = MagicMock()
    result.Success = success
    result.RelativeFilePath = "Project/Study/file.parquet"
    result.FailureReason = failure_reason
    data = MagicMock()
    data.DatahubResourceResults = [result]
    return data


class TestUploadToDatahub:
    def test_returns_true_on_successful_upload(self, tmp_dir):
        staged = tmp_dir / "file.parquet"
        staged.write_text("data")
        mock_data = _make_upload_response(success=True)
        with patch.object(MOD, "CloudSDK") as mock_sdk_cls:
            with patch.object(MOD.SDKBase, "get_response_data", return_value=mock_data):
                result = MOD.upload_to_datahub(staged, "Project/Study", "mock_cli")
        upload_call = mock_sdk_cls.return_value.datahub.upload
        kwargs = upload_call.call_args.kwargs
        assert kwargs["local_folder"] == str(staged.parent)
        assert kwargs["remote_folder"] == "Project/Study"
        assert kwargs["glob_patterns"] == [staged.name]
        assert kwargs["is_versioned"] is True
        assert kwargs["print_message"] is False
        assert result is True

    def test_returns_true_when_file_identical_to_remote(self, tmp_dir):
        staged = tmp_dir / "file.parquet"
        staged.write_text("data")
        mock_data = _make_upload_response(success=False, failure_reason="File is identical to the remote file")
        with patch.object(MOD, "CloudSDK") as mock_sdk_cls:
            with patch.object(MOD.SDKBase, "get_response_data", return_value=mock_data):
                result = MOD.upload_to_datahub(staged, "Project/Study", "mock_cli")
        upload_call = mock_sdk_cls.return_value.datahub.upload
        kwargs = upload_call.call_args.kwargs
        assert kwargs["local_folder"] == str(staged.parent)
        assert kwargs["remote_folder"] == "Project/Study"
        assert kwargs["glob_patterns"] == [staged.name]
        assert kwargs["is_versioned"] is True
        assert kwargs["print_message"] is False
        assert result is True

    def test_returns_false_when_upload_fails(self, tmp_dir):
        staged = tmp_dir / "file.parquet"
        staged.write_text("data")
        mock_data = _make_upload_response(success=False, failure_reason="Access denied")
        with patch.object(MOD, "CloudSDK") as mock_sdk_cls:
            with patch.object(MOD.SDKBase, "get_response_data", return_value=mock_data):
                result = MOD.upload_to_datahub(staged, "Project/Study", "mock_cli")
        upload_call = mock_sdk_cls.return_value.datahub.upload
        kwargs = upload_call.call_args.kwargs
        assert kwargs["local_folder"] == str(staged.parent)
        assert kwargs["remote_folder"] == "Project/Study"
        assert kwargs["glob_patterns"] == [staged.name]
        assert kwargs["is_versioned"] is True
        assert kwargs["print_message"] is False
        assert result is False

    def test_returns_false_when_response_data_is_none(self, tmp_dir):
        staged = tmp_dir / "file.parquet"
        staged.write_text("data")
        with patch.object(MOD, "CloudSDK") as mock_sdk_cls:
            with patch.object(MOD.SDKBase, "get_response_data", return_value=None):
                result = MOD.upload_to_datahub(staged, "Project/Study", "mock_cli")
        assert result is False

    def test_returns_false_on_sdk_exception(self, tmp_dir):
        staged = tmp_dir / "file.parquet"
        staged.write_text("data")
        with patch.object(MOD, "CloudSDK", side_effect=RuntimeError("SDK error")):
            result = MOD.upload_to_datahub(staged, "Project/Study", "mock_cli")
        assert result is False

    def test_passes_print_message_false(self, tmp_dir):
        staged = tmp_dir / "file.parquet"
        staged.write_text("data")
        mock_data = _make_upload_response(success=True)
        with patch.object(MOD, "CloudSDK") as mock_sdk_cls:
            with patch.object(MOD.SDKBase, "get_response_data", return_value=mock_data):
                MOD.upload_to_datahub(staged, "Project/Study", "mock_cli")
        upload_call = mock_sdk_cls.return_value.datahub.upload
        kwargs = upload_call.call_args.kwargs
        assert kwargs["local_folder"] == str(staged.parent)
        assert kwargs["remote_folder"] == "Project/Study"
        assert kwargs["glob_patterns"] == [staged.name]
        assert kwargs["is_versioned"] is True
        assert kwargs["print_message"] is False


# ── main() tests ──────────────────────────────────────────────────────────────

class TestMain:
    def test_returns_1_when_file_not_found(self, tmp_dir, monkeypatch):
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(tmp_dir / "out"))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir / "sim"))
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "missing.csv"])
        assert MOD.main() == 1

    def test_returns_0_when_file_found_and_staged(self, tmp_dir, monkeypatch):
        out = tmp_dir / "out"
        sim = tmp_dir / "sim"
        out.mkdir()
        sim.mkdir()
        (sim / "results.parquet").write_text("data")
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(sim))
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "results.parquet"])
        assert MOD.main() == 0

    def test_returns_0_after_csv_to_parquet_conversion(self, tmp_dir, monkeypatch, sample_csv):
        out = tmp_dir / "out"
        out.mkdir()
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir / "sim"))
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "sample.csv",
                                          "-p", str(sample_csv.parent)])
        assert MOD.main() == 0
        assert (out / "sample.parquet").exists()

    def test_returns_1_when_upload_path_given_but_cli_path_missing(self, tmp_dir, monkeypatch):
        out = tmp_dir / "out"
        sim = tmp_dir / "sim"
        out.mkdir()
        sim.mkdir()
        (sim / "file.parquet").write_text("data")
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(sim))
        monkeypatch.setattr(MOD, "CLOUD_CLI_PATH", "")
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "file.parquet",
                                          "-u", "Project/Study/Results"])
        assert MOD.main() == 1

    def test_returns_0_with_successful_upload(self, tmp_dir, monkeypatch):
        out = tmp_dir / "out"
        sim = tmp_dir / "sim"
        out.mkdir()
        sim.mkdir()
        (sim / "file.parquet").write_text("data")
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(sim))
        monkeypatch.setattr(MOD, "CLOUD_CLI_PATH", "mock_cli")
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "file.parquet",
                                          "-u", "Project/Study/Results"])
        with patch.object(MOD, "upload_to_datahub", return_value=True):
            result = MOD.main()
        assert result == 0

    def test_returns_1_when_upload_fails(self, tmp_dir, monkeypatch):
        out = tmp_dir / "out"
        sim = tmp_dir / "sim"
        out.mkdir()
        sim.mkdir()
        (sim / "file.parquet").write_text("data")
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(sim))
        monkeypatch.setattr(MOD, "CLOUD_CLI_PATH", "mock_cli")
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "file.parquet",
                                          "-u", "Project/Study/Results"])
        with patch.object(MOD, "upload_to_datahub", return_value=False):
            result = MOD.main()
        assert result == 1

    def test_searches_inside_zip_when_not_found_on_filesystem(self, tmp_dir, monkeypatch):
        out = tmp_dir / "out"
        sim = tmp_dir / "sim"
        out.mkdir()
        sim.mkdir()
        with zipfile.ZipFile(sim / "archive.zip", "w") as zf:
            zf.writestr("zipped_results.parquet", "fake parquet data")
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(sim))
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "zipped_results.parquet"])
        assert MOD.main() == 0

    def test_uses_explicit_path_arg_first(self, tmp_dir, monkeypatch):
        out = tmp_dir / "out"
        explicit = tmp_dir / "explicit"
        out.mkdir()
        explicit.mkdir()
        (explicit / "target.parquet").write_text("data")
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir / "sim"))
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "target.parquet",
                                          "-p", str(explicit)])
        assert MOD.main() == 0
        assert (out / "target.parquet").exists()

    def test_returns_1_when_csv_conversion_fails(self, tmp_dir, monkeypatch):
        out = tmp_dir / "out"
        src = tmp_dir / "src"
        out.mkdir()
        src.mkdir()
        bad_csv = src / "bad.csv"
        bad_csv.write_bytes(b"\xff\xfe")
        monkeypatch.setattr(MOD, "OUTPUT_PATH", str(out))
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir / "sim"))
        monkeypatch.setattr(sys, "argv", ["search_and_upload.py", "-f", "bad.csv",
                                          "-p", str(src)])
        assert MOD.main() == 1
