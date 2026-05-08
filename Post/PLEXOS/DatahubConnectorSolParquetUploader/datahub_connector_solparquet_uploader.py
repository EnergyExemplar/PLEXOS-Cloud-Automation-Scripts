"""
Create a temporary DataHub connector, upload solution parquet files, then delete the connector.

Post-simulation script — connector lifecycle plus upload. Solution files are expected to
already be in parquet format.

Reads the local parquet path and model ID from a directory mapping JSON,
then uploads all matching *.parquet files to a timestamped path in DataHub.

Environment variables used:
    cloud_cli_path     – required; path to the Cloud CLI executable
    directory_map_path – optional; path to directory mapping JSON
                         (falls back to /simulation/splits/directorymapping.json)
"""
import os
import sys
import json
import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from eecloud.cloudsdk import CloudSDK, SDKBase


# Required env vars — fail fast with a clear message
try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("[FAIL] Missing required environment variable: cloud_cli_path")
    sys.exit(1)

# Optional env vars — use sensible defaults
DIRECTORY_MAP_PATH = os.environ.get("directory_map_path", "")


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def _resolve_required_env_value(secret_name: str | None, flag_name: str) -> tuple[str | None, str | None]:
    """Resolve required secret value from environment variable name (now called secret name)."""
    if not secret_name:
        return None, f"Missing required argument: {flag_name}"

    resolved = os.getenv(secret_name)
    if resolved is None or resolved == "":
        return None, (
            f"Environment variable '{secret_name}' (provided via {flag_name}) is not set or empty."
        )

    return resolved, None


class ModelData:
    """Holds the model ID and local parquet path resolved from the directory mapping."""

    def __init__(self, model_id: str, parquet_path: str):
        self.id = model_id
        self.parquet_path = parquet_path


@dataclass
class ConnectorRequest:
    """Connector creation settings for AzureBlob and AmazonS3 connectors."""

    name: str
    connector_type: str
    auth_type: str
    service_uri: str | None = None
    connection_string: str | None = None
    account_name: str | None = None
    account_key: str | None = None
    sas_token: str | None = None
    container_name: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    region: str | None = None
    bucket_name: str | None = None
    session_token: str | None = None
    role_arn: str | None = None
    session_name: str | None = None
    service_endpoint_url: str | None = None


