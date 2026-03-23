# ZIP Downloaded XMLs – README

## Overview

**Type:** Post  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** March, 2026  
**Author:** Energy Exemplar

### Purpose

Downloads PLEXOS diagnostics XML files from Datahub, compresses them into a single ZIP archive, and re-uploads the archive. This reduces storage requirements and simplifies diagnostic file management.

This is a **focused script** — it performs a complete download-compress-upload workflow for diagnostics archival.

### Key Features

- Downloads diagnostics XML files from Datahub using glob patterns
- Compresses multiple XML files into a single ZIP archive
- Re-uploads the ZIP archive to Datahub for long-term storage
- Supports custom glob patterns (e.g., only ST diagnostics)
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** Ensure diagnostics XML files are present in Datahub at the expected remote path.
- **After this script:** Consider adding the [CleanupFiles](../CleanupFiles/) script to remove temporary or redundant files if needed.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-r`, `--remote-base-path` | No | `Project/Study` | Base path in Datahub (model name from directory mapping; execution/simulation paths added automatically) |
| `-pt`, `--pattern` | No | `**/*Diagnostics.xml` | Glob pattern for diagnostics files (e.g., `**/*ST*Diagnostics.xml` for only ST phase) |
| `--keep-files` | No | false | Keep downloaded XML files after creating the ZIP (default: remove them so only the ZIP is uploaded as solution artifacts) |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the Cloud CLI binary |
| `execution_id` | Execution identifier used to construct remote paths |
| `simulation_id` | Simulation identifier used to construct remote paths |
| `directory_map_path` | Path to directory mapping JSON (optional; falls back to `/simulation/splits/directorymapping.json` for distributed runs) |
| `output_path` | Working directory — files written here are uploaded as solution artifacts (default: `/output`) |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```python
# Packages used by this script
zipfile  # Standard library
pathlib  # Standard library
eecloud  # Pre-installed in cloud environment
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Archive Diagnostics After Simulation

```json
[
  {
    "Name": "Run PLEXOS Simulation",
    "TaskType": "Compute",
    "Arguments": "...",
    "ExecutionOrder": 1
  },
  {
    "Name": "Extract Diagnostics to Datahub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/extract_diag_xml.py", "Version": null }
    ],
    "Arguments": "python3 extract_diag_xml.py -r Project/Study/diagnostics",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  },
  {
    "Name": "Archive Diagnostics as ZIP",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/zip_downloaded_xmls.py", "Version": null }
    ],
    "Arguments": "python3 zip_downloaded_xmls.py -r Project/Study/diagnostics",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  }
]
```

---

## Example Commands

```bash
# Basic usage — archive all diagnostics
python3 zip_downloaded_xmls.py -m TestModel -r Project/Study

# Archive only ST phase diagnostics
python3 zip_downloaded_xmls.py -m MyModel -r Project/Study -pt "**/*ST*Diagnostics.xml"

# Archive all diagnostics with custom base path
python3 zip_downloaded_xmls.py -m TestModel -r MyOrg/MyProject
```

---

## Expected Behaviour

### Success

1. Script starts and logs received/interpreted arguments
2. Reads model name from directory mapping JSON
3. **Step 1:** Downloads XML files from Datahub matching the glob pattern
3. **Step 2:** Creates a ZIP archive containing all downloaded files
4. **Step 3:** Uploads the ZIP archive back to Datahub
5. Logs success message with remote path of uploaded ZIP
6. Exits with code `0`

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| Missing required environment variable (`cloud_cli_path`, `execution_id`, or `simulation_id`) | 1 | Verify execution environment and ensure all required variables are set |
| Directory mapping file not found | 1 | Set `directory_map_path` or ensure `/simulation/splits/directorymapping.json` exists |
| Directory mapping JSON empty or no entry with ParquetPath and Id | 1 | Check mapping JSON format and ensure it contains model entry with `Id` and `ParquetPath` fields |
| No files matched the glob pattern | 1 | Verify pattern and check if diagnostics exist in Datahub |
| Download from Datahub failed | 1 | Check Datahub permissions and remote path |
| Upload to Datahub failed | 1 | Check Datahub permissions and available storage |

---

## Notes

- **Remote Path Structure:** The script automatically constructs the remote path as:  
  `{remote-base-path}/{model_name}/{execution_id}/diagnostics/{simulation_id}/`
  
- **ZIP Filename:** The output ZIP file is named `{model_name}_diagnostics.zip`

- **Temporary Files:** Downloaded XML files and the ZIP are created in `output_path`. By default, the XML files are removed after a successful upload so only the ZIP is uploaded as a solution artifact. Use `--keep-files` to retain the XMLs (e.g. for debugging).

- **Pattern Flexibility:** Use `--pattern` to filter specific diagnostics:
  - All diagnostics: `**/*Diagnostics.xml` (default)
  - ST phase only: `**/*ST*Diagnostics.xml`
  - MT phase only: `**/*MT*Diagnostics.xml`
  - LT phase only: `**/*LT*Diagnostics.xml`
