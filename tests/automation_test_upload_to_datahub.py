"""
Unit tests for Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py

Covered:
- DataHubUploader.__init__          – stores cli_path, environment; creates SDK
- DataHubUploader.authenticate      – sets environment, logs in; idempotent; re-raises
- DataHubUploader.upload_file       – success, file-not-found raises
- DataHubUploader.upload_directory  – success returns file count, not-a-dir raises
- SDK param names                   – local_folder, remote_folder, glob_patterns,
                                      is_versioned, print_message=False
- main()                            – exit 0 on success, exit 1 on no source given
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from .conftest import get_module

MOD = get_module("auto_upload")
_MOD_NAME = "auto_upload_to_datahub"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth_side_effects():
    """Returns [env_data, login_data] for the two authenticate() SDK calls."""
    env_data = MagicMock()
    env_data.Environment = "preprod"
    login_data = MagicMock()
    login_data.TenantName = "EnergyExemplar"
    login_data.UserName = "user@ee.com"
    return [env_data, login_data]


# ── __init__ ──────────────────────────────────────────────────────────────────

class TestDataHubUploaderInit:

    def test_stores_cli_path_and_environment(self):
        with patch(f"{_MOD_NAME}.CloudSDK"):
            u = MOD.DataHubUploader(cli_path="/path/to/cli", environment="preprod")
        assert u.cli_path == "/path/to/cli"
        assert u.environment == "preprod"

    def test_authenticated_flag_starts_false(self):
        with patch(f"{_MOD_NAME}.CloudSDK"):
            u = MOD.DataHubUploader(cli_path="/path/to/cli", environment="preprod")
        assert u._authenticated is False

    def test_creates_sdk_with_cli_path(self):
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            MOD.DataHubUploader(cli_path="/path/to/cli", environment="preprod")
        MockSDK.assert_called_once_with(cli_path="/path/to/cli")


# ── authenticate ──────────────────────────────────────────────────────────────

class TestAuthenticate:

    def test_sets_environment_and_logs_in(self):
        env_data, login_data = _auth_side_effects()
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                mock_get.side_effect = [env_data, login_data]
                u = MOD.DataHubUploader(cli_path="cli", environment="preprod")
                u.authenticate()

        MockSDK.return_value.environment.set_user_environment.assert_called_once_with("preprod")
        MockSDK.return_value.auth.login.assert_called_once()
        assert u._authenticated is True

    def test_idempotent_only_authenticates_once(self):
        env_data, login_data = _auth_side_effects()
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                mock_get.side_effect = [env_data, login_data]
                u = MOD.DataHubUploader(cli_path="cli", environment="preprod")
                u.authenticate()
                u.authenticate()  # second call must be a no-op

        assert MockSDK.return_value.auth.login.call_count == 1

    def test_reraises_on_sdk_error(self):
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            MockSDK.return_value.environment.set_user_environment.side_effect = RuntimeError("boom")
            u = MOD.DataHubUploader(cli_path="cli", environment="preprod")
            with pytest.raises(RuntimeError, match="boom"):
                u.authenticate()


# ── upload_file ───────────────────────────────────────────────────────────────

class TestUploadFile:
    """Tests for DataHubUploader.upload_file().

    authenticate() is pre-bypassed by setting _authenticated=True.
    """

    def _make_uploader(self, mock_sdk):
        with patch(f"{_MOD_NAME}.CloudSDK"):
            u = MOD.DataHubUploader(cli_path="cli", environment="preprod")
        u._authenticated = True
        u.sdk = mock_sdk
        return u

    def test_upload_file_success(self, tmp_dir):
        local_file = tmp_dir / "results.csv"
        local_file.write_text("a,b\n1,2\n")

        mock_sdk = MagicMock()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data"):
            u = self._make_uploader(mock_sdk)
            u.upload_file(local_path=local_file, datahub_path="Project/Study/Results")

        mock_sdk.datahub.upload.assert_called_once()

    def test_upload_file_not_found_raises(self, tmp_dir):
        mock_sdk = MagicMock()
        u = self._make_uploader(mock_sdk)
        with pytest.raises(FileNotFoundError):
            u.upload_file(local_path=tmp_dir / "ghost.csv", datahub_path="Project/Study/Results")

    def test_upload_file_uses_correct_sdk_param_names(self, tmp_dir):
        """Verifies local_folder, remote_folder, glob_patterns, is_versioned, print_message."""
        local_file = tmp_dir / "output.csv"
        local_file.write_text("x\n1\n")

        mock_sdk = MagicMock()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data"):
            u = self._make_uploader(mock_sdk)
            u.upload_file(local_path=local_file, datahub_path="Project/Study/Results")

        mock_sdk.datahub.upload.assert_called_once()
        _, kwargs = mock_sdk.datahub.upload.call_args
        assert "local_folder"   in kwargs, "Must use 'local_folder'"
        assert "remote_folder"  in kwargs, "Must use 'remote_folder'"
        assert "glob_patterns"  in kwargs, "Must use 'glob_patterns'"
        assert "is_versioned"   in kwargs, "Must use 'is_versioned'"
        assert kwargs.get("print_message") is False
        # Ensure local_folder is the parent directory, not the full file path
        assert kwargs["local_folder"] == str(local_file.parent)
        # Ensure glob_patterns contains just the filename
        assert kwargs["glob_patterns"] == [local_file.name]


# ── upload_directory ──────────────────────────────────────────────────────────

class TestUploadDirectory:
    """Tests for DataHubUploader.upload_directory()."""

    def _make_uploader(self, mock_sdk):
        with patch(f"{_MOD_NAME}.CloudSDK"):
            u = MOD.DataHubUploader(cli_path="cli", environment="preprod")
        u._authenticated = True
        u.sdk = mock_sdk
        return u

    def test_upload_directory_returns_file_count(self, tmp_dir):
        (tmp_dir / "a.csv").write_text("x\n1\n")
        (tmp_dir / "b.csv").write_text("x\n2\n")

        mock_sdk = MagicMock()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data"):
            u = self._make_uploader(mock_sdk)
            count = u.upload_directory(local_dir=tmp_dir, datahub_path="Project/Study/Results", pattern="*.csv")

        assert count == 2

    def test_upload_directory_not_a_dir_raises(self, tmp_dir):
        fake_path = tmp_dir / "notadir"
        mock_sdk = MagicMock()
        u = self._make_uploader(mock_sdk)
        with pytest.raises(NotADirectoryError):
            u.upload_directory(local_dir=fake_path, datahub_path="Project/Study/Results")

    def test_upload_directory_uses_correct_sdk_param_names(self, tmp_dir):
        """Verifies local_folder, remote_folder, glob_patterns, is_versioned, print_message."""
        (tmp_dir / "result.parquet").write_bytes(b"PAR1")

        mock_sdk = MagicMock()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data"):
            u = self._make_uploader(mock_sdk)
            u.upload_directory(
                local_dir=tmp_dir,
                datahub_path="Project/Study/Output",
                pattern="*.parquet",
            )

        mock_sdk.datahub.upload.assert_called_once()
        _, kwargs = mock_sdk.datahub.upload.call_args
        assert "local_folder"  in kwargs, "Must use 'local_folder'"
        assert "remote_folder" in kwargs, "Must use 'remote_folder'"
        assert "glob_patterns" in kwargs, "Must use 'glob_patterns'"
        assert "is_versioned"  in kwargs, "Must use 'is_versioned'"
        assert kwargs.get("print_message") is False
        assert kwargs["local_folder"]  == str(tmp_dir)
        assert kwargs["remote_folder"] == "Project/Study/Output"
        assert kwargs["glob_patterns"] == ["*.parquet"]

    def test_upload_directory_empty_dir_returns_zero(self, tmp_dir):
        mock_sdk = MagicMock()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data"):
            u = self._make_uploader(mock_sdk)
            count = u.upload_directory(local_dir=tmp_dir, datahub_path="Project/Study/Results")

        assert count == 0

    def test_upload_directory_recursive_glob_counts_subdirs(self, tmp_dir):
        sub = tmp_dir / "sub"
        sub.mkdir()
        (tmp_dir / "root.csv").write_text("data")
        (sub / "nested.csv").write_text("data")

        mock_sdk = MagicMock()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data"):
            u = self._make_uploader(mock_sdk)
            count = u.upload_directory(
                local_dir=tmp_dir,
                datahub_path="Project/Study/Results",
                pattern="**/*.csv",
            )

        assert count == 2


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:

    def test_main_no_files_no_directory_returns_1(self, tmp_dir):
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "-d", "Project/Study/Results",
            # Neither --file nor --directory supplied
        ]
        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch("sys.argv", args):
                exit_code = MOD.main()

        assert exit_code == 1

    def test_main_upload_file_success_returns_0(self, tmp_dir):
        local_file = tmp_dir / "output.csv"
        local_file.write_text("a,b\n1,2\n")
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "-f", str(local_file),
            "-d", "Project/Study/Results",
        ]
        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                env_data, login_data = _auth_side_effects()
                mock_get.side_effect = [env_data, login_data, MagicMock()]
                with patch("sys.argv", args):
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_main_upload_directory_success_returns_0(self, tmp_dir):
        (tmp_dir / "result.csv").write_text("data")
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "--directory", str(tmp_dir),
            "--pattern", "*.csv",
            "-d", "Project/Study/Results",
        ]
        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                env_data, login_data = _auth_side_effects()
                mock_get.side_effect = [env_data, login_data, MagicMock()]
                with patch("sys.argv", args):
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_main_file_not_found_is_skipped_and_returns_1(self, tmp_dir):
        """A non-existent --file path is skipped and results in exit code 1."""
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "-f", str(tmp_dir / "ghost.csv"),  # does not exist
            "-d", "Project/Study/Results",
        ]
        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                env_data, login_data = _auth_side_effects()
                mock_get.side_effect = [env_data, login_data]
                with patch("sys.argv", args):
                    exit_code = MOD.main()

        assert exit_code == 1

    def test_main_versioned_flag_propagated_for_file(self, tmp_dir):
        """--versioned passes is_versioned=True to the SDK upload call for --file."""
        local_file = tmp_dir / "output.csv"
        local_file.write_text("a,b\n1,2\n")
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "-f", str(local_file),
            "-d", "Project/Study/Results",
            "--versioned",
        ]
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                env_data, login_data = _auth_side_effects()
                mock_get.side_effect = [env_data, login_data, MagicMock()]
                with patch("sys.argv", args):
                    MOD.main()

        _, kwargs = MockSDK.return_value.datahub.upload.call_args
        assert kwargs.get("is_versioned") is True, "--versioned must propagate is_versioned=True"

    def test_main_versioned_flag_propagated_for_directory(self, tmp_dir):
        """--versioned passes is_versioned=True to the SDK upload call for --directory."""
        (tmp_dir / "result.csv").write_text("data")
        args = [
            "script.py",
            "-c", "cli",
            "-e", "preprod",
            "--directory", str(tmp_dir),
            "--pattern", "*.csv",
            "-d", "Project/Study/Results",
            "--versioned",
        ]
        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.SDKBase.get_response_data") as mock_get:
                env_data, login_data = _auth_side_effects()
                mock_get.side_effect = [env_data, login_data, MagicMock()]
                with patch("sys.argv", args):
                    MOD.main()

        _, kwargs = MockSDK.return_value.datahub.upload.call_args
        assert kwargs.get("is_versioned") is True, "--versioned must propagate is_versioned=True"
