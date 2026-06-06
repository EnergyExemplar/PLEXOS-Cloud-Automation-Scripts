# Workflow: Export PLEXOS Model Memberships, Convert to Parquet, Upload to DataHub, and Clean Up Outputs

## Usecase
You run PLEXOS simulations in the cloud and need a repeatable way to export model structure (membership relationships) for audit, validation, or documentation. This workflow exports memberships from `{simulation_path}/reference.db` into `{output_path}`, converts the CSV to Parquet for efficient storage, uploads the Parquet to a DataHub folder, and then removes intermediate CSV files from `{output_path}`.

## Problem
Without automation, exporting memberships is a manual, error-prone process: you have to locate `reference.db`, run ad-hoc queries, manage output filenames, and remember to upload artifacts to the correct DataHub path. Format conversion and cleanup are often skipped, which leads to inconsistent deliverables and bloated `{output_path}` contents across runs.

## Data Flow Diagram
```mermaid
graph LR
  A["QueryWriteMemberships"] -->|Memberships CSV| B["CsvToParquet"]
  B -->|Memberships Parquet| C["UploadToDataHub"]
  C -->|Uploaded files| D["CleanupFiles"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [QueryWriteMemberships](../Post/PLEXOS/QueryWriteMemberships/README.md) | Post | Export membership relationships from `{simulation_path}/reference.db` to a CSV in `{output_path}` | `--output-file` |
| 2 | [CsvToParquet](../Post/PLEXOS/CsvToParquet/README.md) | Post | Convert CSV files under a folder to Parquet in-place (deletes CSV after validation) | `--root-folder`, `--workers`, `--compression` |
| 3 | [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md) | Automation | Upload the generated Parquet file(s) to a target DataHub path | `--cli-path`, `--environment`, `--datahub-path`, `--file` |
| 4 | [CleanupFiles](../Post/PLEXOS/CleanupFiles/README.md) | Post | Remove intermediate files from `{output_path}` after upload | `--path`, `--pattern`, `--recursive` |

## Complete Task Definition
```json
[
  {
    "Name": "Export Membership Data",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/QueryWriteMemberships/query_write_memberships.py",
        "Version": null
      }
    ],
    "Arguments": "python3 query_write_memberships.py --output-file memberships_data.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Convert Memberships CSV to Parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/CsvToParquet/convert_csv_to_parquet.py",
        "Version": null
      }
    ],
    "Arguments": "python3 convert_csv_to_parquet.py --root-folder output_path --workers 3 --compression zstd",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Upload Memberships to DataHub",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 upload_to_datahub.py --cli-path /path/to/cli --environment <your-environment> --datahub-path Project/Study/ModelStructure --file memberships_data.parquet",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  },
  {
    "Name": "Cleanup Intermediate CSV Files",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/CleanupFiles/cleanup_files.py",
        "Version": null
      }
    ],
    "Arguments": "python3 cleanup_files.py --path output_path --pattern *.csv --recursive",
    "ContinueOnError": true,
    "ExecutionOrder": 4
  }
]
```

## Step-by-Step Walkthrough

### 1) QueryWriteMemberships
**What it does:** Reads `{simulation_path}/reference.db` and exports membership relationships (parent-child object connections) to a CSV file in `{output_path}`.

**Inputs:**
- `{simulation_path}/reference.db`

**Outputs (written to `{output_path}`):**
- `memberships_data.csv` (or the filename you set via `--output-file`)

**Environment variables used:**
- `simulation_path` (optional; default `/simulation`)
- `output_path` (optional; default `/output`)

**Failure behavior:**
- If `reference.db` is missing or the query/export fails, the script exits non-zero and the workflow should stop (this task is `ContinueOnError: false`).

---

### 2) CsvToParquet
**What it does:** Recursively finds `.csv` files under the folder you specify and converts them to Parquet in-place using DuckDB. It deletes each CSV only after validating row counts match.

**Inputs:**
- CSV files under the folder specified by `--root-folder`
  - In this workflow: `--root-folder output_path` resolves to `{output_path}`

**Outputs (written to `{output_path}`):**
- `memberships_data.parquet` (created alongside the CSV)
- Source CSV is deleted after successful validation

**Environment variables used:**
- `output_path` (required when `--root-folder output_path` is used)

**Failure behavior:**
- If `{output_path}` is not set when using `--root-folder output_path`, the script exits non-zero.
- If a specific file fails conversion or validation, that CSV is kept; the overall exit code is non-zero if any file fails.

---

### 3) UploadToDataHub
**What it does:** Uploads one or more local files to the DataHub path you specify. This script authenticates using the PLEXOS Cloud CLI and the selected environment.

**Inputs:**
- Local file path(s) provided via `--file`
  - In this workflow: `memberships_data.parquet` is expected to be present in the task working directory (typically `{output_path}` for Post tasks)

**Outputs:**
- The file is uploaded to DataHub at `--datahub-path` with its original filename.

**Environment variables used:**
- None

**SDK reference:**
- This script uses the Cloud SDK; see [CloudSDK](../Documentation/CloudSDK.md).

**Failure behavior:**
- If authentication fails, the CLI path is invalid, or the file is not found, the script exits non-zero.
- This task is `ContinueOnError: true` so the workflow proceeds to cleanup even if upload fails (useful when you want cleanup to run regardless).

---

### 4) CleanupFiles
**What it does:** Deletes files or folders matching a glob pattern from a specified path. Here it removes any remaining `*.csv` files under `{output_path}` recursively.

**Inputs:**
- `--path output_path` resolves to `{output_path}`
- `--pattern *.csv`
- `--recursive` to search subdirectories

**Outputs:**
- No new files; deletes matching files and prints a summary.

**Environment variables used:**
- `output_path` (required when `--path output_path` is used)

**Failure behavior:**
- If the target path does not exist, the script exits non-zero.
- If no matches are found, it exits `0` (not an error).
- This task is `ContinueOnError: true` so it won’t fail the overall run due to cleanup issues.

## Data Flow Between Steps

1. **Step 1 → Step 2**
   - Step 1 writes `{output_path}/memberships_data.csv`.
   - Step 2 scans `{output_path}` (because `--root-folder output_path`) and converts `*.csv` to `*.parquet`.
   - Naming convention: `memberships_data.csv` becomes `memberships_data.parquet` in the same folder.

2. **Step 2 → Step 3**
   - Step 2 produces `{output_path}/memberships_data.parquet` and typically deletes `{output_path}/memberships_data.csv` after validation.
   - Step 3 uploads `memberships_data.parquet` to the DataHub folder specified by `--datahub-path`.

3. **Step 3 → Step 4**
   - Step 4 does not depend on DataHub state; it operates on `{output_path}`.
   - Step 4 deletes any remaining `*.csv` files under `{output_path}` (including subfolders) to keep the run output lean.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| QueryWriteMemberships exits with code 1 and logs indicate `reference.db` not found | `{simulation_path}` does not contain `reference.db` for this run | Confirm the simulation produced/contains `{simulation_path}/reference.db` and that the platform injected `simulation_path` correctly |
| QueryWriteMemberships fails due to an invalid output filename | `--output-file` includes path separators or an absolute path | Use a plain filename only (for example `memberships_data.csv`) so it is created under `{output_path}` |
| CsvToParquet exits with code 1 and mentions `output_path` missing | `--root-folder output_path` was used but `output_path` env var is not set | Ensure the execution environment provides `output_path`, or pass an explicit folder path to `--root-folder` |
| CsvToParquet reports conversion issues and leaves some CSV files behind | Row-count validation failed or a file conversion failed | Inspect logs for the specific CSV; re-run conversion after correcting malformed CSV content or permissions |
| UploadToDataHub exits with code 1 and authentication fails | Wrong `--environment` or missing credentials for the CLI | Verify `--environment <your-environment>` is correct and that the CLI is authenticated for that environment |
| UploadToDataHub exits with code 1 and file not found | The `--file` path does not exist in the task working directory | Confirm `memberships_data.parquet` exists under `{output_path}` and that the task runs where the file is accessible; adjust `--file` to the correct local path if needed |
| CleanupFiles exits with code 1 and says path does not exist | `--path output_path` was used but `{output_path}` is not set or not present | Ensure `output_path` is available in the run environment and points to an existing directory |
| CleanupFiles deletes more than expected | `--pattern` is too broad (for example default `**/*`) combined with `--recursive` | Use a narrow pattern like `*.csv` and validate with `--dry-run` before enabling deletion in production runs |