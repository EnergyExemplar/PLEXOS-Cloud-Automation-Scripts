# UploadSolutionZipToDatahub – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Automatically reads the first model entry from the directory mapping JSON, then uploads all matching ZIP files from that model's solution path to DataHub. The remote destination path is constructed automatically as `{remote-path}/{execution_id}/{model_id}`.

This is a **focused script** — upload only. No compression or conversion.
Run a separate task (for example, a custom compression script) to create ZIP files before using this uploader.

### Key Features

- Model resolved automatically from the first entry with a `Path` field in the directory mapping JSON
- Automatic remote path construction: `{remote-path}/{execution_id}/{model_id}`
- Configurable glob pattern (default: `**/*.zip`)
- Upload response validation — reports per-file success, skip (identical), and failure
- Files already identical to the remote are treated as success (not failures)
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** Any script or task that creates ZIP files in the model's solution path
- **After this script:** [CleanupFiles](../CleanupFiles/) — remove staged ZIP files after upload

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-r, --remote-path` | Yes | — | Base DataHub destination path. Execution ID and model ID are appended automatically: `{remote-path}/{execution_id}/{model_id}`. |
| `-p, --pattern` | No | `**/*.zip` | One or more glob patterns for files to upload. Pass multiple values space-separated after a single flag: `-p "*.zip" "**/*.zip"`. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|----------|-------------|
| `cloud_cli_path` | **Required.** Path to the Cloud CLI executable |
| `execution_id` | **Required.** Platform execution ID — appended to the remote path to uniquely identify this run |
| `directory_map_path` | Path to the directory mapping JSON (falls back to `/simulation/splits/directorymapping.json`) |
| `simulation_id` | Logged for traceability (optional) |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Upload ZIP files to DataHub

```json
[
  {
    "Name": "Upload ZIP solution files to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_solution_zip_to_datahub.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 upload_solution_zip_to_datahub.py --remote-path Eagles/ZipSolutions",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  }
]
```

### Chain 2 — Upload ZIP files then clean up

```json
[
  {
    "Name": "Upload ZIP solution files to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_solution_zip_to_datahub.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 upload_solution_zip_to_datahub.py --remote-path Eagles/ZipSolutions",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Clean up ZIP files",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/cleanup_files.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 cleanup_files.py --path /output --pattern '*.zip'",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

---

## Output Format

This script produces no output files. All upload results are written to the task log with `[OK]`, `[FAIL]`, or `[WARN]` prefixes. The upload summary reports:

- Number of files uploaded successfully
- Number of files skipped (already identical to remote)
- Number of files that failed, with per-file failure reasons

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All files uploaded successfully |
| `1` | One or more files failed to upload, or a configuration error occurred |
| `130` | Interrupted by user (Ctrl+C) |

### Failure Conditions

| Condition | Exit Code |
|-----------|-----------|
| `cloud_cli_path` environment variable not set | `1` (at startup) |
| `execution_id` environment variable not set | `1` (at startup) |
| Directory mapping file missing or unreadable | `1` |
| Directory mapping JSON empty or has no entry with a non-empty `Path` | `1` |
| Selected mapping entry missing `Id` or `Path` field | `1` |
| Upload response contains failed files | `1` |
| Interrupted by Ctrl+C | `130` |
