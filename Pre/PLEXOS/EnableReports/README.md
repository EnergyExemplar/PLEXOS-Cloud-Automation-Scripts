# EnableReports – README

## Overview

**Type:** Pre
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026
**Author:** Energy Exemplar

### Purpose

Extends an existing Report object in a PLEXOS model with additional reporting properties using the PLEXOS SDK. After updating the database, converts it back to XML so the engine picks up the change. Reporting property lang ids are resolved automatically from `reference.db` — no numeric ids need to be looked up manually. Typical use: add emissions by generator, fuel offtake by generator, or similar per-property outputs before the simulation runs.

This is a **focused script** — it configures reports only. No other model modifications are made.

### Key Features

- Adds reporting properties by name to an existing Report object — no numeric ids required
- Resolves Report class lang id and property lang ids automatically from `reference.db`
- Regenerates `project.xml` from the updated `.db` so the engine sees the change
- Accepts comma-separated property names with case-insensitive matching
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** *(none — typically the first pre-simulation task, or after UpdateHorizon)*
- **After this script:** PLEXOS simulation execution task

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--report-object-name` | Yes | — | Name of the existing Report object in the model. Supports URL-encoding (e.g. `My%20Report`). |
| `--reporting-property-names` | Yes | — | Comma-separated reporting property names to enable (e.g. `Emissions by Generator,Fuel Offtake by Generator`). Names are matched case-insensitively against `t_property_report`. |
| `--phase` | No | `LT` | Simulation phase: `ST` (1), `MT` (2), `PASA` (3), `LT` (4). Case-insensitive. |
| `--report-period` | No | `true` | Enable period output. |
| `--report-samples` | No | `false` | Enable sample output. |
| `--report-statistics` | No | `false` | Enable statistics output. |
| `--report-summary` | No | `true` | Enable summary output. |
| `--write-flat-files` | No | `false` | Enable flat-file output. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the Cloud CLI executable; used for db-to-xml conversion |
| `study_id` | Current study identifier; required by the db-to-xml converter |
| `simulation_path` | Root path for study files; `reference.db` and `project.xml` are read/written here |

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

### Extend report before simulation

```json
[
  {
    "Name": "Extend report with emissions and fuel offtake properties",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/enable_reports.py", "Version": null }
    ],
    "Arguments": "python3 enable_reports.py --report-object-name Generators --reporting-property-names 'Emissions by Generator,Fuel Offtake by Generator' --phase LT --report-period true --report-summary true",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  }
]
```

---

## Example Commands

```bash
# Add a single reporting property
python3 enable_reports.py --report-object-name Generators --reporting-property-names 'Emissions by Generator'

# Add multiple properties
python3 enable_reports.py --report-object-name Generators --reporting-property-names 'Emissions by Generator,Fuel Offtake by Generator'

# Target a specific phase with additional output types
python3 enable_reports.py --report-object-name Generators --reporting-property-names 'Emissions by Generator' --phase ST --report-samples true --report-statistics true

# Report object name with spaces — URL-encode when the task runner doesn't support shell quoting
python3 enable_reports.py --report-object-name My%20Report --reporting-property-names 'Emissions by Generator'
```

---

## Expected Behaviour

### Success

1. Script validates CLI arguments.
2. Resolves model path as `{simulation_path}/reference.db`.
3. Queries `reference.db` to discover the Report class lang id from `t_class`.
4. Queries `reference.db` to resolve each property name to a lang id from `t_property_report`.
5. Opens the PLEXOS model and looks up the named Report object.
6. Calls `configure_report_properties` inside a transaction to add all requested reporting properties.
7. Renames the existing `project.xml` to a `.bak` backup, regenerates a new `project.xml` from the updated database via the Cloud CLI, restores the backup on failure, and removes the `.bak` only after regeneration succeeds.
8. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `cloud_cli_path` env var missing | 1 | Ensure the variable is set in the execution environment |
| `study_id` env var missing | 1 | Ensure the variable is set in the execution environment |
| Missing required argument | 1 | Provide `--report-object-name` and `--reporting-property-names` |
| Invalid boolean argument value | 1 | Use `true/false`, `yes/no`, or `1/0` |
| `reference.db` not found | 1 | Check `simulation_path` |
| Report class not found in `t_class` | 1 | Verify the model contains a class named `Report` |
| Property name not found in `t_property_report` | 1 | Verify property names match entries in `reference.db` |
| Report object not found in model | 1 | Verify `--report-object-name` matches an object in the model |
| db-to-xml conversion fails | 1 | Check `cloud_cli_path` and `study_id` |
| SDK error during configuration | 1 | Verify model/SDK compatibility |
