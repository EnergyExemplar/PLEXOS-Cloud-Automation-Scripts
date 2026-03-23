# CSV to Parquet Conversion – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Converts all CSV files under a folder to Parquet format in-place using DuckDB with ZSTD compression. Deletes each source CSV only after a row-count validation confirms the conversion was successful.

This is a **focused script** — it does one thing only. Pair it with [UploadToDataHub](../UploadToDataHub/) if you need to push the resulting Parquet files to a specific DataHub path.

### Key Features

- Recursive CSV discovery across sub-directories
- Thread-safe parallel conversion with configurable workers
- Row count validation before CSV deletion (prevents data loss)
- Configurable Parquet compression: `zstd` (default), `gzip`, `snappy`, or `none`
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **After this script:** [UploadToDataHub](../UploadToDataHub/) — upload the converted Parquet files to DataHub

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-r, --root-folder` | Yes | — | Folder containing CSV files. Pass `output_path` to resolve the `output_path` env var. |
| `-w, --workers` | No | `3` | Number of parallel conversion workers. |
| `-c, --compression` | No | `zstd` | Parquet compression algorithm: `zstd`, `gzip`, `snappy`, or `none`. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `output_path` | Used when `-r output_path` is passed |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
```

---

## Chaining This Script

### Chain 1 — Convert outputs then upload to DataHub

```json
[
  {
    "Name": "Convert CSV outputs to Parquet",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/convert_csv_to_parquet.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 convert_csv_to_parquet.py -r output_path",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload Parquet files to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results -p **/*.parquet",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

---

## Example Commands

```bash
# Convert all CSV files in output_path (default 3 workers, ZSTD compression)
python3 convert_csv_to_parquet.py -r output_path

# Use more parallel workers to speed up conversion
python3 convert_csv_to_parquet.py -r output_path -w 8

# Use gzip compression instead of the default ZSTD
python3 convert_csv_to_parquet.py -r output_path -c 'gzip'

# Convert a specific sub-folder only
python3 convert_csv_to_parquet.py -r '/output/TimeSeries' -w 4
```

---

## Expected Behaviour

### Success

1. Recursively finds all `.csv` files under the specified folder.
2. Converts each in parallel using DuckDB with the specified compression (default: ZSTD).
3. Validates row counts match before deleting the source CSV.
4. Prints a conversion summary.
5. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `output_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| Folder does not exist | 1 | Check the `-r` argument |
| Row count mismatch on a file | 0* | Source CSV is kept; conversion continues for remaining files |
| Any conversion failure | 1 | Check logs for the specific file error |

\* The overall exit code is `1` if any file fails conversion.
