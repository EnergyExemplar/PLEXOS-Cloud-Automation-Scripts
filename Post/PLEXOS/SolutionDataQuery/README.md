# SolutionDataQuery – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Builds a filtered joined solution dataset from model parquet outputs and stages the result into `output_path` for automatic platform upload at the end of a simulation. The script resolves the model parquet folder from the directory mapping JSON (uses the first model with a ParquetPath), joins FullKeyInfo + data + Period parquet files in DuckDB, and writes one compressed output parquet file.

This is a **focused script** — it extracts and joins solution data only. Chain with [UploadToDataHub](../UploadToDataHub/) to push results to DataHub.

### Key Features

- Automatically uses the first model with ParquetPath from directory mapping
- Case-insensitive matching for all filters (Collection, Property, Object, Category)
- Wildcard support (`*` and `?`) for Collection, Property, Object, and Category filters
- Multiple values supported for all filters
- URL decoding for arguments with spaces (e.g., `%20` → space)
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **After this script:** [UploadToDataHub](../UploadToDataHub/) — upload staged files to a specific DataHub path
- **After upload (optional):** [CleanupFiles](../CleanupFiles/) — remove staged output folders if no longer needed

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-cn, --collection-name` | Yes | — | Filter for `CollectionName` (case-insensitive, supports wildcards `*` and `?`). Pass one or more values after a single flag. Example: `'Gas Zones'` or `'*Zones' '*Demands'` |
| `-pn, --property-name` | Yes | — | Filter for `PropertyName` (case-insensitive, supports wildcards `*` and `?`). Pass one or more values after a single flag. Example: `Price` or `Price Demand '*Flow*'` |
| `-fn, --parquet-name` | No | `SolsData` | Output parquet file name without `.parquet` extension. Defaults to `SolsData`. Must be a plain filename — absolute paths or values containing `/` or `\` are rejected with `[FAIL]` and the script exits non-zero. |
| `-sd, --start-date` | No | — | Inclusive start date filter. Format: `YYYY-MM-DD` (e.g. `2024-01-31`). Filters rows where `StartDate >= value`. StartDate in the parquet files is a timestamp; the filter compares against the date portion only. |
| `-ed, --end-date` | No | — | Inclusive end date filter. Format: `YYYY-MM-DD` (e.g. `2024-12-31`). Filters rows where `EndDate <= value`. EndDate in the parquet files is a timestamp; the filter compares against the date portion only. |
| `-on, --object-name` | No | `[]` | Filter for `ObjectName` (case-insensitive, supports wildcards, maps to `ChildObjectName`). Pass one or more values after a single flag. Example: `'*Texas*' Alberta` |
| `-cat, --category-name` | No | `[]` | Filter for `CategoryName` (case-insensitive, supports wildcards, maps to `ChildObjectCategoryName`). Pass one or more values after a single flag. Example: `'*Hubs' '*Zones'` |


---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|----------|-------------|
| `output_path` | Working directory where staged files are written for platform artifact upload |
| `directory_map_path` | Primary path to the directory mapping JSON containing model `Name`, `Id`, and `ParquetPath`. Falls back to `/simulation/splits/directorymapping.json` for distributed runs. |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Extract and upload filtered solution data

```json
[
  {
    "Name": "Build filtered solution parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Project/Study/solution_data_query.py",
        "Version": null
      }
    ],
    "Arguments": "python3 solution_data_query.py --collection-name 'Gas%20Zones' --property-name Price",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload solution data to DataHub",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Project/Study/upload_to_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Solutions -p '*_filtered_*/**'",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

---

## Example Commands

```bash
# Required filters only
python3 solution_data_query.py --collection-name "Gas Zones" --property-name Price

# Multiple values
python3 solution_data_query.py --collection-name "Gas Zones" "Gas Demands" --property-name Price Demand

# Wildcard patterns with optional object/category filters
python3 solution_data_query.py --collection-name "*Zones" --property-name "*Price*" --object-name "*Texas*" Alberta --category-name "*Hubs"

# Date range filters (start, end, or both)
python3 solution_data_query.py --collection-name "Gas Zones" --property-name Price --start-date 2024-01-01
python3 solution_data_query.py --collection-name "Gas Zones" --property-name Price --start-date 2024-01-01 --end-date 2024-12-31

# Explicit output parquet file name
python3 solution_data_query.py --collection-name "Gas Zones" --property-name Price --parquet-name my_gas_prices

# URL-encoded fallback when your task runner splits arguments on spaces
python3 solution_data_query.py --collection-name Gas%20Zones --property-name Fuel%20Price
```

---

## Expected Behaviour

### Success

1. Script starts and validates required environment variables.
2. Resolves the mapping file from `directory_map_path`; falls back to `/simulation/splits/directorymapping.json` for distributed runs.
3. Reads the mapping file and uses the first model with a ParquetPath.
4. Validates the resolved source `ParquetPath` exists and is a directory.
5. Builds SQL filters from required and optional CLI arguments.
6. Reads source parquet files:
  - `fullkeyinfo/FullKeyInfo.parquet`
  - `period/Period.parquet`
  - `data/dataFileId=*/*.parquet`
7. Joins datasets in DuckDB and exports one parquet file:
  - `{output_path}/{MODEL_NAME}_filtered_sols_data_{YYYYMMDD_HHMMSS}/parquetSolsData_{slug}.parquet` (auto-generated name)
  - or `{output_path}/{MODEL_NAME}_filtered_sols_data_{YYYYMMDD_HHMMSS}/{parquet_name}.parquet` (when `--parquet-name` is provided)
8. Logs output path, size, timing, and row count summary.
9. Exits with code `0` when output is written and contains rows.

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| Missing required environment variable (`output_path`, `directory_map_path`) | 1 | Ensure the variable is set in the execution environment |
| Missing required arguments (`--collection-name`, `--property-name`) | 2 | Provide the required filters |
JSON |
| No entry with ParquetPath found in mapping | 1 | Ensure at least one model entry has a ParquetPath in the mapping JSON |
| Mapping entry missing `Id`, `Name`, or `ParquetPath` | 1 | Fix the model entry in the mapping JSON |
| Source parquet folder missing or invalid | 1 | Verify mapped `ParquetPath` is correct and accessible |
| Expected parquet structure missing (`fullkeyinfo`, `period`, `data`) | 1 | Verify parquet export structure in the model path |
| Join/export failure or zero rows in output | 1 | Review filter values and source parquet content |
