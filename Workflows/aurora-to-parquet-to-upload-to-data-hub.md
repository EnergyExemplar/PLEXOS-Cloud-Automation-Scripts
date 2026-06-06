# Workflow: Convert Aurora solution tables to Parquet and publish them to DataHub

## Usecase
You run an Aurora study in PLEXOS Cloud and want the full set of solution tables available for downstream analytics in a columnar format. This workflow converts the Aurora `.xdb` solution database into a folder of Parquet files under `{output_path}`, then uploads those Parquet files to a DataHub results directory such as `Project/Study/Results`.

This is useful when you need consistent, query-friendly outputs across many simulation runs and want to centralize results in DataHub for sharing and reporting.

## Problem
Without automation, you typically have to manually locate the `.xdb` for each run, export tables one-by-one (or with ad-hoc scripts), and then upload outputs to DataHub. That manual process is slow, easy to misconfigure (wrong run, missing tables, inconsistent naming), and hard to repeat reliably across many runs.

## Data Flow Diagram
```mermaid
graph LR
  A["AuroraToParquet"] -->|Parquet tables| B["UploadToDataHub"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [AuroraToParquet](../Post/Aurora/AuroraToParquet/README.md) | Post | Export every table in the Aurora solution database to Parquet under `{output_path}` and append `SimulationId` | `--xdb-filename` |
| 2 | [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md) | Automation | Upload the generated Parquet files to a target DataHub directory | `--cli-path`, `--environment`, `--directory`, `--pattern`, `--datahub-path`, `--versioned` |

## Complete Task Definition
```json
[
  {
    "Name": "Convert Aurora solution tables to Parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/Aurora/AuroraToParquet/aurora_to_parquet.py",
        "Version": null
      },
      {
        "Path": "requirements.txt",
        "Version": null
      }
    ],
    "Arguments": "python3 aurora_to_parquet.py",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload Parquet results to DataHub",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 upload_to_datahub.py --cli-path /path/to/cli --environment <your-environment> --directory {output_path}/parquet --pattern **/*.parquet --datahub-path Project/Study/Results/Aurora/Parquet --versioned",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

## Step-by-Step Walkthrough

### 1) AuroraToParquet
This step reads the Aurora solution database (`.xdb`) from `{simulation_path}` and exports every table to Parquet. Each exported table includes an appended `SimulationId` column so you can trace rows back to the run that produced them.

**Inputs**
- `{simulation_path}/<simulation_id>.xdb` by default
- Optional override: `--xdb-filename` (filename only, not a path)

**Outputs**
- Writes Parquet files to `{output_path}/parquet/`
- One Parquet file per Aurora table, named `<table_name>.parquet`

**Environment variables**
- `simulation_id` (required)
- `simulation_path` (optional; default `/simulation`)
- `output_path` (optional; default `/output`)

**Failure behavior**
- If `simulation_id` is missing, the script exits with a non-zero code and the workflow stops.
- If the `.xdb` file is not found in `{simulation_path}`, the script exits with a non-zero code and the workflow stops.

---

### 2) UploadToDataHub
This step uploads the Parquet files produced in step 1 from `{output_path}/parquet` into the DataHub directory you specify. Use `--pattern` to control which files are uploaded; in this workflow it targets `**/*.parquet`.

**Inputs**
- Local directory: `{output_path}/parquet`
- File selection: `--pattern **/*.parquet`

**Outputs**
- Files uploaded to DataHub at `--datahub-path` with their original filenames

**Environment variables**
- None

**Failure behavior**
- If `--cli-path` is invalid or authentication fails for `--environment`, the script exits with a non-zero code and the workflow stops.
- If the directory is missing or empty, uploads will fail or upload zero files (depending on the condition), and the script exits non-zero when it cannot proceed.

## Data Flow Between Steps
- **Step 1 writes:** `{output_path}/parquet/<table_name>.parquet` for each table found in the `.xdb`. The directory `{output_path}/parquet/` is the handoff point to the next step.
- **Step 2 reads:** all files matching `**/*.parquet` under `{output_path}/parquet/` and uploads them to the DataHub directory specified by `--datahub-path`.

Naming conventions:
- Parquet filenames are derived from Aurora table names: `<table_name>.parquet`.
- The upload preserves filenames in DataHub; organize runs by choosing a run- or study-specific `--datahub-path` (for example, `Project/Study/Results/Aurora/Parquet`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| AuroraToParquet fails with a non-zero exit code and no Parquet files are created | `simulation_id` is not set in the execution environment | Ensure `simulation_id` is provided by the platform for the run; if running outside the platform, set it before execution |
| AuroraToParquet reports the `.xdb` is not found | The expected `{simulation_path}/<simulation_id>.xdb` does not exist, or the wrong filename was provided | Verify the `.xdb` exists under `{simulation_path}`; if the `.xdb` name differs, pass `--xdb-filename <your_file>.xdb` |
| UploadToDataHub exits with an authentication or environment error | Incorrect `--environment` value or missing credentials for the CLI | Confirm the environment name is correct and that the CLI is authenticated for that environment |
| UploadToDataHub exits with “invalid CLI path” | `--cli-path` does not point to the PLEXOS Cloud CLI executable | Provide the correct executable path (for example `/path/to/cli`) and ensure it is executable |
| UploadToDataHub uploads zero files | `{output_path}/parquet` is empty or `--pattern` does not match the generated files | Confirm step 1 produced Parquet files under `{output_path}/parquet` and use `--pattern **/*.parquet` to match them |