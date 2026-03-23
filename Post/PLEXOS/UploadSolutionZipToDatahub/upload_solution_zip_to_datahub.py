"""
Upload ZIP solution files for the model resolved from the directory mapping to DataHub.

Post-simulation script — upload only. Reads the model's solution path from the
first entry with a Path field in the directory mapping JSON, then uploads all
matching ZIP files to a remote DataHub path.

Focused script — upload only. No conversion or archiving.

Environment variables used:
    cloud_cli_path     – required; path to the Cloud CLI executable
    execution_id       – required; used to construct the remote destination path
    directory_map_path – path to directory mapping JSON
                         (falls back to /simulation/splits/directorymapping.json)
    simulation_id      – logged for traceability (optional)
"""
import argparse
import json
import os
import sys
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

try:
    EXECUTION_ID = os.environ["execution_id"]
except KeyError:
    print("Error: Missing required environment variable: execution_id")
    sys.exit(1)

# Optional env vars — use sensible defaults
DIRECTORY_MAP_PATH = os.environ.get("directory_map_path", "")
SIMULATION_ID = os.environ.get("simulation_id", "")


class ModelData:
    """Holds model ID and local solution path resolved from the directory mapping."""

    def __init__(self, model_id: str, solution_path: str):
        self.id = model_id
        self.solution_path = solution_path


class ZipSolutionUploader:
    """Uploads ZIP solution files for the model resolved from the directory mapping to DataHub."""

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
        split_default_path = "/simulation/splits/directorymapping.json"
        if env_path and os.path.exists(env_path):
            return env_path
        if os.path.exists(split_default_path):
            return split_default_path
        raise FileNotFoundError(
            f"Mapping file not found. Checked: "
            f"{env_path or '[directory_map_path not set]'} and {split_default_path}"
        )

    def _read_mapping(self, mapping_file_path: str) -> ModelData:
        """
        Reads the first entry with a non-empty Path field from the directory mapping JSON.

        Args:
            mapping_file_path: Path to the JSON mapping file.

        Returns:
            ModelData with model ID and local solution path.

        Raises:
            FileNotFoundError: If the mapping file does not exist.
            ValueError: If the JSON is empty, malformed, no entry has a Path field,
                        or the entry is missing a required field.
        """
        with open(mapping_file_path, "r") as f:
            data = json.load(f)

        if not isinstance(data, list) or not data:
            raise ValueError("Mapping JSON is empty or not properly formatted.")

        for item in data:
            if not isinstance(item, dict):
                raise ValueError(
                    f"Mapping JSON contains a non-object entry: {item!r}"
                )
            if not item.get("Path", "").strip():
                continue
            model_id = item.get("Id", "").strip()
            solution_path = item.get("Path", "").strip()
            if not model_id:
                raise ValueError(
                    "Mapping entry with 'Path' is missing a non-empty 'Id' field."
                )
            return ModelData(
                model_id=model_id,
                solution_path=_decode_path(solution_path),
            )

        raise ValueError("No entry with a non-empty 'Path' field found in the mapping file.")

    def upload(
        self,
        remote_base: str,
        execution_id: str,
        patterns: list[str] | None = None,
    ) -> bool:
        """
        Resolves the model's solution path and uploads ZIP files to DataHub.

        Model name and solution path are read automatically from the first entry
        with a non-empty Path field in the directory mapping JSON.

        The remote destination is constructed as:
            {remote_base}/{execution_id}/{model_id}

        Args:
            remote_base:  Base DataHub destination path.
            execution_id: Platform execution ID appended to the remote path.
            patterns:     Glob patterns for files to upload (default: ["**/*.zip"]).

        Returns:
            True if all files uploaded successfully (or already identical),
            False otherwise.
        """
        if patterns is None:
            patterns = ["**/*.zip"]

        mapping_path = self._resolve_mapping_file(DIRECTORY_MAP_PATH)
        print(f"[OK] Using mapping file: {mapping_path}")

        map_data = self._read_mapping(mapping_path)

        remote_path = f"{remote_base.rstrip('/')}/{execution_id}/{map_data.id}"

        print(f"\n[OK] Uploading ZIP files for model id={map_data.id}")
        print(f"     Local  : {map_data.solution_path}")
        print(f"     Remote : {remote_path}")
        if SIMULATION_ID:
            print(f"     Sim ID : {SIMULATION_ID}")

        upload_response = self.sdk.datahub.upload(
            local_folder=map_data.solution_path,
            remote_folder=remote_path,
            glob_patterns=patterns,
            is_versioned=False,
            print_message=False,
        )

        upload_data = SDKBase.get_response_data(upload_response)

        if upload_data is None:
            print("[FAIL] Upload returned no data.")
            return False

        if not hasattr(upload_data, "DatahubResourceResults"):
            print("[FAIL] Upload failed: unexpected response structure")
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
        print(f"[OK] Uploaded : {len(successful)} file(s)")
        if skipped:
            print(f"[OK] Skipped (identical) : {len(skipped)} file(s)")
        if failed:
            print(f"[FAIL] {len(failed)} file(s) failed:")
            for filepath, reason in failed:
                print(f"  {filepath}: {reason}")
            return False

        print(f"[OK] All files uploaded successfully to: {remote_path}")
        return True


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Upload ZIP solution files for the model resolved from the directory mapping to DataHub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload ZIP files using model resolved from directory mapping
  python3 upload_solution_zip_to_datahub.py --remote-path Eagles/ZipSolutions

  # Upload with a custom glob pattern
  python3 upload_solution_zip_to_datahub.py -r Eagles/ZipSolutions -p "*.zip"
        """
    )
    parser.add_argument(
        "-r", "--remote-path",
        required=True,
        help=(
            "Base remote folder path in DataHub. "
            "Execution ID and model ID are appended automatically: "
            "{remote-path}/{execution_id}/{model_id}."
        ),
    )
    parser.add_argument(
        "-p", "--pattern",
        nargs="+",
        default=["**/*.zip"],
        help=(
            "One or more glob patterns for files to upload "
            "(default: **/*.zip). "
            "Pass multiple values space-separated after a single flag."
        ),
    )

    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    remote_path = _decode_path(args.remote_path)
    print(f"[OK] Args interpreted: remote_path={remote_path!r} pattern={args.pattern}\n")

    try:
        uploader = ZipSolutionUploader(cli_path=CLOUD_CLI_PATH)
        success = uploader.upload(
            remote_base=remote_path,
            execution_id=EXECUTION_ID,
            patterns=args.pattern,
        )
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n[WARN] Operation cancelled by user (exit code 130)")
        return 130
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
