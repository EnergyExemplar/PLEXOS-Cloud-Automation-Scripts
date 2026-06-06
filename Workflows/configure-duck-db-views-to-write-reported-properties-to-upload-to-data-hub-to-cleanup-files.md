# Workflow: Export PLEXOS reported properties to Parquet, publish to DataHub, and remove staged outputs

## Usecase
You have a completed PLEXOS Cloud simulation that produced solution Parquet outputs, and you need a shareable, query-friendly extract of reported property key metadata. You want that extract written as a single Parquet file into {output_path}, uploaded to a specific DataHub folder for downstream users, and then removed from {output_path} to keep the run workspace small.

## Problem
Without automation, you typically have to manually locate the solution Parquet directory, build repeatable queries over many Parquet subfolders, export a consistent extract, and then upload it to DataHub. This is slow, easy to misconfigure (wrong folder, missing views, inconsistent filenames), and often leaves behind staged artifacts that accumulate across runs.

## Data Flow Diagram
```mermaid
graph LR
  A["ConfigureDuckDbViews"] -->|DuckDB views| B["WriteReportedProperties"]
  B -->|Parquet export| C["UploadToDataHub"]
  C -->|Staged files| D["CleanupFiles"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [ConfigureDuckDbViews](../Post/PLEXOS/ConfigureDuckDbViews/README.md) | Post | Create DuckDB views over solution Parquet folders so you can query results consistently. | `--verbose` |
| 2 | [WriteReportedProperties](../Post/PLEXOS/WriteReportedProperties/README.md) | Post | Query DuckDB views and export flattened reported property key info to a Parquet file in {output_path}. | `--output-file` |
| 3 | [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md) | Automation | Upload the staged Parquet file from {output_path} to a target DataHub path. | `--cli-path`, `--environment`, `--directory`, `--pattern`, `--datahub-path`, `--versioned` |
| 4 | [CleanupFiles](../Post/PLEXOS/CleanupFiles/README.md) | Post | Delete staged Parquet outputs from {output_path} after upload. | `--path`, `--pattern`, `--recursive`, `--dry-run` |

## Complete Task Definition
```json
[
  {
    "Name": "Configure DuckDB views for solution Parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/ConfigureDuckDbViews/configure_duck_db_views.py",
        "Version": null
      }
    ],
    "Arguments": "python3 configure_duck_db_views.py",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Export reported properties to Parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/WriteReportedProperties/write_reported_properties.py",
        "Version": null
      }
    ],
    "Arguments": "python3 write_reported_properties.py --output-file reported_properties.parquet",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Upload reported properties Parquet to DataHub",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 upload_to_datahub.py --cli-path /path/to/cli --environment <your-environment> --directory {output_path} --pattern \"*.parquet\" --datahub-path Project/Study/Results/ReportedProperties --versioned",
    "ContinueOnError": false,
    "ExecutionOrder": 3
  },
  {
    "Name": "Clean up staged Parquet outputs",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/CleanupFiles/cleanup_files.py",
        "Version": null
      }
    ],
    "Arguments": "python3 cleanup_files.py --path output_path --pattern \"*.parquet\" --recursive",
    "ContinueOnError": true,
    "ExecutionOrder": 4
  }
]
```

## Step-by-Step Walkthrough

### 1) ConfigureDuckDbViews
- What it does: Creates `CREATE OR REPLACE VIEW` entries in a DuckDB database file so each solution Parquet subdirectory can be queried as a view.
- What it reads:
  - `duck_db_path` (required): where the DuckDB file will be created/updated.
  - `directory_map_path` (optional): mapping JSON; if not set, the script falls back to `{simulation_path}/splits/directorymapping.json`.
- What it writes:
  - A DuckDB database at `duck_db_path` containing views pointing at solution Parquet files.
- Failure behavior:
  - Exits non-zero if `duck_db_path` is missing, the mapping JSON cannot be found/parsed, no `ParquetPath` exists in the mapping, or DuckDB view creation fails.

### 2) WriteReportedProperties
- What it does: Queries the DuckDB views (`fullkeyinfo`, `object`, `category`) and writes a flattened Parquet extract of reported property key information.
- What it reads:
  - `duck_db_path` (required): must point to the same DuckDB file configured in step 1.
  - `output_path` (optional, default `/output`): working directory for the Parquet export.
- What it writes:
  - `{output_path}/reported_properties.parquet` (from `--output-file reported_properties.parquet`).
- Failure behavior:
  - Exits non-zero if `duck_db_path` is missing, required views are not present, DuckDB query fails, output directory cannot be created, or `--output-file` is not a plain filename (absolute path or contains `/` or `\`).

### 3) UploadToDataHub
- What it does: Uploads the staged Parquet file(s) from a local directory to a DataHub folder using the PLEXOS Cloud CLI via the SDK.
- What it reads:
  - Local files under `{output_path}` selected by `--pattern "*.parquet"`.
- What it requires (arguments, not env vars):
  - `--cli-path`: full path to the PLEXOS Cloud CLI executable.
  - `--environment`: the cloud environment name (use `<your-environment>` in configs).
  - `--datahub-path`: target DataHub folder (example: `Project/Study/Results/ReportedProperties`).
  - One of: `--directory` or `--file` (this workflow uses `--directory`).
- What it writes:
  - Uploads files to DataHub with their original filenames.
- Failure behavior:
  - Exits non-zero for invalid CLI path, authentication failure, missing local files, no files selected, or if all uploads fail.
- SDK reference:
  - This script uses the SDK methods listed in its extraction (`auth.login`, `environment.set_user_environment`, `datahub.upload`). For parameter details, see [CloudSDK](../Documentation/CloudSDK.md).

### 4) CleanupFiles
- What it does: Deletes staged files matching a glob pattern from a target path (typically the final step).
- What it reads:
  - `output_path` (required by this script’s environment-variable contract) when you pass `--path output_path`.
- What it deletes:
  - Files matching `--pattern "*.parquet"` under `{output_path}` (and subdirectories when `--recursive` is set).
- Failure behavior:
  - Exits non-zero if the target path does not exist or deletion fails due to permissions.
  - Exits zero if no matches are found (safe to run even when there is nothing to delete).
  - Recommended to keep `ContinueOnError: true` so cleanup does not fail the overall run after a successful upload.

## Data Flow Between Steps

1. **ConfigureDuckDbViews → WriteReportedProperties**
   - Step 1 writes/updates the DuckDB database at `duck_db_path`.
   - Step 2 connects to the same `duck_db_path` and expects the views `fullkeyinfo`, `object`, and `category` to exist.

2. **WriteReportedProperties → UploadToDataHub**
   - Step 2 writes a single Parquet file into `{output_path}`.
   - Naming rule: `--output-file` must be a plain filename (for example `reported_properties.parquet`), so the full path is `{output_path}/reported_properties.parquet`.
   - Step 3 uploads from `--directory {output_path}` using `--pattern "*.parquet"`, which will include the exported file.

3. **UploadToDataHub → CleanupFiles**
   - Step 4 deletes the staged Parquet file(s) from `{output_path}` using `--pattern "*.parquet"`.
   - If you later add other Parquet outputs to `{output_path}`, keep the pattern specific (for example, prefer `reported_properties.parquet` over `*.parquet`) to avoid deleting unrelated artifacts.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| ConfigureDuckDbViews exits non-zero immediately | `duck_db_path` is not set | Ensure `duck_db_path` is provided by your run environment and points to a writable DuckDB file location. |
| ConfigureDuckDbViews fails with mapping not found or no ParquetPath | `directory_map_path` not set and `{simulation_path}/splits/directorymapping.json` is missing or does not contain a `ParquetPath` entry | Provide a valid `directory_map_path` or ensure the default mapping file exists and includes at least one entry with `ParquetPath`. |
| WriteReportedProperties fails with missing views | Step 1 did not run, used a different `duck_db_path`, or view creation failed | Run step 1 first and ensure both steps use the same `duck_db_path`. Re-run with ConfigureDuckDbViews `--verbose` to validate view creation. |
| WriteReportedProperties exits non-zero with invalid output filename | `--output-file` contains `/`, `\`, or is an absolute path | Use a plain filename only (for example `reported_properties.parquet`) and let the script write it under `{output_path}`. |
| UploadToDataHub exits non-zero with authentication or environment errors | Wrong `--environment` value or missing credentials for the CLI | Verify `--environment <your-environment>` is correct for your tenant and that the CLI at `--cli-path` can authenticate in your execution context. |
| UploadToDataHub reports no files uploaded | `--directory` points to the wrong location or `--pattern` does not match | Confirm the Parquet file exists in `{output_path}` and that `--pattern "*.parquet"` matches the filename you configured in step 2. |
| CleanupFiles exits non-zero with path not found | `{output_path}` is not available or `--path` was not set to `output_path` correctly | Use `--path output_path` (exact string) and ensure the `output_path` environment variable is set in the run context. |
| CleanupFiles deletes more than expected | Pattern too broad (for example `*.parquet`) | Narrow the pattern to the specific export (for example `--pattern "reported_properties.parquet"`) or write exports into a dedicated subfolder under `{output_path}` and target that folder. |