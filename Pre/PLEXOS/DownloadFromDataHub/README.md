# Download From DataHub – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Downloads one or more files or folders from DataHub to a local directory before the simulation engine starts. Supports glob patterns to download entire folder trees in a single task.

### Key Features

- Glob pattern support for downloading entire folder trees in a single task
- URL-encoding support for paths containing spaces
- Multiple `-r` flags to download from several DataHub locations in one call
- Configurable local destination (simulation or output directory)
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **After this script:** Any pre-simulation task that reads or processes the downloaded files

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-r, --remote-path` | Yes | — | DataHub path to download. Repeat for multiple paths. Supports glob patterns. URL-encode spaces as `%20`. |
| `-l, --local-folder` | No | `output_path` env var | Local destination folder. Pass `simulation_path` to resolve the `simulation_path` env var. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the PLEXOS Cloud CLI executable (required) |
| `output_path` | Default local destination when `-l` is omitted |
| `simulation_path` | Used when `-l simulation_path` is passed |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
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

## Example Commands

```bash
# Simple path — download entire folder tree to simulation_path
python3 download_from_datahub.py -r 'Project/Study/TimeSeries/**' -l simulation_path

# Path with spaces — URL-encode each space as %20
# (quoting alone is not reliable in the task runner Arguments field)
python3 download_from_datahub.py -r 'Kavitha/Study3/TSComparison/Gas%20Demand%20Forecast%20NRT%205min.csv' -l simulation_path

# Download to a specific sub-folder inside output_path
python3 download_from_datahub.py -r 'Kavitha/Study3/TSComparison/Gas%20Demand%20Forecast%20NRT%205min.csv' -l '{output_path}/Results'

# Multiple remote paths — repeat -r for each path
python3 download_from_datahub.py -r 'Project/Study/Baseline/forecast.csv' -r 'Project/Study/Baseline/actuals.csv' -l simulation_path
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
|---|---|---|
| `cloud_cli_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| `-r` argument not provided | 1 | Supply at least one `-r` argument |
| `simulation_path` env var missing (when used) | 1 | Ensure the variable is set in the execution environment |
| No files found after download | 1 | Check the remote path and that files exist in DataHub |
| Download error (network, auth, path) | 1 | Check logs for the specific error message |
