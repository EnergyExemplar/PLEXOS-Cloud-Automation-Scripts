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


def upload_folder(local_folder: str, remote_path: str, pattern: str = "**/*", is_versioned: bool = True) -> bool:
    """
    Upload files matching a glob pattern from local_folder to DataHub.

    Args:
        local_folder:  Local path to upload from.
        remote_path:   DataHub destination path (e.g. Project/Study/Results).
        pattern:       Glob pattern for files to include (default: all files).
        is_versioned:  Whether to create a new DataHub version on upload.

    Returns:
        True if all files uploaded successfully, False otherwise.
    """
    try:
        pxc = CloudSDK(cli_path=CLOUD_CLI_PATH)

        print(f"\n--- Uploading to DataHub ---")
        print(f"Local folder : {local_folder}")
        print(f"Remote path  : {remote_path}")
        print(f"Pattern      : {pattern}")
        print(f"Versioned    : {is_versioned}")

        upload_response = pxc.datahub.upload(
            local_folder=local_folder,
            remote_folder=remote_path,
            glob_patterns=[pattern],
            is_versioned=is_versioned,
            print_message=False,
        )

        upload_data = SDKBase.get_response_data(upload_response)

        if upload_data is None:
            print("Upload failed: no response data returned")
            return False

        if not hasattr(upload_data, "DatahubResourceResults"):
            print("Upload failed: unexpected response structure")
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

        print(f"\n--- Upload Summary ---")
        print(f"Uploaded : {len(successful)} file(s)")
        if skipped:
            print(f"Skipped (identical) : {len(skipped)} file(s)")
        if failed:
            print(f"Failed   : {len(failed)} file(s)")
            for path, reason in failed:
                print(f"  {path}: {reason}")
            return False

        print(f"[OK] Upload complete → {remote_path}")
        return True

    except Exception as e:
        print(f"Upload error: {e}")
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
            "    python3 upload_to_datahub.py -l output_path -r Project/Analysis/Results --pattern 'Analysis_*/**'"
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
        default="**/*",
        help="Glob pattern for files to upload (default: '**/*' — all files).",
    )
    parser.add_argument(
        "-v", "--versioned",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Create a new DataHub version on upload (default: true).",
    )
    args = parser.parse_args()

    local_folder = OUTPUT_PATH if args.local_folder == "output_path" else args.local_folder
    is_versioned = args.versioned.lower() == "true"

    if not Path(local_folder).exists():
        print(f"Error: Folder '{local_folder}' does not exist")
        return 1

    start   = time.time()
    success = upload_folder(local_folder, args.remote_path, args.pattern, is_versioned)
    print(f"\nTotal time: {time.time() - start:.2f}s")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