class DatahubConnectorManager:
    """Creates and deletes a DataHub connector for the upload lifecycle."""

    def __init__(self, sdk):
        self.sdk = sdk

    @staticmethod
    def _extract_response_message(response) -> str:
        """Best-effort extraction of SDK command response message(s)."""
        if response is None:
            return ""

        if isinstance(response, list):
            messages = [str(getattr(item, "Message", "")) for item in response if getattr(item, "Message", None)]
            return " | ".join(messages)

        msg = getattr(response, "Message", None)
        return str(msg) if msg else ""

    def _build_connector_kwargs(self, request: ConnectorRequest) -> dict[str, str | None]:
        """Build create_connector kwargs using values directly (no secret extraction)."""
        return {
            "name": request.name,
            "connector_type": request.connector_type,
            "auth_type": request.auth_type,
            "service_uri": request.service_uri,
            "connection_string": request.connection_string,
            "account_name": request.account_name,
            "account_key": request.account_key,
            "sas_token": request.sas_token,
            "container_name": request.container_name,
            "s3_access_key": request.s3_access_key,
            "s3_secret_key": request.s3_secret_key,
            "region": request.region,
            "bucket_name": request.bucket_name,
            "session_token": request.session_token,
            "role_arn": request.role_arn,
            "session_name": request.session_name,
            "service_endpoint_url": request.service_endpoint_url,
            "print_message": False,
        }

    def create_connector(self, request: ConnectorRequest) -> bool:
        """Create connector and return True only on success."""
        response = self.sdk.datahub.create_connector(**self._build_connector_kwargs(request))
        data = SDKBase.get_response_data(response)
        if data is None:
            print(f"[FAIL] Failed to create connector '{request.name}'.")
            message = self._extract_response_message(response)
            if message:
                print(f"[FAIL] Connector create response message: {message}")
            else:
                print(f"[FAIL] Connector create raw response: {response}")
            return False

        success = getattr(data, "success", None)
        if success is not True:
            if success is None:
                print(f"[FAIL] Connector create returned inconclusive status (success=None) for '{request.name}'.")
            else:
                print(f"[FAIL] Connector create returned unsuccessful status for '{request.name}'.")
            message = self._extract_response_message(response)
            if message:
                print(f"[FAIL] Connector create response message: {message}")
            data_message = getattr(data, "Message", None)
            data_error = getattr(data, "ErrorMessage", None) or getattr(data, "FailureReason", None)
            if data_message:
                print(f"[FAIL] Connector create data message: {data_message}")
            if data_error:
                print(f"[FAIL] Connector create data error: {data_error}")
            return False

        print(f"[OK] Connector created: {request.name}")
        return True

    def delete_connector(self, connector_name: str) -> bool:
        """Delete connector and return True only on success."""
        response = self.sdk.datahub.delete_connector(name=connector_name, print_message=False)
        data = SDKBase.get_response_data(response)
        if data is None:
            print(f"[FAIL] Failed to delete connector '{connector_name}'.")
            return False

        success = getattr(data, "success", None)
        if success is not True:
            if success is None:
                print(
                    f"[FAIL] Connector delete returned inconclusive status (success=None) for '{connector_name}'."
                )
            else:
                print(f"[FAIL] Connector delete returned unsuccessful status for '{connector_name}'.")
            return False

        print(f"[OK] Connector deleted: {connector_name}")
        return True


