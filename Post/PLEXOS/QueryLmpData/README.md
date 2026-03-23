# QueryLmpData – README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Queries generation-weighted Locational Marginal Price (LMP) data from the PLEXOS solution database. The script reads solution parquet views (set up by [ConfigureDuckDbViews](../ConfigureDuckDbViews/)), joins with a technology classification CSV and a memberships CSV, calculates generation-weighted LMPs by zone, and stages two CSV reports to `output_path` for automatic platform upload.

This is a **focused script** — LMP analysis only. Chain it after `configure_duck_db_views.py` (to create solution views) and after any script that produces the memberships CSV.

### Key Features

- Reads generation, price received, and installed capacity from PLEXOS solution parquet views
- Maps generators to zones via memberships data
- Calculates generation-weighted LMP (`SUM(Generation × Price) / SUM(Generation)`) per zone per timestamp
- Classifies generators by technology using a configurable lookup CSV
- Optionally generates an hourly generation-by-fuel chart for a specific date
- Configurable period type and phase filters
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** [ConfigureDuckDbViews](../ConfigureDuckDbViews/) — sets up DuckDB views from the solution parquet files
- **Before this script:** Any script that produces the memberships CSV in `output_path` (e.g. a `query_write_memberships.py` custom script)
- **After this script:** [UploadToDataHub](../UploadToDataHub/) — upload staged CSVs to a specific DataHub path
- **After upload (optional):** [CleanupFiles](../CleanupFiles/) — remove staged output folders if no longer needed

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-t, --tech-lookup-file` | Yes | — | Path to the technology classification CSV. A plain filename is resolved relative to `simulation_path`; an absolute path is used as-is. Expected columns: `PLEXOS` (generator category name), `PSO` (technology label). |
| `-m, --memberships-file` | No | `memberships_data.csv` | Filename of the memberships CSV in `output_path`, or an absolute path. Expected columns: `parent_class`, `parent_object`, `child_class`, `child_object`. |
| `--period-type` | No | `Interval` | `PeriodTypeName` value to filter from `fullkeyinfo` (e.g. `Interval`, `Day`). |
| `--phase` | No | `ST` | `PhaseName` value to filter from `fullkeyinfo` (e.g. `ST`, `LT`). |
| `--graph-date` | No | — | Date for the hourly generation-by-fuel chart, format `YYYY-MM-DD`. If omitted, no chart is generated. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `duck_db_path` | Path to the DuckDB solution database with pre-configured views (set up by `configure_duck_db_views.py`) |
| `output_path` | Working directory — CSVs and charts written here are uploaded as solution artifacts |
| `simulation_path` | Base directory for resolving plain filenames passed to `--tech-lookup-file` |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
matplotlib
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Configure views, query LMP data, upload results

```json
[
  {
    "Name": "Configure DuckDB Solution Views",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/configure_duck_db_views.py", "Version": null }
    ],
    "Arguments": "python3 configure_duck_db_views.py",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Query Write Memberships",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/query_write_memberships.py", "Version": null }
    ],
    "Arguments": "python3 query_write_memberships.py",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Query LMP Data",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/query_lmp_data.py", "Version": null },
      { "Path": "Project/Study/plexos_pso_tech_lookup.csv", "Version": null }
    ],
    "Arguments": "python3 query_lmp_data.py -t plexos_pso_tech_lookup.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 3
  },
  {
    "Name": "Upload LMP Results to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/Results -p '*.csv' '*.png'",
    "ContinueOnError": true,
    "ExecutionOrder": 4
  }
]
```

### Chain 2 — With hourly generation chart

```json
[
  {
    "Name": "Configure DuckDB Solution Views",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/configure_duck_db_views.py", "Version": null }
    ],
    "Arguments": "python3 configure_duck_db_views.py",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Query Write Memberships",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/query_write_memberships.py", "Version": null }
    ],
    "Arguments": "python3 query_write_memberships.py",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Query LMP Data with Chart",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/query_lmp_data.py", "Version": null },
      { "Path": "Project/Study/plexos_pso_tech_lookup.csv", "Version": null }
    ],
    "Arguments": "python3 query_lmp_data.py -t plexos_pso_tech_lookup.csv --graph-date 2024-01-15",
    "ContinueOnError": false,
    "ExecutionOrder": 3
  }
]
```

---

## Example Commands

```bash
# Minimum required — rely on defaults for optional args
python3 query_lmp_data.py -t plexos_pso_tech_lookup.csv

# Explicit memberships file path
python3 query_lmp_data.py -t plexos_pso_tech_lookup.csv -m memberships_data.csv

# Generate hourly chart for a specific date
python3 query_lmp_data.py -t plexos_pso_tech_lookup.csv --graph-date 2024-01-15

# Custom period type and phase
python3 query_lmp_data.py -t plexos_pso_tech_lookup.csv --period-type Day --phase LT

# Absolute paths for CSV inputs
python3 query_lmp_data.py \
  -t /simulation/plexos_pso_tech_lookup.csv \
  -m /output/memberships_data.csv \
  --graph-date 2024-06-01
```

---

## Outputs

| File | Format | Description |
|---|---|---|
| `gen_weighted_lmp_{YYYYMMDD_HHMMSS}.csv` | CSV | Generation-weighted LMP by zone and timestamp |
| `generation_by_generator_{YYYYMMDD_HHMMSS}.csv` | CSV | Total generation by generator name and date |
| `gen_by_fuel_{YYYY-MM-DD}.png` | PNG | Hourly generation by fuel category (from technology lookup CSV) — only when `--graph-date` is provided |

---

## Expected Behaviour

### Success

1. Reads `duck_db_path` and `output_path` from env — exits with code `1` immediately if either is missing.
2. Resolves `--tech-lookup-file` relative to `simulation_path` if a plain filename is given.
3. Resolves `--memberships-file` relative to `output_path` if a plain filename is given.
4. Validates `--graph-date` format if provided.
5. Connects to the DuckDB solution database.
6. Creates views for tech lookup and memberships CSVs.
7. Builds the 9-step LMP analysis pipeline as DuckDB views.
8. Exports `gen_weighted_lmp_*.csv` and `generation_by_generator_*.csv` to `output_path`.
9. If `--graph-date` is provided, generates `gen_by_fuel_{date}.png` (warns and skips if no matching data).
10. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `duck_db_path` or `output_path` env var missing | 1 | Ensure the variables are set in the execution environment |
| `--tech-lookup-file` file not found | 1 | Verify the filename and that the file is present in `simulation_path` |
| `--memberships-file` file not found | 1 | Verify the filename and that the memberships CSV has been produced by a prior task |
| `--graph-date` invalid format | 1 | Use `YYYY-MM-DD` format (e.g. `2024-01-15`) |
| DuckDB error (missing views, schema mismatch) | 1 | Ensure `configure_duck_db_views.py` ran successfully before this script |
| Solution views missing (`fullkeyinfo`, `data`, `period`, `object`, `category`) | 1 | Chain `configure_duck_db_views.py` with a lower `ExecutionOrder` |
