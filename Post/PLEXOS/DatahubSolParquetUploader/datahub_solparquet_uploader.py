"""
Upload solution parquet files for a model to DataHub.

Post-simulation script — upload only. Solution files are expected to already be in parquet format.

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
from datetime import datetime
from urllib.parse import unquote
from eecloud.cloudsdk import CloudSDK, SDKBase


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


# Required env vars — fail fast with a clear message
try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("Error: Missing required environment variable: cloud_cli_path")
    sys.exit(1)

# Optional env vars — use sensible defaults
DIRECTORY_MAP_PATH = os.environ.get("directory_map_path", "")


class ModelData:
    """Holds the model ID and local parquet path resolved from the directory mapping."""

    def __init__(self, model_id: str, parquet_path: str):
        self.id = model_id
        self.parquet_path = parquet_path


class DatahubSolParquetUploader:
    """Uploads solution parquet files for a model to DataHub."""

    def __init__(self, cli_path: str):
        """
        Args:
            cli_path: Path to the Cloud CLI executable (from env).
        """
        self.sdk = CloudSDK(cli_path=cli_path)

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
                if not model_id:
                    raise ValueError(
                        "Mapping entry with 'ParquetPath' is missing a non-empty 'Id' field. "
                        "'Id' is required to build the remote upload path."
                    )
                return ModelData(
                    model_id=model_id,
                    parquet_path=_decode_path(item["ParquetPath"]),
                )

        raise ValueError("No entry with 'ParquetPath' found in the mapping file.")

    def upload(self, remote_base: str) -> bool:
        """
        Resolves the mapping file, reads model data, and uploads parquet files.

        Args:
            remote_base: Base remote folder path in DataHub.
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

        upload_response = self.sdk.datahub.upload(
            local_folder=map_data.parquet_path,
            remote_folder=remote_path,
            glob_patterns=["**/*.parquet"],
            is_versioned=True,
            print_message=False,
        )

        upload_data = SDKBase.get_response_data(upload_response)

        if upload_data is None:
            print("[FAIL] Upload returned no data.")
            return False

        successful, skipped, failed = [], [], []

        for result in upload_data.DatahubResourceResults:
            if result.Success:
                successful.append(result.RelativeFilePath)
            elif result.FailureReason and "identical to the remote file" in result.FailureReason:
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload solution parquet files to DataHub using the directory mapping."
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
    args = parser.parse_args()
    remote_path = _decode_path(args.remote_path)

    try:
        uploader = DatahubSolParquetUploader(cli_path=CLOUD_CLI_PATH)
        success = uploader.upload(remote_base=remote_path)
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