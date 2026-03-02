# PLEXOS Automation Scripts
# PLEXOS
This repository contains reusable, ready-to-run automation scripts for PLEXOS and Aurora platforms. Scripts are small, focused, and chainable — each does one thing well and can be composed with others as part of a pre- or post-simulation workflow.

> **Full platform documentation:** [EE Support Portal](https://support.energyexemplar.com)

| Platform | Guide |
|----------|-------|
| PLEXOS | [PLEXOSReadme.md](PLEXOSReadme.md) |
| Aurora | [AuroraReadme.md](AuroraReadme.md) |

---

## What Are Pre & Post Simulation Tasks?

Pre- and post-simulation tasks let you execute arbitrary logic on Energy Exemplar's compute infrastructure **before or after a simulation runs**, without transferring files manually.

- **Pre-simulation tasks** run before the simulation engine starts — prepare inputs, download files from DataHub, validate data.
- **Post-simulation tasks** run after the engine and ETL complete — query results, convert formats, upload artifacts.

Tasks run in the order defined by `ExecutionOrder` and each runs in its own isolated container, sharing the same `/simulation` and `/output` disk mounts.

> Pre- and post-simulation tasks are supported on **Linux environments only**. See the [EE Support Portal](https://support.energyexemplar.com) for full setup instructions.

---

## File System

| Directory | Access | Purpose |
|-----------|--------|---------|
| `/simulation` | R/W (pre), Read-only (post) | Study data: XML files, time-series inputs, simulation artifacts |
| `/output` | R/W always | Your script's working directory. Files here are **automatically uploaded** as solution artifacts at the end of the run |

---

## Environment Variables

These are automatically injected by the platform — you read them, never set them.

| Variable | Description | Why It Exists |
|----------|-------------|---------------|
| `tenant_id` | Your Tenant ID | Scope API calls and DataHub paths to your organisation |
| `simulation_id` | Current Simulation ID | Scope API calls and output naming to this run |
| `study_id` | Current Study ID | Identifies the study being executed |
| `execution_id` | Current Execution ID | Unique per execution; used in artifact paths |
| `simulation_path` | Root path for study files | Stable, environment-independent way to locate inputs |
| `output_path` | Script working directory | Everything written here is captured automatically |
| `cloud_cli_path` | Full path to the Cloud CLI binary | Required by the Python SDK: `CloudSDK(cli_path=...)` |
| `auth_path` | Path to raw user access token | Programmatic authenticated API calls without re-logging in |
| `duck_db_path` | Default DuckDB database file | All scripts share one DuckDB instance for solution queries |
| `directory_map_path` | Path to directory mapping JSON | Maps model names to solution/output paths — no hardcoded paths needed |

```python
import os

simulation_path = os.environ.get('simulation_path', '/simulation')
output_path     = os.environ.get('output_path', '/output')
duck_db_path    = os.environ.get('duck_db_path')
```

> Platform-specific variables (e.g. `sqlite_input_path`, `xml_input_path` for PLEXOS) are in the platform guides.

---

## DuckDB and Solution Data

[DuckDB](https://duckdb.org/) is a high-performance analytical database that queries Parquet, SQLite, and CSV files directly — no server required. It is the recommended tool for reading solution data in post-simulation tasks.

**Why DuckDB?** After a simulation completes, PLEXOS solution data is stored as Parquet files under `/simulation`. DuckDB lets you query this with standard SQL without loading everything into memory. The `duck_db_path` variable points to a pre-configured DuckDB file with views already set up for the solution.

### Set up views before querying

Run this as an early post-simulation task (before any scripts that read results):

```bash
plexos-cloud solution query configure-views --name 'YOUR MODEL NAME'
```

### Query solution data

```python
import duckdb, os

duck_db_path = os.environ.get('duck_db_path')
output_path  = os.environ.get('output_path', '/output')

with duckdb.connect(duck_db_path) as con:
    con.execute(f"COPY (SELECT * FROM membershipinfo) TO '{output_path}/memberships.csv' WITH (HEADER, DELIMITER ',')")
```

---

## Prerequisites

### Python Version

**Python 3.11 or higher** is required. This matches the version used in cloud execution environments and ensures compatibility with the CLI SDK and all automation features.

### Dependencies

All Python dependencies go in the root `requirements.txt`:

```bash
pip install -r requirements.txt
```

> Only one `requirements.txt` is supported per simulation — consolidate all script dependencies into this one file.

### Energy Exemplar SDKs

The following SDKs are **pre-installed** in the cloud execution environment:

- **EE Cloud SDK** (`eecloud`) – For DataHub operations, simulation management, and secret storage
- **PLEXOS SDK** – For PLEXOS model editing (XML/SQLite)

#### Local Installation

For local testing, both SDKs are available through your CLI installation:

1. **Install the CLI** from the `Energy Exemplar Web / Marketplace` (available in all environments)
2. **Locate the wheel files** in your CLI installation directory:
   - Windows: `%LOCALAPPDATA%\Programs\PlexosCloud\`
   - Linux/Mac: Check your CLI installation path
3. **Install both SDKs**:
   ```bash
   pip install <cli-path>/eecloud-*.whl
   pip install <cli-path>/plexos-*.whl
   ```

#### SDK Documentation

Your CLI installation includes auto-generated documentation:
- Location: `<cli-installation-path>/documentation/`
- Includes: API reference, examples, and usage guides for both SDKs
- Updated automatically with each CLI version

#### Using Custom Python Packages

If you need to use a custom Python package (not available on PyPI):

1. **Generate a wheel file** from your package:
   ```bash
   python setup.py bdist_wheel
   ```
2. **Upload the wheel file** along with your scripts
3. **Reference it in your simulation task**:
   ```json
   {
     "Name": "Install custom package",
     "TaskType": "Pre",
     "Arguments": "pip install /simulation/custom_package-1.0.0-py3-none-any.whl",
     "ExecutionOrder": 1
   }
   ```

> **Note:** Custom packages are the user's responsibility. Ensure compatibility with Python 3.11+ and test thoroughly.

---

## Script Design Philosophy

- **One script, one job.** Keep each script focused on a single task.
- **No shared utility libraries.** Scripts are self-contained — no cross-script imports.
- **Chain by execution order.** Use `ExecutionOrder` to sequence tasks, not code coupling.
- **Environment variables for paths and IDs.** Never hardcode.
- **`argparse` for all script inputs.** Keep interfaces explicit and documented.
- **Write output to `output_path`.** Everything there is captured automatically.

---

## Chaining Scripts Together

Scripts communicate via the shared `/output` directory. Compose workflows with sequential `ExecutionOrder` values:

```json
[
  {
    "Name": "Configure DuckDB views for model results",
    "TaskType": "Post",
    "Arguments": "plexos-cloud solution query configure-views --name 'MY MODEL'",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Export membership data to CSV",
    "TaskType": "Post",
    "Files": [{ "Path": "Project/Study/export_memberships.py", "Version": null }],
    "Arguments": "python3 export_memberships.py",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  },
  {
    "Name": "Convert CSV outputs to Parquet and upload",
    "TaskType": "Post",
    "Files": [{ "Path": "Project/Study/convert_csv_to_parquet.py", "Version": null }],
    "Arguments": "python3 convert_csv_to_parquet.py --root-folder output_path --remote-datahub-path Project/Study/Results",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  }
]
```

---

## Contributing New Automation Scripts

See the platform-specific guides for the script catalog and contribution steps:

- [PLEXOS – Contributing New Automation Scripts](PLEXOSReadme.md#contributing-new-automation-scripts)
- [Aurora – Contributing New Automation Scripts](AuroraReadme.md#contributing-new-automation-scripts)
