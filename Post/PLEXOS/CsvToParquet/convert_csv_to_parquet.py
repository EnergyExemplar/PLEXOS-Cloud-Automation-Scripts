"""
Convert CSV files to Parquet format in-place.

Focused script — conversion only. No DataHub upload.
Chain with UploadToDataHub if you need to upload results.

Environment variables used:
    output_path  – resolved when -r output_path is passed

Passing paths that contain spaces
----------------------------------
URL-encode spaces in the Arguments field:
    -r My%20Folder/Results
"""
import os
import sys
import duckdb
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

try:
    OUTPUT_PATH = os.environ["output_path"]
except KeyError:
    print("Error: Missing required environment variable: output_path")
    sys.exit(1)


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def convert_single_csv_to_parquet(csv_path: str, compression: str = "zstd") -> tuple:
    """Convert one CSV file to Parquet in-place, then delete the source CSV."""
    conn = None
    start_time = time.time()
    try:
        conn = duckdb.connect()

        filename = os.path.basename(csv_path)
        parquet_filename = os.path.splitext(filename)[0] + ".parquet"
        parquet_path = os.path.join(os.path.dirname(csv_path), parquet_filename)

        csv_esc     = csv_path.replace("'", "''")
        parquet_esc = parquet_path.replace("'", "''")
        compression_upper = compression.upper()

        conn.sql(f"""
            COPY (
                SELECT * FROM read_csv_auto('{csv_esc}', sample_size=100000)
            ) TO '{parquet_esc}' (FORMAT 'parquet', COMPRESSION '{compression_upper}')
        """)

        if os.path.exists(parquet_path):
            csv_rows     = conn.sql(f"SELECT COUNT(*) FROM read_csv_auto('{csv_esc}', sample_size=100000)").fetchone()[0]
            parquet_rows = conn.sql(f"SELECT COUNT(*) FROM '{parquet_esc}'").fetchone()[0]

            if csv_rows == parquet_rows:
                duration = time.time() - start_time
                print(f"[OK] {filename} → {parquet_filename}: {csv_rows:,} rows, {duration:.2f}s")
                os.remove(csv_path)
            else:
                print(f"[WARN] {filename}: row count mismatch (CSV={csv_rows:,}, Parquet={parquet_rows:,}) — CSV kept")
                return (csv_path, False, f"Row count mismatch: CSV={csv_rows}, Parquet={parquet_rows}")

        return (csv_path, True, None)

    except Exception as e:
        duration = time.time() - start_time
        print(f"[ERROR] {os.path.basename(csv_path)}: failed after {duration:.2f}s — {e}")
        return (csv_path, False, str(e))
    finally:
        if conn:
            conn.close()


def convert_folder(root_folder: str, workers: int = 3, compression: str = "zstd") -> bool:
    """Convert all CSV files under root_folder to Parquet in-place."""
    csv_files = [
        os.path.join(dirpath, f)
        for dirpath, _, filenames in os.walk(root_folder)
        for f in filenames if f.lower().endswith(".csv")
    ]

    if not csv_files:
        print(f"No CSV files found in {root_folder}")
        return True

    print(f"Found {len(csv_files)} CSV file(s) — converting with {workers} worker(s), compression: {compression}")

    success_count = failure_count = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(convert_single_csv_to_parquet, f, compression): f for f in csv_files}
        for future in futures:
            _, success, _ = future.result()
            if success:
                success_count += 1
            else:
                failure_count += 1

    print(f"\n--- Conversion Summary ---")
    print(f"Total: {len(csv_files)}  Succeeded: {success_count}  Failed: {failure_count}")

    if failure_count:
        print(f"[ERROR] {failure_count} file(s) failed")
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert CSV files to Parquet in-place. Chain with upload_to_datahub.py to upload results.",
        epilog=(
            "Chain example:\n"
            "  python3 convert_csv_to_parquet.py -r output_path\n"
            "  python3 upload_to_datahub.py -l output_path -r Project/Study/Results"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-r", "--root-folder",
        required=True,
        help="Folder containing CSV files. Pass 'output_path' to use the output_path env var.",
    )
    parser.add_argument("-w", "--workers", type=int, default=3, help="Parallel workers (default: 3)")
    parser.add_argument(
        "-c", "--compression",
        choices=["zstd", "gzip", "snappy", "none"],
        default="zstd",
        help="Parquet compression algorithm (default: zstd)",
    )
    args = parser.parse_args()

    decoded_root = _decode_path(args.root_folder)
    folder = OUTPUT_PATH if decoded_root == "output_path" else decoded_root

    if not Path(folder).exists():
        print(f"Error: Folder '{folder}' does not exist")
        return 1

    print(f"Root folder : {folder}")
    print(f"Workers     : {args.workers}")
    print(f"Compression : {args.compression}")

    start = time.time()
    success = convert_folder(folder, args.workers, args.compression)
    print(f"\nTotal time: {time.time() - start:.2f}s")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
