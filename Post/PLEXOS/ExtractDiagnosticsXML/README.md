# Extract Diagnostics – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Uploads PLEXOS diagnostics XML files from the simulation directory to a specific DataHub path after a simulation completes. Use this to preserve diagnostics output for debugging, auditing, or downstream analysis.

This is a **focused script** — it uploads diagnostics files only. No conversion or cleanup. Chain with other scripts for a complete workflow.

### Key Features

- Configurable glob pattern to target specific diagnostics phases (e.g. ST, MT, LT)
- Builds a structured remote path using model name, execution ID, and simulation ID
- Detailed upload summary (uploaded, skipped-identical, failed)
- URL-encoding support for paths containing spaces
- Optional DataHub versioning control
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** None — runs as an independent post task.
- **After this script:** [UploadToDataHub](../UploadToDataHub/) to upload other solution files, or [CleanupFiles](../CleanupFiles/) to clean up temporary data.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-r, --remote-path` | Yes | — | Base remote folder in DataHub. Model name, execution ID, and simulation ID are appended automatically. |
| `-pt, --pattern` | No | `**/*Diagnostics.xml` | Glob pattern for diagnostics files. Use `**/*ST*Diagnostics.xml` for ST phase only. |
| `-v, --versioned` | No | `false` | Create a new DataHub version on upload (`true` or `false`). |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the PLEXOS Cloud CLI executable (required) |
| `simulation_path` | Root path for study files — diagnostics files are read from here |
| `simulation_id` | Platform-provided simulation identifier (used in remote path) |
| `execution_id` | Platform-provided execution identifier (used in remote path) |
| `directory_map_path` | Path to directory mapping JSON — model Name is read from here (optional; falls back to `/simulation/splits/directorymapping.json`) |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Upload diagnostics then upload solution results

```json
[
  {
    "Name": "Upload diagnostics XML to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/extract_diag_xml.py", "Version": null }
    ],
    "Arguments": "python3 extract_diag_xml.py -r Project/Study/diagnostics",
    "ContinueOnError": true,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload solution files to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Upload only ST phase diagnostics

```json
[
  {
    "Name": "Upload ST diagnostics to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/extract_diag_xml.py", "Version": null }
    ],
    "Arguments": "python3 extract_diag_xml.py -r Project/Study/diagnostics -pt '**/*ST*Diagnostics.xml'",
    "ContinueOnError": true,
    "ExecutionOrder": 1
  }
]
```

---

## Example Commands

```bash
# Upload all diagnostics (model name read from directory mapping)
python3 extract_diag_xml.py -r Project/Study/diagnostics

# Upload only ST phase diagnostics
python3 extract_diag_xml.py -r Project/Study/diagnostics -pt '**/*ST*Diagnostics.xml'

# Upload with DataHub versioning enabled
python3 extract_diag_xml.py -r Project/Study/diagnostics -v true

# Remote path with spaces — URL-encode each space as %20
python3 extract_diag_xml.py -r 'Project/My%20Study/diagnostics'
```

---

## Expected Behaviour

### Success

1. Script starts and logs the local path, remote path, pattern, and versioning setting.
2. Diagnostics XML files matching the pattern are found in the simulation directory.
3. Files are uploaded to `<remote-path>/<model-name>/<execution_id>/diagnostics/<simulation_id>`.
4. Upload summary is printed (uploaded, skipped, failed).
5. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| Missing required argument | 2 | Check argument format (`-r` is required) |
| Missing `cloud_cli_path` env var | 1 | Verify execution environment |
| Missing `simulation_id` or `execution_id` env var | 1 | Verify execution environment — platform injects these automatically |
| Upload returns no response data | 1 | Check CLI path and network connectivity |
| One or more files fail to upload | 1 | Check DataHub permissions and remote path |
| No files match the pattern | 0 | Verify pattern matches diagnostics file names; script warns but succeeds |
