"""Unit tests for Post/PLEXOS/CreateChangeSet/create_changeset.py."""

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_mock_eecloud = MagicMock()
sys.modules.setdefault("eecloud", _mock_eecloud)
sys.modules.setdefault("eecloud.cloudsdk", _mock_eecloud.cloudsdk)

from .conftest import get_module

MOD = get_module("create_changeset")


def _sdk_response(status, message):
    item = MagicMock()
    item.Status = status
    item.Message = message
    return item


class TestSyncModelFiles:
    def test_missing_source_and_target_returns_zero(self, tmp_dir):
        staging_dir = tmp_dir / "staging"
        staging_dir.mkdir()

        result = MOD.sync_model_files(str(tmp_dir), str(staging_dir), "project.xml")

        assert result == (0, "missing_source")

    def test_missing_source_with_existing_target_returns_zero(self, tmp_dir):
        staging_dir = tmp_dir / "staging"
        staging_dir.mkdir()
        (staging_dir / "project.xml").write_text("existing", encoding="utf-8")

        result = MOD.sync_model_files(str(tmp_dir), str(staging_dir), "project.xml")

        assert result == (0, "staged_only")
        assert (staging_dir / "project.xml").read_text(encoding="utf-8") == "existing"

    def test_copy_new_target_returns_one(self, tmp_dir):
        source_file = tmp_dir / MOD.MODEL_XML_SOURCE_FILE
        source_file.write_text("fresh xml", encoding="utf-8")
        staging_dir = tmp_dir / "staging"
        staging_dir.mkdir()

        result = MOD.sync_model_files(str(tmp_dir), str(staging_dir), "renamed.xml")

        assert result == (1, "copied")
        assert (staging_dir / "renamed.xml").read_text(encoding="utf-8") == "fresh xml"

    def test_unchanged_file_returns_zero(self, tmp_dir):
        source_file = tmp_dir / MOD.MODEL_XML_SOURCE_FILE
        source_file.write_text("same", encoding="utf-8")
        staging_dir = tmp_dir / "staging"
        staging_dir.mkdir()
        (staging_dir / "project.xml").write_text("same", encoding="utf-8")

        result = MOD.sync_model_files(str(tmp_dir), str(staging_dir), "project.xml")

        assert result == (0, "unchanged")

    def test_overwrite_changed_target_returns_one(self, tmp_dir):
        source_file = tmp_dir / MOD.MODEL_XML_SOURCE_FILE
        source_file.write_text("new value", encoding="utf-8")
        staging_dir = tmp_dir / "staging"
        staging_dir.mkdir()
        target = staging_dir / "project.xml"
        target.write_text("old value", encoding="utf-8")

        result = MOD.sync_model_files(str(tmp_dir), str(staging_dir), "project.xml")

        assert result == (1, "updated")
        assert target.read_text(encoding="utf-8") == "new value"


class TestValidationHelpers:
    def test_decode_argument_value_decodes_url_encoding(self):
        restored_value, changed = MOD._decode_argument_value("update%20model%20file")

        assert restored_value == "update model file"
        assert changed is True

    def test_decode_cli_args_decodes_message_and_target_file(self):
        args = argparse.Namespace(
            message="update%20model%20file",
            target_file="testcommit%201.xml",
        )

        replaced_tokens = MOD._decode_cli_args(args, argparse.ArgumentParser())

        assert replaced_tokens == 2
        assert args.message == "update model file"
        assert args.target_file == "testcommit 1.xml"

    def test_decode_cli_args_rejects_decoded_target_paths_via_parser_error(self):
        args = argparse.Namespace(
            message="update%20model%20file",
            target_file="nested%2Fproject.xml",
        )
        parser = argparse.ArgumentParser()

        with pytest.raises(SystemExit) as exc_info:
            MOD._decode_cli_args(args, parser)

        assert exc_info.value.code == 2

    def test_validate_target_file_rejects_paths(self):
        with pytest.raises(argparse.ArgumentTypeError):
            MOD.validate_target_file("nested/project.xml")

    def test_validate_target_file_rejects_non_xml_names(self):
        with pytest.raises(argparse.ArgumentTypeError):
            MOD.validate_target_file("project.txt")

    def test_prepare_staging_directory_removes_existing_directory(self, tmp_dir):
        staging_dir = tmp_dir / ".changeset_staging"
        staging_dir.mkdir()
        (staging_dir / "old.xml").write_text("stale", encoding="utf-8")

        MOD.prepare_staging_directory(str(staging_dir))

        assert not staging_dir.exists()

    def test_prepare_staging_directory_removes_existing_file(self, tmp_dir):
        staging_path = tmp_dir / ".changeset_staging"
        staging_path.write_text("stale", encoding="utf-8")

        MOD.prepare_staging_directory(str(staging_path))

        assert not staging_path.exists()


