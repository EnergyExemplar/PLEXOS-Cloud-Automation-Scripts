"""
Convert Parquet files to CSV format in-place.

Focused script — conversion only. No DataHub download.
If your Parquet files are in DataHub, download them first using the Cloud CLI,
then point this script at the local folder.

Environment variables used:
    simulation_path  – resolved when -d simulation_path is passed
"""
import os
import sys
import duckdb
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    SIMULATION_PATH = os.environ["simulation_path"]
except KeyError:
    print("Error: Missing required environment variable: simulation_path")
    sys.exit(1)


def convert_single_parquet_to_csv(parquet_path: str) -> tuple:
    """Convert one Parquet file to CSV in-place, then delete the source Parquet."""
    conn = None
    start_time = time.time()
    try:
        conn = duckdb.connect()

        filename     = os.path.basename(parquet_path)
        csv_filename = os.path.splitext(filename)[0] + ".csv"
        csv_path     = os.path.join(os.path.dirname(parquet_path), csv_filename)

        parquet_esc = parquet_path.replace("'", "''")
        csv_esc     = csv_path.replace("'", "''")

        conn.sql(
            f"COPY (SELECT * FROM parquet_scan('{parquet_esc}')) TO '{csv_esc}' (HEADER, DELIMITER ',')"
        )

        if os.path.exists(csv_path):
            parquet_rows = conn.sql(f"SELECT COUNT(*) FROM parquet_scan('{parquet_esc}')").fetchone()[0]
            csv_rows     = conn.sql(f"SELECT COUNT(*) FROM read_csv_auto('{csv_esc}')").fetchone()[0]

            if parquet_rows == csv_rows:
                duration = time.time() - start_time
                print(f"[OK] {filename} → {csv_filename}: {parquet_rows:,} rows, {duration:.2f}s")
                print(f"     CSV path : {csv_path}")
                os.remove(parquet_path)
            else:
                print(f"[WARN] {filename}: row count mismatch (Parquet={parquet_rows:,}, CSV={csv_rows:,}) — Parquet kept")
                return (parquet_path, False, f"Row count mismatch: Parquet={parquet_rows}, CSV={csv_rows}")

        return (parquet_path, True, None)

    except Exception as e:
        duration = time.time() - start_time
        print(f"[ERROR] {os.path.basename(parquet_path)}: failed after {duration:.2f}s — {e}")
        return (parquet_path, False, str(e))
    finally:
        if conn:
            conn.close()


def convert_folder(folder: str, workers: int = 3) -> bool:
    """Convert all Parquet files under folder to CSV in-place."""
    parquet_files = [
        os.path.join(dirpath, f)
        for dirpath, _, filenames in os.walk(folder)
        for f in filenames if f.lower().endswith(".parquet")
    ]

    if not parquet_files:
        print(f"No Parquet files found in {folder}")
        return True

    print(f"Found {len(parquet_files)} Parquet file(s) — converting with {workers} worker(s)")

    success_count = failure_count = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(convert_single_parquet_to_csv, f): f for f in parquet_files}
        for future in futures:
            _, success, _ = future.result()
            if success:
                success_count += 1
            else:
                failure_count += 1

    print(f"\n--- Conversion Summary ---")
    print(f"Total: {len(parquet_files)}  Succeeded: {success_count}  Failed: {failure_count}")

    if failure_count:
        print(f"[ERROR] {failure_count} file(s) failed")
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Parquet files to CSV in-place.",
        epilog=(
            "Chain example — download then convert:\n"
            "  plexos-cloud datahub download --remote-path Project/Study/data/** --local-folder /simulation/data\n"
            "  python3 convert_parquet_to_csv.py -d /simulation/data"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-d", "--folder",
        required=True,
        help="Folder containing Parquet files. Pass 'simulation_path' to use the simulation_path env var.",
    )
    parser.add_argument("-w", "--workers", type=int, default=3, help="Parallel workers (default: 3)")
    args = parser.parse_args()

    folder = SIMULATION_PATH if args.folder == "simulation_path" else args.folder

    if not Path(folder).exists():
        print(f"Error: Folder '{folder}' does not exist")
        return 1

    print(f"Folder  : {folder}")
    print(f"Workers : {args.workers}")

    start = time.time()
    success = convert_folder(folder, args.workers)
    print(f"\nTotal time: {time.time() - start:.2f}s")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