class DatahubSolParquetUploader:
    """Uploads solution parquet files for a model to DataHub."""

    def __init__(self, cli_path: str):
        """
        Args:
            cli_path: Path to the Cloud CLI executable (from env).
        """
        self.sdk = CloudSDK(cli_path=cli_path)
        self.connector_manager = DatahubConnectorManager(self.sdk)

    def _resolve_mapping_file(self, env_path: str) -> str:
        """
        Resolves the directory mapping JSON file path.

        Uses env_path if set and the file exists, then falls back to the
        platform split path (/simulation/splits/directorymapping.json).

        Args:
            env_path: Value of the directory_map_path env var (may be empty).

        Returns:
            Resolved path to an existing mapping file.

        Raises:
            FileNotFoundError: If neither path exists.
        """
        split_mapping_path = "/simulation/splits/directorymapping.json"
        if env_path and os.path.exists(env_path):
            return env_path
        if os.path.exists(split_mapping_path):
            return split_mapping_path
        raise FileNotFoundError(
            f"Mapping file not found. Checked: "
            f"{env_path or '[directory_map_path not set]'} and {split_mapping_path}"
        )

    def _read_mapping(self, mapping_file_path: str) -> ModelData:
        """
        Reads the first entry with a ParquetPath from the directory mapping JSON.

        Args:
            mapping_file_path: Path to the JSON mapping file.

        Returns:
            ModelData with model ID and local parquet path.

        Raises:
            FileNotFoundError: If the mapping file does not exist.
            ValueError: If the JSON is empty, malformed, or contains no ParquetPath entry.
        """
        with open(mapping_file_path, "r") as f:
            data = json.load(f)

        if not data:
            raise ValueError("Mapping JSON is empty or not properly formatted.")

        for item in data:
            if "ParquetPath" in item:
                model_id = item.get("Id", "").strip()
                parquet_path = _decode_path(str(item.get("ParquetPath", "")).strip())
                if not model_id:
                    raise ValueError(
                        "Mapping entry with 'ParquetPath' is missing a non-empty 'Id' field. "
                        "'Id' is required to build the remote upload path."
                    )
                if not parquet_path:
                    raise ValueError("Mapping entry has empty 'ParquetPath' field.")
                return ModelData(
                    model_id=model_id,
                    parquet_path=parquet_path,
                )

        raise ValueError("No entry with 'ParquetPath' found in the mapping file.")

    def _discover_local_parquet_files(self, parquet_path: str) -> list[str]:
        """Return local parquet files found under parquet_path (case-insensitive extension)."""
        root = Path(parquet_path)
        if not root.is_dir():
            return []

        return [
            str(path)
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() == ".parquet"
        ]

    def _upload_solution(self, remote_base: str) -> bool:
        """
        Resolves the mapping file, reads model data, and uploads parquet files.

        Args:
            remote_base: Base remote folder path in DataHub.
                         May include connector prefix if connector was created.
                         Model ID and timestamp are appended automatically.

        Returns:
            True if all files uploaded successfully (or already identical), False otherwise.
        """
        mapping_path = self._resolve_mapping_file(DIRECTORY_MAP_PATH)
        print(f"[OK] Using mapping file: {mapping_path}")

        map_data = self._read_mapping(mapping_path)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_path = f"{remote_base}/{map_data.id}/Solution_{ts}"

        print(f"\n[OK] Uploading solution '{map_data.id}'")
        print(f"     Local  : {map_data.parquet_path}")
        print(f"     Remote : {remote_path}")

        local_parquet_files = self._discover_local_parquet_files(map_data.parquet_path)
        if not local_parquet_files:
            print(f"[FAIL] No local parquet files found under: {map_data.parquet_path}")
            local_root = Path(map_data.parquet_path.strip())
            print(f"[WARN] Local path exists: {local_root.exists()}, is_dir: {local_root.is_dir()}")
            if local_root.exists() and local_root.is_dir():
                top_entries = sorted([entry.name for entry in local_root.iterdir()])
                preview = top_entries[:10]
                if preview:
                    print(f"[WARN] Top entries under local path (up to 10): {preview}")
                else:
                    print("[WARN] Local path is an empty directory.")
            return False
        print(f"[OK] Local parquet files discovered: {len(local_parquet_files)}")

        upload_response = self.sdk.datahub.upload(
            local_folder=map_data.parquet_path,
            remote_folder=remote_path,
            glob_patterns=["**/*.parquet"],
            is_versioned=False,
            print_message=False,
        )

        upload_data = SDKBase.get_response_data(upload_response)

        if upload_data is None:
            print("[FAIL] Upload returned no data.")
            return False

        if upload_data.DatahubResourceResults is None:
            print("[FAIL] Upload returned no file-level results (DatahubResourceResults is None).")
            return False

        if len(upload_data.DatahubResourceResults) == 0:
            print("[FAIL] Upload returned zero file-level results.")
            return False

        successful, skipped, failed = [], [], []

        for result in upload_data.DatahubResourceResults:
            if result.Success:
                successful.append(result.RelativeFilePath)
            elif result.FailureReason and "identical to the remote file" in result.FailureReason.lower():
                skipped.append(result.RelativeFilePath)
            else:
                failed.append((result.RelativeFilePath, result.FailureReason or "Unknown error"))

        print(f"\n--- Upload Summary ---")
        print(f"Uploaded : {len(successful)} file(s)")
        if skipped:
            print(f"Skipped (identical) : {len(skipped)} file(s)")
        if failed:
            print(f"[FAIL] {len(failed)} file(s) failed:")
            for filepath, reason in failed:
                print(f"  {filepath}: {reason}")
            return False

        print(f"[OK] All files uploaded successfully to: {remote_path}")
        return True

    def upload(self, remote_base: str, connector_request: ConnectorRequest) -> bool:
        """Create connector, upload, then delete connector."""
        created_connector = False

        try:
            print(f"[OK] Step  Creating connector '{connector_request.name}'")
            created_connector = self.connector_manager.create_connector(connector_request)
            if not created_connector:
                return False
            # Prepend connector type and name to the remote path
            remote_base = f"connectors/{connector_request.connector_type}/{connector_request.name}/{remote_base}"

            return self._upload_solution(remote_base=remote_base)
        finally:
            if created_connector:
                print(f"[OK] Step  Deleting connector '{connector_request.name}'")
                self.connector_manager.delete_connector(connector_request.name)