class TestResponseHelpers:
    def test_summarize_response_handles_empty_response(self):
        assert MOD.summarize_response([]) == ("", "")


class TestCloneStudy:
    def test_clone_study_calls_sdk_with_expected_kwargs(self, tmp_dir):
        pxc = MagicMock()
        pxc.study.clone_study.return_value = [_sdk_response("Success", "cloned")]
        staging_dir = tmp_dir / ".changeset_staging"

        result = MOD.clone_study(pxc, "study-1", str(staging_dir))

        assert result is True
        pxc.study.clone_study.assert_called_once_with(
            study_id="study-1",
            output_directory_path=str(staging_dir),
            print_message=False,
        )


class TestPushStudyChangeset:
    def test_push_success_returns_true(self):
        pxc = MagicMock()
        pxc.study.push_changeset.return_value = [
            _sdk_response("Info", "starting"),
            _sdk_response("Success", "pushed"),
        ]

        result = MOD.push_study_changeset(pxc, "study-1", "message", retries=3, retry_interval=30)

        assert result is True
        pxc.study.push_changeset.assert_called_once_with(
            study_id="study-1",
            commit_message="message",
            print_message=False,
        )

    def test_no_changes_message_returns_true_without_sleep(self):
        pxc = MagicMock()
        pxc.study.push_changeset.return_value = [
            _sdk_response("Failed", "No changes to push"),
        ]

        with patch.object(MOD.time, "sleep") as sleep_mock:
            result = MOD.push_study_changeset(pxc, "study-1", "message", retries=3, retry_interval=99)

        assert result is True
        sleep_mock.assert_not_called()

    def test_retries_then_fails_returns_false(self):
        pxc = MagicMock()
        pxc.study.push_changeset.return_value = [
            _sdk_response("Failed", "temporary error"),
        ]

        with patch.object(MOD.time, "sleep") as sleep_mock:
            result = MOD.push_study_changeset(pxc, "study-1", "message", retries=3, retry_interval=7)

        assert result is False
        assert pxc.study.push_changeset.call_count == 3
        sleep_mock.assert_called_with(7)
        assert sleep_mock.call_count == 2

    def test_empty_response_returns_false(self):
        pxc = MagicMock()
        pxc.study.push_changeset.return_value = []

        result = MOD.push_study_changeset(pxc, "study-1", "message", retries=1, retry_interval=30)

        assert result is False


