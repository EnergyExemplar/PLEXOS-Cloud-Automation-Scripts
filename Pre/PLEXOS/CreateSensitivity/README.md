# CreateSensitivity - README

## Overview

**Type:** Pre  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** March 2026  
**Author:** Energy Exemplar

### Purpose

Creates sensitivity overrides on a target property in a PLEXOS input model using the PLEXOS SDK.

This is a focused script that performs one job: write one sensitivity definition for one target property per task invocation.

If you need to apply sensitivities to multiple properties or objects, chain multiple task entries so each invocation remains isolated and easy to troubleshoot.

The script supports two modes controlled by `--data-file-name`:

1. Numeric mode (`--data-file-name` omitted)
- Reads the current base value of the target property.
- Creates/reuses a Variable object.
- Writes `Variable.Profile = base × (1 + sensitivity)` with a Scenario tag.
- Tags the target property with the Variable as an expression and the Scenario tag.
- Sets action `=` (assign) on the exact Variable expression-tag row.

2. Expression mode (`--data-file-name` provided)
- Creates/reuses a Variable object.
- Writes `Variable.Profile = 1 + sensitivity` with a Scenario tag.
- Looks up an existing Data File object by name.
- Tags the target property with Variable expression tag + Scenario tag + Data File tag.
- Sets action `×` (multiply) on the exact Variable expression-tag row.

In both modes, the Scenario is created/reused and ensured under `Model.Scenarios`.

### Key Features

- Supports numeric mode and expression mode in a single focused script
- Reuses or creates Scenario and Variable objects as needed
- Resolves collection, property, and membership identifiers from the model database
- Regenerates `project.xml` from the updated `reference.db` using the Cloud CLI
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **After this script:** [EnableReports](../EnableReports/), simulation execution, or any downstream task that consumes the updated `project.xml`

---

## Arguments

| Argument | Required | Type | Default | Description | Example |
|---|---|---|---|---|---|
| `--collection-name` | Yes | str | — | Collection name for membership/property lookup. Use `ParentClass.CollectionName` to disambiguate. | `System.Generators` |
| `--child-object-name` | Yes | str | — | Child object name in the target membership. | `Gen1` |
| `--property-name` | Yes | str | — | Property name to apply the sensitivity to. | `MaxCapacity` |
| `--sensitivity` | Yes | str | — | Sensitivity delta as a percentage (for example `+5%`, `-10%`, `2.5`). | `+5%` |
| `--parent-object-name` | No | str | `System` | Parent object name for membership lookup. Override this if the parent object name differs from the default. | `DEMO` |
| `--data-file-name` | No | str | *(none)* | Existing Data File object name. When omitted, numeric mode writes a scenario-scaled Variable profile; when provided, expression mode writes Variable + Scenario + Data File tags on the target property. | `gen1_sensitivity` |
| `--variable-name` | No | str | `<data-file-name>_Var` in expression mode, else `<child-object-name>_<property-name>_Var` | Variable object name to create or reuse. | `gen1_sensitivity_Var` |
| `--scenario-name` | No | str | `Sensitivity` | Scenario object name to create or reuse. | `Gen1_MaxCap_plus5pct` |
| `--scenario-class-name` | No | str | `Scenario` | Class name for scenario objects. | `Scenario` |
| `--band-id` | No | int | `1` | Band id used to read/write target property data. | `1` |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|----------|-------------|
| `cloud_cli_path` | Path to the Cloud CLI executable; required for db-to-xml conversion. |
| `study_id` | Current study identifier; required for db-to-xml conversion. |
| `simulation_path` | Root path for study files; `reference.db` is read and `project.xml` is written here. |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
plexos_sdk
```

---

## Example Task Definitions

### Numeric mode (no data file)

```json
{
  "Name": "Apply +5% sensitivity to MaxCapacity",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/create_sensitivity.py", "Version": null }
  ],
  "Arguments": "python3 create_sensitivity.py --collection-name System.Generators --parent-object-name System --child-object-name Gen1 --property-name MaxCapacity --sensitivity +5% --scenario-name Gen1_MaxCap_plus5pct",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

### Expression mode (existing Data File object)

```json
{
  "Name": "Apply variable expression sensitivity to MaxCapacity",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/create_sensitivity.py", "Version": null }
  ],
  "Arguments": "python3 create_sensitivity.py --collection-name System.Generators --parent-object-name System --child-object-name Gen1 --property-name MaxCapacity --sensitivity +5% --data-file-name gen1_plus5pct --scenario-name Gen1_MaxCap_plus5pct",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

---

## Example Commands

```bash
# Numeric mode: read the current property value and write a scenario-scaled Variable profile
python3 create_sensitivity.py --collection-name System.Generators --parent-object-name System --child-object-name Gen1 --property-name MaxCapacity --sensitivity +5%

# Numeric mode with explicit scenario and band selection
python3 create_sensitivity.py --collection-name System.Generators --parent-object-name System --child-object-name Gen1 --property-name MaxCapacity --sensitivity -10% --scenario-name Gen1_MaxCap_minus10pct --band-id 2

# Expression mode: use an existing Data File object and multiply by 1 + sensitivity
python3 create_sensitivity.py --collection-name System.Generators --parent-object-name System --child-object-name Gen1 --property-name MaxCapacity --sensitivity +5% --data-file-name gen1_plus5pct

# Expression mode with an explicit Variable name
python3 create_sensitivity.py --collection-name System.Generators --parent-object-name System --child-object-name Gen1 --property-name MaxCapacity --sensitivity 2.5 --data-file-name gen1_profile --variable-name gen1_profile_var --scenario-name Gen1_MaxCap_plus2_5pct
```

---

## Expected Behaviour

### Success

1. Script validates required environment variables and CLI arguments, then resolves `reference.db` under `simulation_path`.
2. It resolves the target collection, property, and membership identifiers from the model database.
3. It creates or reuses the required Scenario and Variable objects.
4. In numeric mode, it reads the current base property value and writes `Variable.Profile = base × (1 + sensitivity)` under the Scenario tag.
5. In expression mode, it validates that the named Data File object exists and writes `Variable.Profile = 1 + sensitivity` under the Scenario tag.
6. It tags the target property with the Variable expression and Scenario, and in expression mode also applies the Data File tag.
7. It sets the exact property action row to `=` in numeric mode or `×` in expression mode.
8. It regenerates `project.xml` from the modified database using the Cloud CLI and exits with code `0`.

### Failure Conditions

| Condition | Mode | Exit Code | Recovery |
|-----------|------|-----------|----------|
| Missing or invalid required arguments | Both | 1 | Provide all required arguments with valid formats |
| Invalid sensitivity format | Both | 1 | Use a numeric percentage value such as `+5%`, `-10%`, `5`, or `2.5` |
| `reference.db` not found at resolved path | Both | 1 | Verify `simulation_path` env var and file access |
| Membership not found for parent/child names | Both | 1 | Verify collection and object names exist in model |
| Base property value not found for selected band | Numeric | 1 | Verify the target property has data for the specified band |
| Data File object not found in model | Expression | 1 | Ensure the named Data File object exists in model before running |
| db-to-xml conversion fails | Both | 1 | Check `cloud_cli_path` and `study_id` env vars |
| SDK/runtime error while writing sensitivity data | Both | 1 | Review logs and validate model/SDK compatibility |