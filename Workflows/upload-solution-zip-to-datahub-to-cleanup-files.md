# Workflow: Upload PLEXOS Solution ZIP Outputs to DataHub and Remove Staged ZIP Files

## Usecase
You run PLEXOS simulations that generate ZIP-packaged solution artifacts (for example, zipped reports or bundled outputs) under the model’s solution directory. After each run, you want those ZIP files uploaded to a DataHub folder structure that is unique per execution and model.

Once the upload is complete, you want to delete the staged ZIP files from the run workspace to reduce storage usage and avoid accidentally re-uploading old artifacts in later runs.

## Problem
Without automation, engineers typically have to locate the correct model solution folder, manually copy ZIP files, and upload them to the right DataHub destination. This is slow and error-prone, especially when multiple models or executions run in parallel.

If you do not clean up after uploading, ZIP files accumulate in the workspace, increasing storage costs and making it harder to tell which artifacts belong to the current run.

## Data Flow Diagram
```mermaid
graph LR
  A["UploadSolutionZipToDatahub"] -->|ZIP files uploaded| B["CleanupFiles"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [UploadSolutionZipToDatahub](../Post/PLEXOS/UploadSolutionZipToDatahub/README.md) | Post | Upload ZIP solution files from the model solution path to a DataHub remote path that includes execution and model identifiers | `--remote-path`, `--pattern` |
| 2 | [CleanupFiles](../Post/PLEXOS/CleanupFiles/README.md) | Post | Delete staged ZIP files after upload to keep the workspace clean | `--path`, `--pattern`, `--recursive`, `--dry-run` |

## Complete Task Definition
```json
[
  {
    "Name": "Upload ZIP solution files to DataHub",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/UploadSolutionZipToDatahub/upload_solution_zip_to_datahub.py",
        "Version": null
      },
      {
        "Path": "requirements.txt",
        "Version": null
      }
    ],
    "Arguments": "python3 upload_solution_zip_to_datahub.py --remote-path DataHub/PLEXOS/ZipSolutions --pattern **/*.zip",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Clean up staged ZIP files",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/CleanupFiles/cleanup_files.py",
        "Version": null
      },
      {
        "Path": "requirements.txt",
        "Version": null
      }
    ],
    "Arguments": "python3 cleanup_files.py --path output_path --pattern *.zip --recursive",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

## Step-by-Step Walkthrough

### 1) UploadSolutionZipToDatahub
**What it does**
- Reads the directory mapping JSON to find the first entry with a non-empty `Path` field (the model solution path).
- Uploads all matching ZIP files from that solution path to DataHub.
- Builds the remote destination as `{remote-path}/{execution_id}/{model_id}` automatically.

**Inputs it reads**
- Directory mapping JSON from `directory_map_path` if set; otherwise it falls back to `{simulation_path}/splits/directorymapping.json`.
- ZIP files under the resolved model solution path, matched by `--pattern` (default is `**/*.zip`).

**What it writes for the next step**
- No files are written to `{output_path}`. This step logs per-file upload results and a summary in the task log.

**Environment variables required**
- `cloud_cli_path` (required)
- `execution_id` (required)
- `directory_map_path` (optional)
- `simulation_id` (optional)

**Failure behavior**
- Exits with code `1` if required environment variables are missing, the directory mapping is missing/invalid, no valid model entry is found, or one or more uploads fail.
- Exits with code `0` only when all uploads succeed (files that are already identical remotely are treated as success).

### 2) CleanupFiles
**What it does**
- Deletes files or folders matching `--pattern` under the specified `--path`.
- In this workflow, it removes ZIP files after upload to prevent workspace buildup.

**Inputs it reads**
- The target root directory from `--path`. When you pass `--path output_path`, it resolves the actual directory from the `output_path` environment variable.
- Matches based on `--pattern` (here `*.zip`). With `--recursive`, it searches subdirectories as well.

**What it writes for the next step**
- No output files. It prints each deletion and a summary to the task log.

**Environment variables required**
- `output_path` is required when `--path output_path` is used.

**Failure behavior**
- Exits with code `1` if the target path does not exist or if a deletion fails due to permissions or filesystem errors.
- Exits with code `0` if no matches are found (not treated as an error). This is why it is safe to run with `ContinueOnError: true`.

## Data Flow Between Steps
- **Step 1 to Step 2:** There is no `{output_path}` handoff. The “handoff” is operational:
  - Step 1 uploads ZIP files found under the model solution directory resolved from the directory mapping JSON.
  - Step 2 deletes ZIP files under `{output_path}` (because `--path output_path` is used) that match `*.zip`, optionally across subfolders when `--recursive` is set.

**File naming and matching**
- Upload matching is controlled by `UploadSolutionZipToDatahub --pattern` (default `**/*.zip`).
- Cleanup matching is controlled by `CleanupFiles --pattern` (example `*.zip`), and scope is controlled by `--recursive`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Upload step fails immediately with exit code `1` | `cloud_cli_path` is not set | Set `cloud_cli_path` to the Cloud CLI executable path for your run environment, then rerun the workflow. |
| Upload step fails with a directory mapping error | `directory_map_path` points to a missing/unreadable file, or the fallback `{simulation_path}/splits/directorymapping.json` is missing | Ensure the directory mapping JSON exists and is readable, or set `directory_map_path` to the correct mapping file location. |
| Upload step reports no valid model entry | The directory mapping JSON is empty or has no entry with a non-empty `Path`, or the selected entry is missing `Id` | Fix the directory mapping JSON so at least one entry includes both `Id` and `Path`. |
| Cleanup step fails with “target path does not exist” | `--path output_path` was used but `output_path` is not set, or the resolved directory is missing | Ensure `output_path` is provided by the platform for the run, or pass an explicit path via `--path` that exists. |
| Cleanup step completes but ZIP files remain | Pattern or recursion does not match where ZIP files were staged | Use `--recursive` if ZIPs are in subfolders, and confirm `--pattern` matches your ZIP naming (for example `**/*.zip` is not used by this script; use `--recursive` plus `--pattern *.zip`). |
| Cleanup step deletes more than expected | `--pattern` is too broad (for example default `**/*`) | Set `--pattern *.zip` (or a tighter prefix pattern) and run once with `--dry-run` to verify matches before deleting. |