class TestMain:
    def test_main_success_path(self):
        mock_sdk = MagicMock()

        with patch.object(MOD, "CloudSDK", return_value=mock_sdk) as cloud_sdk_cls, \
             patch.object(MOD, "prepare_staging_directory") as prepare_staging_mock, \
             patch.object(MOD, "clone_study", return_value=True) as clone_study_mock, \
             patch.object(MOD, "sync_model_files", return_value=(1, "copied")) as sync_mock, \
             patch.object(MOD, "push_study_changeset", return_value=True) as push_mock, \
             patch.object(sys, "argv", ["create_changeset.py", "--message", "commit", "--target-file", "target.xml"]):
            result = MOD.main()

        cloud_sdk_cls.assert_called_once_with(cli_path=MOD.CLOUD_CLI_PATH)
        assert result == 0
        prepare_staging_mock.assert_called_once_with(
            str(Path(MOD.OUTPUT_PATH) / MOD.STAGING_DIRECTORY_NAME)
        )
        clone_study_mock.assert_called_once_with(
            mock_sdk,
            MOD.STUDY_ID,
            str(Path(MOD.OUTPUT_PATH) / MOD.STAGING_DIRECTORY_NAME),
        )
        sync_mock.assert_called_once_with(
            MOD.SIMULATION_PATH,
            str(Path(MOD.OUTPUT_PATH) / MOD.STAGING_DIRECTORY_NAME),
            "target.xml",
        )
        push_mock.assert_called_once_with(mock_sdk, MOD.STUDY_ID, "commit", 3, 30)

    def test_main_uses_default_target_file_and_retry_values(self):
        mock_sdk = MagicMock()

        with patch.object(MOD, "CloudSDK", return_value=mock_sdk), \
             patch.object(MOD, "prepare_staging_directory") as prepare_staging_mock, \
             patch.object(MOD, "clone_study", return_value=True), \
             patch.object(MOD, "sync_model_files", return_value=(1, "copied")) as sync_mock, \
             patch.object(MOD, "push_study_changeset", return_value=True) as push_mock, \
             patch.object(sys, "argv", ["create_changeset.py", "--message", "commit"]):
            result = MOD.main()

        assert result == 0
        prepare_staging_mock.assert_called_once()
        sync_mock.assert_called_once_with(
            MOD.SIMULATION_PATH,
            str(Path(MOD.OUTPUT_PATH) / MOD.STAGING_DIRECTORY_NAME),
            "project.xml",
        )
        push_mock.assert_called_once_with(mock_sdk, MOD.STUDY_ID, "commit", 3, 30)

    def test_main_decodes_url_encoded_message_and_target_file(self):
        mock_sdk = MagicMock()

        with patch.object(MOD, "CloudSDK", return_value=mock_sdk), \
             patch.object(MOD, "prepare_staging_directory"), \
             patch.object(MOD, "clone_study", return_value=True), \
             patch.object(MOD, "sync_model_files", return_value=(1, "copied")) as sync_mock, \
             patch.object(MOD, "push_study_changeset", return_value=True) as push_mock, \
             patch.object(
                 sys,
                 "argv",
                 [
                     "create_changeset.py",
                     "--message",
                     "update%20model%20file",
                     "--target-file",
                     "testcommit%201.xml",
                 ],
             ):
            result = MOD.main()

        assert result == 0
        sync_mock.assert_called_once_with(
            MOD.SIMULATION_PATH,
            str(Path(MOD.OUTPUT_PATH) / MOD.STAGING_DIRECTORY_NAME),
            "testcommit 1.xml",
        )
        push_mock.assert_called_once_with(mock_sdk, MOD.STUDY_ID, "update model file", 3, 30)

    def test_main_no_changes_skips_push(self):
        mock_sdk = MagicMock()

        with patch.object(MOD, "CloudSDK", return_value=mock_sdk), \
             patch.object(MOD, "prepare_staging_directory"), \
             patch.object(MOD, "clone_study", return_value=True), \
             patch.object(MOD, "sync_model_files", return_value=(0, "unchanged")), \
             patch.object(MOD, "push_study_changeset") as push_mock, \
             patch.object(sys, "argv", ["create_changeset.py", "--message", "commit"]):
            result = MOD.main()

        assert result == 0
        push_mock.assert_not_called()

    def test_main_returns_one_when_clone_fails(self):
        mock_sdk = MagicMock()

        with patch.object(MOD, "CloudSDK", return_value=mock_sdk), \
             patch.object(MOD, "prepare_staging_directory"), \
             patch.object(MOD, "clone_study", return_value=False), \
             patch.object(sys, "argv", ["create_changeset.py", "--message", "commit"]):
            result = MOD.main()

        assert result == 1

    def test_main_returns_one_when_push_fails(self):
        mock_sdk = MagicMock()

        with patch.object(MOD, "CloudSDK", return_value=mock_sdk), \
             patch.object(MOD, "prepare_staging_directory"), \
             patch.object(MOD, "clone_study", return_value=True), \
             patch.object(MOD, "sync_model_files", return_value=(1, "copied")), \
             patch.object(MOD, "push_study_changeset", return_value=False), \
             patch.object(sys, "argv", ["create_changeset.py", "--message", "commit"]):
            result = MOD.main()

        assert result == 1

    def test_main_returns_zero_when_source_file_is_missing(self):
        mock_sdk = MagicMock()

        with patch.object(MOD, "CloudSDK", return_value=mock_sdk), \
             patch.object(MOD, "prepare_staging_directory"), \
             patch.object(MOD, "clone_study", return_value=True), \
             patch.object(MOD, "sync_model_files", return_value=(0, "missing_source")), \
             patch.object(MOD, "push_study_changeset") as push_mock, \
             patch.object(sys, "argv", ["create_changeset.py", "--message", "commit"]):
            result = MOD.main()

        assert result == 0
        push_mock.assert_not_called()

    def test_main_returns_one_when_unexpected_exception_occurs(self):
        with patch.object(MOD, "CloudSDK", side_effect=RuntimeError("boom")), \
             patch.object(sys, "argv", ["create_changeset.py", "--message", "commit"]):
            result = MOD.main()

        assert result == 1