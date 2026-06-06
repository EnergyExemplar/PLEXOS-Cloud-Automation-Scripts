# DatahubDeepLink – README

## Overview

**Type:** Automation
**Platform:** PLEXOS
**Version:** 1.1
**Last Updated:** 2026-05-15

### Purpose

Create, list, download, and delete Datahub deep links via CLI subcommands. Deep links provide secure, time-bounded sharing of Datahub files without requiring the recipient to have a PLEXOS Cloud account.

This folder contains **two scripts** (intentional deviation from one-script-per-folder convention — both serve the same "deep link download" capability with different dependency requirements):

| Script | Purpose | Requires CloudSDK? |
|---|---|---|
| `datahub_deep_link.py` | Full deep link lifecycle (create, list, download, delete) | Yes |
| `deep_link_http_download.py` | Batch download files from a folder deep link via raw HTTP | No — uses `requests` only |

### Key Features

**`datahub_deep_link.py`** — Full lifecycle management (requires CloudSDK):
- **create** — Generate a signed deep link URL with configurable expiry and download limits
- **list** — View all deep links created by the current user
- **download** — Download a single file using the SDK's `download_deep_link` method
- **delete** — Revoke a deep link, making it immediately inactive

**`deep_link_http_download.py`** — Lightweight batch downloader (no SDK needed):
- Downloads multiple files from a folder deep link in a single invocation
- Uses raw HTTP GET with `X-DeepLink-Signature` header
- URL-encodes file paths automatically (handles spaces and special characters)
- Reports per-file success/failure with summary counts
- Proper error exit codes for CI/CD integration

---

## Arguments — `datahub_deep_link.py`

### Common Arguments (all subcommands)

| Argument | Required | Description |
|---|---|---|
| `--cli-path` | Yes | Path to PLEXOS Cloud CLI executable |

### `create` Subcommand

| Argument | Required | Default | Description |
|---|---|---|---|
| `--environment` | Yes | — | Cloud environment name |
| `--path` | Yes | — | Datahub relative path to the resource |
| `--type` | Yes | — | Resource type: `File` or `Folder` |
| `--days` | No | `None` | Link validity in days |
| `--hours` | No | `None` | Link validity in hours |
| `--expiry` | No | `None` | Exact expiry time (ISO 8601 UTC) |
| `--limit` | No | `None` | Maximum download count |

> At least one of `--days`, `--hours`, or `--expiry` is required.

### `list` Subcommand

| Argument | Required | Description |
|---|---|---|
| `--environment` | Yes | Cloud environment name |

### `download` Subcommand

| Argument | Required | Default | Description |
|---|---|---|---|
| `--download-url` | Yes | — | The full download URL from deep link creation |
| `--signature` | Yes | — | The X-DeepLink-Signature value |
| `--output-dir` | Yes | — | Local directory to save downloaded file(s) |
| `--internal-file-path` | No | `None` | For folder deep links: relative path to a file within the shared folder |

### `delete` Subcommand

| Argument | Required | Description |
|---|---|---|
| `--environment` | Yes | Cloud environment name |
| `--id` | Yes | Deep link URL ID (GUID) to revoke |

---

## Arguments — `deep_link_http_download.py`

| Argument | Required | Description |
|---|---|---|
| `--url` | Yes | The full deep link download URL (from `create` output) |
| `--signature` | Yes | The `X-DeepLink-Signature` value (shown once at creation) |
| `--output-dir` | Yes | Local directory to save downloaded files (created if it doesn't exist) |
| `--files` | Yes | One or more internal file paths within the deep link folder |

---

## Environment Variables Used

This is an **Automation script** — it does not use platform-injected environment variables. All configuration is passed as CLI arguments.

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud (CloudSDK) — datahub_deep_link.py only
requests           — deep_link_http_download.py only
```

### Minimum SDK / CLI Version

`datahub_deep_link.py` requires **eecloud >= 1.5.2621** (PLEXOS Cloud CLI v1.5.2621.473+).

The deep link methods used:
- `datahub.create_deep_link(relative_path, expiry_days, max_downloads)` → returns `DeepLinkResult` with `.DownloadUrl`, `.Signature`, `.Files[]`
- `datahub.list_deep_links()` → returns object with `.DeepLinks[]` (each has `.UrlId`, `.RelativePath`, `.IsActive`, `.IsExpired`, `.CompletedDownloads`, `.DeepLinkEndTimeUtc`)
- `datahub.revoke_deep_link(id)` → revokes a deep link by its `UrlId`

These methods are not yet documented in `Documentation/CloudSDK.md`.

---

## Usage Examples — `datahub_deep_link.py`

### Create a deep link (valid for 7 days, max 5 downloads)

```bash
python datahub_deep_link.py create \
    --cli-path /path/to/plexos-cloud \
    --environment preprod \
    --path "Project/Study/results.parquet" \
    --type File \
    --days 7 \
    --limit 5
```

### List all deep links

```bash
python datahub_deep_link.py list \
    --cli-path /path/to/plexos-cloud \
    --environment preprod
```

### Download via deep link (no authentication needed)

```bash
python datahub_deep_link.py download \
    --cli-path /path/to/plexos-cloud \
    --download-url "https://cloud.energyexemplar.com/api/datahub/deeplink/..." \
    --signature "abc123..." \
    --output-dir ./downloads
```

### Revoke a deep link

```bash
python datahub_deep_link.py delete \
    --cli-path /path/to/plexos-cloud \
    --environment preprod \
    --id "550e8400-e29b-41d4-a716-446655440000"
```

---

## Usage Examples — `deep_link_http_download.py`

### Download a single file from a folder deep link

```bash
python deep_link_http_download.py \
    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/98a6d0f1-.../download/MyFolder?kst=...&ket=..." \
    --signature "PQDxyzI+XVyPwdwVOCDn0BdU3PME0TTpY2nuCRYbxMc=" \
    --output-dir ./downloads \
    --files "SOLUTION_DATA/result.parquet"
```

### Download multiple files in one invocation

```bash
python deep_link_http_download.py \
    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/98a6d0f1-.../download/MyFolder?kst=...&ket=..." \
    --signature "PQDxyzI+XVyPwdwVOCDn0BdU3PME0TTpY2nuCRYbxMc=" \
    --output-dir ./downloads \
    --files "SOLUTION_DATA/file1.parquet" "SOLUTION_DATA/file2.parquet" "requirements.txt"
```
