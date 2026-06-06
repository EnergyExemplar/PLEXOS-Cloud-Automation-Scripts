# DataHub — Cloud File Storage

## What It Is

DataHub is the cloud file storage layer used by PLEXOS and Aurora automation scripts to move files into and out of the simulation workflow. It is the place where scripts upload inputs, results, and intermediate artifacts so they can be chained without manual file transfer.

In this repository, DataHub is most often used as the handoff point between pre-simulation preparation and post-simulation result processing. It also supports cleanup-oriented workflows where temporary files are removed after upload.

DataHub is accessed through the CloudSDK's `datahub` module, which provides methods for uploading, downloading, searching, querying, deleting, versioning, tagging, and sharing files. All DataHub operations are scoped to the active environment and tenant.

## How Scripts Use It

Scripts use DataHub when a workflow needs to persist files outside the local simulation container or retrieve files before a run starts. For example, [Download From Data Hub](../Pre/PLEXOS/DownloadFromDataHub/README.md) pulls input files into the simulation environment using glob patterns (e.g. `Project/Study/inputs/**`), while [Upload To Data Hub](../Post/PLEXOS/UploadToDataHub/README.md) and [Upload To Data Hub](../Automation/PLEXOS/UploadToDataHub/README.md) push generated outputs from `{output_path}` back to cloud storage at a specific DataHub path.

You can also see DataHub as the bridge between format conversion steps and simulation steps. A common pattern is download → convert → run or query → convert → upload, such as [Download From Data Hub To Parquet To Csv](../Workflows/download-from-data-hub-to-parquet-to-csv.md), [Csv To Parquet To Upload To Data Hub](../Workflows/csv-to-parquet-to-upload-to-data-hub.md), and [Solution Data Query To Upload To Data Hub](../Workflows/solution-data-query-to-upload-to-data-hub.md).

> **Note:** Files written to `{output_path}` are automatically uploaded by the platform as solution artifacts at the end of a simulation. The Upload To Data Hub script is only needed when you want to upload to a *specific* DataHub folder, with a *specific* file pattern, or with versioning control — immediately after another task completes.

## Key Patterns

- **Set the user environment before any cloud operation.**  
  The CloudSDK documentation shows the standard sequence:
  ```python
  from eecloud.cloudsdk import CloudSDK, SDKBase

  pxc: CloudSdk = CloudSDK(cli_path=r"c:\path\to\cli.exe")
  pxc.environment.set_user_environment(environment="NA", print_message=True)
  ```
  This matters because DataHub operations depend on the active environment. In pre/post scripts running inside the cloud container, the environment is already configured via the `cloud_cli_path` env var — no explicit `set_user_environment` call is needed.

- **Authenticate before calling DataHub methods.**  
  The SDK documentation states that most functions require authentication. For automation scripts running locally, the documented client-credentials flow is:
  ```python
  pxc.auth.login_client_credentials(
      use_client_credentials=True,
      client_id=client_id,
      client_secret=client_secret,
      tenant_id=tenant_id,
      print_message=True
  )
  ```
  Pre/post scripts running inside the simulation container are already authenticated via the platform-injected `auth_path` token — no login call is required.

- **Use `{output_path}` as the working handoff directory.**  
  Everything written to `{output_path}` is automatically captured as solution artifacts at the end of the run. DataHub workflows commonly stage files there before upload.

- **Use correct SDK parameter names for download and upload.**  
  The most common source of silent runtime errors is using wrong parameter names:
  - `datahub.download` — correct params: `remote_glob_patterns` (list of glob strings) and `output_directory` (local path). The params `remote_folder` and `local_folder` do **not** exist on download.
  - `datahub.upload` — correct params: `local_folder`, `remote_folder`, `glob_patterns` (list), `is_versioned`.
  - Response model: `data.DatahubResourceResults[i].Success`, `.RelativeFilePath`, `.LocalFilePath`, `.FailureReason`.
  - A `FailureReason` of `"File is identical to the remote file"` is not a real failure — treat it as success.

- **Chain DataHub with format conversion scripts.**  
  DataHub is rarely the end of the workflow by itself. It is usually paired with scripts such as:
  - [Download From Data Hub](../Automation/PLEXOS/DownloadFromDataHub/README.md) — download using glob patterns
  - [Parquet To Csv](../Automation/PLEXOS/ParquetToCsv/README.md) — convert downloaded Parquet to CSV
  - [Csv To Parquet](../Automation/PLEXOS/CsvToParquet/README.md) — convert CSV results to Parquet
  - [Upload To Data Hub](../Automation/PLEXOS/UploadToDataHub/README.md) — upload to a specific DataHub path

- **Use `datahub.search` to discover files before downloading.**  
  If you do not know the exact file paths, use `datahub.search(glob_patterns=["folder/**/*.parquet"])` to list matching files with metadata (size, version, timestamps, tags, deletion status) before downloading.

- **Use `datahub.query` for server-side SQL against DataHub Parquet files.**  
  Instead of downloading a file and querying locally, you can run SQL directly:
  ```python
  resp = pxc.datahub.query(sql="SELECT * FROM fullkeyinfo", relative_path="path/to/file.parquet")
  ```

- **Support versioning and tagging for traceability.**  
  DataHub supports file versioning (`is_versioned=True` on upload) and tagging (`datahub.create_tag`, `datahub.search_tags`). Use versioning when you need to track changes to input files over time, and tagging to organise and filter files by metadata.

- **URL-encode paths with spaces.**  
  When passing DataHub paths through task definition `Arguments` fields, encode spaces as `%20`. Quoting alone is not reliable in the task runner. For example: `Project/Study%203/Output%20Folder`.

## Common Pitfalls

- **Skipping environment setup in automation scripts.**  
  If the user environment is not set, cloud operations can target the wrong environment or fail to resolve the expected tenant context. Pre/post scripts running in the container already have the environment configured.

- **Trying to use DataHub without authentication in automation scripts.**  
  The SDK documentation is explicit that most functions require authentication. If login is missing, upload and download calls will fail. Pre/post scripts are already authenticated via `auth_path`.

- **Writing files outside `{output_path}` when the workflow expects automatic capture.**  
  The repository README states that `{output_path}` is the script working directory and is automatically uploaded as solution artifacts. Files written elsewhere may not be collected.

- **Using wrong parameter names on `datahub.download`.**  
  A common mistake is passing `remote_folder` or `local_folder` to `datahub.download`. The correct parameters are `remote_glob_patterns` and `output_directory`. Wrong names cause silent runtime errors with no clear error message.

- **Using DataHub when the real problem is local file transformation.**  
  If you only need to convert CSV to Parquet or Parquet to CSV, use the conversion scripts first and then upload or download as needed. DataHub is storage and transfer, not the transformation step itself.

- **Ignoring the `FailureReason` field on upload results.**  
  When `FailureReason` is `"File is identical to the remote file"`, it means the file already exists with the same content — this is not a real failure and should be treated as success.
