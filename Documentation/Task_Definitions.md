# Task Definitions — JSON Configuration

## What It Is

Task definitions are the JSON objects you add to a simulation configuration to run automation scripts before or after a PLEXOS or Aurora simulation. Each task tells the platform what file to run, what arguments to pass, and when to run it through `ExecutionOrder`.

They are the unit of orchestration for this repository: one task does one thing, and multiple tasks are chained together to build a workflow. Tasks communicate by reading and writing files in the shared `{output_path}` and `{simulation_path}` directories.

## How Scripts Use It

Scripts in this repository are designed to be launched from task definitions rather than run manually on the simulation agent. Each script exposes its configuration through `argparse` CLI arguments, and the task definition's `Arguments` field provides those arguments.

For example, a pre-simulation task can download inputs from DataHub:

```json
{
  "Name": "Download baseline data from DataHub",
  "TaskType": "Pre",
  "Files": [
    { "Path": "Project/Study/download_from_datahub.py", "Version": null },
    { "Path": "Project/Study/requirements.txt", "Version": null }
  ],
  "Arguments": "python3 download_from_datahub.py -r Project/Study/inputs/** -l simulation_path",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```

Then a later task can convert files with [Parquet To Csv](../Pre/PLEXOS/ParquetToCsv/README.md), and a post-simulation task can query results with [Solution Data Query](../Post/PLEXOS/SolutionDataQuery/README.md) and upload them with [Upload To Data Hub](../Post/PLEXOS/UploadToDataHub/README.md).

Task definitions control larger chains such as [Download From Data Hub To Replace Model Input Files](../Workflows/download-from-data-hub-to-replace-model-input-files.md), [Csv To Parquet To Upload To Data Hub](../Workflows/csv-to-parquet-to-upload-to-data-hub.md), and [Time Series Comparison To Upload To Data Hub](../Workflows/time-series-comparison-to-upload-to-data-hub.md).


## Key Patterns

### Single task

```json
{
  "Name": "Configure DuckDB Views",
  "TaskType": "Post",
  "Files": [
    { "Path": "Project/Study/configure_duck_db_views.py", "Version": null }
  ],
  "Arguments": "python3 configure_duck_db_views.py",
  "ContinueOnError": false,
  "ExecutionOrder": 1
}
```


```json
[
  {
    "Name": "Export Membership Data",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/requirements.txt", "Version": null },
      { "Path": "Project/Study/query_write_memberships.py", "Version": null }
    ],
    "Arguments": "python3 query_write_memberships.py --output-file memberships.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload Memberships to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/ModelStructure -p memberships.csv",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

### URL-encoding spaces in arguments

When task definition `Arguments` fields contain paths with spaces, encode spaces as `%20`. Quoting alone is not reliable in the task runner:

```json
"Arguments": "python3 download_from_datahub.py -r Project/Study%203/TimeSeries/** -l simulation_path"
```

### ContinueOnError best practices

- Set `ContinueOnError: false` for critical tasks (download, query, conversion) — if they fail, downstream tasks would fail too.
- Set `ContinueOnError: true` for upload and cleanup tasks — these are best-effort and should not block the pipeline.

## Environment Variables Available to Tasks

Pre and post tasks receive these platform-injected environment variables automatically:

| Variable | Description |
|----------|-------------|
| `simulation_path` | Root path for study files — `{simulation_path}` |
| `output_path` | Script working directory — `{output_path}` |
| `cloud_cli_path` | Full path to the Cloud CLI binary — `{cloud_cli_path}` |
| `duck_db_path` | Pre-configured DuckDB database file — `{duck_db_path}` |
| `directory_map_path` | Maps model names to solution paths — `{directory_map_path}` |
| `auth_path` | Path to raw user access token — `{auth_path}` |
| `tenant_id` | Your Tenant ID |
| `simulation_id` | Current Simulation ID |
| `study_id` | Current Study ID |
| `execution_id` | Current Execution ID |
| `sqlite_input_path` | (PLEXOS only) Path to PLEXOS SQLite project file |
| `xml_input_path` | (PLEXOS only) Path to PLEXOS XML input file |

Scripts read these via `os.environ` — they are never passed as CLI arguments.

## Common Pitfalls

- **Putting tasks in the wrong order.** The platform runs tasks by `ExecutionOrder`, so a downstream script will fail if the upstream task has not yet written the expected files to `{output_path}`. For example, running a query script before `configure_duck_db_views.py` will fail because the DuckDB views do not exist yet.

- **Assuming a task can read or write anywhere on disk.** The platform only guarantees `{simulation_path}` for study data and `{output_path}` for working files. Scripts should be configured around those paths.

- **Missing environment variables.** The platform injects variables such as `simulation_path`, `output_path`, `cloud_cli_path`, `auth_path`, and `duck_db_path`. If a task depends on one of these and it is missing, the script will not have the context it needs. Scripts should fail fast with a clear error message when required env vars are absent.

- **Using wrong CLI argument names.** Task definitions must use the exact arguments expected by the script. Wrong parameter names cause silent runtime errors — especially with the CloudSDK where `remote_folder` vs `remote_glob_patterns` on `datahub.download` is a frequent mistake. Check each script's README for the correct argument names.

- **Writing to `{simulation_path}` in post tasks.** The `{simulation_path}` mount is read-only in post-simulation tasks. All output must go to `{output_path}`.

- **Not including `requirements.txt` in the `Files` array.** If a script has pip dependencies, the `requirements.txt` must be listed in `Files` so the platform can install them before running the script.

- **Forgetting to URL-encode spaces.** Paths with spaces in the `Arguments` field must use `%%20` encoding. Quoting alone is not reliable in the task runner.
