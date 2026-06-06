# Simulation Lifecycle — Pre/Engine/Post

## What It Is

The simulation lifecycle is the sequence of work that happens before, during, and after a PLEXOS or Aurora run. In this repository, automation scripts are organized around that lifecycle so you can prepare inputs, let the engine run, and then process outputs without manual file handling.

The lifecycle has three phases:

1. **Pre-simulation tasks** — Run before the engine starts. They stage inputs, download files from DataHub, convert formats, patch model files, or configure the simulation environment.
2. **Engine execution** — The PLEXOS or Aurora engine runs the simulation. This phase is managed by the platform and is not scriptable.
3. **Post-simulation tasks** — Run after the engine and ETL complete. They query solution data, convert output formats, upload artifacts to DataHub, and clean up temporary files.

**Automation scripts** sit outside the engine lifecycle entirely. They run locally (not in the cloud container) and are used for standalone DataHub operations, file transformations, or tasks that do not depend on a running simulation.

## How Scripts Use It

### Pre-simulation

Pre scripts stage or transform inputs before the engine reads them:

- [Download From Data Hub](../Pre/PLEXOS/DownloadFromDataHub/README.md) — Downloads files from DataHub into `{simulation_path}` (via `-l simulation_path`) or `{output_path}` using glob patterns.
- [Parquet To Csv](../Pre/PLEXOS/ParquetToCsv/README.md) — Converts Parquet inputs to CSV so the engine can read them.
- [Replace Model Input Files](../Pre/PLEXOS/ReplaceModelInputFiles/README.md) — Downloads a DataHub timeseries file and replaces the assigned data file in the PLEXOS model.
- [Update Horizon](../Pre/PLEXOS/UpdateHorizon/README.md) — Modifies simulation horizon dates in the model XML.
- [Enable Reports](../Pre/PLEXOS/EnableReports/README.md) — Enables or disables report categories before the engine starts.
- [Weather Sample](../Pre/PLEXOS/WeatherSample/README.md) and [Extend Weather Years](../Pre/PLEXOS/ExtendWeatherYears/README.md) — Generate sampled weather year inputs and register them in a PLEXOS study.

Pre scripts can write to both `{simulation_path}` and `{output_path}`.

### Post-simulation

Post scripts work with solution artifacts after the engine finishes:

- [Configure Duck Db Views](../Post/PLEXOS/ConfigureDuckDbViews/README.md) — Creates DuckDB views over solution Parquet data. Should run early (low `ExecutionOrder`) so later query scripts can use the views.
- [Query Write Memberships](../Post/PLEXOS/QueryWriteMemberships/README.md) — Exports model membership relationships (parent-child object structure) from the PLEXOS SQLite database to CSV.
- [Query Lmp Data](../Post/PLEXOS/QueryLmpData/README.md) — Extracts generation-weighted LMP reports from the DuckDB views.
- [Solution Data Query](../Post/PLEXOS/SolutionDataQuery/README.md) — Joins FullKeyInfo + data + Period Parquet files with case-insensitive wildcard filters and stages a compressed output Parquet.
- [Upload To Data Hub](../Post/PLEXOS/UploadToDataHub/README.md) — Uploads files from `{output_path}` to a specific DataHub path with glob pattern and versioning control.
- [Cleanup Files](../Post/PLEXOS/CleanupFiles/README.md) — Deletes files matching a glob pattern from `{output_path}` after upload.

Post scripts can read from `{simulation_path}` (read-only) and write to `{output_path}`.

### Automation

Automation scripts run locally and receive all configuration as CLI arguments (not environment variables):

- [Download From Data Hub](../Automation/PLEXOS/DownloadFromDataHub/README.md) — Download files locally for inspection or pre-packaging.
- [Csv To Parquet](../Automation/PLEXOS/CsvToParquet/README.md) and [Parquet To Csv](../Automation/PLEXOS/ParquetToCsv/README.md) — Local format conversions.
- [Upload To Data Hub](../Automation/PLEXOS/UploadToDataHub/README.md) — Upload local files to DataHub.
- [Download Solutions](../Automation/PLEXOS/DownloadSolutions/README.md) — Download simulation solution data.
- [Time Series Comparison](../Automation/PLEXOS/TimeSeriesComparison/README.md) — Compare time-series datasets locally.

