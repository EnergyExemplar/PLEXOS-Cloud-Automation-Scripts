"""
Unit tests for Post/PLEXOS/DatahubConnectorSolParquetUploader/datahub_connector_solparquet_uploader.py.

Covers connector lifecycle, secret extraction path, and main() argument behavior.
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module

MOD = get_module("connector_solparquet_uploader")

class TestDecodePath:
    def test_decode_path_unquotes_and_decodes(self):
        assert MOD._decode_path("'Project/My%20Path'") == "Project/My Path"


class TestReadMapping:
    def test_read_mapping_strips_whitespace_in_parquet_path(self, tmp_path):
        mapping_file = tmp_path / "directorymapping.json"
        mapping_file.write_text(
            '[{"Id": "model-1", "ParquetPath": "  /simulation/Model%20Fixed%20Solution/version2/ParquetUploads  "}]',
            encoding="utf-8",
        )

        with patch("datahub_connector_solparquet_uploader.CloudSDK"):
            uploader = MOD.DatahubSolParquetUploader(cli_path="mock_cli")

        model_data = uploader._read_mapping(str(mapping_file))

        assert model_data.id == "model-1"
        assert model_data.parquet_path == "/simulation/Model Fixed Solution/version2/ParquetUploads"


class TestDatahubConnectorManager:
    # Valid create_connector parameter names from the SDK signature (eecloud v1.5.2621.473).
    # If the SDK changes, update this set to catch contract mismatches in tests below.
    VALID_CREATE_CONNECTOR_PARAMS = frozenset({
        "name", "connector_type", "auth_type", "service_uri", "connection_string",
        "account_name", "account_key", "sas_token", "container_name",
        "s3_access_key", "s3_secret_key", "region", "bucket_name",
        "session_token", "role_arn", "session_name", "service_endpoint_url",
        "repository", "branch", "personal_access_token", "owner", "base_url",
        "organization_url", "project", "tenant_id", "client_id", "client_secret",
        "print_message",
    })

    @pytest.mark.skip(reason="Secret extraction via SDK secrets commands is currently commented out in implementation.")
    def test_extract_secret_value_uses_secrets_commands(self):
        # Placeholder kept intentionally to preserve planned coverage when feature is re-enabled.
        raise NotImplementedError("Enable this test when secret extraction implementation is restored.")

    def test_build_connector_kwargs_only_contains_valid_sdk_params(self):
        """Contract test: every key from _build_connector_kwargs must be a valid
        create_connector parameter. Catches typos or unsupported kwargs before runtime."""
        sdk = MagicMock()
        manager = MOD.DatahubConnectorManager(sdk)
        request = MOD.ConnectorRequest(
            name="contract-test",
            connector_type="AzureBlob",
            auth_type="ServicePrincipal",
            tenant_id="tid",
            client_id="cid",
            client_secret="csec",
            service_uri="https://example.blob.core.windows.net",
            container_name="container",
        )
        kwargs = manager._build_connector_kwargs(request)
        invalid_keys = set(kwargs.keys()) - self.VALID_CREATE_CONNECTOR_PARAMS
        assert not invalid_keys, f"Unexpected kwargs not in SDK signature: {invalid_keys}"

    def test_create_connector_uses_expected_sdk_kwargs_for_azure_connection_string(self):
        sdk = MagicMock()
        manager = MOD.DatahubConnectorManager(sdk)
        request = MOD.ConnectorRequest(
            name="conn-azure",
            connector_type="AzureBlob",
            auth_type="ConnectionString",
            connection_string="UseDevelopmentStorage=true",
            container_name="datahub-connectors",
        )

        sdk.datahub.create_connector = MagicMock(return_value=object())

        with patch.object(MOD.SDKBase, "get_response_data", return_value=SimpleNamespace(success=True)):
            success = manager.create_connector(request)

        assert success is True
        call_kwargs = sdk.datahub.create_connector.call_args.kwargs
        assert call_kwargs["name"] == "conn-azure"
        assert call_kwargs["connector_type"] == "AzureBlob"
        assert call_kwargs["auth_type"] == "ConnectionString"
        assert call_kwargs["connection_string"] == "UseDevelopmentStorage=true"
        assert call_kwargs["container_name"] == "datahub-connectors"
        assert call_kwargs["print_message"] is False
        assert "s3_access_key" not in call_kwargs
        assert "s3_secret_key" not in call_kwargs
        assert "session_token" not in call_kwargs

    def test_create_connector_uses_expected_sdk_kwargs_for_s3_assume_role(self):
        sdk = MagicMock()
        manager = MOD.DatahubConnectorManager(sdk)
        request = MOD.ConnectorRequest(
            name="conn-s3",
            connector_type="AmazonS3",
            auth_type="AssumeRole",
            region="us-east-1",
            bucket_name="bucket-name",
            role_arn="arn:aws:iam::111122223333:role/TestRole",
            session_name="test-session",
        )

        sdk.datahub.create_connector = MagicMock(return_value=object())

        with patch.object(MOD.SDKBase, "get_response_data", return_value=SimpleNamespace(success=True)):
            success = manager.create_connector(request)

        assert success is True
        call_kwargs = sdk.datahub.create_connector.call_args.kwargs
        assert call_kwargs["name"] == "conn-s3"
        assert call_kwargs["connector_type"] == "AmazonS3"
        assert call_kwargs["auth_type"] == "AssumeRole"
        assert call_kwargs["region"] == "us-east-1"
        assert call_kwargs["bucket_name"] == "bucket-name"
        assert call_kwargs["role_arn"] == "arn:aws:iam::111122223333:role/TestRole"
        assert call_kwargs["session_name"] == "test-session"
        assert call_kwargs["print_message"] is False
        assert "connection_string" not in call_kwargs
        assert "account_key" not in call_kwargs
        assert "sas_token" not in call_kwargs

    def test_create_connector_uses_expected_sdk_kwargs_for_azure_service_principal(self):
        sdk = MagicMock()
        manager = MOD.DatahubConnectorManager(sdk)
        request = MOD.ConnectorRequest(
            name="conn-sp",
            connector_type="AzureBlob",
            auth_type="ServicePrincipal",
            tenant_id="00000000-1111-2222-3333-444444444444",
            client_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            client_secret="super-secret-value",
            service_uri="https://myaccount.blob.core.windows.net",
            container_name="my-container",
        )

        sdk.datahub.create_connector = MagicMock(return_value=object())

        with patch.object(MOD.SDKBase, "get_response_data", return_value=SimpleNamespace(success=True)):
            success = manager.create_connector(request)

        assert success is True
        call_kwargs = sdk.datahub.create_connector.call_args.kwargs
        assert call_kwargs["name"] == "conn-sp"
        assert call_kwargs["connector_type"] == "AzureBlob"
        assert call_kwargs["auth_type"] == "ServicePrincipal"
        assert call_kwargs["tenant_id"] == "00000000-1111-2222-3333-444444444444"
        assert call_kwargs["client_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert call_kwargs["client_secret"] == "super-secret-value"
        assert call_kwargs["service_uri"] == "https://myaccount.blob.core.windows.net"
        assert call_kwargs["container_name"] == "my-container"
        assert call_kwargs["print_message"] is False
        assert "connection_string" not in call_kwargs
        assert "s3_access_key" not in call_kwargs

    def test_delete_connector_uses_expected_sdk_kwargs(self):
        sdk = MagicMock()
        manager = MOD.DatahubConnectorManager(sdk)
        sdk.datahub.delete_connector.return_value = object()

        with patch.object(MOD.SDKBase, "get_response_data", return_value=SimpleNamespace(success=True)):
            success = manager.delete_connector("conn-delete")

        assert success is True
        call_kwargs = sdk.datahub.delete_connector.call_args.kwargs
        assert call_kwargs["name"] == "conn-delete"
        assert call_kwargs["print_message"] is False

    def test_create_connector_fails_when_success_is_none(self):
        sdk = MagicMock()
        manager = MOD.DatahubConnectorManager(sdk)
        request = MOD.ConnectorRequest(
            name="conn-ambiguous",
            connector_type="AzureBlob",
            auth_type="ConnectionString",
            connection_string="UseDevelopmentStorage=true",
            container_name="container",
        )

        sdk.datahub.create_connector = MagicMock(return_value=object())

        with patch.object(MOD.SDKBase, "get_response_data", return_value=SimpleNamespace(success=None)):
            success = manager.create_connector(request)

        assert success is False

    def test_delete_connector_fails_when_success_is_none(self):
        sdk = MagicMock()
        manager = MOD.DatahubConnectorManager(sdk)
        sdk.datahub.delete_connector.return_value = object()

        with patch.object(MOD.SDKBase, "get_response_data", return_value=SimpleNamespace(success=None)):
            success = manager.delete_connector("conn-ambiguous")

        assert success is False


class TestUploaderLifecycle:
    def _make_uploader(self):
        with patch("datahub_connector_solparquet_uploader.CloudSDK"):
            return MOD.DatahubSolParquetUploader(cli_path="mock_cli")

    def test_upload_creates_then_deletes_connector_on_success(self):
        uploader = self._make_uploader()
        request = MOD.ConnectorRequest(
            name="conn-1",
            connector_type="AzureBlob",
            auth_type="ConnectionString",
        )

        with patch.object(uploader.connector_manager, "create_connector", return_value=True) as mock_create:
            with patch.object(uploader, "_upload_solution", return_value=True) as mock_upload:
                with patch.object(uploader.connector_manager, "delete_connector", return_value=True) as mock_delete:
                    success = uploader.upload(remote_base="Project/Study", connector_request=request)

        assert success is True
        mock_create.assert_called_once_with(request)
        # Remote path should be prefixed with connector type and name
        mock_upload.assert_called_once_with(remote_base="connectors/AzureBlob/conn-1/Project/Study")
        mock_delete.assert_called_once_with("conn-1")

    def test_upload_deletes_connector_when_upload_fails(self):
        uploader = self._make_uploader()
        request = MOD.ConnectorRequest(
            name="conn-2",
            connector_type="AzureBlob",
            auth_type="ConnectionString",
        )

        with patch.object(uploader.connector_manager, "create_connector", return_value=True):
            with patch.object(uploader, "_upload_solution", return_value=False):
                with patch.object(uploader.connector_manager, "delete_connector", return_value=True) as mock_delete:
                    success = uploader.upload(remote_base="Project/Study", connector_request=request)

        assert success is False
        mock_delete.assert_called_once_with("conn-2")

    def test_upload_solution_fails_when_resource_results_are_missing(self):
        uploader = self._make_uploader()
        map_data = MOD.ModelData(model_id="ModelA", parquet_path="/output")
        upload_data = SimpleNamespace(DatahubResourceResults=None)

        with patch.object(uploader, "_resolve_mapping_file", return_value="/simulation/splits/directorymapping.json"):
            with patch.object(uploader, "_read_mapping", return_value=map_data):
                with patch.object(uploader, "_discover_local_parquet_files", return_value=["/output/a.parquet"]):
                    with patch.object(uploader.sdk.datahub, "upload", return_value=object()):
                        with patch.object(MOD.SDKBase, "get_response_data", return_value=upload_data):
                            success = uploader._upload_solution(remote_base="Project/Study")

        assert success is False

    def test_upload_solution_treats_identical_reason_as_skipped_case_insensitive(self):
        uploader = self._make_uploader()
        map_data = MOD.ModelData(model_id="ModelA", parquet_path="/output")
        upload_data = SimpleNamespace(
            DatahubResourceResults=[
                SimpleNamespace(Success=False, RelativeFilePath="a.parquet", FailureReason="File is identical to the remote file"),
                SimpleNamespace(Success=True, RelativeFilePath="b.parquet", FailureReason=None),
            ]
        )

        with patch.object(uploader, "_resolve_mapping_file", return_value="/simulation/splits/directorymapping.json"):
            with patch.object(uploader, "_read_mapping", return_value=map_data):
                with patch.object(uploader, "_discover_local_parquet_files", return_value=["/output/a.parquet", "/output/b.parquet"]):
                    with patch.object(uploader.sdk.datahub, "upload", return_value=object()):
                        with patch.object(MOD.SDKBase, "get_response_data", return_value=upload_data):
                            success = uploader._upload_solution(remote_base="Project/Study")

        assert success is True

    def test_upload_solution_fails_when_no_local_parquet_files_found(self):
        uploader = self._make_uploader()
        map_data = MOD.ModelData(model_id="ModelA", parquet_path="/output")

        with patch.object(uploader, "_resolve_mapping_file", return_value="/simulation/splits/directorymapping.json"):
            with patch.object(uploader, "_read_mapping", return_value=map_data):
                with patch.object(uploader, "_discover_local_parquet_files", return_value=[]):
                    success = uploader._upload_solution(remote_base="Project/Study")

        assert success is False

    def test_upload_solution_fails_when_resource_results_are_empty(self):
        uploader = self._make_uploader()
        map_data = MOD.ModelData(model_id="ModelA", parquet_path="/output")
        upload_data = SimpleNamespace(DatahubResourceResults=[])

        with patch.object(uploader, "_resolve_mapping_file", return_value="/simulation/splits/directorymapping.json"):
            with patch.object(uploader, "_read_mapping", return_value=map_data):
                with patch.object(uploader, "_discover_local_parquet_files", return_value=["/output/a.parquet"]):
                    with patch.object(uploader.sdk.datahub, "upload", return_value=object()):
                        with patch.object(MOD.SDKBase, "get_response_data", return_value=upload_data):
                            success = uploader._upload_solution(remote_base="Project/Study")

        assert success is False

    def test_upload_solution_uses_correct_upload_kwargs(self):
        uploader = self._make_uploader()
        map_data = MOD.ModelData(model_id="ModelA", parquet_path="/output")
        upload_data = SimpleNamespace(
            DatahubResourceResults=[
                SimpleNamespace(Success=True, RelativeFilePath="a.parquet", FailureReason=None),
            ]
        )

        with patch.object(uploader, "_resolve_mapping_file", return_value="/simulation/splits/directorymapping.json"):
            with patch.object(uploader, "_read_mapping", return_value=map_data):
                with patch.object(uploader, "_discover_local_parquet_files", return_value=["/output/a.parquet"]):
                    with patch.object(uploader.sdk.datahub, "upload", return_value=object()) as mock_upload:
                        with patch.object(MOD.SDKBase, "get_response_data", return_value=upload_data):
                            success = uploader._upload_solution(remote_base="Project/Study")

        assert success is True
        call_kwargs = mock_upload.call_args.kwargs
        assert "local_folder" in call_kwargs, "local_folder param missing"
        assert "remote_folder" in call_kwargs, "remote_folder param missing"
        assert "glob_patterns" in call_kwargs, "glob_patterns param missing"
        assert "print_message" in call_kwargs, "print_message param missing"
        assert call_kwargs["print_message"] is False
        assert call_kwargs["local_folder"] == "/output"
        assert call_kwargs["glob_patterns"] == ["**/*.parquet"]
        assert "Project/Study/ModelA/Solution_" in call_kwargs["remote_folder"]
        assert call_kwargs["is_versioned"] is False


class TestMain:
    def test_main_exits_when_required_connector_args_are_missing(self):
        # --connector-name, --connector-type, --auth-type are required; argparse raises SystemExit(2)
        # when any of them is omitted.
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
        ]
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit) as exc_info:
                MOD.main()
        assert exc_info.value.code == 2

    def test_main_builds_connector_request_and_calls_upload(self):
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-main",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "ConnectionString",
            "--secret-name-connection-string",
            "AZ_BLOB_CONNECTION_STRING",
            "--container-name",
            "output",
        ]

        env = {"AZ_BLOB_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=myaccount;..."}
        with patch.object(MOD, "DatahubSolParquetUploader") as mock_uploader_cls:
            mock_uploader = mock_uploader_cls.return_value
            mock_uploader.upload.return_value = True

            with patch.dict(MOD.os.environ, env, clear=False):
                with patch.object(sys, "argv", argv):
                    rc = MOD.main()

        assert rc == 0
        call_kwargs = mock_uploader.upload.call_args.kwargs
        assert call_kwargs["remote_base"] == "Project/Study"
        request = call_kwargs["connector_request"]
        assert request.name == "conn-main"
        assert request.connector_type == "AzureBlob"
        assert request.auth_type == "ConnectionString"
        assert request.connection_string == "DefaultEndpointsProtocol=https;AccountName=myaccount;..."
        assert request.container_name == "output"

    def test_main_fails_when_required_variable_name_not_set_in_env(self):
        missing_var_name = "AZ_BLOB_CONNECTION_STRING_MISSING_FOR_TEST"
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-main",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "ConnectionString",
            "--secret-name-connection-string",
            missing_var_name,
            "--container-name",
            "output",
        ]

        with patch.dict(MOD.os.environ, {}, clear=False):
            with patch.object(sys, "argv", argv):
                rc = MOD.main()

        assert rc == 1

    def test_main_fails_when_optional_variable_name_is_passed_but_missing_in_env(self):
        missing_var_name = "S3_ACCESS_KEY_MISSING_FOR_TEST"
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-assume-role",
            "--connector-type",
            "AmazonS3",
            "--auth-type",
            "AssumeRole",
            "--role-arn",
            "arn:aws:iam::111122223333:role/TestRole",
            "--session-name",
            "test-session",
            "--region",
            "us-east-1",
            "--bucket-name",
            "bucket-name",
            "--secret-name-s3-access-key",
            missing_var_name,
        ]

        with patch.dict(MOD.os.environ, {}, clear=False):
            with patch.object(sys, "argv", argv):
                rc = MOD.main()

        assert rc == 1

    def test_main_fails_when_variable_name_resolves_to_empty_env_value(self):
        env_var_name = "AZ_BLOB_CONNECTION_STRING_EMPTY_FOR_TEST"
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-main",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "ConnectionString",
            "--secret-name-connection-string",
            env_var_name,
            "--container-name",
            "output",
        ]

        with patch.dict(MOD.os.environ, {env_var_name: ""}, clear=False):
            with patch.object(sys, "argv", argv):
                rc = MOD.main()

        assert rc == 1

    def test_main_builds_connector_request_for_service_principal(self):
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-sp",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "ServicePrincipal",
            "--tenant-id",
            "00000000-1111-2222-3333-444444444444",
            "--client-id",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--secret-name-client-secret",
            "AZ_CLIENT_SECRET",
            "--service-uri",
            "https://myaccount.blob.core.windows.net",
            "--container-name",
            "my-container",
        ]

        env = {
            "AZ_CLIENT_SECRET": "super-secret-value",
        }
        with patch.object(MOD, "DatahubSolParquetUploader") as mock_uploader_cls:
            mock_uploader = mock_uploader_cls.return_value
            mock_uploader.upload.return_value = True

            with patch.dict(MOD.os.environ, env, clear=False):
                with patch.object(sys, "argv", argv):
                    rc = MOD.main()

        assert rc == 0
        call_kwargs = mock_uploader.upload.call_args.kwargs
        assert call_kwargs["remote_base"] == "Project/Study"
        request = call_kwargs["connector_request"]
        assert request.name == "conn-sp"
        assert request.connector_type == "AzureBlob"
        assert request.auth_type == "ServicePrincipal"
        assert request.tenant_id == "00000000-1111-2222-3333-444444444444"
        assert request.client_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert request.client_secret == "super-secret-value"
        assert request.service_uri == "https://myaccount.blob.core.windows.net"
        assert request.container_name == "my-container"

    def test_main_fails_when_tenant_id_missing(self):
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-sp",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "ServicePrincipal",
            # --tenant-id intentionally omitted
            "--client-id",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--secret-name-client-secret",
            "AZ_CLIENT_SECRET",
            "--service-uri",
            "https://myaccount.blob.core.windows.net",
            "--container-name",
            "my-container",
        ]

        env = {"AZ_CLIENT_SECRET": "super-secret-value"}
        with patch.dict(MOD.os.environ, env, clear=False):
            with patch.object(sys, "argv", argv):
                rc = MOD.main()

        assert rc == 1

    def test_main_fails_when_client_id_missing(self):
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-sp",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "ServicePrincipal",
            "--tenant-id",
            "00000000-1111-2222-3333-444444444444",
            # --client-id intentionally omitted
            "--secret-name-client-secret",
            "AZ_CLIENT_SECRET",
            "--service-uri",
            "https://myaccount.blob.core.windows.net",
            "--container-name",
            "my-container",
        ]

        env = {"AZ_CLIENT_SECRET": "super-secret-value"}
        with patch.dict(MOD.os.environ, env, clear=False):
            with patch.object(sys, "argv", argv):
                rc = MOD.main()

        assert rc == 1

    def test_main_fails_when_client_secret_env_var_missing(self):
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-sp",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "ServicePrincipal",
            "--tenant-id",
            "00000000-1111-2222-3333-444444444444",
            "--client-id",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--secret-name-client-secret",
            "AZ_CLIENT_SECRET_MISSING",
            "--service-uri",
            "https://myaccount.blob.core.windows.net",
            "--container-name",
            "my-container",
        ]

        with patch.dict(MOD.os.environ, {}, clear=False):
            with patch.object(sys, "argv", argv):
                rc = MOD.main()

        assert rc == 1

    def test_main_fails_for_unsupported_connector_auth_combo(self):
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-bad",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "AssumeRole",  # AssumeRole is only for AmazonS3, not AzureBlob
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_main_fails_when_required_args_for_auth_are_missing(self):
        argv = [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path",
            "Project/Study",
            "--connector-name",
            "conn-missing",
            "--connector-type",
            "AzureBlob",
            "--auth-type",
            "SharedKey",
            "--service-uri",
            "https://blob.core.windows.net",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1


class TestConnectorAuthValidationMatrix:
    """Validates that _validate_connector_args enforces the full CONNECTOR_AUTH_REQUIRED_ARGS matrix."""

    def _base_argv(self, connector_type: str, auth_type: str) -> list[str]:
        return [
            "datahub_connector_solparquet_uploader.py",
            "--remote-path", "Project/Study",
            "--connector-name", "conn-test",
            "--connector-type", connector_type,
            "--auth-type", auth_type,
        ]

    # --- AmazonS3 / AssumeRole ---

    def test_amazons3_assumerole_passes_with_all_required_args(self):
        argv = self._base_argv("AmazonS3", "AssumeRole") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            "--role-arn", "arn:aws:iam::111122223333:role/TestRole",
            "--session-name", "test-session",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        env = {"S3_ACCESS_KEY": "AKIA...", "S3_SECRET_KEY": "secret..."}
        with patch.object(MOD, "DatahubSolParquetUploader") as mock_cls:
            mock_cls.return_value.upload.return_value = True
            with patch.dict(MOD.os.environ, env, clear=False):
                with patch.object(sys, "argv", argv):
                    rc = MOD.main()
        assert rc == 0

    def test_amazons3_assumerole_fails_when_s3_access_key_secret_missing(self):
        argv = self._base_argv("AmazonS3", "AssumeRole") + [
            # --secret-name-s3-access-key intentionally omitted
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            "--role-arn", "arn:aws:iam::111122223333:role/TestRole",
            "--session-name", "test-session",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_amazons3_assumerole_fails_when_s3_secret_key_secret_missing(self):
        argv = self._base_argv("AmazonS3", "AssumeRole") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            # --secret-name-s3-secret-key intentionally omitted
            "--role-arn", "arn:aws:iam::111122223333:role/TestRole",
            "--session-name", "test-session",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_amazons3_assumerole_fails_when_role_arn_missing(self):
        argv = self._base_argv("AmazonS3", "AssumeRole") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            # --role-arn intentionally omitted
            "--session-name", "test-session",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_amazons3_assumerole_fails_when_session_name_missing(self):
        argv = self._base_argv("AmazonS3", "AssumeRole") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            "--role-arn", "arn:aws:iam::111122223333:role/TestRole",
            # --session-name intentionally omitted
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    # --- AmazonS3 / SharedKey ---

    def test_amazons3_sharedkey_passes_with_all_required_args(self):
        argv = self._base_argv("AmazonS3", "SharedKey") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            "--secret-name-session-token", "S3_SESSION_TOKEN",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        env = {"S3_ACCESS_KEY": "AKIA...", "S3_SECRET_KEY": "secret...", "S3_SESSION_TOKEN": "token..."}
        with patch.object(MOD, "DatahubSolParquetUploader") as mock_cls:
            mock_cls.return_value.upload.return_value = True
            with patch.dict(MOD.os.environ, env, clear=False):
                with patch.object(sys, "argv", argv):
                    rc = MOD.main()
        assert rc == 0

    def test_amazons3_sharedkey_fails_when_s3_access_key_secret_missing(self):
        argv = self._base_argv("AmazonS3", "SharedKey") + [
            # --secret-name-s3-access-key intentionally omitted
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            "--secret-name-session-token", "S3_SESSION_TOKEN",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_amazons3_sharedkey_fails_when_s3_secret_key_secret_missing(self):
        argv = self._base_argv("AmazonS3", "SharedKey") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            # --secret-name-s3-secret-key intentionally omitted
            "--secret-name-session-token", "S3_SESSION_TOKEN",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_amazons3_sharedkey_fails_when_session_token_secret_missing(self):
        argv = self._base_argv("AmazonS3", "SharedKey") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            # --secret-name-session-token intentionally omitted
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    # --- AmazonS3 / AccountCreds ---

    def test_amazons3_accountcreds_fails_when_s3_access_key_secret_missing(self):
        argv = self._base_argv("AmazonS3", "AccountCreds") + [
            # --secret-name-s3-access-key intentionally omitted
            "--secret-name-s3-secret-key", "S3_SECRET_KEY",
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_amazons3_accountcreds_fails_when_s3_secret_key_secret_missing(self):
        argv = self._base_argv("AmazonS3", "AccountCreds") + [
            "--secret-name-s3-access-key", "S3_ACCESS_KEY",
            # --secret-name-s3-secret-key intentionally omitted
            "--region", "us-east-1",
            "--bucket-name", "my-bucket",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    # --- AzureBlob / ServicePrincipal ---

    def test_azureblob_serviceprincipal_passes_with_all_required_args(self):
        argv = self._base_argv("AzureBlob", "ServicePrincipal") + [
            "--tenant-id", "00000000-1111-2222-3333-444444444444",
            "--client-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--secret-name-client-secret", "AZ_CLIENT_SECRET",
            "--service-uri", "https://myaccount.blob.core.windows.net",
            "--container-name", "my-container",
        ]
        env = {"AZ_CLIENT_SECRET": "super-secret-value"}
        with patch.object(MOD, "DatahubSolParquetUploader") as mock_cls:
            mock_cls.return_value.upload.return_value = True
            with patch.dict(MOD.os.environ, env, clear=False):
                with patch.object(sys, "argv", argv):
                    rc = MOD.main()
        assert rc == 0

    def test_azureblob_serviceprincipal_fails_when_tenant_id_missing(self):
        argv = self._base_argv("AzureBlob", "ServicePrincipal") + [
            # --tenant-id intentionally omitted
            "--client-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--secret-name-client-secret", "AZ_CLIENT_SECRET",
            "--service-uri", "https://myaccount.blob.core.windows.net",
            "--container-name", "my-container",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_azureblob_serviceprincipal_fails_when_client_id_missing(self):
        argv = self._base_argv("AzureBlob", "ServicePrincipal") + [
            "--tenant-id", "00000000-1111-2222-3333-444444444444",
            # --client-id intentionally omitted
            "--secret-name-client-secret", "AZ_CLIENT_SECRET",
            "--service-uri", "https://myaccount.blob.core.windows.net",
            "--container-name", "my-container",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_azureblob_serviceprincipal_fails_when_client_secret_secret_missing(self):
        argv = self._base_argv("AzureBlob", "ServicePrincipal") + [
            "--tenant-id", "00000000-1111-2222-3333-444444444444",
            "--client-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            # --secret-name-client-secret intentionally omitted
            "--service-uri", "https://myaccount.blob.core.windows.net",
            "--container-name", "my-container",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_azureblob_serviceprincipal_fails_when_service_uri_missing(self):
        argv = self._base_argv("AzureBlob", "ServicePrincipal") + [
            "--tenant-id", "00000000-1111-2222-3333-444444444444",
            "--client-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--secret-name-client-secret", "AZ_CLIENT_SECRET",
            # --service-uri intentionally omitted
            "--container-name", "my-container",
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

    def test_azureblob_serviceprincipal_fails_when_container_name_missing(self):
        argv = self._base_argv("AzureBlob", "ServicePrincipal") + [
            "--tenant-id", "00000000-1111-2222-3333-444444444444",
            "--client-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--secret-name-client-secret", "AZ_CLIENT_SECRET",
            "--service-uri", "https://myaccount.blob.core.windows.net",
            # --container-name intentionally omitted
        ]
        with patch.object(sys, "argv", argv):
            rc = MOD.main()
        assert rc == 1

