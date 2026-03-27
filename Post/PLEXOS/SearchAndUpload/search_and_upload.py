"""
Find a file by name and move it to output_path. CSV files are converted to Parquet.
Optionally uploads the staged file to DataHub.

Focused script — file discovery, staging, and optional upload.
Searches the given path, or output_path then simulation_path when no path is supplied.
Also searches inside ZIP archives found in each search path.
Files already in output_path are left in place, only the CSV→Parquet conversion is applied.
Files found in simulation_path (read-only mount) are copied rather than moved.

After upload, it is recommended to run a cleanup step (e.g. CleanupFiles) to remove staged files from output_path.

Environment variables used:
    output_path     – required; destination directory for the found file
    simulation_path – optional; fallback search location (falls back to /simulation)
    cloud_cli_path  – required when --upload-path is passed; path to the Cloud CLI executable
"""
import fnmatch
import os
import sys
import shutil
import zipfile
import argparse
import duckdb
from pathlib import Path
from urllib.parse import unquote
from eecloud.cloudsdk import CloudSDK, SDKBase


try:
    OUTPUT_PATH = os.environ["output_path"]
except KeyError:
    print("Error: Missing required environment variable: output_path")
    sys.exit(1)
try:
    SIMULATION_PATH = os.environ["simulation_path"]
except KeyError:
    print("Error: Missing required environment variable: simulation_path")
    sys.exit(1)
try:
    CLOUD_CLI_PATH  = os.environ["cloud_cli_path"]
except KeyError:
    print("Error: Missing required environment variable: cloud_cli_path")
    sys.exit(1)