Automation scripts require explicit `--cli-path` and `--environment` arguments, and must authenticate via `login()` or `login_client_credentials()` before calling SDK methods.

## Key Patterns

The lifecycle is built around two shared mounts, accessed via environment variables:

- `{simulation_path}` for study files and simulation artifacts
- `{output_path}` for script output that is automatically captured as solution artifacts

A typical pre-task pattern reads from `{simulation_path}` and writes staged files:

```python
import os

simulation_path = os.environ.get('simulation_path', '{simulation_path}')
output_path     = os.environ.get('output_path', '{output_path}')
```

A typical post-task pattern reads solution data and writes derived files to `{output_path}`:

```python
import os

duck_db_path = os.environ.get('duck_db_path')
output_path  = os.environ.get('output_path', '{output_path}')
```

Tasks are chained with `ExecutionOrder`, and each task runs in its own isolated container. The only reliable handoff between steps is the shared file system — specifically `{output_path}`.

### Recommended post-simulation task ordering

| ExecutionOrder | Script | Purpose |
|---------------|--------|---------|
| 1 | Configure Duck Db Views | Set up DuckDB views over solution Parquet |
| 2 | Query Write Memberships / Query Lmp Data / Solution Data Query | Extract result sets |
| 3 | Csv To Parquet | Convert CSV outputs to Parquet |
| 4 | Upload To Data Hub | Upload artifacts to a specific DataHub path |
| 5 | Cleanup Files | Remove temporary files from `{output_path}` |

## Environment Variables

Pre and post scripts receive these platform-injected variables:

| Variable | Description |
|----------|-------------|
| `simulation_path` | Root path for study files — `{simulation_path}` |
| `output_path` | Script working directory — `{output_path}` |
| `cloud_cli_path` | Full path to the Cloud CLI binary — `{cloud_cli_path}` |
| `duck_db_path` | Pre-configured DuckDB database file — `{duck_db_path}` |
| `directory_map_path` | Maps model names to solution/{output_path} paths — `{directory_map_path}` |
| `auth_path` | Path to raw user access token — `{auth_path}` |
| `tenant_id` | Your Tenant ID |
| `simulation_id` | Current Simulation ID |
| `study_id` | Current Study ID |
| `execution_id` | Current Execution ID |
| `sqlite_input_path` | (PLEXOS only) Path to PLEXOS SQLite project file |
| `xml_input_path` | (PLEXOS only) Path to PLEXOS XML input file |

Automation scripts do **not** have access to these variables — they receive all configuration as CLI arguments.

## Common Pitfalls

- **Writing post-simulation files to `{simulation_path}`.** In post tasks, `{simulation_path}` is read-only. Write all output to `{output_path}`.

- **Assuming scripts share memory or local state.** They do not — each task runs in its own container. Only files in `{simulation_path}` and `{output_path}` persist between steps.

- **Forgetting that only files written to `{output_path}` are automatically uploaded as artifacts.** Files written elsewhere will not be captured by the platform.

- **Using the wrong phase for the job.** Input preparation belongs in pre tasks, result extraction belongs in post tasks, and DataHub-only file movement can often be done with automation scripts.

- **Ignoring platform constraints.** Pre- and post-simulation tasks are supported on **Linux environments only**. Python 3.11+ is required.

- **Skipping DuckDB view setup before querying solution data.** The [Configure Duck Db Views](../Post/PLEXOS/ConfigureDuckDbViews/README.md) script must run with a low `ExecutionOrder` before any script that queries solution views.

- **Using environment variables in automation scripts.** Automation scripts run locally and do not have platform-injected variables. Use CLI arguments (`--cli-path`, `--environment`) instead.
