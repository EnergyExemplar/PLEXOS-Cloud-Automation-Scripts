"""
Download files or folders from DataHub to a local directory.

Focused script — download only. No conversion or analysis.
Chain with convert_parquet_to_csv.py if the downloaded files need converting.

Environment variables used:
    cloud_cli_path  – required; path to the PLEXOS Cloud CLI executable
    output_path     – default local destination when -l is not provided
    simulation_path – resolved when -l simulation_path is passed

Passing paths that contain spaces
----------------------------------
The cloud task runner splits the Arguments field on whitespace before passing tokens
to Python, so quoting in Arguments (' or ") is NOT reliable for paths with spaces.

Safe approach — URL-encode spaces in the Arguments field:
    -r Kavitha/Study3/TSComparison/Gas%20Demand%20Forecast%20NRT%205min.csv
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

OUTPUT_PATH     = os.environ.get("output_path",     "/output")
SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def download_files(remote_paths: list, local_folder: str) -> bool:
    """
    Download one or more DataHub paths to local_folder.

    Args:
        remote_paths:  List of DataHub paths to download (files or folder globs).
        local_folder:  Local destination directory.

    Returns:
        True if all downloads succeeded, False otherwise.
    """
    try:
        pxc = CloudSDK(cli_path=CLOUD_CLI_PATH)
        Path(local_folder).mkdir(parents=True, exist_ok=True)

        print(f"\n--- Downloading from DataHub ---")
        print(f"Local folder  : {local_folder}")
        print(f"Remote path(s): {remote_paths}")

        successful = []
        failed     = []

        for remote_path in remote_paths:
            response = pxc.datahub.download(
                remote_glob_patterns=[remote_path],
                output_directory=local_folder,
                print_message=False,
            )
            data = SDKBase.get_response_data(response)

            if data is None:
                print(f"[FAIL] No response data for: {remote_path}")
                failed.append((remote_path, "no response data"))
                continue

            if hasattr(data, "DatahubResourceResults"):
                for result in data.DatahubResourceResults:
                    if result.Success:
                        print(f"[OK] {result.RelativeFilePath} → {result.LocalFilePath}")
                        successful.append(result.RelativeFilePath)
                    else:
                        reason = result.FailureReason or "unknown"
                        failed.append((result.RelativeFilePath, reason))

        print(f"\n--- Download Summary ---")
        print(f"Downloaded : {len(successful)} file(s)")
        if failed:
            print(f"Failed     : {len(failed)} file(s)")
            for path, reason in failed:
                print(f"  {path}: {reason}")
            return False

        if not successful:
            print("[WARN] No files were downloaded")
            return False

        print(f"[OK] Download complete → {local_folder}")
        return True

    except Exception as e:
        print(f"Download error: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download files from DataHub to a local folder.",
        epilog=(
            "Paths with spaces — URL-encode them in the Arguments field:\n"
            "    -r Kavitha/Study3/TSComparison/Gas%%20Demand%%20Forecast.csv\n\n"
            "Chain example — download Parquet inputs then convert to CSV:\n"
            "    python3 download_from_datahub.py -r Project/Study/inputs/** -l simulation_path\n"
            "    python3 convert_parquet_to_csv.py -d simulation_path"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-r", "--remote-path",
        dest="remote_paths",
        action="append",
        default=None,
        metavar="DATAHUB_PATH",
        help=(
            "DataHub path to download (file path or glob). "
            "Repeat for multiple paths. URL-encode spaces as %%20 when the path "
            "contains spaces."
        ),
    )
    parser.add_argument(
        "-l", "--local-folder",
        default=None,
        help=(
            "Local destination folder. "
            "Pass 'simulation_path' to use the SIMULATION_PATH env var. "
            "Defaults to output_path env var when omitted."
        ),
    )
    args = parser.parse_args()

    # ── Resolve remote paths ──────────────────────────────────────────────────
    if args.remote_paths:
        remote_paths = [_decode_path(p) for p in args.remote_paths]
    else:
        print("Error: No remote paths supplied. Use -r to specify one or more DataHub paths.")
        return 1

    # ── Resolve local folder ──────────────────────────────────────────────────
    # Priority: -l CLI flag  →  output_path env var
    raw_local = args.local_folder
    if raw_local is not None and _decode_path(raw_local) == "simulation_path":
        local_folder = SIMULATION_PATH
    elif raw_local is not None and _decode_path(raw_local) != "output_path":
        local_folder = _decode_path(raw_local)
    else:
        local_folder = OUTPUT_PATH

    start   = time.time()
    success = download_files(remote_paths, local_folder)
    print(f"\nTotal time: {time.time() - start:.2f}s")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
