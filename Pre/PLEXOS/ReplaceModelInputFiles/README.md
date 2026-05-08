# ReplaceModelInputFiles – README

## Overview

**Type:** Pre  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** March 2026  
**Author:** Energy Exemplar

### Purpose

Replaces an existing property input assignment in a PLEXOS model with an alternative DataHub-backed input file using the PLEXOS SDK. This enables complete timeseries replacement for targeted inputs such as Natural Gas Europe gas prices.


### Key Features

- **Dual lookup modes:** Supports both name-based (easy mode) and lang-id-based (explicit mode) arguments for class, collection, and property resolution. IDs take priority when both are provided.
- **Space placeholder restoration:** Automatically converts `%20` placeholders back to spaces in argument values, enabling safe passing of spaced names through task definitions.
- **Data file validation:** Verifies the data file exists at `simulation_path` before executing, ensuring the file has been downloaded (e.g. via DownloadFromDataHub) prior to replacement.
- **Automatic DB-to-XML conversion:** Regenerates `project.xml` from the updated model database after replacement.
- **Flexible model resolution:** Resolves the model path via `--model-path`, then `simulation_path/reference.db`, then `sqlite_input_path` environment variable.
- **Band-level replacement:** Targets a specific band id and optionally removes the existing property assignment before adding the new one.

### Related Scripts

- **Before this script:** [DownloadFromDataHub](../DownloadFromDataHub/) – Downloads the data file to `simulation_path` so it is available for validation and replacement.


---

## Arguments

### Required Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `--parent-object-name` | str | Parent object name in the target membership. | `System` |
| `--child-object-name` | str | Child object name in the target membership. | `Natural Gas Europe` |
| `--data-file-path` | str | Relative path from `simulation_path` to the data file downloaded from DataHub. Must not be an absolute filesystem path or DataHub remote path. | `gas_prices_ng_europe.csv` |

### Name-Based Arguments (Easy Mode)

Use these to auto-discover lang IDs from the model database. At least one of the name-based or lang-id-based arguments must be provided for each of class, collection, and property.

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `--parent-class-name` | str | Parent class name. Auto-discovers lang_id from model. | `System` |
| `--collection-name` | str | Collection name. Auto-discovers lang_id from model. | `Data Files` |
| `--property-name` | str | Property name. Auto-discovers lang_id from model. | `Filename` |

### Lang-ID-Based Arguments (Explicit Mode)

Use these for deterministic lookup. If both name and ID are given for the same field, the ID takes priority.

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `--parent-class-lang-id` | int | Parent class lang id. Overrides `--parent-class-name`. | `1` |
| `--collection-lang-id` | int | Collection lang id. Overrides `--collection-name`. | `201` |
| `--property-lang-id` | int | Property lang id. Overrides `--property-name`. | `4021` |

### Optional Arguments

| Argument | Type | Default | Description | Example |
|----------|------|---------|-------------|---------|
| `--model-path` | str | `None` | Path to the PLEXOS SQLite input model. Falls back to `simulation_path/reference.db`, then `sqlite_input_path`. | `/simulation/input.xml.db` |
| `--band-id` | int | `1` | Property band id to replace. | `1` |
| `--value` | float/none | `none` | Optional scalar value for assignment (`none` keeps scalar unset). | `none` |
| `--time-slice-text` | str | `None` | Optional time slice text for the assignment. | `M1-12` |
| `--period-type-id` | int | `None` | Optional period type id. | `4` |
| `--replace-existing` | bool | `true` | Remove existing property at the selected band before adding replacement. | `true` |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|----------|-------------|
| `cloud_cli_path` | Path to the Cloud CLI executable; used for DB-to-XML conversion. |
| `simulation_path` | Root path for study files. Used to resolve `reference.db`, validate data file existence, and regenerate `project.xml`. |
| `sqlite_input_path` | Fallback model database path when `--model-path` is not provided and `simulation_path/reference.db` does not exist. |
| `study_id` | PLEXOS study ID. Required for DB-to-XML conversion after replacement. |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`. 

```
eecloud
plexos_sdk
```

---

## Example Commands

```bash
# Using names (easy mode) — auto-discover lang IDs from model
python3 replace_model_input_files.py --parent-class-name System --collection-name Data%20Files --parent-object-name System --child-object-name Solar%20Rating --property-name Filename --data-file-path Offshore%20Wind%20-%20BE.csv --replace-existing true

