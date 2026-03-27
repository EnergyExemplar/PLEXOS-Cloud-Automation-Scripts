# SearchAndUpload – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Searches for a file by name (or glob pattern), moves it to `output_path`, converts it to Parquet if it is a CSV, and optionally uploads it to DataHub. Also searches inside ZIP archives found in each search path.

This is a **focused script** — file discovery, staging, conversion, and optional DataHub upload in one step.

### Key Features

- Supports glob patterns for the filename (e.g. `report_*.csv`, `*.parquet`)
- Recursive filesystem search under the specified (or default) search path(s)
- Also searches entry names inside every `*.zip` archive found in the search paths
- Default search order when `--path` is omitted: `output_path` first, then `simulation_path`; same fallback applies when `--path` is given but the file is absent there
- Files in `simulation_path` (read-only mount) are **copied**, not moved — original is preserved
- CSV files are automatically converted to Parquet (ZSTD) after staging; row-count validated before source deletion
- Optional `--upload-path` uploads the staged (and converted) file to a DataHub folder in one command
- Proper error exit codes for CI/CD integration

### Related Scripts

 > Scripts commonly chained with this one.

 - **After this script:**
   - [UploadToDataHub](../UploadToDataHub/) — only when a separate upload step is preferred.
   - [CleanupFiles](../CleanupFiles/) — recommended to remove staged files from `output_path` after upload, especially in chained tasks.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-f, --file-name` | Yes | — | Filename or glob pattern to search for (e.g. `results.csv`, `report_*.csv`). Also matched against entry names inside ZIP archives. URL-encode spaces as `%20`. |
| `-p, --path` | No | — | Primary directory to search. When omitted (or if the file is not found there), `output_path` is searched next, then `simulation_path`. |
| `-u, --upload-path` | No | — | DataHub destination folder for the staged file (e.g. `Project/Study/Results`). When provided, the file is uploaded to DataHub after staging/conversion. Requires `cloud_cli_path` env var. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `output_path` | Destination directory; found files are moved (or copied) here (required) |
| `simulation_path` | Fallback search location when `--path` is omitted (optional, defaults to `/simulation`) |
| `cloud_cli_path` | Path to the Cloud CLI executable — required only when `--upload-path` is passed |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
eecloud
```

---

## Chaining This Script

### Chain 1 — Find, convert, and upload in one step

```json
[
  {
    "Name": "Search, convert, and upload results CSV",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/search_and_upload.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 search_and_upload.py -f results.csv -u Project/Study/Results",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Cleanup staged files after upload",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/cleanup_files.py", "Version": null }
    ],
    "Arguments": "python3 cleanup_files.py -d output_path -p '*.parquet'",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Stage only (no upload), then upload separately

```json
[
  {
    "Name": "Search and stage results CSV",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/search_and_upload.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 search_and_upload.py -f results.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload staged Parquet file to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results -p '*.parquet'",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  },
  {
    "Name": "Cleanup staged files after upload",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/cleanup_files.py", "Version": null }
    ],
    "Arguments": "python3 cleanup_files.py -d output_path -p '*.parquet'",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  }
]
```

---

## Example Commands

```bash
# Search default paths (output_path first, then simulation_path)
python3 search_and_upload.py -f results.csv

# Search a specific directory
python3 search_and_upload.py -f results.csv -p /simulation/MyStudy

# Find, convert CSV to Parquet, and upload to DataHub in one step
python3 search_and_upload.py -f results.csv -u Project/Study/Results

# Glob pattern search — first match wins
python3 search_and_upload.py -f 'report_*.csv' -p /simulation/Reports

# File inside a ZIP archive — found automatically
python3 search_and_upload.py -f 'data.csv' -p /simulation/Archives

# Find a parquet file and upload (no conversion applied)
python3 search_and_upload.py -f output_data.parquet -u Project/Study/Results

# URL-encoded filename with spaces
python3 search_and_upload.py -f 'My%20Report.csv'
```

---

## Expected Behaviour

### Success

1. Parses `--file-name`, optional `--path`, and optional `--upload-path` arguments.
2. Builds the search path list: `[--path, output_path, simulation_path]` when `--path` is given; `[output_path, simulation_path]` otherwise.
3. Recursively searches the filesystem in order; stops at the first match.
4. If not found on the filesystem, searches entry names inside every `*.zip` archive in the search paths and extracts the first match to `output_path`.
5. Stages the file into `output_path`:
   - If the file is **already in** `output_path`: no move — proceeds to conversion if needed.
   - If the source is under **`simulation_path`** (read-only): copies the file; original is preserved.
   - Otherwise: moves the file.
6. If the staged file is a `.csv`:
   - Converts it to Parquet (ZSTD) using DuckDB.
   - Validates that the row count matches before deleting the source CSV.
7. If `--upload-path` is provided, uploads the staged (converted) file to the specified DataHub folder.
8. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `output_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| `cloud_cli_path` env var missing (when `--upload-path` used) | 1 | Ensure `cloud_cli_path` is set in the execution environment |
| File not found in any search path or ZIP archive | 1 | Check `--file-name` and `--path` arguments |
| File could not be moved or copied | 1 | Check file permissions and paths |
| CSV conversion fails or row count mismatches | 1 | Check CSV integrity; source CSV is preserved on mismatch |
| DataHub upload fails | 1 | Check `cloud_cli_path`, `--upload-path`, and network connectivity |
