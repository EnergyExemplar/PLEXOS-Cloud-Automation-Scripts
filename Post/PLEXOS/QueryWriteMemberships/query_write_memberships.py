"""
Export PLEXOS model membership relationships to CSV.

Queries the PLEXOS SQLite database (reference.db) and exports membership
relationships (parent-child object connections) to a CSV file. Useful for
model analysis, documentation, and validation.

Environment variables used:
    simulation_path  – Path to simulation directory containing reference.db (default: /simulation)
    output_path      – Working directory (default: /output)

Chaining:
    Run this as a Pre or Post-simulation task to extract model structure.
    The output CSV can be used for model documentation or comparison.
"""
import argparse
import os
import sys
from pathlib import Path

import duckdb


# Optional environment variables with defaults
SIMULATION_PATH = os.environ.get('simulation_path', '/simulation')
OUTPUT_PATH = os.environ.get('output_path', '/output')


class MembershipExporter:
    """Exports PLEXOS membership data from SQLite to CSV using DuckDB."""
    
    def __init__(self, simulation_path: str, output_path: str):
        """
        Initialize the MembershipExporter.
        
        Args:
            simulation_path: Path to simulation directory containing reference.db
            output_path: Working directory for output files
        """
        self.simulation_path = Path(simulation_path)
        self.output_path = Path(output_path)
        self.database_file = self.simulation_path / "reference.db"
    
    def export_memberships(self, output_filename: str = "memberships_data.csv") -> bool:
        """
        Export membership relationships to CSV.
        
        Connects to the PLEXOS SQLite database and exports membership data showing
        parent-child relationships between model objects. The query joins across
        multiple tables (t_membership, t_object, t_collection, t_class) to provide
        comprehensive relationship information.
        
        Args:
            output_filename: Name of output CSV file (default: memberships_data.csv)
            
        Returns:
            True if export successful, False otherwise. Returns False for all
            failure conditions including: invalid filename, missing database,
            output directory creation failure, and DuckDB/IO errors.
        """
        # Validate output_filename — reject path traversal or absolute paths
        if Path(output_filename).is_absolute() or any(sep in output_filename for sep in ("/", "\\")):
            print(f"[FAIL] --output-file '{output_filename}' is invalid — must be a plain filename with no path separators or absolute paths")
            return False

        output_file = self.output_path / output_filename

        # Check if database exists
        if not self.database_file.exists():
            print(f"[FAIL] Database file not found: {self.database_file}")
            print(f"Expected under simulation_path: reference.db")
            return False

        # Ensure output directory exists before writing
        try:
            self.output_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"[FAIL] Cannot create output directory: {self.output_path}: {e}")
            return False

        print(f"\n{'='*60}")
        print("PLEXOS Membership Exporter")
        print(f"{'='*60}")
        print(f"Database      : {self.database_file}")
        print(f"Output File   : {output_file}")
        print(f"{'='*60}\n")
        
        try:
            # Connect to DuckDB (in-memory) and attach SQLite database
            with duckdb.connect() as con:
                # Load SQLite extension — install only if not already available
                try:
                    con.execute("LOAD sqlite;")
                except duckdb.Error:
                    con.execute("INSTALL sqlite;")
                    con.execute("LOAD sqlite;")

                print("[OK] Loaded SQLite extension")
                print(f"[OK] Attaching database: {self.database_file}")

                # Attach the PLEXOS SQLite database (escape path for SQL safety)
                safe_db_path = str(self.database_file).replace("'", "''")
                con.execute(f"ATTACH '{safe_db_path}' AS reference (TYPE SQLITE, READ_ONLY true);")
                con.execute("USE reference;")
                
                print("[OK] Connected to reference database")
                print("[OK] Querying membership data...")
                
                # Define query to extract membership relationships
                query_text = """
                SELECT 
                    cl1.Name AS parent_class,
                    cl2.Name AS child_class,
                    col.Name AS collection,
                    obj1.Name AS parent_object,
                    obj2.Name AS child_object
                FROM t_membership mem 
                INNER JOIN t_object obj1 ON obj1.object_id = mem.parent_object_id
                INNER JOIN t_object obj2 ON obj2.object_id = mem.child_object_id
                INNER JOIN t_collection col ON col.collection_id = mem.collection_id
                INNER JOIN t_class cl1 ON cl1.class_id = mem.parent_class_id
                INNER JOIN t_class cl2 ON cl2.class_id = mem.child_class_id
                """
                
                # Write data to CSV
                output_file_sql = str(output_file).replace("'", "''")
                con.execute(
                    f"COPY ({query_text}) TO '{output_file_sql}' "
                    f"WITH (HEADER, DELIMITER ',');"
                )
                
                print("[OK] Membership data written to CSV")

                # Preview and count are read from the already-written CSV to avoid
                # re-executing the full JOIN query a second time.
                print("\n--- Data Preview ---")
                result = con.sql(f"SELECT * FROM read_csv_auto('{output_file_sql}') LIMIT 20")
                col_names = result.columns
                rows = result.fetchall()

                row_count = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{output_file_sql}')").fetchone()[0]

                if rows:
                    print("  " + " | ".join(col_names))
                    print("  " + "-" * max(40, sum(len(c) for c in col_names) + 2 * (len(col_names) - 1)))
                    for row in rows:
                        print("  " + " | ".join(str(v) if v is not None else "" for v in row))
                    print(f"  ({row_count} rows total, {len(rows)} shown)")
                else:
                    print("  No data to preview")
                
                print(f"\n{'='*60}")
                print("[OK] Export completed successfully")
                print(f"  Total relationships: {row_count}")
                print(f"  Output file: {output_file}")
                print(f"{'='*60}\n")
                
                return True
                
        except Exception as e:
            print(f"\n{'='*60}")
            print("[FAIL] Failed to export membership data")
            print(f"  {type(e).__name__}: {e}")
            print(f"{'='*60}\n")
            return False


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Export PLEXOS membership relationships to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export memberships to default file (memberships_data.csv)
  python3 query_write_memberships.py

  # Export to custom filename
  python3 query_write_memberships.py --output-file my_memberships.csv

  # Use in Pre-simulation task to document model structure
  # Or in Post-simulation task for analysis
        """
    )
    parser.add_argument(
        "-o", "--output-file",
        default="memberships_data.csv",
        help="Name of output CSV file (default: memberships_data.csv)"
    )
    
    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    print(f"[OK] Args interpreted: output_file={args.output_file!r}\n")
    
    try:
        exporter = MembershipExporter(SIMULATION_PATH, OUTPUT_PATH)
        success = exporter.export_memberships(args.output_file)
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
