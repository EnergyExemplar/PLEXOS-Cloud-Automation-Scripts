"""
Copy model solution parquet files to output_path for automatic platform upload.

Focused script — file staging only. No DataHub upload.
Files written to output_path are automatically uploaded by the platform at the
end of the simulation. Chain with upload_to_datahub.py if you need to push
results to a specific DataHub path immediately.

Performance:
    - Suitable for large solution datasets (millions of rows)
    - Uses DuckDB COPY to export directly from the solution database to Parquet

CLI arguments:
    -cn, --collection-name   Required one-or-more CollectionName values.
    -pn, --property-name     Required one-or-more PropertyName values.
    -on, --object-name       Optional one-or-more ObjectName values.
    -cat, --category-name    Optional one-or-more CategoryName values.
    -fn, --parquet-name      Optional output parquet file name (without .parquet extension).
                             Defaults to SolsData.
    -sd, --start-date        Optional start date filter (inclusive, YYYY-MM-DD). Filters rows where StartDate >= value.
    -ed, --end-date          Optional end date filter (inclusive, YYYY-MM-DD). Filters rows where EndDate <= value.

Environment variables used:
    output_path        - directory where output files are staged
    directory_map_path - required; primary path to the directory mapping JSON containing model Name, Id, and ParquetPath.
                         Falls back to /simulation/splits/directorymapping.json for distributed runs.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import unquote

import duckdb


# ── Environment variables ─────────────────────────────────────────────────────
# Platform-provided — injected automatically. Do not set these manually.

try:
    OUTPUT_PATH = Path(os.environ["output_path"])
except KeyError:
    print("Error: Missing required environment variable: output_path")
    sys.exit(1)

try:
    DIRECTORY_MAP_PATH = Path(os.environ["directory_map_path"])
except KeyError:
    print("Error: Missing required environment variable: directory_map_path")
    sys.exit(1)


@dataclass
class ModelMapping:
    model_id: str
    model_name: str
    parquet_path: str


def _validate_date_arg(value: str, flag: str) -> bool:
    """Return True if value is a valid YYYY-MM-DD date, False (with a printed error) otherwise."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        print(f"[FAIL] Invalid date for {flag}: '{value}' — expected format YYYY-MM-DD (e.g. 2024-01-31)")
        return False


def _decode_value(value: str) -> str:
    """Strip surrounding quotes left by non-shell runners, then URL-decode."""
    return unquote(value.strip("'\""))


def _decode_cli_args(args: argparse.Namespace) -> None:
    """URL-decode supported CLI string fields in-place."""
    for field_name in ["collection_name", "property_name", "object_name", "category_name"]:
        field_value = getattr(args, field_name)
        if isinstance(field_value, str):
            setattr(args, field_name, _decode_value(field_value))
        elif isinstance(field_value, list):
            setattr(args, field_name, [_decode_value(item) if isinstance(item, str) else item for item in field_value])


def _to_sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _convert_wildcard_to_sql_pattern(value: str) -> tuple[str, bool]:
    """
    Convert Python-style wildcards to SQL LIKE patterns.
    Returns (pattern, has_wildcards).

    * -> %  (matches any sequence of characters)
    ? -> _  (matches any single character)
    """
    if '*' in value or '?' in value:
        # Escape existing % and _ in the value first
        escaped = value.replace('%', r'\%').replace('_', r'\_')
        # Convert wildcards
        pattern = escaped.replace('*', '%').replace('?', '_')
        return pattern, True
    return value, False


def _build_in_filter(column_sql: str, values: list[object]) -> str:
    """
    Build SQL filter with case-insensitive matching and wildcard support.
    Uses ILIKE for pattern matching (case-insensitive LIKE in DuckDB).
    """
    if not values:
        return ""
    
    # Separate wildcard patterns, string values, non-string values, and None
    patterns = []
    string_values = []
    non_string_values = []
    has_null = False

    for value in values:
        if value is None:
            has_null = True
        elif isinstance(value, str):
            sql_pattern, has_wildcards = _convert_wildcard_to_sql_pattern(value)
            if has_wildcards:
                patterns.append(sql_pattern)
            else:
                string_values.append(value)
        else:
            # Integers, floats, booleans, etc. - no case-insensitive comparison needed
            non_string_values.append(value)

    # Build filter clauses
    clauses = []

    # None values — must use IS NULL, not = NULL
    if has_null:
        clauses.append(f"{column_sql} IS NULL")

    # Non-string values - direct comparison without LOWER()
    if non_string_values:
        if len(non_string_values) == 1:
            clauses.append(f"{column_sql} = {_to_sql_literal(non_string_values[0])}")
        else:
            in_values = ", ".join(_to_sql_literal(v) for v in non_string_values)
            clauses.append(f"{column_sql} IN ({in_values})")

    # String values - case-insensitive comparison with LOWER()
    if string_values:
        if len(string_values) == 1:
            clauses.append(f"LOWER({column_sql}) = LOWER({_to_sql_literal(string_values[0])})")
        else:
            in_values = ", ".join(f"LOWER({_to_sql_literal(v)})" for v in string_values)
            clauses.append(f"LOWER({column_sql}) IN ({in_values})")

    # Pattern matching with ILIKE (case-insensitive)
    for pattern in patterns:
        escaped_pattern = _to_sql_literal(pattern)
        clauses.append(f"{column_sql} ILIKE {escaped_pattern}")

    # Combine with OR if multiple conditions
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " OR ".join(clauses) + ")"


