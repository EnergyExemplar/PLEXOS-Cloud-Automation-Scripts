# Repository Overview

This repository contains reusable, ready-to-run automation scripts for the **PLEXOS** and **Aurora** simulation platforms on Energy Exemplar's cloud infrastructure.

---

## Purpose

Scripts in this repository extend the cloud simulation lifecycle by running custom logic **before** or **after** the simulation engine executes, or as **standalone automation** tasks against the DataHub. Each script is small, focused, and self-contained — it does one thing and does it well.

---

## Repository Structure

```
Pre/PLEXOS/<ScriptName>/         # Runs before the PLEXOS engine starts
Post/PLEXOS/<ScriptName>/        # Runs after the PLEXOS engine and ETL complete
Automation/PLEXOS/<ScriptName>/  # Standalone / local DataHub operations for PLEXOS

Pre/Aurora/<ScriptName>/
Post/Aurora/<ScriptName>/
Automation/Aurora/<ScriptName>/

Documentation/                   # SDK and CLI reference files (this folder)
tests/                           # Unit tests for all scripts
```

Each script folder contains exactly two files:

| File | Description |
|---|---|
| `script_name.py` | The main script |
| `README.md` | Per-script documentation (filled from `_capability_readme_template.md`) |

**Naming convention:** Folder `ParquetToCsv` → file `parquet_to_csv.py` (PascalCase folder, snake_case file).

---

## Script Types

### Pre-Simulation Scripts (`Pre/`)

Run **before** the simulation engine starts. Use these to:
- Download files from DataHub
- Validate or transform model inputs
- Stage data into `/simulation`

Environment: Linux container. Both `/simulation` and `/output` are writable.

### Post-Simulation Scripts (`Post/`)

Run **after** the engine and ETL complete. Use these to:
- Query solution results via DuckDB
- Convert or export output data
- Upload artifacts back to DataHub

Environment: Linux container. `/simulation` is **read-only**; `/output` is writable and auto-uploaded.

### Automation Scripts (`Automation/`)

Run **locally** (not in the cloud container). Use these to:
- Manage DataHub resources from a developer machine
- Batch upload/download files
- Orchestrate multi-step workflows

All configuration is passed as explicit CLI arguments — no platform-injected environment variables.

---

## Execution Environment

| Item | Detail |
|---|---|
| OS | Linux (Pre/Post tasks) |
| Python | 3.11+ |
| SDKs pre-installed | `eecloud` (Cloud SDK), `plexos` (PLEXOS SDK) |
| Shared mounts | `/simulation` (study files), `/output` (artifacts, auto-uploaded) |

---

## Configuration: Environment Variables vs. CLI Arguments

| Script type | How configuration is supplied |
|---|---|
| Pre / Post | Platform-injected **environment variables** (e.g. `cloud_cli_path`, `output_path`) |
| Automation | Explicit **CLI arguments** via `argparse` |

Available platform variables: `tenant_id`, `simulation_id`, `study_id`, `execution_id`, `simulation_path`, `output_path`, `cloud_cli_path`, `auth_path`, `duck_db_path`, `directory_map_path`.  
PLEXOS-only: `sqlite_input_path`, `xml_input_path`.

---

## Key Design Rules

- **One script, one job.** Each script does exactly one thing.
- **No shared utility libraries.** Pre/Post scripts are fully self-contained.
- **Write output to `output_path`.** Never write to arbitrary paths — `output_path` is auto-uploaded.
- **Never write to `/simulation` in Post scripts.** It is read-only at that stage.
- **Return an integer exit code from `main()`.** Use `raise SystemExit(main())`.
- **Required env vars fail fast.** Use `os.environ["key"]` with a `try/except KeyError` that prints a clear message and calls `sys.exit(1)`.
- **All tests live in `tests/`.** Run with `python -m pytest` from the repo root.

---

## Task Definition Format

Scripts are invoked by the platform via a JSON task definition:

```json
{
  "Name": "Descriptive task name",
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

## SDK Reference

See the other files in this `Documentation/` folder:

| File | Contents |
|---|---|
| [`CloudSDK.md`](CloudSDK.md) | Full CloudSDK API reference — method signatures, parameters, response shapes |
| [`PLEXOS_SDK_Methods.md`](PLEXOS_SDK_Methods.md) | PLEXOS SDK public method signatures |
| [`PLEXOS_SDK_TLDR.md`](PLEXOS_SDK_TLDR.md) | PLEXOS SDK quick-reference cheat sheet |

---

## Further Reading

| Document | Purpose |
|---|---|
| [`README.md`](../README.md) | Platform overview, environment variables, file system layout, script chaining |
| [`PLEXOSReadme.md`](../PLEXOSReadme.md) | PLEXOS-specific variables, available scripts, contributing guide |
| [`AuroraReadme.md`](../AuroraReadme.md) | Aurora-specific notes, available scripts, contributing guide |
| [`_capability_readme_template.md`](../_capability_readme_template.md) | Template for per-script READMEs |
| [`Automation/PLEXOS/README.md`](../Automation/PLEXOS/README.md) | Importable automation classes and how to create custom automation scripts |
