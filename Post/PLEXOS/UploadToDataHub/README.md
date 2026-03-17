# Upload to DataHub – README

Dummy Update

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Uploads files from a local folder to a DataHub path. This is a **focused, reusable upload step** — use it as the final task in any chain that produces files you want to store in DataHub at a specific path.

> **Note:** Files written to `output_path` are automatically uploaded by the platform at the end of the simulation without this script. Use this script only when you need to upload to a *specific* DataHub path, or with a *specific* file pattern, immediately after another task completes.

### Key Features

- Configurable glob pattern to upload only specific file types or folders
- Optional DataHub versioning control
- Detailed upload summary (uploaded, skipped-identical, failed)
- Safe to chain after any script that writes to `output_path`

### Related Scripts

> Scripts commonly chained before this one.

- [CsvToParquet](../CsvToParquet/) — convert CSV outputs then upload
- [TimeSeriesComparison](../TimeSeriesComparison/) — run analysis then upload results

---

## Script Location

```
Post/PLEXOS/UploadToDataHub/
├── upload_to_datahub.py    # Main script
└── README.md               # This file
```

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-l, --local-folder` | Yes | — | Local folder to upload from. Pass `output_path` to use the `output_path` env var |
| `-r, --remote-path` | Yes | — | DataHub destination path (e.g. `Project/Study/Results`) |
| `-p, --pattern` | No | `**/*` | Glob pattern for files to include (e.g. `**/*.parquet`, `Analysis_*/**`) |
| `-v, --versioned` | No | `true` | Create a new DataHub version on upload (`true` or `false`) |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the PLEXOS Cloud CLI executable (required) |
| `output_path` | Used when `-l output_path` is passed |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
```

---

## Chaining This Script

### Chain 1 — Convert CSV outputs then upload

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
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results --pattern '**/*.parquet'",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Run time series analysis then upload results

```json
[
  {
    "Name": "Compare time series output vs baseline",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/timeseries_comparison.py", "Version": null },
      { "Path": "Project/Study/baseline.csv", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 timeseries_comparison.py -f baseline.csv:Baseline -f result.csv:Simulation -p MyStudy",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload analysis results to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Analysis --pattern 'MyStudy_*/**'",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

---

## Example Task Definition

```json
{
  "Name": "Upload results to DataHub",
  "TaskType": "Post",
  "Files": [
    { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
  ],
  "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results",
  "ContinueOnError": true,
  "ExecutionOrder": 2
}
```

---

## Expected Behaviour

### Success

1. Resolves local folder path (env var or explicit path).
2. Uploads all files matching the glob pattern to the specified DataHub path.
3. Reports per-file status: uploaded, skipped (identical), or failed.
4. Exits with code `0` if all files upload successfully or are skipped as identical.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `cloud_cli_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| `output_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| Local folder does not exist | 1 | Check the `-l` argument |
| One or more files fail to upload | 1 | Check logs; files skipped as identical are not failures |
| SDK / network error | 1 | Check connectivity and CLI path |
