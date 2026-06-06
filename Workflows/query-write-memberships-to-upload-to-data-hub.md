# Workflow: Export PLEXOS Model Memberships and Upload the CSV to DataHub

## Usecase
You want a repeatable way to capture your PLEXOS model structure (parent-child memberships such as Region to Generator, Generator to Fuel) from `reference.db` and store it in DataHub for audit, documentation, or model comparison. This workflow exports memberships to a CSV in `{output_path}`, then uploads that CSV to a DataHub folder you control.

This is typically run as a Post task after a simulation completes, but the export step can also be used as a Pre task when you want to document the model before solving.

## Problem
Without automation, you have to manually locate `{simulation_path}/reference.db`, run ad-hoc queries, export results, and then remember to upload the correct file to the correct DataHub location. This is slow, inconsistent across users, and easy to get wrong (wrong database, wrong output filename, or missing uploads).

## Data Flow Diagram
```mermaid
graph LR
  A["QueryWriteMemberships"] -->|Memberships CSV| B["UploadToDataHub"]
  B -->|Files in DataHub| C["DataHub"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [QueryWriteMemberships](../Post/PLEXOS/QueryWriteMemberships/README.md) | Post | Export membership relationships from `{simulation_path}/reference.db` to a CSV in `{output_path}` | `--output-file` |
| 2 | [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md) | Automation | Upload the exported CSV from the local working directory to a target DataHub path | `--cli-path`, `--environment`, `--file`, `--datahub-path`, `--versioned` |

## Complete Task Definition
```json
[
  {
    "Name": "Export Membership Data",
    "TaskType": "Post",
    "Files": [
      { "Path": "Post/PLEXOS/QueryWriteMemberships/query_write_memberships.py", "Version": null },
      { "Path": "requirements.txt", "Version": null }
    ],
    "Arguments": "python3 query_write_memberships.py --output-file memberships_data.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload Memberships CSV to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py --cli-path /path/to/cli --environment <your-environment> --file {output_path}/memberships_data.csv --datahub-path Project/Study/ModelStructure --versioned",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

## Step-by-Step Walkthrough

### 1) QueryWriteMemberships (Export Membership Data)
- **What it does:** Reads `{simulation_path}/reference.db`, queries membership relationships, and writes a CSV to `{output_path}`.
- **Inputs:**
  - `{simulation_path}/reference.db`
- **Outputs:**
  - `{output_path}/memberships_data.csv` (or the filename you set with `--output-file`)
- **Environment variables used:**
  - `simulation_path` (optional; default `/simulation`)
  - `output_path` (optional; default `/output`)
- **Failure behavior:**
  - Exits with code `1` if `reference.db` is missing, DuckDB SQLite extension fails, the query fails, or the CSV cannot be written. Because `ContinueOnError` is `false`, the workflow stops and the upload step will not run.

### 2) UploadToDataHub (Upload Memberships CSV to DataHub)
- **What it does:** Authenticates to your PLEXOS Cloud environment and uploads the CSV file to the DataHub path you specify. This script uses the SDK; see [CloudSDK](../Documentation/CloudSDK.md) for background.
- **Inputs:**
  - Local file: `{output_path}/memberships_data.csv`
- **Outputs:**
  - The same filename uploaded into DataHub under `Project/Study/ModelStructure` (or your chosen `--datahub-path`)
- **Environment variables used:**
  - None
- **Required arguments:**
  - `--cli-path` (full path to the PLEXOS Cloud CLI executable)
  - `--environment` (your cloud environment name)
  - `--datahub-path` (target DataHub folder)
  - At least one of `--file` or `--directory` (this workflow uses `--file`)
- **Failure behavior:**
  - Exits with code `1` if authentication fails, the CLI path is invalid, the local file is missing, or uploads fail. With `ContinueOnError` set to `true`, the overall run continues even if the upload fails (useful when you don’t want a documentation upload to fail the entire simulation pipeline).

## Data Flow Between Steps
- **Step 1 writes:** a single CSV file into `{output_path}`:
  - `{output_path}/memberships_data.csv` (or `{output_path}/{your-output-file}`)
- **Step 2 reads:** the exact file path you pass via `--file`.
  - In this workflow, it uploads `{output_path}/memberships_data.csv`.
- **Naming convention:** keep `--output-file` as a plain filename only (no directories). The file is always created in `{output_path}`, and the upload step should reference that full path.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| QueryWriteMemberships exits with code `1` and logs indicate `reference.db` not found | `{simulation_path}` does not contain `reference.db`, or the simulation did not produce/ship the expected database | Verify the simulation produced `reference.db` and that `{simulation_path}` points to the directory containing it |
| QueryWriteMemberships fails to write the CSV | `{output_path}` is not writable or disk space is exhausted | Confirm `{output_path}` is writable in your run context and that sufficient space is available |
| UploadToDataHub exits with code `1` and reports invalid CLI path | `--cli-path` does not point to the PLEXOS Cloud CLI executable | Provide the correct executable path (example format: `/path/to/cli`) |
| UploadToDataHub exits with code `1` due to authentication failure | Wrong `--environment` value or missing/invalid credentials for the CLI/SDK | Confirm the environment name is correct (`<your-environment>`) and that your credentials are valid for that environment |
| UploadToDataHub exits with code `1` and reports local file not found | Step 1 did not create the file, the filename differs from `--output-file`, or `--file` points to the wrong location | Ensure Step 1 succeeded, confirm the CSV name, and set `--file {output_path}/memberships_data.csv` to match the exported filename |