"""
Configure DuckDB views for querying PLEXOS solution parquet data.

Focused script — view creation only. No DataHub upload.
The views point at parquet files under the solution parquet directory,
resolved from the first ParquetPath entry in the directory mapping JSON.

Environment variables used:
    duck_db_path       – required; path to the DuckDB file to write views into
                         (platform default: /output/solution_views.ddb)
    directory_map_path – optional; path to directory mapping JSON
                         (falls back to /simulation/splits/directorymapping.json)
"""
import os
import sys
import json
import argparse
import duckdb


# Required env vars — fail fast with a clear message
try:
    DUCK_DB_PATH = os.environ["duck_db_path"]
except KeyError:
    print("Error: Missing required environment variable: duck_db_path")
    sys.exit(1)

# Optional env vars — use sensible defaults
DIRECTORY_MAP_PATH = os.environ.get("directory_map_path", "")


class DuckViewConfigurator:
    """Creates DuckDB views for all solution subdirectories from the directory mapping."""

    def __init__(self, duck_db_path: str):
        """
        Args:
            duck_db_path: Path to the DuckDB file where views will be created.
        """
        self.duck_db_path = duck_db_path

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
        fallback = "/simulation/splits/directorymapping.json"
        if env_path and os.path.exists(env_path):
            return env_path
        if os.path.exists(fallback):
            return fallback
        raise FileNotFoundError(
            f"Mapping file not found. Checked: "
            f"{env_path or '[directory_map_path not set]'} and {fallback}"
        )

    def _read_parquet_path(self, mapping_file_path: str) -> str:
        """
        Reads the ParquetPath from the first matching entry in the directory mapping JSON.

        Args:
            mapping_file_path: Path to the directory mapping JSON file.

        Returns:
            The ParquetPath string from the first entry that contains one.

        Raises:
            FileNotFoundError: If the mapping file does not exist.
            ValueError: If the file is empty or no entry has a ParquetPath.
        """
        with open(mapping_file_path) as f:
            data = json.load(f)

        if not data:
            raise ValueError("Mapping JSON is empty or not properly formatted.")

        for item in data:
            parquet_path = item.get("ParquetPath")
            if parquet_path:
                return parquet_path

        raise ValueError("No entry with 'ParquetPath' found in the mapping file.")

    def configure(self, verbose: bool = False) -> bool:
        """
        Create or replace DuckDB views for all solution subdirectories.

        Each subdirectory under the resolved ParquetPath becomes a view that reads
        all *.parquet files in that subtree via a recursive glob pattern.

        Args:
            verbose: If True, print each CREATE VIEW statement and a 2-row sample.

        Returns:
            True on success, False on failure.
        """
        try:
            mapping_path = self._resolve_mapping_file(DIRECTORY_MAP_PATH)
            print(f"[OK] Using mapping file: {mapping_path}")

            model_directory = self._read_parquet_path(mapping_path)
            print(f"[OK] Solution data found at: {model_directory}")

            subdirs = [
                dirpath
                for dirpath, _, _ in os.walk(model_directory)
                if dirpath != model_directory
            ]

            if not subdirs:
                print(f"[WARN] No subdirectories found under: {model_directory}")
                return True

            print(f"[OK] Configuring views in: {self.duck_db_path}")

            with duckdb.connect(self.duck_db_path) as con:
                views_created = 0
                for subdir in subdirs:
                    rel = os.path.relpath(subdir, model_directory)
                    view_name = rel.replace(os.sep, "__")

                    # Skip internal DuckDB storage artefacts
                    if "datadataFileId=" in view_name:
                        continue

                    # Use forward slashes for the glob path (DuckDB convention)
                    glob_path = subdir.replace("\\", "/") + "/**/*.parquet"
                    glob_esc = glob_path.replace("'", "''")

                    # Quote the identifier to handle any characters safely
                    view_name_q = f'"{view_name}"'
                    sql = (
                        f"CREATE OR REPLACE VIEW {view_name_q} AS "
                        f"SELECT * FROM read_parquet('{glob_esc}', union_by_name=true);"
                    )

                    if verbose:
                        print(f"  {sql}")
                    con.execute(sql)
                    if verbose:
                        con.sql(f"SELECT * FROM {view_name_q} LIMIT 2;").show()
                    views_created += 1

            print(f"[OK] Created {views_created} view(s)")
            return True

        except FileNotFoundError as e:
            print(f"[FAIL] {e}")
            return False
        except ValueError as e:
            print(f"[FAIL] {e}")
            return False
        except Exception as e:
            print(f"[FAIL] Unexpected error: {e}")
            return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure DuckDB views for querying PLEXOS solution parquet data.",
        epilog=(
            "Examples:\n\n"
            "  python3 configure_duck_db_views.py\n\n"
            "  python3 configure_duck_db_views.py --verbose"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each CREATE VIEW statement and a 2-row sample query result.",
    )
    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()

    configurator = DuckViewConfigurator(duck_db_path=DUCK_DB_PATH)
    success = configurator.configure(verbose=args.verbose)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
