# DatahubSolParquetUploader – README

## Overview

**Type:** Post  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** 2026-03-03  
**Author:** IDC Energy Exemplar

### Purpose

Uploads all `*.parquet` files for a simulation solution to DataHub. The local parquet folder
and model ID are resolved from a **directory mapping JSON** produced by the platform. The remote
folder path is built automatically as `{remote_path}/{model_id}/Solution_{YYYYMMDD_HHMMSS}`.

This is a **focused script** — upload only. Solution files are expected to already be in parquet format.

### Key Features

- Reads `directorymapping.json` from `directory_map_path` if set, otherwise falls back to
  `/simulation/splits/directorymapping.json`, and uses the first entry that contains a `ParquetPath` field.
- Builds remote folder as: `{remote_path}/{model_id}/Solution_{YYYYMMDD_HHMMSS}`.
- Uploads recursively with `glob_patterns=["**/*.parquet"]` and versioning enabled.
- Treats "identical to the remote file" results as success (no false failures on re-upload).
- Exits with code `0` on full success, `1` on any failure.

### Related Scripts

> Scripts commonly chained with this one.

- **After this script:** None — or any task that depends on the solution parquet files being available in DataHub.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-r, --remote-path` | Yes | — | Base remote folder path in DataHub. Model ID and a timestamp (`YYYYMMDD_HHMMSS`) are appended automatically. Example: `FolderName/Solutions` |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Required | Description |
|---|---|---|
| `cloud_cli_path` | ✅ | Path to the Cloud CLI executable used by `CloudSDK` |
| `directory_map_path` | ❌ | Path to directory mapping JSON. Falls back to `/simulation/splits/directorymapping.json` for split solutions |

> Expected JSON format: a list of objects where each item may contain `Id` and `ParquetPath`.
> The script uses the **first** entry that has a `ParquetPath` field.

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
```

- Python 3.11+
- Cloud CLI installed and accessible at the path given by `cloud_cli_path`

---

## Expected Behaviour

### Success

1. Reads `cloud_cli_path` from env — exits with code `1` immediately if missing.
2. Resolves the directory mapping JSON: uses `directory_map_path` if set, otherwise falls back to `/simulation/splits/directorymapping.json`.
3. Reads the first mapping entry with a `ParquetPath` field.
4. Builds remote path: `{remote_path}/{model_id}/Solution_{YYYYMMDD_HHMMSS}`.
5. Uploads all `*.parquet` files from the local path to DataHub with versioning.
6. Prints an upload summary (uploaded / skipped-identical / failed counts).
7. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `cloud_cli_path` env var missing | 1 | Set the `cloud_cli_path` environment variable |
| Mapping file not found at either path | 1 | Set `directory_map_path` or ensure `/simulation/splits/directorymapping.json` exists |
| Mapping JSON empty or malformed | 1 | Fix JSON formatting |
| No entry with `ParquetPath` in mapping | 1 | Ensure mapping JSON contains a `ParquetPath` field |
| One or more files fail to upload | 1 | Check DataHub permissions and remote path |

---

## Output Artifacts

| Artifact | DataHub Path | Format | Description |
|---|---|---|---|
| Uploaded parquet files | `{remote_path}/{model_id}/Solution_{YYYYMMDD_HHMMSS}/**/*.parquet` | Parquet | All parquet files found under `ParquetPath` from the mapping |

---

## Example Commands

```
python datahub_solparquet_uploader.py -r 'BaseModel'
```

> The model ID from the mapping and a timestamp are appended automatically.
> For example, `-r 'BaseModel'` produces a remote path like:
> `BaseModel/{model_id}/Solution_20260303_141500/`

---

## Example Task Definition

```json
{
  "Name": "Upload Solution Parquet Files to DataHub",
  "TaskType": "Post",
  "Files": [
    { "Path": "Project/Study/datahub_solparquet_uploader.py", "Version": null }
  ],
  "Arguments": "python3 datahub_solparquet_uploader.py -r BaseModel",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```