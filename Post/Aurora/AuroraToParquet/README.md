# Aurora To Parquet – README

## Overview

**Type:** Post
**Platform:** Aurora
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Converts all tables in an Aurora `.xdb` solution database to compressed Parquet files, appending a `SimulationId` column to each. This makes Aurora results available in a columnar format suitable for downstream analytics, dashboards, or DataHub upload.

This is a **focused script** — it does conversion only. Pair it with an upload script to push results to DataHub.

### Key Features

- Exports every table from the Aurora `.xdb` SQLite database to individual Parquet files
- Appends `SimulationId` to each table for traceability across simulation runs
- Reads the `.xdb` directly via SQLite read-only mode — no copy needed, no extra storage consumed
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** *(none — runs immediately after Aurora engine)*
- **After this script:** [UploadToDataHub](../../PLEXOS/UploadToDataHub/) — upload the generated Parquet files to DataHub

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--xdb-filename` | No | `<simulation_id>.xdb` | Name of the `.xdb` file to convert (filename only, not a path) |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `simulation_id` | Identifies the current simulation run; used to locate the `.xdb` file and stamp each Parquet row (required) |
| `simulation_path` | Root path for study files — location of the `.xdb` database (read-only in post tasks) |
| `output_path` | Working directory — Parquet files are written to `<output_path>/parquet/` |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Convert Aurora results then upload to DataHub

```json
[
  {
    "Name": "Convert Aurora solution to Parquet",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/aurora_to_parquet.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 aurora_to_parquet.py",
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
# Default — converts <simulation_id>.xdb
python3 aurora_to_parquet.py

# Explicit .xdb filename
python3 aurora_to_parquet.py --xdb-filename my_model.xdb
```

---

## Expected Behaviour

### Success

1. Script starts and validates that the `.xdb` file exists in `simulation_path`.
2. Attaches the database via DuckDB in read-only mode (no lock/journal files created on the read-only mount).
3. Discovers all tables and exports each to `<output_path>/parquet/<table_name>.parquet`.
4. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `simulation_id` env var missing | 1 | Ensure the variable is set in the execution environment |
| `.xdb` file not found | 1 | Check `simulation_path` and `--xdb-filename` argument |
| DuckDB / SQLite error | 1 | Check `.xdb` file integrity |
