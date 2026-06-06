# Workflow: Stage PLEXOS Results, Upload to DataHub, and Clean Up Staged Outputs

## Usecase
You have a PLEXOS Cloud simulation that produces one or more results files (commonly CSV) somewhere under `{simulation_path}` or inside ZIP archives created during the run. You want to reliably stage the right file into `{output_path}`, convert CSV to Parquet for efficient storage, upload the staged Parquet to a DataHub folder, and then remove staged artifacts to keep the run workspace clean.

This workflow is designed for cases where you prefer a dedicated upload step (for example, to upload multiple staged files later, or to control upload behavior separately from discovery and conversion).

## Problem
Without automation, you typically have to manually locate the correct results file (sometimes buried in nested folders or ZIPs), copy it out of the read-only `{simulation_path}` mount, convert it to a more storage-friendly format, and then upload it to DataHub. This manual process is slow and error-prone: you can upload the wrong file, miss files inside ZIP archives, or leave large staged outputs behind that increase storage usage and complicate later steps.

## Data Flow Diagram
```mermaid
graph LR
  A["SearchAndUpload"] -->|Staged Parquet file| B["UploadToDataHub"]
  B -->|Uploaded DataHub objects| C["CleanupFiles"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [SearchAndUpload](../Post/PLEXOS/SearchAndUpload/README.md) | Post | Find a target file (including inside ZIPs), stage it into `{output_path}`, and convert CSV to Parquet | `--file-name`, `--path` |
| 2 | [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md) | Automation | Upload the staged file(s) from `{output_path}` to a DataHub folder | `--cli-path`, `--environment`, `--directory`, `--pattern`, `--datahub-path` |
| 3 | [CleanupFiles](../Post/PLEXOS/CleanupFiles/README.md) | Post | Delete staged files from `{output_path}` after upload | `--path`, `--pattern`, `--recursive` |

## Complete Task Definition
```json
[
  {
    "Name": "Search and stage results CSV",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/SearchAndUpload/search_and_upload.py",
        "Version": null
      },
      {
        "Path": "requirements.txt",
        "Version": null
      }
    ],
    "Arguments": "python3 search_and_upload.py --file-name results.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload staged Parquet file to DataHub",
    "TaskType": "Automation",
    "Files": [
      {
        "Path": "Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 upload_to_datahub.py --cli-path /path/to/cli --environment <your-environment> --directory {output_path} --pattern \"*.parquet\" --datahub-path Project/Study/Results",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Cleanup staged files after upload",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/CleanupFiles/cleanup_files.py",
        "Version": null
      }
    ],
    "Arguments": "python3 cleanup_files.py --path output_path --pattern \"*.parquet\" --recursive",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  }
]
```

## Step-by-Step Walkthrough

### 1) SearchAndUpload (stage and convert)
**Script:** [SearchAndUpload](../Post/PLEXOS/SearchAndUpload/README.md)

**What it does**
- Searches for `--file-name` (supports glob patterns) in the provided `--path`, or falls back to `{output_path}` then `{simulation_path}`.
- If the file is not found on the filesystem, it searches inside `*.zip` archives located in the search paths and extracts the first match.
- Stages the file into `{output_path}`:
  - If the source is under `{simulation_path}` (read-only), it copies.
  - Otherwise, it moves.
  - If the file is already in `{output_path}`, it leaves it in place.
- If the staged file is a CSV, it converts it to Parquet (ZSTD) and validates row counts before deleting the source CSV.

**Inputs**
- A file matching `--file-name` located under `--path`, `{output_path}`, `{simulation_path}`, or inside ZIP archives found there.

**Outputs written for the next step**
- A staged file in `{output_path}`.
- If the staged file was CSV, the output is a Parquet file with the same stem name (for example, `results.csv` becomes `results.parquet` in `{output_path}`).

**Environment variables required**
- `output_path`
- `simulation_path`
- `cloud_cli_path` (required by this script only when `--upload-path` is used; in this workflow it is not used, but the variable may still be present in your run environment)

**Failure behavior**
- Exits with code `1` if the file cannot be found, staged, or converted. Downstream steps should not run if this step fails.

---

### 2) UploadToDataHub (upload staged outputs)
**Script:** [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md)

**What it does**
- Authenticates to the specified cloud environment and uploads either:
  - one or more `--file` paths, or
  - all files under `--directory` filtered by `--pattern`
- Uploads to the DataHub folder specified by `--datahub-path`.

**Inputs**
- The staged Parquet file(s) in `{output_path}` created by Step 1.

**Outputs**
- Files uploaded to DataHub at `--datahub-path` with their original filenames.

**Environment variables required**
- None.

**Failure behavior**
- Exits with code `1` if authentication fails, no files are specified, or uploads fail. If this step fails, you typically want to keep staged files for inspection (do not run cleanup, or run cleanup only after you confirm what happened).

---

### 3) CleanupFiles (remove staged artifacts)
**Script:** [CleanupFiles](../Post/PLEXOS/CleanupFiles/README.md)

**What it does**
- Deletes files and/or folders matching `--pattern` under `--path`.
- With `--recursive`, it searches subdirectories as well.
- This is commonly run with `ContinueOnError: true` so the workflow still completes even if there is nothing to delete.

**Inputs**
- The staged files in `{output_path}` (for example, `*.parquet`).

**Outputs**
- No files are produced; matching files are deleted and a summary is printed.

**Environment variables required**
- `output_path` (only used when you pass `--path output_path`)

**Failure behavior**
- Exits with code `1` if the target path does not exist or deletion fails due to permissions. If no matches are found, it exits cleanly with code `0`.

## Data Flow Between Steps

**Step 1 → Step 2**
- **Written by Step 1:** `{output_path}/<stem>.parquet` when the discovered file is CSV (CSV is converted and the source CSV is deleted on successful validation).
- **Read by Step 2:** All files in `{output_path}` matching `--pattern "*.parquet"` when using `--directory {output_path}`.
- **Naming convention:** The Parquet filename matches the CSV stem (example: `results.csv` becomes `results.parquet`).

**Step 2 → Step 3**
- **Written by Step 2:** No local files; upload occurs to DataHub.
- **Read by Step 3:** The same staged Parquet files in `{output_path}` that were uploaded.
- **Deletion scope:** With `--pattern "*.parquet"` and `--recursive`, all matching Parquet files under `{output_path}` are removed.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Step 1 fails with file not found | `--file-name` does not match the produced output, or the file is only present in a different directory than `--path`, `{output_path}`, or `{simulation_path}` | Use a glob pattern with `--file-name` (for example `report_*.csv`) and/or set `--path` to the directory where outputs are written. Confirm the file is not nested inside an unexpected ZIP name. |
| Step 1 fails during CSV conversion | The CSV is malformed or inconsistent, causing conversion or row-count validation to fail | Inspect the CSV in `{output_path}` (the source is preserved on mismatch). Fix the upstream generation or choose a different file via `--file-name`. |
| Step 2 fails with authentication error | Wrong `--environment` or missing/invalid credentials for the CLI | Verify `--environment <your-environment>` is correct and that the CLI at `--cli-path` can authenticate in your execution context. |
| Step 2 exits with code 1 and reports no files specified or no uploads | `--directory` is wrong, or `--pattern` does not match the staged file name | Ensure `--directory {output_path}` is correct and the pattern matches what Step 1 produced (for example `*.parquet`). |
| Step 3 fails with target path does not exist | `{output_path}` was not created or is not available in the runtime where cleanup runs | Confirm the platform provides `output_path` and that Step 1 ran successfully. If needed, run cleanup only when staging succeeded. |
| Step 3 deletes more than expected | `--pattern` is too broad (default is `**/*`) and `--recursive` is enabled | Use a narrow `--pattern` such as `"*.parquet"` (or a specific prefix) and keep cleanup scoped to `--path output_path`. |