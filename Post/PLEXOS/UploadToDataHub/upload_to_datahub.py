"""
Upload files from a local folder to DataHub.

Focused script — upload only. No conversion or analysis.
Use as the final step in a chain after conversion or analysis scripts.

Environment variables used:
    cloud_cli_path  – required; path to the PLEXOS Cloud CLI executable
    output_path     – resolved when -l output_path is passed
"""
import os
import sys
import argparse
import time
from pathlib import Path
from urllib.parse import unquote
from eecloud.cloudsdk import CloudSDK, SDKBase

try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("Error: Missing required environment variable: cloud_cli_path")
    sys.exit(1)

try:
    OUTPUT_PATH = os.environ["output_path"]
except KeyError:
    print("Error: Missing required environment variable: output_path")
    sys.exit(1)


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def upload_folder(local_folder: str, remote_path: str, patterns: list[str] | None = None, is_versioned: bool = True) -> bool:
    """
    Upload files matching one or more glob patterns from local_folder to DataHub.

    Args:
        local_folder:  Local path to upload from.
        remote_path:   DataHub destination path (e.g. Project/Study/Results).
        patterns:      One or more glob patterns for files to include. Defaults to ['**/*'] (all files).
        is_versioned:  Whether to create a new DataHub version on upload.

    Returns:
        True if all files uploaded successfully, False otherwise.
    """
    try:
        if patterns is None:
            patterns = ["**/*"]

        pxc = CloudSDK(cli_path=CLOUD_CLI_PATH)

        print(f"\n[OK] Starting upload to DataHub...")

        upload_response = pxc.datahub.upload(
            local_folder=local_folder,
            remote_folder=remote_path,
            glob_patterns=patterns,
            is_versioned=is_versioned,
            print_message=False,
        )

        upload_data = SDKBase.get_response_data(upload_response)

        if upload_data is None:
            print("[FAIL] Upload failed: no response data returned")
            return False

        if not hasattr(upload_data, "DatahubResourceResults"):
            print("[FAIL] Upload failed: unexpected response structure")
            return False

        successful = []
        skipped    = []
        failed     = []

        for result in upload_data.DatahubResourceResults:
            if result.Success:
                successful.append(result.RelativeFilePath)
            elif result.FailureReason and "identical to the remote file" in result.FailureReason:
                skipped.append(result.RelativeFilePath)
            else:
                failed.append((result.RelativeFilePath, result.FailureReason or "Unknown error"))

        print(f"\nSummary Upload complete")
        print(f"[OK] Uploaded : {len(successful)} file(s)")
        if skipped:
            print(f"[OK] Skipped (identical) : {len(skipped)} file(s)")
        if failed:
            print(f"[FAIL] Failed : {len(failed)} file(s)")
            for path, reason in failed:
                print(f"        {path}: {reason}")
            return False

        print(f"[OK] Upload complete → {remote_path}")
        return True

    except Exception as e:
        print(f"[FAIL] Upload error: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload files from a local folder to DataHub.",
        epilog=(
            "Chain examples:\n\n"
            "  After CSV → Parquet conversion:\n"
            "    python3 convert_csv_to_parquet.py -r output_path\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Study/Results\n\n"
            "  After time series analysis:\n"
            "    python3 timeseries_comparison.py -f baseline.csv -f result.csv\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Analysis/Results --pattern 'Analysis_*/**'\n\n"
            "  Multiple patterns:\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Study/Results -p 'Analysis_*/**' '*.parquet'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-l", "--local-folder",
        required=True,
        help="Local folder to upload from. Pass 'output_path' to use the output_path env var.",
    )
    parser.add_argument(
        "-r", "--remote-path",
        required=True,
        help="DataHub destination path (e.g. Project/Study/Results).",
    )
    parser.add_argument(
        "-p", "--pattern",
        nargs="+",
        default=["**/*"],
        help="One or more glob patterns, space-separated in a single flag (e.g. -p '*.csv' '*.parquet'). Default: '**/*' — all files.",
    )
    parser.add_argument(
        "-v", "--versioned",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Create a new DataHub version on upload (default: true).",
    )
    args = parser.parse_args()
    print(f"\n[OK] Args Received: python3 {' '.join(sys.argv)}")
    print(f"[OK] Args Interpreted: {args}")

    raw_local    = _decode_path(args.local_folder)
    local_folder = OUTPUT_PATH if raw_local == "output_path" else raw_local
    remote_path  = _decode_path(args.remote_path)
    is_versioned = args.versioned.lower() == "true"

    if not Path(local_folder).exists():
        print(f"[FAIL] Error: Folder '{local_folder}' does not exist")
        return 1

    start   = time.time()
    success = upload_folder(local_folder, remote_path, args.pattern, is_versioned)
    print(f"\n[OK] Total time: {time.time() - start:.2f}s")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
