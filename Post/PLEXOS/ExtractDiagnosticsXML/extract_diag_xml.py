"""
Upload diagnostics XML files from the simulation directory to DataHub.

Focused script — upload only. Finds PLEXOS diagnostics XML files produced
during a simulation run and uploads them to a configurable DataHub path.

Chain with other post scripts if you need conversion or cleanup afterward.

Environment variables used:
    cloud_cli_path     – required; path to the Cloud CLI executable
    simulation_path    – root path for study files (read-only in post tasks)
    simulation_id      – platform-provided simulation identifier
    execution_id       – platform-provided execution identifier
    directory_map_path – optional; path to directory mapping JSON
                         (falls back to /simulation/splits/directorymapping.json)
"""
import json
import os
import sys
import argparse
from urllib.parse import unquote
from eecloud.cloudsdk import CloudSDK, SDKBase


# Required env vars — fail fast with a clear message
try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("Error: Missing required environment variable: cloud_cli_path")
    sys.exit(1)

# Optional env vars — use sensible defaults
SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")
SIMULATION_ID = os.environ.get("simulation_id", "")
EXECUTION_ID = os.environ.get("execution_id", "")
DIRECTORY_MAP_PATH = os.environ.get("directory_map_path", "")


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def _resolve_mapping_file(env_path: str) -> str:
    """
    Resolve the directory mapping JSON file path.

    Uses env_path if set and the file exists, then falls back to
    /simulation/splits/directorymapping.json for distributed runs.

    Args:
        env_path: Value of the directory_map_path env var (may be empty).

    Returns:
        Resolved path to an existing mapping file.

    Raises:
        FileNotFoundError: If neither path exists.
    """
    fallback = "/simulation/splits/directorymapping.json"
    if env_path and os.path.exists(env_path):
        return env_path
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError(
        f"Mapping file not found. Checked: "
        f"{env_path or '[directory_map_path not set]'} and {fallback}"
    )


def _get_model_name_from_mapping(env_path: str) -> str:
    """
    Read model name (Name) from directory mapping JSON.

    Resolves the mapping file, then returns the Name of the first entry
    that has a ParquetPath field. This is the human-readable model name
    used in remote paths.

    Args:
        env_path: Value of the directory_map_path env var (may be empty).

    Returns:
        Model name (Name) for path construction.

    Raises:
        FileNotFoundError: If mapping file not found at either path.
        ValueError: If JSON is empty, malformed, or no entry with ParquetPath and Name.
    """
    mapping_path = _resolve_mapping_file(env_path)

    with open(mapping_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) or not data:
        raise ValueError("Mapping JSON must be a non-empty list")

    for item in data:
        if not isinstance(item, dict):
            continue
        if "ParquetPath" not in item:
            continue

        model_name = str(item.get("Name", "")).strip()
        if not model_name:
            raise ValueError(
                "Mapping entry with 'ParquetPath' is missing a non-empty 'Name' field. "
                "'Name' is required for path construction."
            )
        return model_name

    raise ValueError("No entry with 'ParquetPath' found in the directory mapping file.")


def upload_diagnostics(
    remote_base: str,
    model_name: str,
    pattern: str = "**/*Diagnostics.xml",
    is_versioned: bool = False,
) -> bool:
    """
    Upload diagnostics XML files from the simulation directory to DataHub.

    Args:
        remote_base:  Base remote folder in DataHub. Model name, execution ID,
                      and simulation ID are appended automatically.
        model_name:   Name of the split model (used in the remote path).
        pattern:      Glob pattern for diagnostics files to upload.
        is_versioned: Whether to create a new DataHub version on upload.

    Returns:
        True if all files uploaded successfully, False otherwise.
    """
    pxc = CloudSDK(cli_path=CLOUD_CLI_PATH)

    remote_folder = f"{remote_base}/{model_name}/{EXECUTION_ID}/diagnostics/{SIMULATION_ID}"

    print(f"\n--- Uploading Diagnostics ---")
    print(f"Local folder : {SIMULATION_PATH}")
    print(f"Remote path  : {remote_folder}")
    print(f"Pattern      : {pattern}")
    print(f"Versioned    : {is_versioned}")

    upload_response = pxc.datahub.upload(
        local_folder=SIMULATION_PATH,
        remote_folder=remote_folder,
        glob_patterns=[pattern],
        is_versioned=is_versioned,
        print_message=False,
    )

    upload_data = SDKBase.get_response_data(upload_response)

    if upload_data is None:
        print("[FAIL] Upload returned no response data.")
        return False

    if not hasattr(upload_data, "DatahubResourceResults"):
        print("[FAIL] Unexpected response structure.")
        return False

    successful = []
    skipped = []
    failed = []

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

    if not successful and not skipped:
        print("[WARN] No diagnostics files matched the pattern.")
        return True

    print(f"[OK] Diagnostics uploaded to: {remote_folder}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload diagnostics XML files from the simulation directory to DataHub.",
        epilog=(
            "Examples:\n\n"
            "  Upload all diagnostics (model name read from directory mapping):\n"
            "    python3 extract_diag_xml.py -r Project/Study/diagnostics\n\n"
            "  Upload only ST phase diagnostics:\n"
            "    python3 extract_diag_xml.py -r Project/Study/diagnostics "
            "-pt '**/*ST*Diagnostics.xml'\n\n"
            "  Chain — upload diagnostics then upload solution parquets:\n"
            "    python3 extract_diag_xml.py -r Project/Study/diagnostics\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Study/Results"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-r", "--remote-path",
        required=True,
        help=(
            "Base remote folder path in DataHub. "
            "Model name, execution ID, and simulation ID are appended automatically. "
            "Example: Project/Study/diagnostics"
        ),
    )
    parser.add_argument(
        "-pt", "--pattern",
        default="**/*Diagnostics.xml",
        help=(
            "Glob pattern for diagnostics files to upload. "
            "Default: '**/*Diagnostics.xml' (all phase diagnostics). "
            "Use '**/*ST*Diagnostics.xml' for ST phase only."
        ),
    )
    parser.add_argument(
        "-v", "--versioned",
        type=str,
        default="false",
        choices=["true", "false"],
        help="Create a new DataHub version on upload (default: false).",
    )
    args = parser.parse_args()

    remote_path = _decode_path(args.remote_path)
    is_versioned = args.versioned.lower() == "true"

    try:
        model_name = _get_model_name_from_mapping(DIRECTORY_MAP_PATH)
    except (FileNotFoundError, ValueError) as e:
        print(f"[FAIL] {e}")
        return 1

    missing_ids = []
    if not SIMULATION_ID:
        missing_ids.append("simulation_id")
    if not EXECUTION_ID:
        missing_ids.append("execution_id")
    if missing_ids:
        print(
            "[FAIL] Missing required environment variable(s): "
            + ", ".join(missing_ids)
            + ". Cannot construct a safe remote upload path."
        )
        return 1

    try:
        success = upload_diagnostics(
            remote_base=remote_path,
            model_name=model_name,
            pattern=args.pattern,
            is_versioned=is_versioned,
        )
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