# Using lang IDs (explicit mode) — deterministic lookup (replace IDs with values from your model)
python3 replace_model_input_files.py --parent-class-lang-id 1 --collection-lang-id 16 --parent-object-name System --child-object-name Solar%20Rating --property-lang-id 193 --data-file-path new_solar.csv
 
# With optional band-id (target band 3 instead of the default band 1)
python3 replace_model_input_files.py --parent-class-name System --collection-name Data%20Files --property-name Filename --parent-object-name System --child-object-name Solar%20Rating --data-file-path Offshore%20Wind%20-%20BE.csv --band-id 3

# With optional value and time slice (numeric property example)
python3 replace_model_input_files.py --parent-class-name System --collection-name Fuels --property-name Price --parent-object-name System --child-object-name Natural%20Gas --data-file-path gas_price_timeseries.csv --value 12.5 --time-slice-text M1-12
# The updated value 12.5 might not be visible in the desktop UI but can be verified by querying the database.

# Skip removing existing property (append mode)
python3 replace_model_input_files.py --parent-class-lang-id 1 --collection-lang-id 16 --property-lang-id 193 --parent-object-name System --child-object-name Solar%20Rating --data-file-path gas_prices.csv --replace-existing false
```

---

## Chaining This Script

### Chain 1 — Download file from DataHub
### Chain 2 — Replace model input file

### Example Task Chain

```json
[
  {
    "Name": "Chain 1 – Download gas price file from DataHub",
    "TaskType": "Pre",
    "Files": [
      {
        "Path": "Project/Study/download_from_datahub.py",
        "Version": null
      }
    ],
    "Arguments": "python3 download_from_datahub.py -r MyFolder/Offshore%20Wind%20-%20BE.csv -l simulation_path",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Chain 2 – Replace Natural Gas Europe gas price input file",
    "TaskType": "Pre",
    "Files": [
      {
        "Path": "Project/Study/replace_model_input_files.py",
        "Version": null
      }
    ],
    "Arguments": "python3 replace_model_input_files.py --parent-class-name System --collection-name Data%20Files --parent-object-name System --child-object-name Solar%20Rating --property-name Filename --data-file-path Offshore%20Wind%20-%20BE.csv --replace-existing true",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

---

## Expected Behaviour

### Success

1. Script validates CLI inputs and restores `%20` space placeholders in argument values.
2. Resolves model path from `--model-path`, then `simulation_path/reference.db`, then `sqlite_input_path`.
3. Resolves membership and property using explicit lang IDs or auto-discovers them from names.
4. Validates that the data file exists at `simulation_path/<data-file-path>` where `<data-file-path>` is a relative path from `simulation_path` — not an absolute filesystem path or DataHub remote path.
5. Optionally removes existing property assignment at the selected band.
6. Adds replacement property assignment with the new `data_file_text` path.
7. Applies optional `value`, `time_slice_text`, and `period_type_id` if provided.
8. Regenerates `project.xml` from the updated model database via DB-to-XML conversion.
9. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| Missing/invalid required arguments | 1 | Provide valid required arguments |
| Neither name nor lang-id provided for class/collection/property | 1 | Provide at least one of `--*-name` or `--*-lang-id` for each field |
| Invalid boolean or float argument value | 1 | Use supported formats (`true/false`, numeric, `none`) |
| Missing `--model-path` and missing `simulation_path/reference.db` and missing `sqlite_input_path` | 1 | Provide `--model-path` or set `simulation_path` / `sqlite_input_path` |
| Missing `study_id` environment variable | 1 | Set `study_id` before running the script |
| Model file not found at resolved path | 1 | Verify model path and file access |
| Data file not found at `simulation_path/<data-file-path>` | 1 | Provide a relative path from `simulation_path`, not an absolute filesystem path or DataHub remote path. Ensure the file has been downloaded (e.g. via DownloadFromDataHub) before running this script |
| Membership/property not found for provided IDs/names | 1 | Verify class/collection/property IDs and object names |
| DB-to-XML conversion failure | 1 | Review logs and validate model/SDK compatibility |
| SDK/runtime replacement failure | 1 | Review logs and validate model/SDK compatibility |