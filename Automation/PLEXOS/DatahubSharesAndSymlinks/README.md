# DatahubSharesAndSymlinks – README

## Overview

**Type:** Automation
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** 2026-05-19

### Purpose

Create, list, and delete Datahub **Shares** and **Symlinks** via CLI subcommands. Shares grant dataset access to external parties. Symlinks reference shared datasets within a study or workflow — supporting both same-tenant (local) and cross-tenant links.

This folder contains one script with two manager classes (intentional deviation from one-script-per-folder convention — both features serve the same "dataset sharing and referencing" capability):

| Class | Purpose |
|---|---|
| `DatahubShareManager` | Create, list, and delete file shares |
| `DatahubSymlinkManager` | Create (local + cross-tenant), list, and delete symlinks |

### Key Features

- **share-create** — Create a file share with optional permissions (inline or from file)
- **share-list** — List all shares with permission details
- **share-delete** — Delete a share by ID
- **symlink-create** — Create a local or cross-tenant symlink to a shared dataset
- **symlink-list** — List all symlinks with target details
- **symlink-delete** — Delete a symlink by path
- Proper error exit codes for CI/CD integration

### Related Scripts

- **[DatahubDeepLink](../DatahubDeepLink/)** — Time-bounded sharing via deep links (alternative to shares)
- **[DownloadFromDataHub](../DownloadFromDataHub/)** — Download files after resolving a symlink

---

## Arguments

### Common Arguments (all subcommands)

| Argument | Required | Description |
|---|---|---|
| `--cli-path` | Yes | Path to PLEXOS Cloud CLI executable |
| `--environment` | Yes | Cloud environment name (e.g. 'preprod') |

### `share-create`

| Argument | Required | Default | Description |
|---|---|---|---|
| `--display-name` | Yes | — | Human-readable name for the share |
| `--remote-path` | Yes | — | Datahub relative path to share |
| `--permissions` | No | `None` | One or more permission strings in CSV format `AllowedScope,TenantId,UserId` (e.g. `Read,<TenantId>,` for tenant-wide read access). Multiple values can be passed by repeating the flag. |
| `--permissions-file` | No | `None` | Path to a file containing permissions |

### `share-list`

No additional arguments.

### `share-delete`

| Argument | Required | Description |
|---|---|---|
| `--share-id` | Yes | Share ID (GUID) to delete |

### `symlink-create`

| Argument | Required | Default | Description |
|---|---|---|---|
| `--display-name` | Yes | — | Human-readable name for the symlink |
| `--target-remote-path` | Yes | — | Datahub path the symlink points to |
| `--symlink-path` | Yes | — | Path where the symlink will be created |
| `--symlink-type` | Yes | — | Symlink type: `File` or `Directory` |
| `--local` | No | `False` | Create a local symlink (same tenant) |
| `--target-tenant-id` | No | `None` | Target tenant ID (required for cross-tenant) |

> **Note:** Use `--local` for same-tenant symlinks. For cross-tenant, omit `--local` and provide `--target-tenant-id`.

### `symlink-list`

| Argument | Required | Default | Description |
|---|---|---|---|
| `--path-filter` | No | `None` | Only show symlinks whose `SymlinkPath` starts with this value |

### `symlink-delete`

| Argument | Required | Description |
|---|---|---|
| `--symlink-path` | Yes | Path of the symlink to delete |

---

## Environment Variables Used

None. This is an Automation script — all configuration is passed as CLI arguments.

---

## Dependencies

The `eecloud` package (CloudSDK) is not pinned in the repository root `requirements.txt`.
It is installed as part of the PLEXOS Cloud CLI and must be available in the same Python
environment where this script runs (e.g. installed via the CLI installer or manually with
`pip install eecloud` using the CLI-bundled wheel).

```
eecloud (CloudSDK) — provided by the PLEXOS Cloud CLI installation
```

### Minimum SDK / CLI Version

Requires **eecloud >= 1.5.2621** (PLEXOS Cloud CLI v1.5.2621.473+).

SDK methods used:
- `datahub.create_share(display_name, remote_path, permissions, permissions_file_path)` → `Success`
- `datahub.list_shares()` → `Shares[].ShareId, .Name, .RelativePath, .Permissions[]`
- `datahub.delete_share(share_id)` → `Success`
- `datahub.create_local_symlink(display_name, target_remote_path, symlink_path, symlink_type)` → `Success`
- `datahub.create_symlink(display_name, target_tenant_id, target_remote_path, symlink_path, symlink_type)` → `Success`
- `datahub.list_symlinks()` → `Symlinks[].DisplayName, .SymlinkId, .Type, .TargetTenantId, .RemotePath, .SymlinkPath`
- `datahub.delete_symlink(symlink_path)` → `Success`

---

## Usage Examples

### Create a file share

```bash
python datahub_shares_symlinks.py share-create \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod \
    --display-name "Q3 Forecast Data" \
    --remote-path "datasets/q3-forecast" \
    --permissions "cloud.api,550e8400-e29b-41d4-a716-446655440000,"
```

### Create a share with permissions from file

```bash
python datahub_shares_symlinks.py share-create \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod \
    --display-name "Model Inputs" \
    --remote-path "models/inputs" \
    --permissions-file permissions.csv
```

### List all shares

```bash
python datahub_shares_symlinks.py share-list \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod
```

### Delete a share

```bash
python datahub_shares_symlinks.py share-delete \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod \
    --share-id "550e8400-e29b-41d4-a716-446655440000"
```

### Create a local symlink (same tenant)

```bash
python datahub_shares_symlinks.py symlink-create \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod \
    --local \
    --display-name "Shared Inputs Link" \
    --target-remote-path "datasets/shared-inputs" \
    --symlink-path "my-project/inputs" \
    --symlink-type Directory
```

### Create a cross-tenant symlink (Directory)

```bash
python datahub_shares_symlinks.py symlink-create \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod \
    --display-name "Partner Data Link" \
    --target-tenant-id "550e8400-e29b-41d4-a716-446655440000" \
    --target-remote-path "shared/partner-data" \
    --symlink-path "my-project/partner" \
    --symlink-type Directory
```

### Create a cross-tenant symlink (File)

```bash
python datahub_shares_symlinks.py symlink-create \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod \
    --display-name "Partner Forecast CSV" \
    --target-tenant-id "550e8400-e29b-41d4-a716-446655440000" \
    --target-remote-path "shared/forecast.csv" \
    --symlink-path "my-project/forecast.csv" \
    --symlink-type File
```

### List all symlinks

```bash
python datahub_shares_symlinks.py symlink-list \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod
```

### Delete a symlink

```bash
python datahub_shares_symlinks.py symlink-delete \
    --cli-path "C:\Programs\PLEXOS.Cloud\plexos-cloud.exe" \
    --environment preprod \
    --symlink-path "my-project/inputs"
```
