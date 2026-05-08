# Island Node – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** 2026-05-04
**Author:** Energy Exemplar

### Purpose

Detects transmission-network islands caused by branch outages and writes SRD properties (Node Units, Generator Units Out, Must Run, DC Tie Region Units) into the PLEXOS model so the simulation engine respects islanding constraints.

This is a **focused script** — it downloads inputs from DataHub, runs the full island-detection pipeline, writes SRD CSV outputs, imports them into the model DB, regenerates the XML, and uploads results back to DataHub.

### Key Features

- Downloads input files from DataHub and flattens folder structure
- Processes branch outage data and generates hourly outage status
- Uses NetworkX graph analysis to detect electrically isolated islands
- Builds SRD CSVs for Node, Generator Unit Out, Must Run, and DC Tie properties
- Imports SRD properties into the PLEXOS model via the SDK
- Regenerates project.xml from the modified DB
- Uploads all outputs and model artifacts to DataHub
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** None (standalone pre-script)
- **After this script:** PLEXOS engine simulation

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--start-date` | Yes | — | Analysis start date, e.g. `2025-03-01T00:00` |
| `--end-date` | Yes | — | Analysis end date, e.g. `2025-03-31T23:00` |
| `--output-folder` | Yes | — | DataHub remote folder for output files, e.g. `IslandScript/outputs` |
| `--model-name` | Yes | — | PLEXOS Model object name to enable scenarios on |
| `--branch-data-file` | Yes | — | DataHub path to branch outage CSV, e.g. `IslandScript/inputs/Plexos Branch Data.csv` |
| `--network-data-file` | Yes | — | DataHub path to network topology Excel, e.g. `IslandScript/inputs/Network Branch Data.xlsx` |
| `--plexos-input-file` | Yes | — | DataHub path to PLEXOS input Excel, e.g. `IslandScript/inputs/Island Script data 0527.xlsx` |
| `--scenario` | Yes | — | Scenario name for SRD entries, e.g. `Node off island script` |
| `--default-from-date` | No | `12/1/2024 0:00` | Default From Date for outages missing a start date |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the Cloud CLI executable (required) |
| `output_path` | Working directory — files written here are uploaded as solution artifacts (required) |
| `study_id` | Study ID for DB-to-XML conversion (required, fail-fast) |
| `simulation_path` | Root path for study files; `reference.db` and `project.xml` live here |
| `sqlite_input_path` | Fallback model DB path when `simulation_path` is unavailable |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
pandas
networkx
openpyxl
plexos_sdk
eecloud
```

---

## Input Files

The following files must exist on DataHub at the paths specified by their respective arguments:

| Argument | Format | Description |
|---|---|---|
| `--branch-data-file` | CSV | Branch outage data with Date From/To and status |
| `--network-data-file` | Excel | Network topology (From/To Number mapping) |
| `--plexos-input-file` | Excel | Resource-node memberships, generator outages, must-run units, DC tie memberships |

---

## Output Files

Written to `output_path` and uploaded to DataHub under `--output-folder`:

| File | Format | Description |
|---|---|---|
| `grid_data.csv` | CSV | Processed grid/branch outage data |
| `hourly_data.parquet` | Parquet | Hourly outage status matrix |
| `island_node_srd.csv` | CSV | SRD: Node Units = 0 for islanded nodes |
| `island_gen_unit_out_srd.csv` | CSV | SRD: Generator Units Out for islanded generators |
| `island_gen_unit_out_srd_helper.csv` | CSV | Helper: generator outage scenario labelling |
| `island_gen_must_run_srd.csv` | CSV | SRD: Must Run units in islanded areas |
| `island_gen_must_run_srd_helper.csv` | CSV | Helper: must-run units affected by islands |
| `dc_tie_units_srd.csv` | CSV | SRD: DC Tie Region Units = 0 for islanded regions |
| `final_island_periods.xlsx` | Excel | Consolidated island period summary per node |

---

## Example Task Definition

```json
{
  "Name": "Island Detection and SRD Import",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/island_node.py", "Version": null }
  ],
  "Arguments": "python3 island_node.py --start-date 2025-03-01T00:00 --end-date 2025-03-31T23:00 --output-folder IslandScript/outputs --model-name WY2025 woPTC_hourly --branch-data-file IslandScript/inputs/Plexos Branch Data.csv --network-data-file IslandScript/inputs/Network Branch Data.xlsx --plexos-input-file IslandScript/inputs/Island Script data 0527.xlsx --scenario Node off island script",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

---

## Expected Behaviour

### Success

1. Script starts and logs its configuration.
2. Downloads input files from DataHub.
3. Processes grid data and generates hourly outage status.
4. Detects islands using graph analysis.
5. Builds SRD CSVs for Node, Generator, Must Run, and DC Tie properties.
6. Uploads SRD outputs to DataHub.
7. Imports SRD properties into the PLEXOS model DB.
8. Regenerates `project.xml` from the modified DB.
9. Uploads model artifacts to DataHub.
10. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| Missing required environment variable | 1 | Verify execution environment |
| Input file not found after download | 1 | Check DataHub input folder contents |
| Model DB not found | 1 | Check `simulation_path` or `sqlite_input_path` |
| SRD import failure | 1 | Check model DB structure matches SRD columns |
| XML regeneration failure | 1 | Original XML is restored from backup |
