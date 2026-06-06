# Workflow: Compare time series outputs and publish the analysis to DataHub

## Usecase
You have two to four time-series datasets (CSV, Excel, Parquet, or JSON) representing results from different runs (for example, a new simulation output versus a baseline). You want a repeatable way to compare them, generate metrics and plots, and store the analysis in DataHub under a consistent project folder.

This workflow runs a local comparison, produces analysis artifacts, and then uploads those artifacts to a DataHub location for sharing and audit.

## Problem
Without automation, you typically download files, align timestamps manually, handle missing values inconsistently, compute metrics in spreadsheets or ad-hoc notebooks, and then upload results by hand. That process is slow, hard to reproduce, and easy to get wrong (misaligned timestamps, wrong columns, missing files, or overwritten outputs).

## Data Flow Diagram
```mermaid
graph LR
  A["TimeSeriesComparison"] -->|Analysis files| B["UploadToDataHub"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [TimeSeriesComparison](../Automation/PLEXOS/TimeSeriesComparison/README.md) | Automation | Compare 2 to 4 time-series datasets and generate metrics, aligned data, and plots | `--file`, `--output-path`, `--cli-path`, `--environment`, `--alignment`, `--handle-missing` |
| 2 | [UploadToDataHub](../Automation/PLEXOS/UploadToDataHub/README.md) | Automation | Upload the generated analysis artifacts from local disk to a DataHub folder | `--cli-path`, `--environment`, `--directory`, `--pattern`, `--datahub-path`, `--versioned` |

## Complete Task Definition
```json
[
  {
    "ExecutionOrder": 1,
    "ScriptPath": "Automation/PLEXOS/TimeSeriesComparison/timeseries_comparison.py",
    "Arguments": [
      "-f",
      "Project/Study/Baselines/baseline_results.parquet:datahub-filepath:timestamp:Total Demand,Total Supply",
      "-f",
      "Project/Study/Results/latest_results.parquet:datahub-filepath:timestamp:Total Demand,Total Supply",
      "-o",
      "Project/Study/Results/QA:BaselineVsLatest",
      "-c",
      "/path/to/cli/plexos-cloud",
      "-e",
      "<your-environment>",
      "-j",
      "union",
      "-m",
      "none",
      "-ta",
      "_parsed_datetime"
    ]
  },
  {
    "ExecutionOrder": 2,
    "ScriptPath": "Automation/PLEXOS/UploadToDataHub/upload_to_datahub.py",
    "Arguments": [
      "-c",
      "/path/to/cli/plexos-cloud",
      "-e",
      "<your-environment>",
      "--directory",
      "{output_path}",
      "--pattern",
      "**/*",
      "-d",
      "Project/Study/Results/QA/BaselineVsLatest",
      "--versioned"
    ]
  }
]
```

## Step-by-Step Walkthrough

### 1) TimeSeriesComparison
This step resolves each `--file` entry as either a `datahub-filepath` or `local-filepath`, loads the datasets, detects or uses the specified timestamp and value columns, aligns the time series, and computes pairwise comparison metrics. It generates a JSON summary, an aligned Parquet dataset with difference columns, and PNG plots.

**Inputs**
- DataHub files referenced in `--file` configurations (for `datahub-filepath`) and/or local files (for `local-filepath`).

**Outputs**
- Uploads comparison artifacts to the DataHub location specified by `--output-path` in a timestamped subfolder (for example, `BaselineVsLatest_Comparison_20260212_143522/`).
- Also uses local temporary working files during processing; treat `{output_path}` as the local working directory for chaining in this workflow.

**Environment variables**
- None.

**Failure behavior**
- Exits with code `1` if fewer than two files resolve, if datetime/value columns cannot be detected, if alignment produces an empty dataset, or if CLI/environment authentication fails.

### 2) UploadToDataHub
This step authenticates to the specified cloud environment and uploads files from a local directory (or individual files) to a target DataHub directory. In this workflow, it uploads everything under `{output_path}` using `--directory` and `--pattern`.

**Inputs**
- Local analysis artifacts located under `{output_path}`.

**Outputs**
- Files uploaded to the DataHub directory specified by `--datahub-path`, preserving filenames. If `--versioned` is set, uploads are versioned in DataHub.

**Environment variables**
- None.

**Failure behavior**
- Exits with code `1` if authentication fails, `{output_path}` is not a directory, no files match the pattern, or uploads fail due to permissions/connectivity.

## Data Flow Between Steps

**Step 1 → Step 2**
- Step 1 produces analysis artifacts (JSON summary, Parquet aligned dataset, PNG plots). These artifacts are expected to be present under `{output_path}` for Step 2 to pick up.
- Step 2 reads all files under `{output_path}` (recursive by default with `--pattern "**/*"`) and uploads them to the DataHub folder given by `--datahub-path`.

**Naming and structure**
- TimeSeriesComparison organizes outputs in a timestamped comparison folder name of the form:
  - `Comparison_YYYYMMDD_HHMMSS/` (no custom prefix), or
  - `<CustomPrefix>_Comparison_YYYYMMDD_HHMMSS/` (when `--output-path` includes `:CustomPrefix`)
- UploadToDataHub uploads files with their original filenames into the target DataHub directory.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| TimeSeriesComparison exits with code 1 and reports fewer than two files resolved | One or more `--file` entries point to a missing DataHub path or a missing local file | Verify each `--file` path and its type (`datahub-filepath` vs `local-filepath`). Confirm the DataHub paths exist and you have access. |
| TimeSeriesComparison exits with code 1 due to missing datetime detection | The dataset has no parseable timestamp column, or the timestamp components are not correctly specified | Provide the timestamp explicitly in each `--file` config (for example `:timestamp` or `:year,month,day`). Ensure the column names match exactly. |
| TimeSeriesComparison produces empty results after alignment | `--alignment` choice removes all rows due to non-overlapping timestamps | Switch `--alignment` to `union` or confirm both datasets cover overlapping time ranges. |
| UploadToDataHub exits with code 1 and reports directory not found | `{output_path}` does not exist in the runtime context, or the workflow is being run outside the expected working directory | Ensure the workflow runs in a context where `{output_path}` is created and populated. If running locally, point `--directory` to the actual local output folder. |
| UploadToDataHub exits with code 1 due to authentication failure | Wrong `--environment` value or CLI credentials not available | Confirm `--environment` is correct for your tenant and that the CLI at `--cli-path` can authenticate interactively before running the workflow. |
| UploadToDataHub uploads nothing | `--pattern` does not match any files under the directory | Use `--pattern "**/*"` to upload everything, or adjust the glob (for example `--pattern "*.png"`). |