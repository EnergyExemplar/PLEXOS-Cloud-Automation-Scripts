# Download From DataHub – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Downloads one or more files or folders from DataHub to a local directory before the simulation engine starts. Supports glob patterns to download entire folder trees in a single task.

**Use Cases:**
- Download Parquet or CSV input files from DataHub before conversion or analysis
- Pull baseline reference files for time-series comparison
- Fetch study inputs stored in DataHub prior to simulation

---

## Script Location

```
Pre/PLEXOS/DownloadFromDataHub/
├── download_from_datahub.py    # Main script
└── README.md                   # This file
```

---

## Arguments

### Optional Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `-r, --remote-path` | DataHub path to download. Repeat for multiple paths. Supports glob patterns. Omit if using `datahub_remote_paths` env var. | `-r Project/Study/TimeSeries/**` |
| `-l, --local-folder` | Local destination folder. Pass `simulation_path` or `output_path` to resolve the respective env var. Falls back to `datahub_local_folder` env var, then `output_path` env var. | `-l simulation_path` |

> **Note:** At least one of `-r` or the `datahub_remote_paths` env var must be provided.

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Required | Description |
|----------|----------|-------------|
| `cloud_cli_path` | Yes | Full path to the PLEXOS Cloud CLI executable |
| `output_path` | No | Default local destination when `-l` is omitted and `datahub_local_folder` is not set |
| `simulation_path` | No | Used when `-l simulation_path` is passed |
| `datahub_remote_paths` | No | Semicolon-separated list of DataHub paths to download. **Use this instead of `-r` for paths that contain spaces.** |
| `datahub_local_folder` | No | Local destination folder. **Use this instead of `-l` for paths that contain spaces.** |

---

## Passing Paths That Contain Spaces

The cloud task runner splits the `Arguments` field on whitespace before passing tokens to Python. Quoting (single or double) in the `Arguments` field is **not** reliably handled — a path like `Gas Demand Forecast NRT 5min.csv` will be truncated to `Gas` at the first space.

Use one of two safe approaches:

### Option A — URL-encode spaces in the Arguments field

Replace each space with `%20`. No quoting required.

```json
"Arguments": "python3 download_from_datahub.py -r Project/Study/Gas%20Demand%20Forecast%20NRT%205min.csv -l /output/Results"
```

### Option B — Set env vars in the task configuration (recommended)

Leave `Arguments` minimal and pass the full path (including spaces) via env vars, which are never space-split by the task runner.

```json
"Arguments": "python3 download_from_datahub.py",
"EnvironmentVariables": {
  "datahub_remote_paths": "Kavitha/Study3/TSComparison/Gas Demand Forecast NRT 5min.csv",
  "datahub_local_folder": "/output/Results"
}
```

For multiple paths, separate them with `;`:

```
datahub_remote_paths = Project/Study/file one.csv;Project/Study/file two.parquet
```

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
```

---

## Example Task Definition

### Simple path (no spaces)

```json
{
  "Name": "Download TimeSeries inputs from DataHub",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/download_from_datahub.py", "Version": null },
    { "Path": "Project/Study/requirements.txt", "Version": null }
  ],
  "Arguments": "python3 download_from_datahub.py -r Project/Study/TimeSeries/** -l simulation_path",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

### Path with spaces — Option A: URL-encode

```json
{
  "Name": "Download Gas Demand Forecast from DataHub",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/download_from_datahub.py", "Version": null },
    { "Path": "Project/Study/requirements.txt", "Version": null }
  ],
  "Arguments": "python3 download_from_datahub.py -r Kavitha/Study3/TSComparison/Gas%20Demand%20Forecast%20NRT%205min.csv -l /output/Results",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

### Path with spaces — Option B: env vars (recommended)

```json
{
  "Name": "Download Gas Demand Forecast from DataHub",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/download_from_datahub.py", "Version": null },
    { "Path": "Project/Study/requirements.txt", "Version": null }
  ],
  "Arguments": "python3 download_from_datahub.py",
  "EnvironmentVariables": {
    "datahub_remote_paths": "Kavitha/Study3/TSComparison/Gas Demand Forecast NRT 5min.csv",
    "datahub_local_folder": "/output/Results"
  },
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

---

## Chaining This Script

### Chain 1 — Download then convert Parquet to CSV

```json
[
  {
    "Name": "Download Parquet inputs from DataHub",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/download_from_datahub.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 download_from_datahub.py -r Project/Study/inputs/** -l simulation_path",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Convert Parquet inputs to CSV",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/convert_parquet_to_csv.py", "Version": null }
    ],
    "Arguments": "python3 convert_parquet_to_csv.py -d simulation_path",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Download specific files for time-series comparison

```json
[
  {  
    "Name": "Download baseline files from DataHub",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/download_from_datahub.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 download_from_datahub.py -r Project/Study/Baseline/forecast.csv -r Project/Study/Baseline/actuals.csv -l simulation_path",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  }
]
```

---

## Expected Behaviour

### Success

1. Connects to the DataHub using `cloud_cli_path`.
2. Downloads all files matching the specified remote path(s) to the local folder.
3. Prints a summary listing every downloaded file with its size.
4. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| `cloud_cli_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| `simulation_path` env var missing (when used) | 1 | Ensure the variable is set in the execution environment |
| No files found after download | 1 | Check the remote path and that files exist in DataHub |
| Download error (network, auth, path) | 1 | Check logs for the specific error message |

---

## Related Scripts

- **After this script:** [ParquetToCsv](../ParquetToCsv/) — convert downloaded Parquet files to CSV
- **After this script:** [Post/TimeSeriesComparison](../../../Post/PLEXOS/TimeSeriesComparison/) — compare downloaded files against simulation results