class SolutionDataQueryWorker:
    """
    Builds a filtered joined parquet from model solution outputs and stages
    it in output_path for automatic platform upload.
    """

    def __init__(self, output_path: Path, directory_map_path: Path) -> None:
        """
        Args:
            output_path:        Directory where output files are staged.
            directory_map_path: Primary path to the directory mapping JSON.
        """
        self.output_path = output_path
        self.directory_map_path = directory_map_path

    def _resolve_mapping_file(self) -> Path:
        """
        Resolve the directory mapping JSON file path.

        Uses self.directory_map_path if the file exists there, then falls back
        to /simulation/splits/directorymapping.json for distributed runs.

        Returns:
            Resolved path to an existing mapping file.

        Raises:
            FileNotFoundError: If neither path exists.
        """
        if self.directory_map_path.exists():
            return self.directory_map_path

        split_mapping_path = Path("/simulation/splits/directorymapping.json")
        if split_mapping_path.exists():
            return split_mapping_path

        raise FileNotFoundError(
            f"Mapping file not found. Checked: {self.directory_map_path} and {split_mapping_path}"
        )

    @staticmethod
    def read_mapping(mapping_file_path: Path) -> ModelMapping:
        """
        Read the first entry with a ParquetPath from the directory mapping JSON.

        Args:
            mapping_file_path: Path to the JSON mapping file.

        Returns:
            ModelMapping with model ID, name, and local parquet path.

        Raises:
            FileNotFoundError: If the mapping file does not exist.
            ValueError: If the JSON is empty, malformed, or contains no ParquetPath entry.
        """
        if not mapping_file_path.is_file():
            raise FileNotFoundError(f"Mapping file not found: {mapping_file_path}")

        with mapping_file_path.open("r", encoding="utf-8") as file:
            try:
                mapping_data = json.load(file)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in mapping file: {exc}") from exc

        if not isinstance(mapping_data, list) or not mapping_data:
            raise ValueError("Mapping JSON must be a non-empty list")

        for item in mapping_data:
            if not isinstance(item, dict):
                continue
            if "ParquetPath" not in item:
                continue

            model_id = str(item.get("Id", "")).strip()
            model_name = str(item.get("Name", "")).strip()
            parquet_path = str(item.get("ParquetPath", "")).strip()

            if not model_id:
                raise ValueError(
                    "Mapping entry with 'ParquetPath' is missing a non-empty 'Id' field. "
                    "'Id' is required to identify the model."
                )
            if not model_name:
                raise ValueError(
                    "Mapping entry with 'ParquetPath' is missing a non-empty 'Name' field. "
                    "'Name' is required to identify the model."
                )
            if not parquet_path:
                raise ValueError("Mapping entry has empty 'ParquetPath' field")

            return ModelMapping(
                model_id=model_id,
                model_name=model_name,
                parquet_path=parquet_path,
            )

        raise ValueError("No entry with 'ParquetPath' found in the mapping file")

    def _validate_source_structure(
        self, source_folder: Path
    ) -> tuple[Path, Path, list[str]] | None:
        """
        Validate that the expected parquet substructure exists under source_folder.

        Returns:
            (fullkeyinfo_path, period_path, data_paths) on success, None on failure.
        """
        fullkeyinfo_path = source_folder / "fullkeyinfo" / "FullKeyInfo.parquet"
        period_path = source_folder / "period" / "Period.parquet"
        data_paths = [str(p) for p in (source_folder / "data").glob("dataFileId=*/*.parquet")]

        missing_components = []
        if not fullkeyinfo_path.exists():
            missing_components.append("fullkeyinfo/FullKeyInfo.parquet")
        if not period_path.exists():
            missing_components.append("period/Period.parquet")
        if not data_paths:
            missing_components.append("data/dataFileId=*/*.parquet")

        if missing_components:
            print(f"[FAIL] Missing parquet structure in {source_folder}: {', '.join(missing_components)}")
            return None

        return fullkeyinfo_path, period_path, data_paths

    def _build_select_sql(
        self,
        fullkeyinfo_path: Path,
        period_path: Path,
        data_paths: list[str],
        collection_names: list[str],
        property_names: list[str],
        object_names: list[str],
        category_names: list[str],
        start_date: str | None,
        end_date: str | None,
    ) -> str:
        """Build the DuckDB SELECT SQL for the filtered three-way join."""
        get_columns = [
            "PhaseName", "PeriodTypeName", "ChildObjectCategoryName", "ChildObjectName",
            "PropertyName", "SampleName", "StartDate", "Value", "UnitValue", "ModelName",
        ]
        get_columns_as = [
            "PhaseName", "PeriodTypeName", "CategoryName", "ObjectName",
            "PropertyName", "SampleName", "StartDate", "Value", "Measure", "ModelName",
        ]
        select_column_sources = {
            "PhaseName": "fk.PhaseName",
            "PeriodTypeName": "fk.PeriodTypeName",
            "ChildObjectCategoryName": "fk.ChildObjectCategoryName",
            "ChildObjectName": "fk.ChildObjectName",
            "PropertyName": "fk.PropertyName",
            "SampleName": "fk.SampleName",
            "StartDate": "p.StartDate",
            "Value": "d.Value",
            "UnitValue": "fk.UnitValue",
            "ModelName": "fk.ModelName",
        }

        where_predicates = [
            _build_in_filter("fk.CollectionName", collection_names),
            _build_in_filter("fk.PropertyName", property_names),
        ]

        object_filter_sql = _build_in_filter("fk.ChildObjectName", object_names)
        if object_filter_sql:
            where_predicates.append(object_filter_sql)

        category_filter_sql = _build_in_filter("fk.ChildObjectCategoryName", category_names)
        if category_filter_sql:
            where_predicates.append(category_filter_sql)

        if start_date:
            where_predicates.append(f"CAST(p.StartDate AS DATE) >= CAST({_to_sql_literal(start_date)} AS DATE)")
        if end_date:
            where_predicates.append(f"CAST(p.EndDate AS DATE) <= CAST({_to_sql_literal(end_date)} AS DATE)")

        where_predicates = [p for p in where_predicates if p]
        where_sql = ""
        if where_predicates:
            where_sql = "\n            WHERE " + "\n              AND ".join(where_predicates)

        projection_sql = ",\n                ".join(
            f"{select_column_sources[col]} AS {alias}"
            for col, alias in zip(get_columns, get_columns_as)
        )
        data_paths_sql = "[" + ", ".join("'" + p.replace("'", "''") + "'" for p in data_paths) + "]"

        return f"""
            SELECT
                {projection_sql}
            FROM '{str(fullkeyinfo_path).replace("'", "''")}' fk
            INNER JOIN read_parquet({data_paths_sql}, hive_partitioning = true) d
                ON fk.SeriesId = d.SeriesId
            INNER JOIN '{str(period_path).replace("'", "''")}' p
                ON p.PeriodId = d.PeriodId
            {where_sql}
        """

    def _write_parquet(
        self,
        connection: duckdb.DuckDBPyConnection,
        select_sql: str,
        output_file: Path,
    ) -> bool:
        """Execute the COPY statement and handle write errors."""
        output_sql_path = str(output_file).replace("'", "''")
        try:
            print(f"[OK] Starting DuckDB join and export (streaming mode enabled)...")
            connection.execute(
                f"COPY ({select_sql}) TO '{output_sql_path}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            return True
        except Exception as exc:
            error_msg = str(exc).lower()
            if "memory" in error_msg or "out of memory" in error_msg:
                print(f"[FAIL] Out of memory during export - add more restrictive filters or increase memory_limit")
            elif "permission" in error_msg or "access" in error_msg:
                print(f"[FAIL] Permission denied writing output file: {output_file}")
            elif "space" in error_msg or "disk" in error_msg:
                print(f"[FAIL] Insufficient disk space writing output file: {output_file}")
            else:
                print(f"[FAIL] Failed to write output parquet {output_file}: {exc}")
            return False

    def copy_to_output(
        self,
        source_folder: Path,
        dest_folder: Path,
        collection_names: list[str],
        property_names: list[str],
        object_names: list[str],
        category_names: list[str],
        parquet_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> bool:
        """
        Orchestrate solution extraction, filtering, and parquet export.

        Validates source structure, builds the filtered SQL query, runs the
        DuckDB join/export, and logs performance metrics.

        Args:
            source_folder: Local folder containing fullkeyinfo, period, and data folders.
            dest_folder:   Destination folder under output_path.

        Returns:
            True if a joined parquet file was written successfully, False otherwise.
        """
        try:
            dest_folder.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            print(f"[FAIL] Permission denied creating output directory {dest_folder}: {exc}")
            return False
        except OSError as exc:
            print(f"[FAIL] Cannot create output directory {dest_folder}: {exc}")
            return False

        if parquet_name:
            # Reject absolute paths and any path separators to prevent traversal outside dest_folder
            if Path(parquet_name).is_absolute() or any(sep in parquet_name for sep in ("/", "\\")):
                print(f"[FAIL] --parquet-name '{parquet_name}' is invalid — must be a plain filename with no path separators or absolute paths")
                return False
            output_file = dest_folder / f"{parquet_name}.parquet"
        else:
            output_file = dest_folder / "SolsData.parquet"
        staging_start = perf_counter()

        # Solution extraction — validate source parquet structure
        source = self._validate_source_structure(source_folder)
        if source is None:
            return False
        fullkeyinfo_path, period_path, data_paths = source

        # Solution filtering — build the parameterised SQL query
        select_sql = self._build_select_sql(
            fullkeyinfo_path, period_path, data_paths,
            collection_names, property_names, object_names, category_names,
            start_date, end_date,
        )

        # DuckDB export — streaming join and parquet write
        connection = duckdb.connect()
        connection.execute(f"PRAGMA temp_directory='{str(dest_folder).replace(chr(39), chr(39) * 2)}'")
        connection.execute("SET enable_progress_bar=true")
        connection.execute("SET enable_progress_bar_print=false")

        try:
            export_start = perf_counter()
            if not self._write_parquet(connection, select_sql, output_file):
                return False
            export_elapsed_seconds = perf_counter() - export_start

            # Result validation — read row count from parquet footer metadata (no data scan)
            output_sql_path = str(output_file).replace("'", "''")
            total_rows = connection.execute(
                f"SELECT SUM(num_rows) FROM parquet_file_metadata('{output_sql_path}')"
            ).fetchone()[0] or 0

            if total_rows == 0:
                print(f"[FAIL] Zero rows in output - filters matched no data in {source_folder}")
                print(f"        Verify filter values match the actual data in source parquet files")
                return False

            size_bytes = output_file.stat().st_size if output_file.exists() else 0
            size_mb = size_bytes / (1024 * 1024)
            total_elapsed_seconds = perf_counter() - staging_start
            rows_per_second = total_rows / export_elapsed_seconds if export_elapsed_seconds > 0 else 0
            mb_per_second = size_mb / export_elapsed_seconds if export_elapsed_seconds > 0 else 0

            print(f"[OK] Written: {output_file}")
            print(f"[OK] Size: {size_mb:.2f} MB ({size_bytes:,} bytes)")
            print(f"[OK] Time: Export={export_elapsed_seconds:.2f}s, Total={total_elapsed_seconds:.2f}s")
            print(f"[OK] Performance: {rows_per_second:,.0f} rows/sec, {mb_per_second:.2f} MB/sec")
            print(f"[OK] Summary: SolutionsJoined=1, Rows={total_rows:,}")

            return True
        finally:
            connection.close()

    def run(self, args: argparse.Namespace) -> int:
        """
        Execute the solution data query and stage the output parquet.

        Args:
            args: Parsed and decoded CLI arguments.

        Returns:
            0 on success, 1 on failure.
        """
        process_start = perf_counter()

        try:
            mapping_file_path = self._resolve_mapping_file()
            print(f"[OK] Using mapping file: {mapping_file_path}")
            mapping = self.read_mapping(mapping_file_path)

            source_folder = Path(mapping.parquet_path)
            if not source_folder.exists() or not source_folder.is_dir():
                print(f"[FAIL] Source parquet folder not found or invalid: {source_folder}")
                return 1

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_folder = self.output_path / f"{mapping.model_name.upper()}_filtered_sols_data_{timestamp}"

            print(f"[OK] Model: Name={mapping.model_name}, Id={mapping.model_id}")
            print(f"[OK] Source: {source_folder}")
            print(f"[OK] Dest: {dest_folder}")

            success = self.copy_to_output(
                source_folder=source_folder,
                dest_folder=dest_folder,
                collection_names=args.collection_name,
                property_names=args.property_name,
                object_names=args.object_name,
                category_names=args.category_name,
                parquet_name=args.parquet_name,
                start_date=args.start_date,
                end_date=args.end_date,
            )

            if success:
                print(f"[OK] Files staged to: {dest_folder}")
                return 0

            print("[WARN] Staging finished with failures")
            return 1

        except Exception as exc:
            print(f"[FAIL] {exc}")
            return 1
        finally:
            process_elapsed_seconds = perf_counter() - process_start
            print(f"[OK] Total script runtime: {process_elapsed_seconds:.2f}s")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy model solution parquet files to output_path for platform upload.\n\n"
            "All filters are case-insensitive and support wildcards:\n"
            "  * matches any sequence of characters (SQL %)\n"
            "  ? matches any single character (SQL _)\n\n"
            "The first model with a ParquetPath in the mapping file will be used.\n"
            "Collection, Property, Object, and Category filters support wildcards."
        ),
        epilog=(
            "Examples:\n\n"
            "  Required filters — single or multiple values:\n"
            "    python3 solution_data_query.py "
            "--collection-name \"Gas Zones\" --property-name Price\n"
            "    python3 solution_data_query.py "
            "--collection-name \"Gas Zones\" \"Gas Demands\" --property-name Price Demand\n\n"
            "  Wildcards and optional region/category filters (all case-insensitive):\n"
            "    python3 solution_data_query.py "
            "--collection-name \"*Zones\" --property-name \"*Price*\" "
            "--object-name \"*Texas*\" Alberta --category-name \"*Hubs\"\n\n"
            "  Date range filters (start, end, or both):\n"
            "    Accepted format: YYYY-MM-DD (e.g. 2024-01-31)\n"
            "    StartDate/EndDate in the parquet files are timestamps; the date filter\n"
            "    compares against the date portion only (time is ignored).\n"
            "    python3 solution_data_query.py "
            "--collection-name \"Gas Zones\" --property-name Price "
            "--start-date 2024-01-01\n"
            "    python3 solution_data_query.py "
            "--collection-name \"Gas Zones\" --property-name Price "
            "--start-date 2024-01-01 --end-date 2024-12-31\n\n"
            "  URL-encoded values are decoded automatically (use when spaces break args):\n"
            "    python3 solution_data_query.py "
            "--collection-name Gas%%20Zones --property-name Fuel%%20Price\n\n"
            "  Chain with upload and cleanup:\n"
            "    python3 solution_data_query.py "
            "--collection-name \"Gas Zones\" --property-name Price\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Study/Solutions --pattern '**/*.parquet'\n"
            "    python3 cleanup_files.py -p output_path -pt '*_filtered_sols_data_*'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-cn", "--collection-name",
        nargs="+",
        required=True,
        help="Required filter for CollectionName (case-insensitive, supports wildcards: * and ?).",
    )
    parser.add_argument(
        "-pn", "--property-name",
        nargs="+",
        required=True,
        help="Required filter for PropertyName (case-insensitive, supports wildcards: * and ?).",
    )
    parser.add_argument(
        "-fn", "--parquet-name",
        default=None,
        help="Optional output parquet file name without extension (default: slug from collection+property filters).",
    )
    parser.add_argument(
        "-sd", "--start-date",
        default=None,
        help="Optional start date filter (inclusive). Format: YYYY-MM-DD. Filters rows where StartDate >= value.",
    )
    parser.add_argument(
        "-ed", "--end-date",
        default=None,
        help="Optional end date filter (inclusive). Format: YYYY-MM-DD. Filters rows where EndDate <= value.",
    )
    parser.add_argument(
        "-on", "--object-name",
        nargs="+",
        default=[],
        help="Optional filter for ObjectName (maps to ChildObjectName, case-insensitive, supports wildcards: * and ?).",
    )
    parser.add_argument(
        "-cat", "--category-name",
        nargs="+",
        default=[],
        help="Optional filter for CategoryName (maps to ChildObjectCategoryName, case-insensitive, supports wildcards: * and ?).",
    )

    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")

    args = parser.parse_args()
    _decode_cli_args(args)

    if args.start_date and not _validate_date_arg(args.start_date, "--start-date"):
        return 1
    if args.end_date and not _validate_date_arg(args.end_date, "--end-date"):
        return 1

    print(f"[OK] Args interpreted: {args}")

    worker = SolutionDataQueryWorker(
        output_path=OUTPUT_PATH,
        directory_map_path=DIRECTORY_MAP_PATH,
    )
    return worker.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
