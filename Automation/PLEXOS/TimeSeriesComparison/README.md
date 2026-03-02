# Time Series Comparison (Local) – README

## Overview

**Type:** Automation
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026
**Author:** Energy Exemplar

### Purpose

Compares 2–4 time-series datasets from multiple file formats (CSV, Excel, Parquet, JSON) for local or standalone use. Unlike the Post version, authentication and environment selection are passed explicitly as arguments, making this suitable for running outside a cloud simulation context.

**Use Cases:**
- Local comparison of datasets downloaded from DataHub
- Standalone quality assurance or validation outside of a simulation run
- Multi-scenario or multi-region comparative analysis on a local machine

---

## Arguments

### Required Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `-f, --file` | str | File configuration: `filepath:type:timestamp:data_cols:group_cols:aliases`. Type: `datahub-filepath` or `local-filepath`. Repeat for 2–4 files | `-f "file1.csv":local-filepath:date:demand,supply` |
| `-o, --output-path` | str | DataHub path for results. Format: `path` or `path:CustomPrefix` | `-o Project/Study/Results:MyAnalysis` |
| `-c, --cli-path` | str | Full path to the PLEXOS Cloud CLI executable | `-c /usr/local/bin/plexos-cloud` |
| `-e, --environment` | str | Cloud environment name (contact your Energy Exemplar administrator) | `-e <your-environment>` |

### Optional Arguments

| Argument | Type | Default | Description | Example |
|----------|------|---------|-------------|---------|
| `-ta, --timestamp-alias` | str | `_parsed_datetime` | Output column name for the parsed datetime | `-ta DateTime` |
| `-j, --alignment` | choice | `union` | Join type: `intersection` / `union` / `use-first-file` / `use-last-file` | `-j intersection` |
| `-m, --handle-missing` | choice | `none` | Missing value strategy: `none` / `drop` / `forward_fill` / `backward_fill` / `interpolate` | `-m interpolate` |
| `-k, --keep-diff-unchanged` | flag | `False` | Keep records where all differences are zero | `-k` |

---

## Environment Variables Used

**None.** This script is designed for local/standalone use and does not rely on environment variables. All paths are passed as explicit arguments.

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`. If your script requires additional packages, add them there.

```
# In root requirements.txt
pandas>=1.3.0
numpy>=1.20.0
matplotlib>=3.3.0
seaborn>=0.11.0
openpyxl>=3.0.0
pyarrow>=6.0.0
```

---

## Example Task Definition

This script is designed for **local / standalone execution** and does not need a cloud task definition. Run it directly from a terminal:

```bash
python timeseries_comparison.py \
  -f "forecast.csv":local-filepath \
  -f "actual.csv":local-filepath \
  -o "Project/Study/Results:ForecastCheck" \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment>
```

> For running as a post-simulation task inside PLEXOS Cloud, use the cloud-native version at [Post/PLEXOS/TimeSeriesComparison/](../../Post/PLEXOS/TimeSeriesComparison/) instead.

---

## Expected Behaviour

### Success

1. Validates all arguments and detects duplicate aliases early.
2. Connects to the specified cloud environment using the provided CLI path.
3. Resolves each file — downloads from DataHub (`datahub-filepath`) or loads from local disk (`local-filepath`). Files that fail are skipped; at least 2 must resolve.
4. Loads data from all resolved files.
5. Detects or uses specified datetime and value columns; pivots flat-format data if group columns are provided.
6. Aligns dataframes using the specified join type.
7. Applies missing value handling strategy.
8. Performs all pairwise comparisons and calculates statistics (MAE, RMSE, Correlation, R², MAPE).
9. Generates output: JSON summary, aligned Parquet with difference columns, PNG plots.
10. Uploads results to DataHub and cleans up local temp files.
11. Exits with code `0`. Output saved to `{output_dir}/{PREFIX}_Comparison_{TIMESTAMP}/`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| Invalid CLI path or environment | 1 | Verify `-c` path is correct and `-e` environment name is valid |
| Fewer than 2 files resolve successfully | 1 | Fix file paths or check DataHub connectivity |
| File not found (local-filepath) | 1 | Verify the local file path exists |
| No datetime column detected | 1 | Specify timestamp columns explicitly with `-f ...:...:timestamp_col` |
| No numeric value columns found | 1 | Specify value columns explicitly with `-f ...:...:...:value_col` |
| Empty DataFrame after alignment | 1 | Check join type and whether the datasets share overlapping timestamps |

---

## Output Artifacts

All outputs are uploaded to the DataHub path provided via `-o` and organised in a timestamped folder.

| Artifact | Format | Description |
|----------|--------|-------------|
| `comparison_summary.json` | JSON | Full metrics, statistics, and run metadata |
| `aligned_data.parquet` | Parquet | Merged time series with per-pair difference columns |
| `comparison_*.png` | PNG | Time series overlay, difference, and scatter plots per compared pair |

**Folder naming:**
- Without prefix: `Comparison_20260212_143522/`
- With custom prefix: `MyAnalysis_Comparison_20260212_143522/`

---

## Examples

### Example 1: Compare two local files

```bash
python timeseries_comparison.py \
  -f forecast.csv:local-filepath \
  -f actual.csv:local-filepath \
  -o "Project/Study/Results:ForecastCheck" \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment>
```

### Example 2: Mix local and DataHub files

```bash
python timeseries_comparison.py \
  -f "historical.csv":local-filepath:timestamp:price \
  -f "Project/Study/forecast.csv":datahub-filepath:date:price \
  -o "Project/Study/Results:HistoricalVsForecast" \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -j union \
  -m backward_fill \
  -ta DateTime
```

### Example 3: Multi-component datetime with regional pivoting

```bash
python timeseries_comparison.py \
  -f "forecast_data.csv":local-filepath:year,month,day:"Total Demand","Total Supply":Region:forecast \
  -f "Project/Study/actual.csv":datahub-filepath:Year,Month,Day:demand,supply:Region:actual \
  -o "Project/Study/Results:RegionalAnalysis" \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -j intersection \
  -m interpolate
```

---

## Related Scripts

**Relies on:** [DownloadFromDataHub](../DownloadFromDataHub/), [UploadToDataHub](../UploadToDataHub/).
