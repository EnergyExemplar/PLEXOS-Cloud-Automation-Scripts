# GitHub Copilot Instructions

This repository contains pre- and post-simulation automation scripts for the **PLEXOS** and **Aurora** platforms on Energy Exemplar's cloud infrastructure. Scripts run in isolated Linux containers with shared `/simulation` and `/output` mounts.

---

## SDK & CLI Documentation

> **Always open the relevant doc before writing or reviewing any SDK call.** Do not guess parameter names — wrong names cause silent runtime errors (e.g. `Datahub.download() got an unexpected keyword argument 'remote_folder'`).

**Documentation root:** `C:\Users\<user>\AppData\Local\Programs\PLEXOS.Cloud\Documentation\`

| Topic | File | Key sections |
|---|---|---|
| CloudSDK method signatures, param names, response shapes | `CloudSDK.md` | `## Datahub` → `datahub.download`, `datahub.upload` |
| SDK code-generation patterns and idioms | `CloudSDK_CodeGen.md` | Full file |
| PLEXOS SDK public method signatures | `PLEXOS_SDK_Methods.md` | Full file |
| PLEXOS SDK quick-reference cheat sheet | `PLEXOS_SDK_TLDR.md` | Full file |

---

## Repositories

| | Repository |
|---|---|
| **Public repo** | [EnergyExemplar/PLEXOS-Cloud-Automation-Scripts](https://github.com/EnergyExemplar/PLEXOS-Cloud-Automation-Scripts) |
| **Internal repo** | [PLEXOS-Cloud-Automation-Scripts-internal](https://github.com/EnergyExemplar/PLEXOS-Cloud-Automation-Scripts-internal) |
| **Related** | [EnergyExemplar/PLEXOS-Analysis-Scripts](https://github.com/EnergyExemplar/PLEXOS-Analysis-Scripts) |

> Changes intended for public release go to the public repo. Internal-only work (unreleased scripts, drafts, sensitive configs) stays in the internal repo.

---

## Repository Documentation

Always consult these repo-level docs before creating or modifying scripts:

| File | Purpose |
|---|---|
| [`README.md`](../README.md) | Platform overview, environment variables, file system layout, script chaining patterns |
| [`PLEXOSReadme.md`](../PLEXOSReadme.md) | PLEXOS-specific env variables, contributing guide, available scripts |
| [`AuroraReadme.md`](../AuroraReadme.md) | Aurora-specific notes, Python script standards, contributing guide, available scripts |
| [`_capability_readme_template.md`](../_capability_readme_template.md) | Template to fill when creating a new per-script README |
| [`Automation/PLEXOS/README.md`](../Automation/PLEXOS/README.md) | Available automation scripts, importable classes, and how to create custom automation scripts |

---

## Repository Structure

```
Pre/PLEXOS/<ScriptName>/     # Runs before the PLEXOS engine starts
Post/PLEXOS/<ScriptName>/    # Runs after the engine and ETL complete
Automation/PLEXOS/<ScriptName>/  # Standalone / local DataHub operations
Pre/Aurora/<ScriptName>/
Post/Aurora/<ScriptName>/
Automation/Aurora/<ScriptName>/
```

Each script folder contains exactly two files:
- `script_name.py` — the main script
- `README.md` — filled from `_capability_readme_template.md`

**Naming convention:** Folder `ParquetToCsv` → file `parquet_to_csv.py` (PascalCase folder, snake_case file).

---

## Script Structure

### Pre & Post Scripts

Pre and Post scripts run inside the cloud container and receive configuration exclusively through **platform-injected environment variables**. All paths and credentials come from the environment — never from CLI arguments.

```python
"""
One-line summary of what this script does.

Focused script — [action] only. No [unrelated concern].
Chain with [other_script.py] if you need [other capability].

Environment variables used:
    cloud_cli_path  – required; path to the Cloud CLI executable
    output_path     – working directory; files here are auto-uploaded
    simulation_path – root path for study files
"""
import os
import sys
import argparse
# ... other stdlib/third-party imports
from eecloud.cloudsdk import CloudSDK, SDKBase


# Required env vars — fail fast with a clear message
try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("Error: Missing required environment variable: cloud_cli_path")
    sys.exit(1)

# Optional env vars — use sensible defaults
OUTPUT_PATH     = os.environ.get("output_path",     "/output")
SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")


# For simple scripts, put logic directly in main() — no class needed.
# Use a class when the script is complex enough to benefit from encapsulation
# (e.g. multiple methods, shared state, or logic you want to unit-test in isolation).
def main() -> int:
    parser = argparse.ArgumentParser(description="Brief description.")
    parser.add_argument("--some-arg", required=True, help="What it does")
    args = parser.parse_args()

    try:
        sdk = CloudSDK(cli_path=CLOUD_CLI_PATH)
        # ... do the work directly here for a simple script ...
        print("[OK] Done.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

For a more complex script with multiple steps or shared state, wrapping logic in a class keeps `main()` clean and makes the worker independently testable:

```python
class MyWorker:
    def __init__(self, cli_path: str, output_path: str):
        self.sdk = CloudSDK(cli_path=cli_path)
        self.output_path = output_path

    def do_work(self, ...) -> bool:
        ...


def main() -> int:
    ...
    worker = MyWorker(cli_path=CLOUD_CLI_PATH, output_path=OUTPUT_PATH)
    return 0 if worker.do_work(...) else 1
```

### Automation Scripts

Automation scripts run **locally** (not in the cloud container). They do **not** have access to platform-injected environment variables. All configuration — CLI path, environment name, file paths — is passed as explicit CLI arguments.

Automation scripts may define a class to make their logic importable and reusable by other automation scripts — this is the one place in this repo where cross-script imports are permitted. For simple, standalone automations a class is not required; use one when the logic is complex, has shared state, or is likely to be imported by another script.

```python
"""
One-line summary of what this script does.

Standalone script — all configuration is passed as CLI arguments.
Define a class if this script's logic should be importable by other automation scripts.
"""
import argparse
import sys
from pathlib import Path
from eecloud.cloudsdk import CloudSDK, SDKBase
# ... other stdlib/third-party imports


def main() -> int:
    parser = argparse.ArgumentParser(description="Brief description.")
    parser.add_argument("--cli-path",    required=True, help="Path to PLEXOS Cloud CLI executable")
    parser.add_argument("--environment", required=True, help="Cloud environment name")
    parser.add_argument("--some-arg",    required=True, help="What it does")
    args = parser.parse_args()

    try:
        sdk = CloudSDK(cli_path=args.cli_path)
        # ... do the work directly here for a simple script ...
        print("[OK] Done.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

For complex scripts, or when the logic should be importable by other automation scripts, use a class:

```python
class MyProcessor:
    """Reusable processor — importable by other automation scripts."""

    def __init__(self, cli_path: str, environment: str):
        """
        Args:
            cli_path: Full path to the PLEXOS Cloud CLI executable
            environment: Cloud environment name
        """
        self.sdk = CloudSDK(cli_path=cli_path)
        self.environment = environment

    def do_work(self, ...) -> bool:
        """Docstring with Args and Returns."""
        ...


def main() -> int:
    parser = argparse.ArgumentParser(description="Brief description.")
    parser.add_argument("--cli-path",    required=True, help="Path to PLEXOS Cloud CLI executable")
    parser.add_argument("--environment", required=True, help="Cloud environment name")
    parser.add_argument("--some-arg",    required=True, help="What it does")
    args = parser.parse_args()

    try:
        processor = MyProcessor(cli_path=args.cli_path, environment=args.environment)
        success = processor.do_work(...)
        return 0 if success else 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## Rules — Always Apply

### Environment Variables (Pre & Post scripts only)
- **Never hardcode** paths, IDs, or credentials. Always read from `os.environ`.
- Required variables: use `os.environ["key"]` with a `try/except KeyError` that prints a clear error and calls `sys.exit(1)`.
- Optional variables: use `os.environ.get("key", "default")`.
- Only declare env vars the script actually reads. Do not copy the full list from the README.
- Available platform variables: `tenant_id`, `simulation_id`, `study_id`, `execution_id`, `simulation_path`, `output_path`, `cloud_cli_path`, `auth_path`, `duck_db_path`, `directory_map_path`.
- PLEXOS-only: `sqlite_input_path`, `xml_input_path`.
- **Automation scripts do not use platform env vars** — all configuration is passed as CLI arguments.

### Script Design
- **One script, one job.** Each script does exactly one thing (download, convert, upload, compare — not combinations).
- **No shared utility libraries.** Pre/Post scripts are fully self-contained — no imports from other scripts in this repo. Automation scripts are an exception: they may import classes from other Automation scripts in the same platform folder.
- **No per-script `requirements.txt`.** All dependencies go in the root `requirements.txt`.
- **`argparse` for all inputs.** Never use `sys.argv` directly or read config files for script inputs.
- **Write output to `output_path`.** Never write to arbitrary paths. Everything in `output_path` is auto-uploaded as a solution artifact.
- **`/simulation` is read-only in post tasks.** Never write to `simulation_path` in a Post script.
- **Return an integer exit code from `main()`.** Use `raise SystemExit(main())` — this is how the task runner detects success or failure.
- **Print progress with `[OK]`, `[FAIL]`, `[WARN]` prefixes** so logs are scannable.

### CloudSDK Usage

```python
from eecloud.cloudsdk import CloudSDK, SDKBase

pxc = CloudSDK(cli_path=CLOUD_CLI_PATH)
```

Always pass `print_message=False` and handle response data manually for consistent output formatting.

> **For correct parameter names and response shapes, refer to `CloudSDK.md` → `## Datahub` section.**
>
> Common gotchas confirmed from that doc:
> - `datahub.download` — correct params are `remote_glob_patterns` (list) and `output_directory`. The params `remote_folder` and `local_folder` do **not** exist on download.
> - `datahub.upload` — correct params are `local_folder`, `remote_folder`, `glob_patterns` (list), `is_versioned`. Always pass `print_message=False`.
> - Response model for both: `data.DatahubResourceResults[i].Success`, `.RelativeFilePath`, `.LocalFilePath`, `.FailureReason`.
> - A `FailureReason` of `"File is identical to the remote file"` is not a real failure — treat it as success.

### DuckDB Usage (Post scripts only)

> **For DuckDB API details, refer to the [DuckDB Python docs](https://duckdb.org/docs/api/python/overview).**

```python
import duckdb

duck_db_path = os.environ.get("duck_db_path")

with duckdb.connect(duck_db_path) as con:
    con.execute(f"COPY (SELECT * FROM some_view) TO '{output_path}/result.csv' WITH (HEADER, DELIMITER ',')")
```
- Use `duck_db_path` for the pre-configured solution database (views already set up).
- For ephemeral conversions, use `duckdb.connect()` (in-memory, no path).
- Always close connections (prefer `with` blocks).

### Tests
- **Always add or update tests** in `tests/` when a script is created or modified.
- Test files follow the naming convention: `<phase>_test_<script_name>.py` (e.g. `pre_test_download_from_datahub.py`, `post_test_upload_to_datahub.py`, `automation_test_converters.py`).
- Use `unittest.mock.patch` to mock `CloudSDK` and `SDKBase.get_response_data` — never call real cloud services in tests.
- Every test that calls through to an SDK method must assert the **correct parameter names** are used (the most common source of silent runtime errors).
- Run the full test suite from `tests/` before committing: `python -m pytest`.
- **Pre & Post scripts run on Linux only** — do not write tests that pass Windows absolute paths (e.g. `C:\data\file.csv`) to Pre/Post script classes. Windows path handling only applies to Automation scripts, which may run on either platform.
- **Escape `%` in `argparse` help/epilog strings.** Python's `argparse` treats `%` as a format specifier in `help=` and `epilog=` strings. Any literal `%` (e.g. URL-encoded examples like `%20`) must be written as `%%`. Failing to do so causes `ValueError: badly formed help string` on Python 3.14+ which validates help strings at argument registration time, breaking every test that calls `main()`.

### Script README Maintenance
- **Always update the script's `README.md`** whenever structural changes are made to a script — this includes adding/removing/renaming CLI arguments, changing environment variables read, adding new output files, or modifying behaviour described in the README.
- Changes to `argparse` arguments must be reflected in the **Arguments** table in the README.
- Changes to env vars read must be reflected in the **Environment Variables Used** section.
- Changes to expected output or chaining behaviour must be reflected in the **Overview** and **Example Task Definition** sections.
- **When a script is added, removed, or significantly changed, also update the platform-level README** — [`PLEXOSReadme.md`](../PLEXOSReadme.md) for PLEXOS scripts and [`AuroraReadme.md`](../AuroraReadme.md) for Aurora scripts. These files list available scripts and their purpose; they must stay in sync with what is actually in the repo.

---

## Rules — Never Do

- Do not create shared/utility modules — scripts must be self-contained.
- Do not add a `requirements.txt` inside a script folder.
- Do not use `print()` for structured data — write to files in `output_path`.
- Do not catch bare `except:` without re-raising or logging the exception.
- Do not use `os.system()` or `subprocess` for DataHub operations — use the CloudSDK.
- Do not write to `/simulation` in Post scripts.
- Do not use `argparse` for environment variables — they are not script arguments.

---

## README for Each Script

When creating a script README, copy `_capability_readme_template.md` and fill in:
- **Overview:** Type (Pre/Post/Automation), Platform (PLEXOS/Aurora/Both), Purpose
- **Arguments:** Only arguments defined in `argparse` — required and optional tables
- **Environment Variables Used:** Only variables the script actually reads
- **Dependencies:** Packages needed (declared in root `requirements.txt`)
- **Example Task Definition:** A complete JSON block ready to paste into a simulation config

> **Keep the README in sync with the script.** Any time a script's structure changes — arguments added/removed/renamed, env vars changed, output behaviour modified — the corresponding `README.md` must be updated in the same commit. A README that disagrees with the script it documents is worse than no README.

---

## Task Definition Format

```json
{
  "Name": "Descriptive name for this task",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/script_name.py", "Version": null }
  ],
  "Arguments": "python3 script_name.py --arg1 value1",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

Use sequential `ExecutionOrder` values to chain scripts. Scripts communicate via the shared `/output` directory.

---

## Platforms

- **PLEXOS scripts** go in `Pre/PLEXOS/`, `Post/PLEXOS/`, or `Automation/PLEXOS/`.
- **Aurora scripts** go in `Pre/Aurora/`, `Post/Aurora/`, or `Automation/Aurora/`.
- Pre/Post tasks run on **Linux only**. Default paths use `/simulation` and `/output`.
- Python version: **3.11+**.