CONNECTOR_AUTH_REQUIRED_ARGS: dict[tuple[str, str], list[str]] = {
    ("AzureBlob", "ConnectionString"): ["connection_string_secret_name", "container_name"],
    ("AzureBlob", "Token"): ["sas_token_secret_name", "service_uri", "container_name"],
    ("AzureBlob", "SharedKey"): ["service_uri", "account_name", "account_key_secret_name", "container_name"],
    ("AmazonS3", "AccountCreds"): ["s3_access_key_secret_name", "s3_secret_key_secret_name", "region", "bucket_name"],
    ("AmazonS3", "AssumeRole"): ["s3_access_key_secret_name", "s3_secret_key_secret_name", "role_arn", "session_name", "region", "bucket_name"],
    ("AmazonS3", "SharedKey"): ["s3_access_key_secret_name", "s3_secret_key_secret_name", "session_token_secret_name", "region", "bucket_name"],
}

ARG_FLAG_MAP: dict[str, str] = {
    "service_uri": "--service-uri",
    "connection_string_secret_name": "--secret-name-connection-string",
    "account_name": "--account-name",
    "account_key_secret_name": "--secret-name-account-key",
    "sas_token_secret_name": "--secret-name-sas-token",
    "container_name": "--container-name",
    "s3_access_key_secret_name": "--secret-name-s3-access-key",
    "s3_secret_key_secret_name": "--secret-name-s3-secret-key",
    "region": "--region",
    "bucket_name": "--bucket-name",
    "session_token_secret_name": "--secret-name-session-token",
    "role_arn": "--role-arn",
    "session_name": "--session-name",
}