def _decode_arg(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def find_file(file_name: str, search_paths: list[str]) -> str | None:
    """
    Search for file_name (glob-compatible) in each path (in order).

    Args:
        file_name:    Filename or glob pattern to find (e.g. 'results.csv', '*.csv').
        search_paths: Directories to search, checked left-to-right.

    Returns:
        Absolute path to the first match, or None if not found.
    """
    for path in search_paths:
        p = Path(path)
        if not p.exists():
            continue
        matches = sorted(p.rglob(file_name))
        if matches:
            return str(matches[0])
    return None


def find_in_zips(file_name: str, search_paths: list[str], extract_dir: str) -> str | None:
    """
    Search for file_name inside ZIP archives found in search_paths.

    Scans every *.zip file found (recursively) in each search path in order.
    Extracts the first matching entry to extract_dir, flattening any subdirectory
    inside the ZIP so the file lands directly in extract_dir.

    Args:
        file_name:    Filename or glob pattern to match against ZIP entry basenames.
        search_paths: Directories to scan for ZIP files, checked left-to-right.
        extract_dir:  Directory to extract the matched file into.

    Returns:
        Absolute path to the extracted file, or None if not found.
    """
    for path in search_paths:
        p = Path(path)
        if not p.exists():
            continue
        for zip_path in sorted(p.rglob("*.zip")):
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    for entry in zf.namelist():
                        if not fnmatch.fnmatch(Path(entry).name, file_name):
                            continue
                        # Reject entries that could escape extract_dir (Zip Slip)
                        entry_path = Path(entry)
                        if entry_path.is_absolute() or any(
                            part == ".." for part in entry_path.parts
                        ):
                            print(f"[WARN] Skipping unsafe ZIP entry: {entry}")
                            continue
                        print(f"[OK] Found '{entry}' inside ZIP: {zip_path}")
                        safe_dest = Path(extract_dir) / entry_path.name
                        safe_dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(entry) as src, safe_dest.open("wb") as dst:
                            dst.write(src.read())
                        return str(safe_dest)
            except zipfile.BadZipFile:
                print(f"[WARN] Skipping invalid ZIP file: {zip_path}")
            except Exception as e:
                print(f"[WARN] Could not read ZIP {zip_path}: {e}")
    return None


def convert_csv_to_parquet(csv_path: str) -> tuple[str, bool]:
    """
    Convert a single CSV file to Parquet (ZSTD compression) in the same directory.

    Validates row counts before deleting the source CSV.

    Args:
        csv_path: Absolute path to the source CSV file.

    Returns:
        (parquet_path, success) — parquet_path is empty string on failure.
    """
    conn = None
    try:
        conn = duckdb.connect()
        parquet_path = str(Path(csv_path).with_suffix(".parquet"))
        csv_esc = csv_path.replace("'", "''")
        parquet_esc = parquet_path.replace("'", "''")

        conn.sql(
            f"COPY (SELECT * FROM read_csv_auto('{csv_esc}', sample_size=100000)) "
            f"TO '{parquet_esc}' (FORMAT 'parquet', COMPRESSION 'ZSTD')"
        )

        if not Path(parquet_path).exists():
            print(f"[FAIL] Parquet file was not created: {parquet_path}")
            return "", False

        csv_rows = conn.sql(
            f"SELECT COUNT(*) FROM read_csv_auto('{csv_esc}', sample_size=100000)"
        ).fetchone()[0]
        parquet_rows = conn.sql(f"SELECT COUNT(*) FROM '{parquet_esc}'").fetchone()[0]

        if csv_rows != parquet_rows:
            print(
                f"[WARN] Row count mismatch (CSV={csv_rows:,}, Parquet={parquet_rows:,}) — CSV kept"
            )
            # Delete the Parquet file on mismatch
            try:
                if Path(parquet_path).exists():
                    Path(parquet_path).unlink()
            except Exception as cleanup_err:
                print(f"[WARN] Failed to delete Parquet on mismatch: {cleanup_err}")
            return "", False

        os.remove(csv_path)
        print(
            f"[OK] {Path(csv_path).name} → {Path(parquet_path).name}: {csv_rows:,} rows"
        )
        return parquet_path, True

    except Exception as e:
        print(f"[FAIL] CSV conversion failed: {e}")
        # Delete Parquet file if it was created
        try:
            parquet_path = str(Path(csv_path).with_suffix(".parquet"))
            if Path(parquet_path).exists():
                Path(parquet_path).unlink()
        except Exception as cleanup_err:
            print(f"[WARN] Failed to delete Parquet on exception: {cleanup_err}")
        return "", False
    finally:
        if conn:
            conn.close()


def stage_file(found_path: str, output_path: str, simulation_path: str) -> Path | None:
    """
    Move or copy found_path into output_path.

    Files already in output_path are left in place.
    Files inside simulation_path are copied (read-only mount — cannot be deleted).
    All other files are moved.

    Args:
        found_path:      Absolute path to the discovered file.
        output_path:     Destination directory.
        simulation_path: Read-only simulation directory (files here are copied, not moved).

    Returns:
        Path to the staged file inside output_path, or None on error.
    """
    src = Path(found_path).resolve()
    dst_dir = Path(output_path).resolve()
    dst = dst_dir / src.name

    # Already in output_path — nothing to do
    if src.parent == dst_dir:
        print(f"[OK] File is already in output_path — no move needed")
        return src

    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        sim_root = Path(simulation_path).resolve()
        # Robust check: is src under simulation_path?
        is_in_simulation = False
        try:
            src.relative_to(sim_root)
            is_in_simulation = True
        except ValueError:
            is_in_simulation = False

        if is_in_simulation:
            shutil.copy2(str(src), str(dst))
            print(f"[OK] Copied to output_path (source in simulation_path — original kept): {dst}")
        else:
            shutil.move(str(src), str(dst))
            print(f"[OK] Moved to output_path: {dst}")
        return dst
    except Exception as e:
        print(f"[FAIL] Failed to stage file: {e}")
        return None


def upload_to_datahub(staged_path: Path, remote_path: str, cli_path: str) -> bool:
    """
    Upload a single staged file to DataHub.

    Args:
        staged_path: Local path to the file to upload.
        remote_path: DataHub destination folder path (e.g. Project/Study/Results).
        cli_path:    Path to the Cloud CLI executable.

    Returns:
        True if uploaded (or already identical), False otherwise.
    """
    try:
        pxc = CloudSDK(cli_path=cli_path)
        upload_response = pxc.datahub.upload(
            local_folder=str(staged_path.parent),
            remote_folder=remote_path,
            glob_patterns=[staged_path.name],
            is_versioned=True,
            print_message=False,
        )
        upload_data = SDKBase.get_response_data(upload_response)

        if upload_data is None:
            print("[FAIL] Upload failed: no response data returned")
            return False

        successful, skipped, failed = [], [], []
        for result in upload_data.DatahubResourceResults:
            if result.Success:
                successful.append(result.RelativeFilePath)
            elif result.FailureReason and "identical to the remote file" in result.FailureReason:
                skipped.append(result.RelativeFilePath)
            else:
                failed.append((result.RelativeFilePath, result.FailureReason or "Unknown error"))

        if failed:
            for path, reason in failed:
                print(f"[FAIL] {path}: {reason}")
            return False

        if skipped:
            print(f"[OK] Skipped (identical): {staged_path.name}")
        else:
            print(f"[OK] Uploaded: {staged_path.name} → {remote_path}")
        return True

    except Exception as e:
        print(f"[FAIL] Upload error: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Find a file by name and move it to output_path. "
            "If the file is a CSV it is also converted to Parquet. "
            "Also searches inside ZIP archives. "
            "Optionally uploads the result to DataHub."
        ),
        epilog=(
            "Examples:\n\n"
            "  Search default paths (output_path first, then simulation_path):\n"
            "    python3 search_and_upload.py -f results.csv\n\n"
            "  Search a specific directory:\n"
            "    python3 search_and_upload.py -f results.csv -p /simulation/MyStudy\n\n"
            "  Glob pattern search with DataHub upload:\n"
            "    python3 search_and_upload.py -f '*.csv' -p /simulation/Reports -u Project/Study/Results\n\n"
            "  URL-encoded filename with spaces:\n"
            "    python3 search_and_upload.py -f 'My%%20Report.csv'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-f", "--file-name",
        required=True,
        help=(
            "Filename (or glob pattern) to search for. "
            "Example: 'results.csv', 'report_*.csv'. "
            "Also checked against entries inside ZIP archives."
        ),
    )
    parser.add_argument(
        "-p", "--path",
        default=None,
        help=(
            "Primary directory to search. When omitted (or if the file is not found "
            "there), output_path is searched next, then simulation_path."
        ),
    )
    parser.add_argument(
        "-u", "--upload-path",
        default=None,
        dest="upload_path",
        help=(
            "DataHub destination folder to upload the staged file to "
            "(e.g. Project/Study/Results). Requires cloud_cli_path env var. "
            "When omitted, no upload is performed."
        ),
    )

    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    print(f"[OK] Args interpreted: {args}\n")

    file_name   = _decode_arg(args.file_name)
    upload_path = _decode_arg(args.upload_path) if args.upload_path else None

    if upload_path and not CLOUD_CLI_PATH:
        print("Error: Missing required environment variable: cloud_cli_path (needed for --upload-path)")
        return 1

    if args.path:
        explicit_path = _decode_arg(args.path)
        search_paths = list(dict.fromkeys([explicit_path, OUTPUT_PATH, SIMULATION_PATH]))
    else:
        explicit_path = None
        search_paths = list(dict.fromkeys([OUTPUT_PATH, SIMULATION_PATH]))

    print(f"File name    : {file_name}")
    print(f"Search paths : {search_paths}")
    print(f"Destination  : {OUTPUT_PATH}")
    if upload_path:
        print(f"Upload path  : {upload_path}")
    print()

    # 1. Search filesystem directly
    found = find_file(file_name, search_paths)

    # 2. Fall back to searching inside ZIP archives
    if not found:
        print(f"[OK] Not found directly — searching inside ZIP archives...")
        found = find_in_zips(file_name, search_paths, OUTPUT_PATH)

    if not found:
        print(f"[FAIL] '{file_name}' not found in: {search_paths} (including ZIP archives)")
        return 1

    if explicit_path and not found.startswith(str(Path(explicit_path).resolve())):
        print(f"[WARN] '{file_name}' not found in explicit path '{explicit_path}' — found via fallback")

    print(f"[OK] Found: {found}")

    staged = stage_file(found, OUTPUT_PATH, SIMULATION_PATH)
    if staged is None:
        return 1

    # 3. Convert CSV to Parquet; track the final staged path for upload
    if staged.suffix.lower() == ".csv":
        print(f"\n[OK] CSV file detected — converting to Parquet")
        parquet_path, success = convert_csv_to_parquet(str(staged))
        if not success:
            print(f"[FAIL] Parquet conversion failed")
            return 1
        staged = Path(parquet_path)

    # 4. Optional DataHub upload
    if upload_path:
        print(f"\n[OK] Uploading {staged.name} to DataHub: {upload_path}")
        if not upload_to_datahub(staged, upload_path, CLOUD_CLI_PATH):
            print(f"[FAIL] Upload failed")
            return 1

    print(f"\n[OK] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
