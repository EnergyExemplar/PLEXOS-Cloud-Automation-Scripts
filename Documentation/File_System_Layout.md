# File System — {simulation_path} and {output_path}

## What It Is

PLEXOS Cloud automation scripts run in an isolated container with two shared disk mounts: `{simulation_path}` and `{output_path}` . The `{simulation_path}` directory holds study data, input files, and simulation artifacts, while `{output_path}` is the script's working directory and the place where files are captured automatically at the end of the run.

This layout is what makes pre- and post-simulation tasks chainable. One script can read from `{simulation_path}`, write results to `{output_path}`, and the platform can pass those files forward or upload them as artifacts without manual file transfer.

## How Scripts Use It

Scripts use `{simulation_path}` as the stable location for model inputs and simulation outputs, and `{output_path}` as the handoff point between steps. For example, [Download From Data Hub](../Pre/PLEXOS/DownloadFromDataHub/README.md) can download files into `{simulation_path}` (via `-l simulation_path`) before the engine starts, while [Upload To Data Hub](../Post/PLEXOS/UploadToDataHub/README.md) uploads files from `{output_path}` (via `-l output_path`) to a specific DataHub path after the run. [Cleanup Files](../Post/PLEXOS/CleanupFiles/README.md) removes temporary files from `{output_path}` as the final step in a chain.

This pattern also appears in conversion and query workflows such as [Csv To Parquet](../Post/PLEXOS/CsvToParquet/README.md), [Query Write Memberships](../Post/PLEXOS/QueryWriteMemberships/README.md), and [Time Series Comparison](../Post/PLEXOS/TimeSeriesComparison/README.md). If you write files somewhere else, later tasks will not see them and the platform will not capture them as solution artifacts.

## Key Patterns

Use the platform-provided environment variables instead of hardcoded paths:

```python
import os

simulation_path = os.environ.get('simulation_path', '{simulation_path}')
output_path     = os.environ.get('output_path', '{output_path}')
duck_db_path    = os.environ.get('duck_db_path')
```

### Directory access rules

| Directory | Pre-simulation | Post-simulation | Purpose |
|-----------|---------------|-----------------|---------|
| `{simulation_path}` | Read/Write | **Read-only** | Study data: XML files, time-series inputs, simulation artifacts, solution Parquet files |
| `{output_path}` | Read/Write | Read/Write | Script working directory. Files here are **automatically uploaded** as solution artifacts |

### Additional platform-injected paths

| Variable | Purpose |
|----------|---------|
| `{duck_db_path}` | Pre-configured DuckDB database file for solution queries |
| `{directory_map_path}` | Maps model names to solution{output_path} paths -- avoids hardcoded subdirectory names |
| `{cloud_cli_path}` | Full path to the Cloud CLI binary, required for CloudSDK initialisation |
| `{auth_path}` | Path to raw user access token for programmatic API calls |
| `{sqlite_input_path}` | (PLEXOS only) Path to the PLEXOS SQLite project file |
| `{xml_input_path}` | (PLEXOS only) Path to the XML file PLEXOS will use as input |

### Write output files to `{output_path}` so they are captured automatically:

```python
with duckdb.connect(duck_db_path) as con:
    con.execute(f"COPY (SELECT * FROM membershipinfo) TO '{output_path}/memberships.csv' WITH (HEADER, DELIMITER ',')")
```

Tasks run in order defined by `ExecutionOrder`, and each task runs in its own isolated container while sharing these mounts. The only reliable handoff between steps is the shared file system -- scripts cannot share memory or local state.

### Common directory structure under `{simulation_path}`

```
{simulation_path}/
+-- Model.xml                          # PLEXOS XML input file ({xml_input_path})
+-- reference.db                       # PLEXOS SQLite project database ({sqlite_input_path})
+-- TimeSeries/                        # Time-series input CSV/Parquet files
+-- splits/
    +-- directorymapping.json          # Maps model names to ParquetPath ({directory_map_path})
    +-- <ModelName>/
        +-- <ParquetPath>/             # Solution Parquet data
            +-- fullkeyinfo/
            |   +-- FullKeyInfo.parquet
            +-- period/
            |   +-- Period.parquet
            +-- data/
                +-- dataFileId=*/
                    +-- *.parquet
```

## Common Pitfalls

- **Writing files outside `{output_path}` when you expect them to be uploaded automatically.** Only files in `{output_path}` are captured as solution artifacts.

- **Hardcoding `{simulation_path}` or `{output_path}` instead of reading `{simulation_path}` and `{output_path}` from `os.environ`.** Always use `os.environ.get('simulation_path', '{simulation_path}')` and `os.environ.get('output_path', '{output_path}')`.

- **Writing to `{simulation_path}` in post-simulation tasks.** The `{simulation_path}` mount is **read-only** in post tasks. Files in `{simulation_path}` are copied (not moved) by scripts like [Search And Upload](../Post/PLEXOS/SearchAndUpload/README.md) to preserve the original.

- **Forgetting that each task runs in its own isolated container.** Only files in the shared mounts (`{simulation_path}` and `{output_path}`) persist between steps. Local temp files, environment variables set at runtime, and in-memory state are not shared.

- **Using the wrong file location for DuckDB queries.** Always use the platform-provided `{duck_db_path}` rather than constructing your own path to the database file.

- **Assuming the directory structure is fixed.** Use `{directory_map_path}` to resolve model names and Parquet paths dynamically. The [Configure Duck Db Views](../Post/PLEXOS/ConfigureDuckDbViews/README.md) script demonstrates this pattern.
