"""
Export PLEXOS reported property key information to Parquet.

Queries the pre-configured DuckDB solution database (set up by ConfigureDuckDbViews)
and writes a flattened Parquet file of reported-property key info — enriched with
child and parent object category names — to output_path for automatic platform upload.

Focused script — Parquet export only. No DataHub upload.
Chain with upload_to_datahub.py if you need to push results to DataHub immediately.

Requires ConfigureDuckDbViews to have run first so the fullkeyinfo, object, and
category views are available in duck_db_path.

Environment variables used:
    duck_db_path  – required; path to the DuckDB solution database containing views
    output_path   – working directory for output files (default: /output)
"""
import argparse
import os
import sys
from pathlib import Path

import duckdb


# Required env vars — fail fast with a clear message
try:
    DUCK_DB_PATH = os.environ["duck_db_path"]
except KeyError:
    print("Error: Missing required environment variable: duck_db_path")
    sys.exit(1)

# Optional env vars — use sensible defaults
OUTPUT_PATH = os.environ.get("output_path", "/output")


class ReportedPropertiesExporter:
    """Exports PLEXOS reported property key info from DuckDB views to Parquet."""

    def __init__(self, duck_db_path: str, output_path: str):
        """
        Args:
            duck_db_path: Path to the DuckDB solution database containing views
            output_path:  Working directory for output files
        """
        self.duck_db_path = duck_db_path
        self.output_path = Path(output_path)

    def export(self, output_filename: str = "flattened_data.parquet") -> bool:
        """
        Export reported property key info to Parquet.

        Connects to the DuckDB solution database and exports a flattened view of
        reported-property keys joined with child and parent object category names.
        The query joins fullkeyinfo, object, and category views.

        Args:
            output_filename: Name of the output Parquet file
                             (default: flattened_data.parquet)

        Returns:
            True if export successful, False otherwise. Returns False for all
            failure conditions including: invalid filename, output directory
            creation failure, and DuckDB/IO errors.
        """
        # Validate output_filename — reject path traversal or absolute paths
        if Path(output_filename).is_absolute() or any(sep in output_filename for sep in ("/", "\\")):
            print(
                f"[FAIL] --output-file '{output_filename}' is invalid — "
                "must be a plain filename with no path separators or absolute paths"
            )
            return False

        output_file = self.output_path / output_filename

        # Ensure output directory exists before writing
        try:
            self.output_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"[FAIL] Cannot create output directory {self.output_path}: {e}")
            return False

        print(f"\n{'='*60}")
        print("PLEXOS Reported Properties Exporter")
        print(f"{'='*60}")
        print(f"DuckDB path   : {self.duck_db_path}")
        print(f"Output file   : {output_file}")
        print(f"{'='*60}\n")

        output_file_str = str(output_file)
        output_file_sql = output_file_str.replace("'", "''")

        try:
            with duckdb.connect(self.duck_db_path) as con:
                print("[OK] Connected to DuckDB solution database")
                print("[OK] Querying reported property data...")

                query = """
                SELECT
                    key.SeriesId,
                    key.DataFileId,
                    key.ChildObjectName,
                    cat_child.Name AS ChildObjectCategoryName,
                    cat_parent.Name AS ParentObjectCategoryName,
                    key.PropertyName
                FROM fullkeyinfo AS key
                LEFT JOIN object AS obj_child ON key.ChildObjectId = obj_child.ObjectId
                LEFT JOIN category AS cat_child ON obj_child.CategoryId = cat_child.CategoryId
                LEFT JOIN object AS obj_parent ON key.ParentObjectId = obj_parent.ObjectId
                LEFT JOIN category AS cat_parent ON obj_parent.CategoryId = cat_parent.CategoryId
                """

                # Write data to Parquet
                con.sql(query).write_parquet(output_file_str)

                print("[OK] Reported property data written to Parquet")

                # Preview and count are read from the already-written Parquet file to
                # avoid re-executing the full JOIN query a second time.
                print("\n--- Data Preview ---")
                result = con.sql(f"SELECT * FROM read_parquet('{output_file_sql}') LIMIT 20")
                col_names = result.columns
                rows = result.fetchall()

                # Use parquet_metadata() to get the row count from Parquet row-group
                # metadata instead of scanning the entire file with COUNT(*).
                row_count = con.execute(
                    f"SELECT SUM(row_group_num_rows) FROM parquet_metadata('{output_file_sql}')"
                ).fetchone()[0]

                if rows:
                    print("  " + " | ".join(col_names))
                    print("  " + "-" * max(40, sum(len(c) for c in col_names) + 3 * (len(col_names) - 1)))
                    for row in rows:
                        print("  " + " | ".join(str(v) if v is not None else "" for v in row))
                    print(f"  ({row_count} rows total, {len(rows)} shown)")
                else:
                    print("  No data to preview")

                print(f"\n{'='*60}")
                print("[OK] Export completed successfully")
                print(f"  Total rows: {row_count}")
                print(f"  Output file: {output_file}")
                print(f"{'='*60}\n")

                return True

        except Exception as e:
            print(f"\n{'='*60}")
            print("[FAIL] Failed to export reported properties")
            print(f"  {type(e).__name__}: {e}")
            print(f"{'='*60}\n")
            return False


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Export PLEXOS reported property key info to Parquet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export to default file (flattened_data.parquet)
  python3 write_reported_properties.py

  # Export to custom filename
  python3 write_reported_properties.py --output-file my_properties.parquet
        """
    )
    parser.add_argument(
        "-o", "--output-file",
        default="flattened_data.parquet",
        help=(
            "Name of output Parquet file (default: flattened_data.parquet). "
            "Must be a plain filename — no path separators or absolute paths."
        )
    )

    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    print(f"[OK] Args interpreted: output_file={args.output_file!r}\n")

    try:
        exporter = ReportedPropertiesExporter(DUCK_DB_PATH, OUTPUT_PATH)
        success = exporter.export(args.output_file)
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n[WARN] Operation cancelled by user (exit code 130)")
        return 130
    except Exception as e:
        print("\n[FAIL] Unexpected error occurred")
        print(f"  {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
