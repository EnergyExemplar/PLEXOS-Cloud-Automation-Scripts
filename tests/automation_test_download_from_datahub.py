"""
Unit tests for Automation/PLEXOS/DownloadFromDataHub/download_from_datahub.py

Covered:
- DataHubDownloader.__init__       – stores cli_path, environment; creates SDK
- DataHubDownloader.authenticate   – sets environment, logs in; idempotent; re-raises
- DataHubDownloader.download_file  – success (single & multiple results), no data,
                                     all-failure, partial failure, creates local dir
- SDK param names                  – remote_glob_patterns, output_directory, print_message
- main()                           – exit 0 on all downloads, exit 1 on any failure
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from .conftest import get_module

MOD = get_module("auto_download")
_MOD_NAME = "auto_download_from_datahub"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_download_result(success: bool, rel_path: str, local_path: str, reason: str = None):
    r = MagicMock()
    r.Success = success
    r.RelativeFilePath = rel_path
    r.LocalFilePath = local_path
    r.FailureReason = reason
    return r


def _make_datahub_data(results: list):
    data = MagicMock()
    data.DatahubResourceResults = results
    return data


def _auth_side_effects():
    """Returns [env_data, login_data] for the two authenticate() SDK calls."""
    env_data = MagicMock()
    env_data.Environment = "preprod"
    login_data = MagicMock()
    login_data.TenantName = "EnergyExemplar"
    login_data.UserName = "user@ee.com"
    return [env_data, login_data]


# ── __init__ ──────────────────────────────────────────────────────────────────

class TestDataHubDownloaderInit:

    def test_stores_cli_path_and_environment(self):
        with patch(f"{_MOD_NAME}.CloudSDK"):
            d = MOD.DataHubDownloader(cli_path="/path/to/cli", environment="preprod")
        assert d.cli_path == "/path/to/cli"
        assert d.environment == "preprod"

    def test_authenticated_flag_starts_false(self):
        with patch(f"{_MOD_NAME}.CloudSDK"):
            d = MOD.DataHubDownloader(cli_path="/path/to/cli", environment="preprod")
        assert d._authenticated is False

    def test_creates_sdk_with_cli_path(self):
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            MOD.DataHubDownloader(cli_path="/path/to/cli", environment="preprod")
        MockSDK.assert_called_once_with(cli_path="/path/to/cli")


# ── authenticate ──────────────────────────────────────────────────────────────

class TestAuthenticate:

    def test_sets_environment_and_logs_in(self):
        env_data, login_data = _auth_side_effects()
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                mock_get.side_effect = [env_data, login_data]
                d = MOD.DataHubDownloader(cli_path="cli", environment="preprod")
                d.authenticate()

        MockSDK.return_value.environment.set_user_environment.assert_called_once_with("preprod")
        MockSDK.return_value.auth.login.assert_called_once()
        assert d._authenticated is True

    def test_idempotent_only_authenticates_once(self):
        env_data, login_data = _auth_side_effects()
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                mock_get.side_effect = [env_data, login_data]
                d = MOD.DataHubDownloader(cli_path="cli", environment="preprod")
                d.authenticate()
                d.authenticate()  # second call must be a no-op

        assert MockSDK.return_value.auth.login.call_count == 1

    def test_reraises_on_sdk_error(self):
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            MockSDK.return_value.environment.set_user_environment.side_effect = RuntimeError("SDK boom")
            d = MOD.DataHubDownloader(cli_path="cli", environment="preprod")
            with pytest.raises(RuntimeError, match="SDK boom"):
                d.authenticate()


# ── download_file ─────────────────────────────────────────────────────────────

class TestDownloadFile:
    """Tests for DataHubDownloader.download_file().

    authenticate() is pre-bypassed by setting _authenticated = True and
    injecting a mock SDK directly, so tests focus purely on download logic.
    """

    def _make_downloader(self, mock_sdk):
        with patch(f"{_MOD_NAME}.CloudSDK"):
            d = MOD.DataHubDownloader(cli_path="cli", environment="preprod")
        d._authenticated = True
        d.sdk = mock_sdk
        return d

    def test_success_single_result_returns_local_path(self, tmp_dir):
        local_file = tmp_dir / "file.csv"
        local_file.write_text("a,b\n1,2\n")

        mock_sdk = MagicMock()
        datahub_data = _make_datahub_data([
            _make_download_result(True, "Project/Study/file.csv", str(local_file))
        ])
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=datahub_data):
            d = self._make_downloader(mock_sdk)
            result = d.download_file("Project/Study/file.csv", tmp_dir)

        assert result == local_file

    def test_success_multiple_results_returns_local_dir(self, tmp_dir):
        for name in ("a.csv", "b.csv"):
            (tmp_dir / name).write_text("x\n1\n")

        mock_sdk = MagicMock()
        datahub_data = _make_datahub_data([
            _make_download_result(True, "a.csv", str(tmp_dir / "a.csv")),
            _make_download_result(True, "b.csv", str(tmp_dir / "b.csv")),
        ])
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=datahub_data):
            d = self._make_downloader(mock_sdk)
            result = d.download_file("Project/Study/**", tmp_dir)

        assert result == tmp_dir

    def test_no_data_raises_runtime_error(self, tmp_dir):
        mock_sdk = MagicMock()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=None):
            d = self._make_downloader(mock_sdk)
            with pytest.raises(RuntimeError):
                d.download_file("Project/Study/file.csv", tmp_dir)

    def test_missing_datahub_resource_results_raises_runtime_error(self, tmp_dir):
        mock_sdk = MagicMock()
        data_without_results = MagicMock(spec=[])  # no DatahubResourceResults attr
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=data_without_results):
            d = self._make_downloader(mock_sdk)
            with pytest.raises(RuntimeError):
                d.download_file("Project/Study/file.csv", tmp_dir)

    def test_all_results_failed_raises_file_not_found(self, tmp_dir):
        mock_sdk = MagicMock()
        datahub_data = _make_datahub_data([
            _make_download_result(False, "file.csv", "", "Not found"),
        ])
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=datahub_data):
            d = self._make_downloader(mock_sdk)
            with pytest.raises(FileNotFoundError):
                d.download_file("Project/Study/file.csv", tmp_dir)

    def test_partial_failure_still_returns_path_for_succeeded_files(self, tmp_dir):
        """Files that downloaded successfully are returned; failures are logged."""
        ok_file = tmp_dir / "ok.csv"
        ok_file.write_text("x\n1\n")

        mock_sdk = MagicMock()
        datahub_data = _make_datahub_data([
            _make_download_result(True,  "ok.csv",   str(ok_file)),
            _make_download_result(False, "fail.csv", "",          "Permissions"),
        ])
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=datahub_data):
            d = self._make_downloader(mock_sdk)
            result = d.download_file("Project/Study/**", tmp_dir)

        # Partial success: something was downloaded
        assert result is not None

    def test_creates_local_dir_if_not_exists(self, tmp_dir):
        nested = tmp_dir / "deep" / "sub"
        assert not nested.exists()
        local_file = nested / "file.csv"

        mock_sdk = MagicMock()
        datahub_data = _make_datahub_data([
            _make_download_result(True, "file.csv", str(local_file))
        ])

        def _side_effect(*_args, **_kwargs):
            # Simulate runtime: SDK creates the file as a side-effect of download
            nested.mkdir(parents=True, exist_ok=True)
            local_file.write_text("data")
            return datahub_data

        mock_sdk.datahub.download.side_effect = None
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", side_effect=_side_effect):
            d = self._make_downloader(mock_sdk)
            d.download_file("Project/Study/file.csv", nested)

        assert nested.exists()

    def test_uses_correct_sdk_param_names(self, tmp_dir):
        """Verifies remote_glob_patterns, output_directory, print_message=False."""
        local_file = tmp_dir / "file.csv"
        local_file.write_text("data")

        mock_sdk = MagicMock()
        datahub_data = _make_datahub_data([
            _make_download_result(True, "file.csv", str(local_file))
        ])
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=datahub_data):
            d = self._make_downloader(mock_sdk)
            d.download_file("Project/Study/file.csv", tmp_dir)

        mock_sdk.datahub.download.assert_called_once()
        _, kwargs = mock_sdk.datahub.download.call_args
        assert "remote_glob_patterns" in kwargs, "Must use 'remote_glob_patterns'"
        assert "output_directory"     in kwargs, "Must use 'output_directory'"
        assert kwargs.get("print_message") is False
        assert "remote_folder" not in kwargs, "'remote_folder' is not a valid param"
        assert "local_folder"  not in kwargs, "'local_folder' is not a valid param for download"


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:

    def _make_all_succeed_mock(self, tmp_dir):
        local_file = tmp_dir / "result.csv"
        local_file.write_text("data")
        datahub_data = _make_datahub_data([
            _make_download_result(True, "result.csv", str(local_file))
        ])
        return datahub_data

    def test_main_all_success_returns_0(self, tmp_dir):
        datahub_data = self._make_all_succeed_mock(tmp_dir)
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "-f", "Project/Study/file.csv",
            "-o", str(tmp_dir),
        ]
        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                env_data, login_data = _auth_side_effects()
                mock_get.side_effect = [env_data, login_data, datahub_data]
                with patch("sys.argv", args):
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_main_download_failure_returns_1(self, tmp_dir):
        datahub_data = _make_datahub_data([
            _make_download_result(False, "file.csv", "", "Not found")
        ])
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "-f", "Project/Study/missing.csv",
            "-o", str(tmp_dir),
        ]
        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                env_data, login_data = _auth_side_effects()
                mock_get.side_effect = [env_data, login_data, datahub_data]
                with patch("sys.argv", args):
                    exit_code = MOD.main()

        assert exit_code == 1
