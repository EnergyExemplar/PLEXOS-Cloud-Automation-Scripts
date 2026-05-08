# DatahubConnectorSolParquetUploader - README

## Overview

**Type:** Post  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** 2026-04-01

### Purpose

Creates a DataHub connector, uploads solution parquet files, and then deletes the connector.

The script reads model ID and parquet path from the directory mapping JSON and uploads `*.parquet` files to a timestamped remote folder.

When a connector is created, the remote path is automatically prefixed with the connector type and name:

**With connector:** `connectors/{ConnectorType}/{ConnectorName}/{remote_path}/{model_id}/Solution_{YYYYMMDD_HHMMSS}`

### Key Features

- Resolves mapping file from `directory_map_path` or `/simulation/splits/directorymapping.json`
- Supports connector lifecycle in one run: create -> upload -> delete
- Supports multiple connector/auth combinations via connector CLI arguments
- Resolves sensitive connector auth values from environment variables passed via --secret-name-* args
- Validates every provided --secret-name-* arg against the environment; missing or empty values fail fast
- Uses CloudSDK `datahub.upload` with correct parameter names, `is_versioned=False`, and `print_message=False`
- Treats "File is identical to the remote file" as success

### Permissions And Execution Context

- Creating/deleting DataHub connectors and using task `Secrets` requires a role with connector administration permissions (Admin role recommended).
- Primary usage is as a cloud Post task with `simulationTasks[].Secrets` that inject environment variables.
- The script can be run from CLI, but required secret environment variables must be set in the shell beforehand.

---

## Arguments

### Required

| Argument | Description |
|---|---|
| `-r, --remote-path` | Base DataHub remote folder. Model ID and timestamp are appended automatically |
| `--connector-name` | Connector name to create before upload and delete afterward |
| `--connector-type` | Connector type: `AzureBlob` or `AmazonS3` |
| `--auth-type` | Auth type: `ConnectionString`, `Token`, `SharedKey` (AzureBlob); `AccountCreds`, `AssumeRole`, `SharedKey` (AmazonS3) |

### Connector Parameters (optional; supply as needed for chosen auth type)

| Argument | Used By |
|---|---|
| `--service-uri` | AzureBlob (Token, SharedKey) |
| `--account-name` | AzureBlob (SharedKey) |
| `--container-name` | AzureBlob (all auth types) |
| `--region` | AmazonS3 (all auth types) |
| `--bucket-name` | AmazonS3 (all auth types) |
| `--role-arn` | AmazonS3 (AssumeRole) |
| `--session-name` | AmazonS3 (AssumeRole) |
| `--service-endpoint-url` | AzureBlob (rare) |

### Secret Variable Name Arguments (optional; used to resolve sensitive values)

Pass environment variable identifiers (for example, `MY_BLOB_CONNECTION_STRING`), not raw secret values.
These flags are resolved using `os.getenv(<SECRET_NAME>)`.

| Argument | Used By |
|---|---|
| `--secret-name-connection-string` | AzureBlob (ConnectionString) |
| `--secret-name-account-key` | AzureBlob (SharedKey) |
| `--secret-name-sas-token` | AzureBlob (Token) |
| `--secret-name-s3-access-key` | AmazonS3 (AccountCreds, AssumeRole, SharedKey) |
| `--secret-name-s3-secret-key` | AmazonS3 (AccountCreds, AssumeRole, SharedKey) |
| `--secret-name-session-token` | AmazonS3 (SharedKey) |

### Connector/Auth Validation Matrix

The script validates connector/auth combinations and required arguments before any SDK call.

**AzureBlob Connector**

| Auth Type | Required Arguments |
|---|---|
| `ConnectionString` | `--secret-name-connection-string`, `--container-name` |
| `Token` | `--secret-name-sas-token`, `--service-uri`, `--container-name` |
| `SharedKey` | `--service-uri`, `--account-name`, `--secret-name-account-key`, `--container-name` |

**AmazonS3 Connector**

