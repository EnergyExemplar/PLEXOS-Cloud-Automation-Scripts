# WriteReportedProperties – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Exports PLEXOS reported property key information to a Parquet file by querying the
pre-configured DuckDB solution database. The script joins `fullkeyinfo`, `object`, and
`category` views to produce a flat table of reported properties enriched with child
and parent object category names. The output Parquet file is written to `output_path`
for automatic platform upload.

This is a **focused script** — Parquet export only. No DataHub upload.
Chain with [UploadToDataHub](../UploadToDataHub/) if you need to push results to DataHub
immediately after export.

> **Prerequisite:** [ConfigureDuckDbViews](../ConfigureDuckDbViews/) must run before this
> script so the `fullkeyinfo`, `object`, and `category` views exist in `duck_db_path`.

### Key Features

- Queries DuckDB views without re-executing the joining query twice (preview reads from the already-written Parquet)
- Path traversal protection — `--output-file` rejects absolute paths or values containing path separators
- Output directory is created automatically if it does not exist
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** [ConfigureDuckDbViews](../ConfigureDuckDbViews/) — creates the DuckDB views used by this script
- **After this script:** [UploadToDataHub](../UploadToDataHub/) — upload the Parquet output to a specific DataHub path
- **After upload (optional):** [CleanupFiles](../CleanupFiles/) — remove staged output files if no longer needed

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-o, --output-file` | No | `flattened_data.parquet` | Name of output Parquet file. Must be a plain filename — absolute paths or values containing `/` or `\` are rejected with `[FAIL]` and the script exits non-zero. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|----------|-------------|
| `duck_db_path` | **Required.** Path to the DuckDB solution database containing the `fullkeyinfo`, `object`, and `category` views (created by ConfigureDuckDbViews) |
| `output_path` | Working directory where Parquet output is written for automatic platform upload (default: `/output`) |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline. Always run ConfigureDuckDbViews first.

### Chain 1 — Configure views and export reported properties

```json
[
  {
    "Name": "Configure DuckDB views",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/configure_duck_db_views.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 configure_duck_db_views.py",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Export reported properties to Parquet",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/write_reported_properties.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 write_reported_properties.py",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Configure views, export properties, upload to DataHub, and clean up

```json
[
  {
    "Name": "Configure DuckDB views",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/configure_duck_db_views.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 configure_duck_db_views.py",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Export reported properties to Parquet",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/write_reported_properties.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 write_reported_properties.py --output-file my_properties.parquet",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Upload Parquet to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py --local-folder output_path --remote-path MyProject/Properties -p *.parquet",
    "ContinueOnError": false,
    "ExecutionOrder": 3
  },
  {
    "Name": "Clean up staged Parquet files",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/cleanup_files.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 cleanup_files.py --path /output --pattern *.parquet",
    "ContinueOnError": true,
    "ExecutionOrder": 4
  }
]
```

---

## Output Format

The output Parquet file contains one row per reported property key with the following columns:

| Column | Description |
|--------|-------------|
| `SeriesId` | Unique identifier for the data series |
| `DataFileId` | Identifier for the associated data file |
| `ChildObjectName` | Name of the child object |
| `ChildObjectCategoryName` | Category name of the child object (`NULL` if the object has no category, e.g. the System object) |
| `ParentObjectCategoryName` | Category name of the parent object (`NULL` if the object has no category, e.g. the System object) |
| `PropertyName` | Name of the reported property |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Export completed successfully |
| `1` | Export failed — see `[FAIL]` log lines for details |
| `130` | Interrupted by user (Ctrl+C) |

### Failure Conditions

| Condition | Exit Code |
|-----------|-----------|
| `duck_db_path` environment variable not set | `1` (at startup) |
| `--output-file` contains path separators or is an absolute path | `1` |
| Output directory cannot be created | `1` |
| DuckDB connection or query error | `1` |
| Views (`fullkeyinfo`, `object`, `category`) not found in database | `1` |
| Interrupted by Ctrl+C | `130` |
