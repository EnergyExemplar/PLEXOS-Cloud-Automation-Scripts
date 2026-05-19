# CalibrationEvaluation – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** April 2026
**Author:** Energy Exemplar

### Purpose

Post-simulation evaluation script for iterative bid adder calibration. Extracts Region price data from solution parquets, calculates the average price, and compares it against a configurable threshold. If the average falls within the acceptable margin, calibration succeeds. Otherwise, the script adjusts parameters and enqueues the next simulation iteration automatically (up to a maximum of 3 iterations).

This is a **focused script** — it evaluates results and manages the calibration loop only. Chain it after [BidadderGeneration](../../../Pre/PLEXOS/BidadderGeneration/) and a PLEXOS simulation.

### Key Features

- Extracts and joins solution parquets (data, fullkeyinfo, period) via DuckDB
- Filters for Region price data and calculates average
- Convergence check: average within threshold ± margin = success
- Automatic retry with escalating band parameters (up to 3 iterations)
- Downloads and updates simulation payload JSON for next iteration
- Enqueues next simulation via Cloud SDK
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** [BidadderGeneration](../../../Pre/PLEXOS/BidadderGeneration/) (pre) → PLEXOS simulation
- **After this script:** Enqueues next simulation automatically if calibration is not converged

---

## DataHub Prerequisites

The following file must be uploaded to DataHub before running this script:

| File | DataHub Path | Description |
|------|-------------|-------------|
| `payload.json` | `calibration/payloadjson/payload.json` | Simulation payload JSON used to enqueue retry iterations |

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--threshold-value` | No | `80.0` | Target average price for calibration convergence. |
| `--simulation-file-path` | Yes | — | DataHub path to the simulation payload JSON. |
| `--counter` | No | `0` | Current calibration iteration counter (0-based). |
| `--margin` | No | `0.05` | Acceptable deviation from threshold (fraction, e.g. 0.05 = ±5%). |
| `--pre-task-name` | No | `generate_bid_adder` | Name of the pre-simulation task in the payload JSON. |
| `--post-task-name` | No | `evaluate_results` | Name of the post-simulation task in the payload JSON. |
| `--pre-script-name` | No | `bid_adder_generation.py` | Script filename for the pre-simulation task written into the next iteration's payload. |
| `--post-script-name` | No | `calibration_evaluation.py` | Script filename for the post-simulation task written into the next iteration's payload. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `output_path` | Working directory — staged parquets and payload are written here |
| `duck_db_path` | Path to the DuckDB database used for solution queries |
| `cloud_cli_path` | Path to the Cloud CLI executable (used for payload download and simulation enqueue) |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
eecloud
```

---

## Chaining This Script

This script is the post-simulation step in a calibration loop.

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
    "Arguments": "python3 bid_adder_generation.py --bands \"0.0:0,0.6:0,0.8:25,0.9:125,1.0:225\" --seasonal-weights \"1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05\" --counter 0 --bidadder-filename Plexos_Markup_Adders_AllGenerators-2027.csv --netload-file calibration/inputs/Netload_2027.xlsx",
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
    "Arguments": "python3 calibration_evaluation.py --threshold-value 80.0 --counter 0 --margin 0.05 --simulation-file-path calibration/payloadjson/payload.json",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

### Calibration Flow

1. **Pre:** `bid_adder_generation.py` modifies bid adders based on bands + seasonal weights
2. **Simulation:** PLEXOS engine runs with modified bid adders
3. **Post:** `calibration_evaluation.py` extracts Region prices, checks convergence:
   - **Within margin** → calibration complete (exit 0)
   - **Max iterations reached** → stop (exit 0)
   - **Outside margin** → escalate bands, enqueue next simulation with incremented counter

---

## Example Commands

```bash
# Evaluate simulation results against a threshold of 80.0 with ±5% margin
python3 calibration_evaluation.py \
  --threshold-value 80.0 \
  --counter 2 \
  --margin 0.05 \
  --simulation-file-path calibration/payloadjson/payload.json

# With custom task and script names
python3 calibration_evaluation.py \
  --threshold-value 80.0 \
  --counter 0 \
  --margin 0.05 \
  --simulation-file-path calibration/payloadjson/payload.json \
  --pre-task-name my_bid_adder \
  --post-task-name my_evaluator \
  --pre-script-name my_bid_adder_generation.py \
  --post-script-name my_calibration_evaluation.py
```
