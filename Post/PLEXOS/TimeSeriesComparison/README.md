# Time Series Comparison – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 2.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Compares 2-4 time-series files and writes statistical results, aligned data, and 3-panel plots to an output directory. No DataHub operations — focused purely on analysis. Chain with [UploadToDataHub](../UploadToDataHub/) to push results to DataHub.

### Key Features

- Multi-format file support: CSV (UTF-8 + latin-1 fallback), Parquet, Excel, JSON
- Automatic datetime detection — single datetime column or year/month/day/hour component columns
- Configurable alignment: intersection, union, use-first-file, use-last-file
- Configurable missing value strategy: none, drop, forward fill, backward fill, interpolate
- Pairwise statistics: MAE, RMSE, Correlation, R2, MAPE, max error, mean bias
- 3-panel plots per pair: overlay, difference (with fill), scatter + regression line
- Gap detection (flags intervals > 3x typical spacing)
- Anomaly detection per series (IQR method)
- URL-encoding support for file paths containing spaces
- Output: aligned Parquet + JSON summary + PNG plots
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** [Pre/PLEXOS/DownloadFromDataHub](../../../Pre/PLEXOS/DownloadFromDataHub/) — download baseline files before the simulation so they are available for comparison.
- **After this script:** [UploadToDataHub](../UploadToDataHub/) — upload the comparison results to a specific DataHub path.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-f, --file PATH[:LABEL]` | Yes | — | File to compare. Repeat 2-4 times. Optionally append `:Label`. Relative paths resolved against `simulation_path`. URL-encode spaces as `%20`. |
| `-o, --output-path PATH` | No | `output_path` env var | Directory to write results. Pass `output_path` to explicitly use the env var. |
| `-p, --prefix TEXT` | No | None | Prefix for the timestamped output folder (`{prefix}_Analysis_{ts}/`). |
| `-j, --alignment CHOICE` | No | `union` | Timestamp alignment: `intersection` `union` `use-first-file` `use-last-file`. |
| `-m, --handle-missing CHOICE` | No | `none` | Missing value strategy after alignment: `none` `drop` `forward_fill` `backward_fill` `interpolate`. |
| `-ta, --timestamp-alias NAME` | No | None | Rename `_parsed_datetime` to this name in the output Parquet. |
| `-k, --keep-zero-diff` | No | `False` | Keep rows where all differences are zero (default: zero-diff rows removed). |

---

## Environment Variables Used

| Variable | Description |
|---|---|
| `output_path` | Default output directory when `-o` is not provided. |
| `simulation_path` | Used to resolve relative file paths (defaults to `/simulation`). |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
pandas>=1.3.0
numpy>=1.20.0
matplotlib>=3.3.0
seaborn>=0.11.0
pyarrow>=6.0.0
openpyxl>=3.0.0
```

---

## Chaining This Script

### Chain 1 — Compare and upload results

```json
[
  {
    "Name": "Compare simulation output vs baseline",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/timeseries_comparison.py", "Version": null },
      { "Path": "Project/Study/baseline.csv", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 timeseries_comparison.py -f baseline.csv:Baseline -f result.csv:Simulation -o output_path -p ForecastCheck",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload analysis results to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Analysis -p ForecastCheck_*/**",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Convert CSV outputs, compare, then upload

```json
[
  {
    "Name": "Convert CSV outputs to Parquet",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/convert_csv_to_parquet.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 convert_csv_to_parquet.py -r output_path",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Compare results vs baseline",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/timeseries_comparison.py", "Version": null },
      { "Path": "Project/Study/baseline.parquet", "Version": null }
    ],
    "Arguments": "python3 timeseries_comparison.py -f baseline.parquet:Baseline -f result.parquet:Simulation -o output_path -p MyStudy -j union -m interpolate",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Upload all results to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  }
]
```

---

## Example Commands

```bash
# Two files, default settings
python3 timeseries_comparison.py -f 'baseline.csv:Baseline' -f 'result.csv:Simulation' -o output_path -p 'ForecastCheck'

# Three-way comparison
python3 timeseries_comparison.py -f 'baseline.csv:Baseline' -f 'scenario_a.csv:ScenarioA' -f 'scenario_b.csv:ScenarioB' -o output_path -p 'MultiScenario'

# Intersection alignment with interpolation to fill gaps
python3 timeseries_comparison.py -f 'baseline.csv:Baseline' -f 'result.csv:Simulation' -o output_path -p 'ForecastCheck' -j intersection -m interpolate

# Parquet files with a custom timestamp column name in the output
python3 timeseries_comparison.py -f 'baseline.parquet:Baseline' -f 'result.parquet:Simulation' -o output_path -p 'MyStudy' -ta 'Timestamp'

# File paths with spaces — URL-encode each space as %20
python3 timeseries_comparison.py -f '/simulation/TimeSeries/Gas%20Demand/Gas%20Demand%20Forecast%20NRT%205min.csv:Baseline' -f '/output/Results/Gas%20Demand%20Forecast%20NRT%205min.csv:Run2' -o output_path -p 'Study3'
```

---

## Expected Behaviour

### Success

1. Loads each file; retries CSV with latin-1 if UTF-8 fails.
2. Detects datetime — single column or year/month/day/hour component columns.
3. Skips files that fail; aborts if fewer than 2 remain.
4. Aligns series using the specified join type; auto-upgrades `outer`+`drop` to `interpolate`.
5. Applies missing value strategy.
6. Reports gap and anomaly counts.
7. Calculates pairwise statistics and saves 3-panel plots.
8. Saves aligned Parquet, JSON summary, and PNG plots to the output directory.
9. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| Fewer than 2 files load successfully | 1 | Fix file paths; check `simulation_path` |
| No datetime column or components detected | skipped | Pre-process the file or rename columns to `timestamp`/`year`/`month`/`day` |
| No numeric value columns | skipped | Check file contents |
| No rows remain after missing handling | 1 | Change `-m` strategy or use `-j union` |
