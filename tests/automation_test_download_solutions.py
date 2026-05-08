"""
Unit tests for Automation/PLEXOS/DownloadSolutions/download_solutions.py

Covered:
- authenticate        – sets environment, logs in via SSO or client credentials; raises on None data
- list_solution_ids   – success, no data, no simulations, no model identifiers
- download_solution   – success, failure, creates output dir
- download_all        – all success, partial failure, no solutions found
- SDK param names     – execution_id, solution_id, output_directory, solution_type
- main()              – exit 0 on all success, exit 1 on failure, client-credentials args wired
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from .conftest import get_module

MOD = get_module("auto_download_solutions")
_MOD_NAME = "auto_download_solutions"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_sdk():
    return MagicMock()


def _make_model_identifier(name: str, solution_id: str):
    mi = MagicMock()
    mi.Name = name
    mi.Id = solution_id
    return mi


def _make_simulation(sim_id: str, status: str, model_identifiers=None):
    sim = MagicMock()
    id_obj = MagicMock()
    id_obj.Value = sim_id
    sim.Id = id_obj
    sim.Status = status
    sim.ModelIdentifiers = model_identifiers
    return sim


def _make_sim_data(simulations: list):
    data = MagicMock()
    data.SimulationRecords = simulations
    return data


# ── authenticate ──────────────────────────────────────────────────────────────

class TestAuthenticate:

    def test_sets_environment_and_logs_in_via_sso(self):
        mock_sdk = _make_sdk()
        env_data = MagicMock()
        env_data.Environment = "preprod"
        login_data = MagicMock()
        login_data.TenantName = "EnergyExemplar"
        login_data.UserName = "user@ee.com"

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", side_effect=[env_data, login_data]):
            MOD.authenticate(mock_sdk, "preprod")

        mock_sdk.environment.set_user_environment.assert_called_once_with("preprod")
        mock_sdk.auth.login.assert_called_once()
        mock_sdk.auth.login_client_credentials.assert_not_called()

    def test_sets_environment_and_logs_in(self):
        """Alias for backwards-compat — SSO path."""
        mock_sdk = _make_sdk()
        env_data = MagicMock()
        env_data.Environment = "preprod"
        login_data = MagicMock()
        login_data.TenantName = "EnergyExemplar"
        login_data.UserName = "user@ee.com"

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", side_effect=[env_data, login_data]):
            MOD.authenticate(mock_sdk, "preprod")

        mock_sdk.environment.set_user_environment.assert_called_once_with("preprod")
        mock_sdk.auth.login.assert_called_once()

    def test_uses_client_credentials_when_all_three_provided(self):
        mock_sdk = _make_sdk()
        env_data = MagicMock()
        env_data.Environment = "preprod"
        login_data = MagicMock()
        login_data.TenantName = "EnergyExemplar"
        login_data.UserName = "svc@ee.com"

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", side_effect=[env_data, login_data]):
            MOD.authenticate(
                mock_sdk, "preprod",
                client_id="my-client-id",
                client_secret="my-secret",
                tenant_id="my-tenant",
            )

        mock_sdk.auth.login_client_credentials.assert_called_once_with(
            use_client_credentials=True,
            client_id="my-client-id",
            client_secret="my-secret",
            tenant_id="my-tenant",
        )
        mock_sdk.auth.login.assert_not_called()

    def test_falls_back_to_sso_when_only_some_credentials_provided(self):
        """Partial credentials (e.g. only client_id) → fall back to SSO."""
        mock_sdk = _make_sdk()
        env_data = MagicMock()
        env_data.Environment = "preprod"
        login_data = MagicMock()
        login_data.TenantName = "EnergyExemplar"
        login_data.UserName = "user@ee.com"

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", side_effect=[env_data, login_data]):
            MOD.authenticate(mock_sdk, "preprod", client_id="only-id")

        mock_sdk.auth.login.assert_called_once()
        mock_sdk.auth.login_client_credentials.assert_not_called()

    def test_raises_if_env_data_is_none(self):
        mock_sdk = _make_sdk()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=None):
            with pytest.raises(RuntimeError, match="Failed to set user environment"):
                MOD.authenticate(mock_sdk, "preprod")

    def test_raises_if_login_data_is_none(self):
        mock_sdk = _make_sdk()
        env_data = MagicMock()
        env_data.Environment = "preprod"
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", side_effect=[env_data, None]):
            with pytest.raises(RuntimeError, match="Login failed"):
                MOD.authenticate(mock_sdk, "preprod")

    def test_raises_if_login_data_is_none_client_credentials(self):
        mock_sdk = _make_sdk()
        env_data = MagicMock()
        env_data.Environment = "preprod"
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", side_effect=[env_data, None]):
            with pytest.raises(RuntimeError, match="Login failed"):
                MOD.authenticate(
                    mock_sdk, "preprod",
                    client_id="id", client_secret="sec", tenant_id="ten",
                )

    def test_reraises_on_sdk_exception(self):
        mock_sdk = _make_sdk()
        mock_sdk.environment.set_user_environment.side_effect = RuntimeError("auth boom")
        with pytest.raises(RuntimeError, match="auth boom"):
            MOD.authenticate(mock_sdk, "preprod")


# ── list_solution_ids ─────────────────────────────────────────────────────────

class TestListSolutionIds:

    def test_returns_model_name_to_solution_id_mapping(self):
        mock_sdk = _make_sdk()
        mi1 = _make_model_identifier("ModelA", "sol-aaa")
        mi2 = _make_model_identifier("ModelB", "sol-bbb")
        sim = _make_simulation("sim-001", "Completed", [mi1, mi2])
        sim_data = _make_sim_data([sim])

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=sim_data):
            result = MOD.list_solution_ids(mock_sdk, "exec-001")

        assert result == {"sol-aaa": "ModelA", "sol-bbb": "ModelB"}

    def test_uses_correct_execution_id_param_name(self):
        """execution_id must be passed as a keyword argument to list_simulations."""
        mock_sdk = _make_sdk()
        mi = _make_model_identifier("ModelA", "sol-aaa")
        sim_data = _make_sim_data([_make_simulation("sim-001", "Completed", [mi])])

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=sim_data):
            MOD.list_solution_ids(mock_sdk, "exec-xyz")

        mock_sdk.simulation.list_simulations.assert_called_once_with(
            execution_id="exec-xyz",
        )

    def test_raises_if_no_data_returned(self):
        mock_sdk = _make_sdk()
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=None):
            with pytest.raises(RuntimeError, match="No simulations found"):
                MOD.list_solution_ids(mock_sdk, "exec-001")

    def test_raises_if_simulation_records_is_none(self):
        mock_sdk = _make_sdk()
        data = MagicMock()
        data.SimulationRecords = None
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=data):
            with pytest.raises(RuntimeError, match="No simulations found"):
                MOD.list_solution_ids(mock_sdk, "exec-001")

    def test_raises_if_simulation_records_is_empty(self):
        mock_sdk = _make_sdk()
        data = MagicMock()
        data.SimulationRecords = []
        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=data):
            with pytest.raises(RuntimeError, match="No simulations found"):
                MOD.list_solution_ids(mock_sdk, "exec-001")

    def test_skips_simulations_without_model_identifiers(self):
        mock_sdk = _make_sdk()
        sim_no_ids = _make_simulation("sim-001", "Failed", model_identifiers=None)
        sim_with_ids = _make_simulation("sim-002", "Completed",
                                        [_make_model_identifier("ModelA", "sol-aaa")])
        sim_data = _make_sim_data([sim_no_ids, sim_with_ids])

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=sim_data):
            result = MOD.list_solution_ids(mock_sdk, "exec-001")

        assert result == {"sol-aaa": "ModelA"}

    def test_skips_model_identifier_with_missing_name_or_id(self):
        mock_sdk = _make_sdk()
        mi_bad_name = _make_model_identifier(None, "sol-xxx")
        mi_bad_id = _make_model_identifier("ModelBad", None)
        mi_ok = _make_model_identifier("ModelOK", "sol-ok")
        sim = _make_simulation("sim-001", "Completed", [mi_bad_name, mi_bad_id, mi_ok])
        sim_data = _make_sim_data([sim])

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=sim_data):
            result = MOD.list_solution_ids(mock_sdk, "exec-001")

        assert result == {"sol-ok": "ModelOK"}


# ── download_solution ─────────────────────────────────────────────────────────

class TestDownloadSolution:

    def test_returns_true_when_download_successful(self, tmp_path):
        """Success = IsDownloadSuccessful is True in SDK response."""
        mock_sdk = _make_sdk()
        sol_dir = tmp_path / "sol-abc"
        dl_data = MagicMock()
        dl_data.IsDownloadSuccessful = True
        dl_data.files = ["result.zip"]

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=dl_data):
            result = MOD.download_solution(mock_sdk, "sol-abc", sol_dir)

        assert result is True

    def test_returns_false_when_data_is_none(self, tmp_path):
        """Failure = SDKBase.get_response_data returns None."""
        mock_sdk = _make_sdk()
        mock_sdk.solution.download_solution.return_value = []

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=None):
            result = MOD.download_solution(mock_sdk, "sol-bad", tmp_path / "sol-bad")

        assert result is False

    def test_returns_false_when_is_download_unsuccessful(self, tmp_path):
        """Failure = IsDownloadSuccessful is False."""
        mock_sdk = _make_sdk()
        dl_data = MagicMock()
        dl_data.IsDownloadSuccessful = False

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=dl_data):
            result = MOD.download_solution(mock_sdk, "sol-bad", tmp_path / "sol-bad")

        assert result is False

    def test_creates_output_directory(self, tmp_path):
        nested = tmp_path / "new_dir" / "sol-abc"
        assert not nested.exists()
        mock_sdk = _make_sdk()
        dl_data = MagicMock()
        dl_data.IsDownloadSuccessful = True
        dl_data.files = []

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=dl_data):
            MOD.download_solution(mock_sdk, "sol-abc", nested)

        assert nested.exists()

    def test_uses_correct_sdk_param_names(self, tmp_path):
        """Verify solution_id, output_directory, solution_type are passed correctly."""
        mock_sdk = _make_sdk()
        sol_dir = tmp_path / "sol-abc"
        dl_data = MagicMock()
        dl_data.IsDownloadSuccessful = True
        dl_data.files = []

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=dl_data):
            MOD.download_solution(
                mock_sdk,
                solution_id="sol-abc",
                output_directory=sol_dir,
                solution_type="Raw",
            )

        mock_sdk.solution.download_solution.assert_called_once_with(
            solution_id="sol-abc",
            output_directory=str(sol_dir),
            solution_type="Raw",
        )


# ── download_all ──────────────────────────────────────────────────────────────

class TestDownloadAll:

    def test_returns_true_when_all_succeed(self, tmp_path):
        mock_sdk = _make_sdk()
        mi1 = _make_model_identifier("ModelA", "sol-aaa")
        mi2 = _make_model_identifier("ModelB", "sol-bbb")
        sim = _make_simulation("sim-001", "Completed", [mi1, mi2])
        sim_data = _make_sim_data([sim])

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=sim_data):
            with patch(f"{_MOD_NAME}.download_solution", return_value=True):
                result = MOD.download_all(mock_sdk, "exec-001", tmp_path)

        assert result is True

    def test_returns_false_when_any_download_fails(self, tmp_path):
        mock_sdk = _make_sdk()
        mi1 = _make_model_identifier("ModelA", "sol-aaa")
        mi2 = _make_model_identifier("ModelB", "sol-bbb")
        sim = _make_simulation("sim-001", "Completed", [mi1, mi2])
        sim_data = _make_sim_data([sim])

        call_count = [0]

        def _dl_side_effect(**kwargs):
            call_count[0] += 1
            return call_count[0] == 1  # first succeeds, second fails

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=sim_data):
            with patch(f"{_MOD_NAME}.download_solution", side_effect=_dl_side_effect):
                result = MOD.download_all(mock_sdk, "exec-001", tmp_path)

        assert result is False

    def test_returns_false_when_no_solution_ids(self, tmp_path):
        mock_sdk = _make_sdk()
        sim = _make_simulation("sim-001", "Running", model_identifiers=None)
        sim_data = _make_sim_data([sim])

        with patch(f"{_MOD_NAME}.SDKBase.get_response_data", return_value=sim_data):
            result = MOD.download_all(mock_sdk, "exec-001", tmp_path)

        assert result is False


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:

    def test_exit_0_on_all_solutions_downloaded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "download_solutions.py",
            "--cli-path", "/path/to/cli",
            "--environment", "preprod",
            "--execution-id", "exec-001",
            "--output-dir", str(tmp_path),
        ])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.authenticate"):
                with patch(f"{_MOD_NAME}.download_all", return_value=True):
                    exit_code = MOD.main()

        assert exit_code == 0

    def test_exit_1_when_download_all_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "download_solutions.py",
            "--cli-path", "/path/to/cli",
            "--environment", "preprod",
            "--execution-id", "exec-001",
            "--output-dir", str(tmp_path),
        ])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.authenticate"):
                with patch(f"{_MOD_NAME}.download_all", return_value=False):
                    exit_code = MOD.main()

        assert exit_code == 1

    def test_exit_1_on_exception(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "download_solutions.py",
            "--cli-path", "/path/to/cli",
            "--environment", "preprod",
            "--execution-id", "exec-001",
            "--output-dir", str(tmp_path),
        ])

        with patch(f"{_MOD_NAME}.CloudSDK"):
            with patch(f"{_MOD_NAME}.authenticate", side_effect=RuntimeError("boom")):
                exit_code = MOD.main()

        assert exit_code == 1

    def test_passes_correct_args_to_sdk_and_functions(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "download_solutions.py",
            "--cli-path", "/my/cli",
            "--environment", "prod",
            "--execution-id", "exec-xyz",
            "--output-dir", str(tmp_path),
            "--solution-type", "Standard",
        ])

        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.authenticate") as mock_auth:
                with patch(f"{_MOD_NAME}.download_all", return_value=True) as mock_dl:
                    MOD.main()

        MockSDK.assert_called_once_with(cli_path="/my/cli")
        mock_auth.assert_called_once_with(
            MockSDK.return_value,
            "prod",
            client_id=None,
            client_secret=None,
            tenant_id=None,
        )
        mock_dl.assert_called_once_with(
            sdk=MockSDK.return_value,
            execution_id="exec-xyz",
            output_dir=tmp_path,
            solution_type="Standard",
        )

    def test_passes_client_credentials_args_to_authenticate(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "download_solutions.py",
            "--cli-path", "/my/cli",
            "--environment", "prod",
            "--execution-id", "exec-xyz",
            "--output-dir", str(tmp_path),
            "--client-id", "my-client-id",
            "--client-secret", "my-secret",
            "--tenant-id", "my-tenant",
        ])

        with patch(f"{_MOD_NAME}.CloudSDK") as MockSDK:
            with patch(f"{_MOD_NAME}.authenticate") as mock_auth:
                with patch(f"{_MOD_NAME}.download_all", return_value=True):
                    MOD.main()

        mock_auth.assert_called_once_with(
            MockSDK.return_value,
            "prod",
            client_id="my-client-id",
            client_secret="my-secret",
            tenant_id="my-tenant",
        )