| Auth Type | Required Arguments |
|---|---|
| `AccountCreds` | `--secret-name-s3-access-key`, `--secret-name-s3-secret-key`, `--region`, `--bucket-name` |
| `AssumeRole` | `--secret-name-s3-access-key`, `--secret-name-s3-secret-key`, `--role-arn`, `--session-name`, `--region`, `--bucket-name` |
| `SharedKey` | `--secret-name-s3-access-key`, `--secret-name-s3-secret-key`, `--secret-name-session-token`, `--region`, `--bucket-name` |

---

## Environment Variables Used

| Variable | Required | Description |
|---|---|---|
| `cloud_cli_path` | Yes | Path to Cloud CLI executable |
| `directory_map_path` | No | Path to directory mapping JSON. Falls back to `/simulation/splits/directorymapping.json` |

---

## Dependencies

Declared in root `requirements.txt`:

- `eecloud`

---

## Creating Secrets With PLEXOS CLI

Create secrets before running simulation tasks that use `--secret-name-*` arguments.

```bash
pxc secrets create --name secret_name --value secret_value
```

Example:

```bash
pxc secrets create --name S3-access-key-post --value <your-access-key>
```

Then reference that secret in the task `Secrets` block with a valid environment variable identifier in `VariableName` (for example, `S3_ACCESS_KEY`).

---

## Simulation Task Examples

Use simulation task JSON with `Secrets` so the platform injects environment variables used by `--secret-name-*` arguments.

### AzureBlob + ConnectionString

```json
"simulationTasks": [
  {
    "name": "Azure Blob Storage Connector Parquet Upload",
    "files": [
      {
        "path": "Anurag/Scripts/requirements.txt",
        "version": null
      },
      {
        "path": "Anurag/Scripts/datahub_connector_solparquet_uploader.py",
        "version": null
      }
    ],
    "taskType": "POST",
    "Secrets": [
      { "SecretKey": "Blob-connection-string-post", "VariableName": "BLOB_CONNECTION_STRING" }
    ],
    "arguments": "python3 datahub_connector_solparquet_uploader.py --remote-path PostOperation/Solutions --connector-name ENTER_CONNECTOR_NAME --connector-type AzureBlob --auth-type ConnectionString --secret-name-connection-string BLOB_CONNECTION_STRING --container-name YOUR_CONTAINER_NAME",
    "continueOnError": true,
    "executionOrder": 1,
    "appliesTo": []
  }
]
```

### AzureBlob + Token

```json
"simulationTasks": [
  {
    "name": "Azure Blob Connector Parquet Upload (Token)",
    "files": [
      {
        "path": "Anurag/Scripts/requirements.txt",
        "version": null
      },
      {
        "path": "Anurag/Scripts/datahub_connector_solparquet_uploader.py",
        "version": null
      }
    ],
    "taskType": "POST",
    "Secrets": [
      { "SecretKey": "Blob-sas-token-post", "VariableName": "BLOB_SAS_TOKEN" }
    ],
    "arguments": "python3 datahub_connector_solparquet_uploader.py --remote-path PostOperation/Solutions --connector-name ENTER_CONNECTOR_NAME --connector-type AzureBlob --auth-type Token --secret-name-sas-token BLOB_SAS_TOKEN --service-uri https://exampleaccount.blob.core.windows.net --container-name YOUR_CONTAINER_NAME",
    "continueOnError": true,
    "executionOrder": 1,
    "appliesTo": []
  }
]
```

### AzureBlob + SharedKey

```json
"simulationTasks": [
  {
    "name": "Azure Blob Connector Parquet Upload (SharedKey)",
    "files": [
      {
        "path": "Anurag/Scripts/requirements.txt",
        "version": null
      },
      {
        "path": "Anurag/Scripts/datahub_connector_solparquet_uploader.py",
        "version": null
      }
    ],
    "taskType": "POST",
    "Secrets": [
      { "SecretKey": "Blob-account-key-post", "VariableName": "BLOB_ACCOUNT_KEY" }
    ],
    "arguments": "python3 datahub_connector_solparquet_uploader.py --remote-path PostOperation/Solutions --connector-name ENTER_CONNECTOR_NAME --connector-type AzureBlob --auth-type SharedKey --service-uri https://exampleaccount.blob.core.windows.net --account-name exampleaccount --secret-name-account-key BLOB_ACCOUNT_KEY --container-name YOUR_CONTAINER_NAME",
    "continueOnError": true,
    "executionOrder": 1,
    "appliesTo": []
  }
]
```

