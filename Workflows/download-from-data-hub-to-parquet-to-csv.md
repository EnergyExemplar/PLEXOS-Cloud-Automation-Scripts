# Workflow: Download DataHub Parquet Inputs and Convert Them to CSV for PLEXOS Preprocessing

## Usecase
You have one or more Parquet input files stored in DataHub (for example, time series or reference datasets) and you need them as CSV for downstream preprocessing or tools that do not read Parquet. You want a repeatable workflow that pulls the exact DataHub versions you specify and converts them in-place after download.

This workflow downloads Parquet files into your run workspace and then converts every Parquet file under the target folder to CSV.

## Problem
Without automation, you typically:
- Manually download files from DataHub (often inconsistently across engineers or runs).
- Convert Parquet to CSV using ad-hoc local scripts, risking partial conversions, wrong folders, or accidental data loss.
- Spend time debugging path issues and re-running conversions when a single file fails.

This workflow makes the download and conversion steps explicit, ordered, and repeatable.

## Data Flow Diagram
```mermaid
graph LR
  A["DownloadFromDataHub"] -->|Parquet files| B["ParquetToCsv"]
  B -->|CSV files| C["Preprocessing or tools"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [DownloadFromDataHub](../Automation/PLEXOS/DownloadFromDataHub/README.md) | Automation | Download one or more DataHub files to a local folder | `--cli-path`, `--environment`, `--file`, `--output-dir` |
| 2 | [ParquetToCsv](../Pre/PLEXOS/ParquetToCsv/README.md) | Pre | Convert all Parquet files under a folder to CSV in-place | `--folder`, `--workers` |

## Complete Task Definition
```json
[
  {
    "Name": "Download Parquet inputs from DataHub",
    "TaskType": "Automation",
    "Files": [
      {
        "Path": "Automation/PLEXOS/DownloadFromDataHub/download_from_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 download_from_datahub.py --cli-path /path/to/cli/plexos-cloud --environment <your-environment> --file Project/Study/Inputs/TimeSeries/load.parquet --file Project/Study/Inputs/TimeSeries/price.parquet --output-dir {output_path}/datahub_downloads",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Convert downloaded Parquet inputs to CSV",
    "TaskType": "Pre",
    "Files": [
      {
        "Path": "Pre/PLEXOS/ParquetToCsv/convert_parquet_to_csv.py",
        "Version": null
      }
    ],
    "Arguments": "python3 convert_parquet_to_csv.py --folder {output_path}/datahub_downloads --workers 3",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

## Step-by-Step Walkthrough

### 1) DownloadFromDataHub
**What it does**
- Authenticates to the cloud environment you specify and downloads each `--file` DataHub path into the local directory you provide via `--output-dir`.

**Inputs**
- DataHub file paths provided via one or more `--file` arguments.

**Writes to**
- `{output_path}/datahub_downloads/` (or whatever you set in `--output-dir`)
- Files are saved with their original filenames (for example, `load.parquet`, `price.parquet`).

**Environment variables**
- None.

**If it fails**
- The task exits with code `1` for common issues like invalid CLI path, authentication failure, or missing DataHub files. Because `ContinueOnError` is `false`, the workflow stops and conversion does not run.

### 2) ParquetToCsv
**What it does**
- Recursively finds all `.parquet` files under `--folder`, converts each to CSV using DuckDB, validates row counts, and only then deletes the source Parquet for successfully converted files.

**Inputs**
- Parquet files located under `--folder` (in this workflow, `{output_path}/datahub_downloads`).

**Writes to**
- CSV files in the same directories as the source Parquet files (in-place conversion).
- For each `name.parquet`, the output is `name.csv` alongside it.

**Environment variables**
- `simulation_path` is required only when you pass `--folder simulation_path`. In this workflow, you pass an explicit folder under `{output_path}`, so `simulation_path` is not used.

**If it fails**
- If any file fails conversion, the script exits with code `1`. If a row count mismatch occurs for a file, the source Parquet is kept for that file and conversion continues for remaining files, but the overall exit code is `1` if any file fails conversion.

## Data Flow Between Steps
- **Step 1 → Step 2**
  - Step 1 writes downloaded files into `{output_path}/datahub_downloads/`.
  - Step 2 reads all `*.parquet` files anywhere under `{output_path}/datahub_downloads/` (including subfolders, if present).
  - Step 2 produces `*.csv` files next to each Parquet file:
    - `{output_path}/datahub_downloads/load.parquet` becomes `{output_path}/datahub_downloads/load.csv`
    - `{output_path}/datahub_downloads/price.parquet` becomes `{output_path}/datahub_downloads/price.csv`
  - After successful validation, the corresponding `*.parquet` is deleted for that file; failed conversions keep the source Parquet.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Download step exits with code 1 and logs indicate CLI issues | `--cli-path` does not point to the PLEXOS Cloud CLI executable | Verify the CLI is installed and update `--cli-path` to the correct executable location |
| Download step exits with code 1 due to authentication or environment errors | Wrong `--environment` value or insufficient permissions | Confirm the environment name with your administrator and ensure your credentials have DataHub access |
| Download step reports file not found | One or more `--file` DataHub paths are incorrect | Verify the DataHub paths and re-run with corrected `--file` values |
| Convert step exits with code 1 and reports folder missing | `--folder` points to a directory that does not exist (for example, download step wrote elsewhere) | Ensure `--output-dir` in step 1 matches `--folder` in step 2 and that the download completed successfully |
| Convert step exits with code 1 and logs show a specific file conversion failure | A Parquet file is corrupted or not a valid Parquet file | Re-download the file from DataHub, confirm it opens as Parquet, and re-run conversion |
| Convert step indicates `simulation_path` missing | You passed `--folder simulation_path` but the environment variable is not set | Either set `simulation_path` in the execution environment or pass an explicit folder path (as shown in this workflow) |