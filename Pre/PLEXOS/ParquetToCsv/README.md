# Parquet to CSV Conversion – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Converts all Parquet files under a folder to CSV format in-place using DuckDB. Deletes each source Parquet only after a row-count validation confirms the conversion was successful.

This is a **focused script** — it does one thing only. If your Parquet files are in DataHub, download them first using the Cloud CLI, then pass the local folder to this script.

### Key Features

- Recursive Parquet discovery across sub-directories
- Thread-safe parallel conversion with configurable workers
- Row count validation before Parquet deletion (prevents data loss)
- SQL path escaping for files with special characters
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** Use the Cloud CLI to download Parquet files from DataHub (see Chaining section)

---

## Script Location

```
Pre/PLEXOS/ParquetToCsv/
├── convert_parquet_to_csv.py    # Main script
└── README.md                    # This file
```

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-d, --folder` | Yes | — | Folder containing Parquet files. Pass `simulation_path` to resolve the `simulation_path` env var |
| `-w, --workers` | No | `3` | Number of parallel conversion workers |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `simulation_path` | Used when `-d simulation_path` is passed |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Download from DataHub then convert

Use the Cloud CLI as a Pre-simulation task to download files, then convert:

```json
[
  {
    "Name": "Download Parquet inputs from DataHub",
    "TaskType": "Pre",
    "Arguments": "plexos-cloud datahub download --remote-path 'Project/Study/inputs/**' --local-folder /simulation/inputs",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Convert Parquet inputs to CSV",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/convert_parquet_to_csv.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 convert_parquet_to_csv.py -d /simulation/inputs",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Use the combined script instead

If you always download and convert together, use [ParquetToCsvConversion](../ParquetToCsvConversion/) which handles both steps in a single task.

---

## Example Task Definition

```json
{
  "Name": "Convert Parquet inputs to CSV",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/convert_parquet_to_csv.py", "Version": null },
    { "Path": "Project/Study/requirements.txt", "Version": null }
  ],
  "Arguments": "python3 convert_parquet_to_csv.py -d simulation_path -w 4",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

---

## Expected Behaviour

### Success

1. Recursively finds all `.parquet` files under the specified folder.
2. Converts each in parallel using DuckDB.
3. Validates row counts match before deleting the source Parquet.
4. Prints a conversion summary.
5. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `simulation_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| Folder does not exist | 1 | Check the `-d` argument |
| Row count mismatch on a file | 0* | Source Parquet is kept; conversion continues for remaining files |
| Any conversion failure | 1 | Check logs for the specific file error |

\* The overall exit code is `1` if any file fails conversion.
