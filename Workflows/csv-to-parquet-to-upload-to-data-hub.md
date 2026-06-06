# Workflow: Convert PLEXOS CSV outputs to Parquet and publish results to DataHub

## Usecase
You run PLEXOS simulations that produce large CSV result sets under `{output_path}`, and you want to store results in DataHub in a compact, analytics-friendly format. This workflow converts all CSV outputs to Parquet in-place, then uploads the Parquet results to a specified DataHub folder.

This is commonly used when you need consistent, shareable result artifacts for downstream reporting, dashboards, or model validation across teams.

## Problem
Without automation, you typically:
- Manually locate and convert many CSV files (often nested in subfolders), which is slow and easy to miss.
- Risk uploading inconsistent formats (mix of CSV and Parquet) or partial results.
- Spend time re-running conversions and uploads when a simulation is repeated.

This workflow standardizes the post-processing and publishing step so each run produces the same DataHub-ready outputs.

## Data Flow Diagram
```mermaid
graph LR
  A["CsvToParquet"] -->|Parquet files| B["UploadToDataHub"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [CsvToParquet](../Post/PLEXOS/CsvToParquet/README.md) | Post | Convert all CSV files under a folder to Parquet in-place | `--root-folder`, `--workers`, `--compression` |
| 2 | [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md) | Automation | Upload the converted Parquet files to a DataHub path | `--cli-path`, `--environment`, `--directory`, `--pattern`, `--datahub-path`, `--versioned` |

## Complete Task Definition
```json
[
  {
    "Name": "Convert CSV outputs to Parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/CsvToParquet/convert_csv_to_parquet.py",
        "Version": null
      }
    ],
    "Arguments": "python3 convert_csv_to_parquet.py --root-folder output_path --workers 6 --compression zstd",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload Parquet files to DataHub",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 upload_to_datahub.py --cli-path /path/to/cli --environment <your-environment> --directory {output_path} --pattern **/*.parquet --datahub-path Project/Study/Results --versioned",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

## Step-by-Step Walkthrough

### 1) Convert CSV outputs to Parquet ([CsvToParquet](../Post/PLEXOS/CsvToParquet/README.md))
**What it does**
- Recursively finds `.csv` files under the folder you specify.
- Converts each CSV to Parquet in-place.
- Validates row counts before deleting the source CSV.

**Inputs**
- CSV files located under `{output_path}` (when you pass `--root-folder output_path`).

**Outputs written for the next step**
- Parquet files written alongside the original CSV locations under `{output_path}`.
- Source CSV files are deleted only after validation succeeds for each file.

**Environment variables needed**
- `output_path` (required when `--root-folder` is set to `output_path`)

**If it fails**
- The task exits non-zero if any conversion fails.
- If a row-count mismatch occurs for a file, the source CSV is kept and conversion continues for remaining files, but the overall exit code is `1` if any file fails conversion.

---

### 2) Upload Parquet files to DataHub ([UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md))
**What it does**
- Authenticates to your PLEXOS Cloud environment using the CLI path you provide.
- Uploads all files matching the glob pattern from the specified directory to the target DataHub path.

**Inputs**
- Parquet files under `{output_path}`, selected via:
  - `--directory {output_path}`
  - `--pattern **/*.parquet`

**Outputs**
- The same Parquet files uploaded into DataHub at `Project/Study/Results` (or your chosen `--datahub-path`) with their original filenames.

**Environment variables needed**
- None.

**If it fails**
- Exits non-zero for invalid CLI path, authentication failure, missing local files, no files specified, or if all uploads fail.
- If this step fails, your Parquet files still remain in `{output_path}` (conversion already completed).

**SDK behavior**
- This script uses the `eecloud` SDK. For SDK parameter conventions, see [CloudSDK](../Documentation/CloudSDK.md).

## Data Flow Between Steps

### Step 1 to Step 2
- **Where data is written:** `{output_path}` (existing simulation output directory structure is preserved).
- **What files are produced:** `**/*.parquet` files created next to the original CSVs.
- **What files are removed:** corresponding `**/*.csv` files are deleted only after row-count validation succeeds per file.
- **What the next step reads:** Step 2 scans `{output_path}` recursively and uploads files matching `**/*.parquet`.

**File naming and structure**
- Parquet files keep the same base name as the CSV, with the extension changed to `.parquet`.
- Subdirectory layout under `{output_path}` is preserved (uploads mirror the local file selection, but DataHub stores them under the single target `--datahub-path`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| CsvToParquet exits with code 1 and logs mention `output_path` | `output_path` environment variable is not set, but `--root-folder output_path` was used | Ensure the run context provides `output_path`, or pass a real folder path to `--root-folder` |
| CsvToParquet reports folder does not exist | `--root-folder` points to a non-existent directory | Verify the folder name and whether you intended to use `--root-folder output_path` |
| CsvToParquet leaves some CSV files behind | Row-count validation failed for those files or conversion failed for specific files | Review logs for the specific file errors; re-run after fixing the problematic CSVs |
| UploadToDataHub exits with code 1 and reports invalid CLI path | `--cli-path` does not point to the PLEXOS Cloud CLI executable | Provide the correct executable path in `--cli-path` (use a valid path like `/path/to/cli`) |
| UploadToDataHub fails authentication | Wrong `--environment` value or missing/invalid credentials for the CLI/SDK | Confirm `--environment <your-environment>` is correct and that your CLI authentication is configured for that environment |
| UploadToDataHub uploads nothing | `--pattern` does not match any files under `--directory`, or conversion did not produce Parquet | Confirm Parquet files exist under `{output_path}` and use `--pattern **/*.parquet` when uploading recursively |
| UploadToDataHub reports no files specified | Neither `--file` nor `--directory` was provided | Provide `--directory {output_path}` (or one or more `--file` arguments) |