def _validate_connector_args(args: argparse.Namespace) -> tuple[bool, str | None]:
    """Validate connector/auth combinations and required args for selected auth type."""
    combo = (args.connector_type, args.auth_type)
    if combo not in CONNECTOR_AUTH_REQUIRED_ARGS:
        supported = sorted(
            [f"{conn}:{auth}" for (conn, auth) in CONNECTOR_AUTH_REQUIRED_ARGS.keys()]
        )
        return False, (
            f"Unsupported connector/auth combination: {args.connector_type}/{args.auth_type}. "
            f"Supported combinations: {', '.join(supported)}"
        )

    required_attrs = CONNECTOR_AUTH_REQUIRED_ARGS[combo]
    missing_flags = [ARG_FLAG_MAP[attr] for attr in required_attrs if not getattr(args, attr)]
    if missing_flags:
        return False, (
            f"Missing required arguments for {args.connector_type}/{args.auth_type}: "
            f"{', '.join(missing_flags)}"
        )

    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a DataHub connector, upload solution parquet files, "
            "then delete the connector."
        )
    )
    parser.add_argument(
        "-r", "--remote-path",
        required=True,
        dest="remote_path",
        help=(
            "Base remote folder path in DataHub. "
            "Model ID and a timestamp (YYYYMMDD_HHMMSS) are appended automatically. "
            "Example: FolderName/Solutions"
        ),
    )
    parser.add_argument(
        "--connector-name",
        required=True,
        help="Connector name to create and delete for this run.",
    )
    parser.add_argument(
        "--connector-type",
        required=True,
        choices=["AzureBlob", "AmazonS3"],
        help="Connector type.",
    )
    parser.add_argument(
        "--auth-type",
        required=True,
        choices=["ConnectionString", "Token", "SharedKey", "AccountCreds", "AssumeRole"],
        help="Connector authentication type.",
    )

    # Generic connector parameters for multiple auth methods.
    parser.add_argument("--service-uri")
    parser.add_argument("--account-name")
    parser.add_argument("--container-name")
    parser.add_argument("--region")
    parser.add_argument("--bucket-name")
    parser.add_argument("--role-arn")
    parser.add_argument("--session-name")
    parser.add_argument("--service-endpoint-url")

    # Token and credential inputs must be environment variable names.
    parser.add_argument(
        "--secret-name-connection-string",
        dest="connection_string_secret_name",
    )
    parser.add_argument(
        "--secret-name-account-key",
        dest="account_key_secret_name",
    )
    parser.add_argument(
        "--secret-name-sas-token",
        dest="sas_token_secret_name",
    )
    parser.add_argument(
        "--secret-name-s3-access-key",
        dest="s3_access_key_secret_name",
    )
    parser.add_argument(
        "--secret-name-s3-secret-key",
        dest="s3_secret_key_secret_name",
    )
    parser.add_argument(
        "--secret-name-session-token",
        dest="session_token_secret_name",
    )

    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    print(f"[OK] Args interpreted: {args}\n")
    
    remote_path = _decode_path(args.remote_path)

    is_valid, validation_error = _validate_connector_args(args)
    if not is_valid:
        print(f"[FAIL] {validation_error}")
        return 1

    secret_arg_map: dict[str, str] = {
        "connection_string_secret_name": "--secret-name-connection-string",
        "account_key_secret_name": "--secret-name-account-key",
        "sas_token_secret_name": "--secret-name-sas-token",
        "s3_access_key_secret_name": "--secret-name-s3-access-key",
        "s3_secret_key_secret_name": "--secret-name-s3-secret-key",
        "session_token_secret_name": "--secret-name-session-token",
    }

    resolved_secret_values: dict[str, str | None] = {
        "connection_string": None,
        "account_key": None,
        "sas_token": None,
        "s3_access_key": None,
        "s3_secret_key": None,
        "session_token": None,
    }

    for attr_name, flag_name in secret_arg_map.items():
        secret_name = getattr(args, attr_name)
        if not secret_name:
            continue

        resolved_value, error = _resolve_required_env_value(secret_name, flag_name)
        if error:
            print(f"[FAIL] {error}")
            return 1

        resolved_secret_values[attr_name.replace("_secret_name", "")] = resolved_value

    connector_request = ConnectorRequest(
        name=_decode_path(args.connector_name),
        connector_type=args.connector_type,
        auth_type=args.auth_type,
        service_uri=_decode_path(args.service_uri) if args.service_uri else None,
        connection_string=resolved_secret_values["connection_string"],
        account_name=_decode_path(args.account_name) if args.account_name else None,
        account_key=resolved_secret_values["account_key"],
        sas_token=resolved_secret_values["sas_token"],
        container_name=_decode_path(args.container_name) if args.container_name else None,
        s3_access_key=resolved_secret_values["s3_access_key"],
        s3_secret_key=resolved_secret_values["s3_secret_key"],
        region=_decode_path(args.region) if args.region else None,
        bucket_name=_decode_path(args.bucket_name) if args.bucket_name else None,
        session_token=resolved_secret_values["session_token"],
        role_arn=_decode_path(args.role_arn) if args.role_arn else None,
        session_name=_decode_path(args.session_name) if args.session_name else None,
        service_endpoint_url=_decode_path(args.service_endpoint_url) if args.service_endpoint_url else None,
    )

    try:
        uploader = DatahubSolParquetUploader(cli_path=CLOUD_CLI_PATH)
        success = uploader.upload(remote_base=remote_path, connector_request=connector_request)
        if success:
            print("\n[OK] Upload process completed.")
        else:
            print("\n[FAIL] Upload process completed with errors.")
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