### AmazonS3 + AccountCreds

```json
"simulationTasks": [
  {
    "name": "Amazon S3 Connector Parquet Upload",
    "files": [
      {
        "path": "Anurag/Scripts/requirements.txt",
        "version": null
      },
      {
        "path": "Anurag/Scripts/datahub_connector_solparquet_uploader.py",
        "version": null
      }
    ],
    "taskType": "POST",
    "Secrets": [
      { "SecretKey": "S3-access-key-post", "VariableName": "S3_ACCESS_KEY" },
      { "SecretKey": "S3-secret-key-post", "VariableName": "S3_SECRET_KEY" }
    ],
    "arguments": "python3 datahub_connector_solparquet_uploader.py --remote-path PostScript_v1/Solutions --connector-name ENTER_CONNECTOR_NAME --connector-type AmazonS3 --auth-type AccountCreds --secret-name-s3-access-key S3_ACCESS_KEY --secret-name-s3-secret-key S3_SECRET_KEY --region ap-southeast-2 --bucket-name YOUR_BUCKET_NAME",
    "continueOnError": true,
    "executionOrder": 1,
    "appliesTo": []
  }
]
```

### AmazonS3 + AssumeRole

```json
"simulationTasks": [
  {
    "name": "Amazon S3 Connector Parquet Upload (AssumeRole)",
    "files": [
      {
        "path": "Anurag/Scripts/requirements.txt",
        "version": null
      },
      {
        "path": "Anurag/Scripts/datahub_connector_solparquet_uploader.py",
        "version": null
      }
    ],
    "taskType": "POST",
    "Secrets": [
      { "SecretKey": "S3-access-key-post", "VariableName": "S3_ACCESS_KEY" },
      { "SecretKey": "S3-secret-key-post", "VariableName": "S3_SECRET_KEY" }
    ],
    "arguments": "python3 datahub_connector_solparquet_uploader.py --remote-path PostScript_v1/Solutions --connector-name ENTER_CONNECTOR_NAME --connector-type AmazonS3 --auth-type AssumeRole --secret-name-s3-access-key S3_ACCESS_KEY --secret-name-s3-secret-key S3_SECRET_KEY --role-arn arn:aws:iam::123456789012:role/ExampleRole --session-name datahub-session --region ap-southeast-2 --bucket-name YOUR_BUCKET_NAME",
    "continueOnError": true,
    "executionOrder": 1,
    "appliesTo": []
  }
]
```

### AmazonS3 + SharedKey

```json
"simulationTasks": [
  {
    "name": "Amazon S3 Connector Parquet Upload (SharedKey)",
    "files": [
      {
        "path": "Anurag/Scripts/requirements.txt",
        "version": null
      },
      {
        "path": "Anurag/Scripts/datahub_connector_solparquet_uploader.py",
        "version": null
      }
    ],
    "taskType": "POST",
    "Secrets": [
      { "SecretKey": "S3-temp-access-key-post", "VariableName": "S3_TEMP_ACCESS_KEY" },
      { "SecretKey": "S3-temp-secret-key-post", "VariableName": "S3_TEMP_SECRET_KEY" },
      { "SecretKey": "S3-session-token-post", "VariableName": "S3_SESSION_TOKEN" }
    ],
    "arguments": "python3 datahub_connector_solparquet_uploader.py --remote-path PostScript_v1/Solutions --connector-name ENTER_CONNECTOR_NAME --connector-type AmazonS3 --auth-type SharedKey --secret-name-s3-access-key S3_TEMP_ACCESS_KEY --secret-name-s3-secret-key S3_TEMP_SECRET_KEY --secret-name-session-token S3_SESSION_TOKEN --region ap-southeast-2 --bucket-name YOUR_BUCKET_NAME",
    "continueOnError": true,
    "executionOrder": 1,
    "appliesTo": []
  }
]
```



