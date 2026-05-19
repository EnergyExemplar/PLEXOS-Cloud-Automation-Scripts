# BidadderGeneration – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** April 2026
**Author:** Energy Exemplar

### Purpose

Generates bid adder markup values from net-load curves and applies them to an existing bid adder file before simulation. The script downloads load, solar, and wind data from DataHub, calculates a normalized net-load curve, applies piecewise-linear interpolation with configurable band breakpoints, multiplies by monthly seasonal weights, and writes the modified bid adder back into the model's `timeseries.zip`.

This is a **focused script** — it modifies bid adders only. Chain it with [CalibrationEvaluation](../../../Post/PLEXOS/CalibrationEvaluation/) for an iterative calibration loop.

### Key Features

- Reads existing bid adder file (CSV or XLSX) and applies markup as a multiplier
- Updates `timeseries.zip` in-place so the PLEXOS engine picks up the change
- Copies modified bid adder to `output_path` for downstream tasks
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** Upload your net-load Excel file to DataHub and pass its path via `--netload-file`
- **After this script:** PLEXOS simulation → [CalibrationEvaluation](../../../Post/PLEXOS/CalibrationEvaluation/) (post)

---

## DataHub Prerequisites

The following files must be uploaded to DataHub before running this script:

| File | DataHub Path (example) | Description |
|------|------------------------|-------------|
| Net-load Excel file | passed via `--netload-file` | Load, Solar, and Wind data (3 sheets). Path is configurable — upload to any DataHub location and pass the path as `--netload-file`. |

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--bands` | No | `0.0:0,0.6:0,0.8:25,0.9:125,1.0:225` | Piecewise-linear breakpoints as `x:y` pairs. `x` = normalized net-load, `y` = markup value. **Note:** when `--counter` is a supported calibration counter (`0`, `1`, or `2`), the script overrides any CLI value and uses the canonical `BANDS_BY_COUNTER` breakpoints for that counter instead. |
| `--seasonal-weights` | No | `1:0.50,2:0.55,...,12:1.05` | Monthly weight multipliers as `month:weight` pairs (all 12 months). |
| `--counter` | No | `0` | Calibration iteration counter. Supported counters `0`–`2` select canonical breakpoint sets from the script's `BANDS_BY_COUNTER` table and therefore override any value supplied via `--bands`. |
| `--bidadder-filename` | Yes | — | Name of the existing bid adder file in the timeseries subdirectory (e.g. `Plexos_Markup_Adders_AllGenerators-2027.csv`). |
| `--netload-file` | Yes | — | DataHub path to the net-load Excel file (e.g. `calibration/inputs/Netload_2027.xlsx`). Supports file names with spaces. |
| `--timeseries-subdir` | No | `TimeSeries/Bid Adders` | Subdirectory under `simulation_path` where the bid adder file lives, and the zip entry prefix inside `timeseries.zip`. Supports names with spaces. |
| `--local-mode` | No | `False` | Use local input files from `inputs/` folder instead of downloading from DataHub. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the Cloud CLI executable (required for DataHub download) |
| `simulation_path` | Root path for study files; bid adder and `timeseries.zip` are read/written here |
| `output_path` | Modified bid adder is copied here for downstream tasks |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
pandas
numpy
openpyxl
eecloud
```

---

## Chaining This Script

This script is designed to be the pre-simulation step in a calibration loop.

### Calibration Loop — Generate Bid Adder → Simulate → Evaluate

```json
[
  {
    "Name": "generate_bid_adder",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/bid_adder_generation.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 bid_adder_generation.py --bands \"0.0:0,0.6:0,0.8:125,0.9:625,1.0:1125\" --seasonal-weights \"1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05\" --counter 2 --bidadder-filename Plexos_Markup_Adders_AllGenerators-2027.csv --netload-file calibration/inputs/Netload_2027.xlsx",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "evaluate_results",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/calibration_evaluation.py", "Version": null },
      { "Path": "Project/Study/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 calibration_evaluation.py --threshold-value 80.0 --counter 2 --margin 0.05 --simulation-file-path calibration/payloadjson/payload.json",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

---

## Example Commands

```bash
# Cloud mode — download inputs from DataHub and modify bid adder
python3 bid_adder_generation.py \
  --bands "0.0:0,0.6:0,0.8:125,0.9:625,1.0:1125" \
  --seasonal-weights "1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05" \
  --counter 2 \
  --bidadder-filename Plexos_Markup_Adders_AllGenerators-2027.csv \
  --netload-file calibration/inputs/Netload_2027.xlsx

# Local mode — use files from inputs/ folder
python3 bid_adder_generation.py \
  --bands "0.0:0,0.6:0,0.8:25,0.9:125,1.0:225" \
  --seasonal-weights "1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05" \
  --counter 0 \
  --bidadder-filename Plexos_Markup_Adders_AllGenerators-2027.csv \
  --netload-file calibration/inputs/Netload_2027.xlsx \
  --local-mode

# Custom timeseries subdirectory
python3 bid_adder_generation.py \
  --bands "0.0:0,0.6:0,0.8:25,0.9:125,1.0:225" \
  --seasonal-weights "1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05" \
  --counter 0 \
  --bidadder-filename MyAdders.csv \
  --netload-file data/inputs/MyNetload.xlsx \
  --timeseries-subdir "TimeSeries/Custom Adders"
```
