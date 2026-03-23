# Upload to DataHub – README

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
- URL-encoding support for paths containing spaces
- Safe to chain after any script that writes to `output_path`
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** Any task that produces files you want to store in DataHub. This script is focused on uploading — chain it wherever an upload is needed.
- **After this script:** None — or any post-simulation task that depends on the uploaded files being available in DataHub.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-l, --local-folder` | Yes | — | Local folder to upload from. Pass `output_path` to use the `output_path` env var. URL-encode spaces as `%20`. |
| `-r, --remote-path` | Yes | — | DataHub destination path. URL-encode spaces as `%20`. |
| `-p, --pattern` | No | `**/*` | Glob pattern(s) for files to include. Accepts one or more patterns after a single flag. Example: `-p '**/*.parquet' '**/*.csv'` |
| `-v, --versioned` | No | `true` | Create a new DataHub version on upload. |

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
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results -p **/*.parquet",
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
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Analysis -p MyStudy_*/**",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

---

## Example Commands

```bash
# Upload entire output folder to DataHub
python3 upload_to_datahub.py -l output_path -r 'Project/Study/Results'

# Upload only Parquet files
python3 upload_to_datahub.py -l output_path -r 'Project/Study/Results' -p '**/*.parquet'

# Upload multiple file types using multi-pattern
python3 upload_to_datahub.py -l output_path -r 'Project/Study/Results' -p '**/*.parquet' '**/*.csv'

# Upload without creating a new DataHub version (overwrites existing)
python3 upload_to_datahub.py -l output_path -r 'Project/Study/Results' -v false

# Upload analysis output folder matched by prefix pattern
python3 upload_to_datahub.py -l output_path -r 'Project/Study/Analysis' -p 'MyStudy_*/**'

# Remote path with spaces — URL-encode each space as %20
python3 upload_to_datahub.py -l output_path -r 'Kavitha/Study%203/Output%20Folder'
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
