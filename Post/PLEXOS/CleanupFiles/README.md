# Cleanup Files – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Deletes files or folders matching a glob pattern from a specified path. Use this script to clean up temporary data after upload or between processing steps in your automation workflow.

This is a **focused script** — it does one thing only. Chain it as the final step after conversion and upload tasks to remove files you no longer need.

### Key Features

- Recursive or non-recursive file/folder matching via glob pattern
- Dry-run mode to preview deletions without making changes
- Prints each deleted item with its size and a deletion summary
- Safe to run with `ContinueOnError: true` — a clean exit even if no matches are found
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **After this script:** None — usually the last step in a simulation or any subsequent task that runs after the cleanup is complete.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-p, --path` | Yes | — | Root directory to search. Pass `output_path` to use the `output_path` env var. |
| `-pt, --pattern` | No | `**/*` | Glob pattern to match files/folders (e.g. `*.csv`, `Analysis_*`). Defaults to all files including subdirectories. |
| `-r, --recursive` | No | `False` | Search subdirectories recursively. |
| `--dry-run` | No | `False` | Preview what would be deleted without actually deleting. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `output_path` | Resolved when `-p output_path` is passed |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
# Standard library only — no additional packages required
```

---

## Chaining This Script

### Chain 1 — Convert  Upload  Cleanup CSV files

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
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Cleanup source CSV files",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/cleanup_files.py", "Version": null }
    ],
    "Arguments": "python3 cleanup_files.py -p output_path -pt *.csv -r",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  }
]
```

### Chain 2 — Time series analysis  Upload  Cleanup analysis folders

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
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Analysis -p MyStudy_*/**",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Cleanup analysis folders",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/cleanup_files.py", "Version": null }
    ],
    "Arguments": "python3 cleanup_files.py -p output_path -pt MyStudy_* -r",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  }
]
```

---

## Example Commands

```bash
# Delete all CSV files recursively under output_path
python3 cleanup_files.py -p output_path -pt '*.csv' -r

# Preview what would be deleted without making changes (dry run)
python3 cleanup_files.py -p output_path -pt '*.csv' -r --dry-run

# Delete timestamped analysis folders matching a prefix
python3 cleanup_files.py -p output_path -pt 'ForecastCheck_*' -r

# Delete files in a specific sub-folder (non-recursive)
python3 cleanup_files.py -p '/output/TimeSeries' -pt '*.csv'
```

---

## Expected Behaviour

### Success

1. Resolves the target path (env var or explicit path).
2. Finds all files and folders matching the pattern (recursively if `-r` is set).
3. Deletes each match and prints its path and size.
4. Prints a deletion summary.
5. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| Target path does not exist | 1 | Check the `-p` argument |
| No matches found | 0 | Not an error — script exits cleanly |
| Deletion permission error | 1 | Check file permissions |
