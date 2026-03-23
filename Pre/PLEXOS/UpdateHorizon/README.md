# Update Horizon – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Updates the simulation horizon (date range, step count, and step type) in a PLEXOS model before the engine starts. This allows parameterising the simulation period at run time without manually editing the model.

After modifying `reference.db` via the PLEXOS SDK, the script deletes the existing `project.xml` and regenerates it from the updated database using the Cloud CLI converter.

This is a **focused script** — it updates the horizon only. No other model modifications are made.

### Key Features

- Updates any combination of `date_from`, `step_count`, and `step_type` on a named horizon
- Accepts step type as a name (`day`, `week`, `month`, `year`) or number (`1`–`4`)
- Regenerates `project.xml` from the updated `.db` so the engine sees the change
- Uses the PLEXOS SDK transaction model for safe, atomic updates
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** *(none — typically the first pre-simulation task)*
- **After this script:** Any other pre-simulation task that reads from `reference.db` or `project.xml`

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--horizon-name` | Yes | — | Name of the horizon to update |
| `--date-from` | No | *(unchanged)* | New simulation start date (ISO format, e.g. `2025-01-01`) |
| `--step-count` | No | *(unchanged)* | New number of steps |
| `--step-type` | No | *(unchanged)* | Step type: `day` (1), `week` (2), `month` (3), `year` (4) |

At least one of `--date-from`, `--step-count`, or `--step-type` must be provided.

> **Horizon names with spaces:** Pass the value with %20 as placeholder for spaces (e.g. `--horizon-name 'My%20Horizon'`). 

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the Cloud CLI executable; used for db-to-xml conversion |
| `study_id` | Current study identifier; required by the db-to-xml converter |
| `simulation_path` | Root path for study files; location of `reference.db` and `project.xml` (read/write in pre tasks) |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
plexos_sdk
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Update horizon before simulation

```json
[
  {
    "Name": "Update simulation horizon to 2026",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/update_horizon.py", "Version": null }
    ],
    "Arguments": "python3 update_horizon.py --horizon-name Base --date-from 2026-01-01 --step-count 12 --step-type month",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  }
]
```

---

## Example Commands

```bash
# Update start date and step count
python3 update_horizon.py --horizon-name Base --date-from 2026-01-01 --step-count 12

# Change step type to weekly with 52 steps
python3 update_horizon.py --horizon-name Base --step-type week --step-count 52

# Update only the start date
python3 update_horizon.py --horizon-name Base --date-from 2027-06-01

# Use numeric step type
python3 update_horizon.py --horizon-name Base --step-type 3 --step-count 24

# Horizon name with spaces — URL-encode when the task runner doesn't support shell quoting
python3 update_horizon.py --horizon-name Base%20Horizon --date-from 2026-01-01
```

---

## Expected Behaviour

### Success

1. Script validates that `reference.db` exists in `simulation_path`.
2. Opens the database with the PLEXOS SDK and locates the named horizon.
3. Updates the specified horizon attributes inside a transaction.
4. Deletes the existing `project.xml`.
5. Converts the updated `.db` back to XML using the Cloud CLI.
6. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `cloud_cli_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| `study_id` env var missing | 1 | Ensure the variable is set in the execution environment |
| `reference.db` not found | 1 | Check `simulation_path` |
| Horizon name not found in model | 1 | Verify `--horizon-name` matches a horizon in the model |
| No update arguments provided | 1 | Provide at least one of `--date-from`, `--step-count`, `--step-type` |
| db-to-xml conversion fails | 1 | Check CLI path and study_id |
