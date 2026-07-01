# DatahubDeepLink – README

## Overview

**Type:** Automation
**Platform:** PLEXOS
**Version:** 1.1
**Last Updated:** 2026-06-11

### Purpose

Create, list, browse, download, and delete Datahub deep links via CLI subcommands. Deep links provide secure, time-bounded sharing of Datahub files without requiring the recipient to have a PLEXOS Cloud account.

This folder contains **two scripts** (intentional deviation from one-script-per-folder convention — both serve the same "deep link management" capability with different dependency requirements):

| Script | Purpose | Requires CloudSDK? | Subcommands |
|---|---|---|---|
| `datahub_deep_link.py` | Full deep link lifecycle (authenticated operations via SDK) | Yes | `create`, `list`, `browse`, `download`, `delete` |
| `deep_link_http_download.py` | Browse and download deep links via raw HTTP (no authentication) | No — uses `urllib`/`requests` only | `browse`, `download` |

### Key Features

**`datahub_deep_link.py`** — Full lifecycle management (requires CloudSDK):
- **create** — Generate a signed deep link URL with configurable expiry and download limits
- **list** — View all deep links created by the current user
- **browse** — List files inside a folder deep link (uses `sdk.datahub.browse_deep_link()`, no authentication needed)
- **download** — Download a single file (uses `sdk.datahub.download_deep_link()`, no authentication needed)
- **delete** — Revoke a deep link, making it immediately inactive

**`deep_link_http_download.py`** — Raw HTTP browse and download (no SDK, CLI-agnostic):
- **browse** — List files inside a folder deep link using raw HTTP (`urllib`) with `X-DeepLink-Signature` header
- **download** — Download multiple files from a folder deep link in a single invocation via `requests`
- URL-encodes file paths automatically (handles spaces and special characters)
- Reports per-file success/failure with summary counts
- Proper error exit codes for CI/CD integration
- **Note:** To create deep links, use `datahub_deep_link.py` which handles authenticated creation via the SDK

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

### `browse` Subcommand

No authentication or environment login required — uses the SDK's `browse_deep_link` method.

| Argument | Required | Default | Description |
|---|---|---|---|
| `--cli-path` | Yes | — | Path to PLEXOS Cloud CLI executable |
| `--url` | Yes | — | The full deep link URL from creation output (download or browse URL) |
| `--signature` | Yes | — | The X-DeepLink-Signature value (shown once at creation) |
| `--file-path` | No | `None` | Subfolder path within the shared folder to browse |

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

This script uses subcommands: `browse` and `download`. Use `datahub_deep_link.py` to create deep links.

### `browse` Subcommand

No authentication needed — uses the pre-signed URL and signature over raw HTTP (`urllib`).

| Argument | Required | Default | Description |
|---|---|---|---|
| `--url` | Yes | — | The full deep link URL (download or browse URL from creation) |
| `--signature` | Yes | — | The `X-DeepLink-Signature` value (shown once at creation) |
| `--file-path` | No | `None` | Subfolder path within the shared folder to list |

### `download` Subcommand

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

The **create**, **list**, **download**, **browse**, and **delete** subcommands all require **eecloud >= 1.5.2854.495** (PLEXOS Cloud CLI v1.5.2854.495+).

The **browse** subcommand uses `sdk.datahub.browse_deep_link()` introduced in eecloud 1.5.2854.495 — no authentication or environment login is needed, but the SDK must be installed.

The eecloud methods used by the subcommands:
- `datahub.create_deep_link(...)` → returns `DeepLinkResult` with `.DownloadUrl` and `.Signature`
- `datahub.list_deep_links()` → returns object with `.DeepLinks[]` (each has `.UrlId`, `.RelativePath`, `.IsActive`, `.IsExpired`, `.CompletedDownloads`, `.DeepLinkEndTimeUtc`)
- `datahub.download_deep_link(url, signature, output, file_path)` → downloads the file to disk and returns `.FileName`, `.FilePath`, and `.FileSize` in the response
- `datahub.browse_deep_link(url, signature, file_path)` → returns object with `.DatahubSearchResults[]` (each has `.RelativePath`, `.FileSize`, `.LastModifiedAtUtc`, `.CreatedAtUtc`)
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

### Browse a folder deep link (no authentication needed)

```bash
python datahub_deep_link.py browse \
    --cli-path /path/to/plexos-cloud \
    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/a1b2c3.../download/MyFolder?kst=..." \
    --signature "abc123..."
```

Browse a specific subfolder within the deep link:

```bash
python datahub_deep_link.py browse \
    --cli-path /path/to/plexos-cloud \
    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/a1b2c3.../download/MyFolder?kst=..." \
    --signature "abc123..." \
    --file-path "SOLUTION_DATA"
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

**To create a deep link, use `datahub_deep_link.py`** (see examples above).

### Browse a deep link folder (HTTP/urllib)

```bash
python deep_link_http_download.py browse \
    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/98a6d0f1-.../download/" \
    --signature "PQDxyzI+XVyPwdwVOCDn0BdU3PME0TTpY2nuCRYbxMc="
```

### Download a single file from a folder deep link

```bash
python deep_link_http_download.py download \
    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/98a6d0f1-.../download/MyFolder?kst=...&ket=..." \
    --signature "PQDxyzI+XVyPwdwVOCDn0BdU3PME0TTpY2nuCRYbxMc=" \
    --output-dir ./downloads \
    --files "SOLUTION_DATA/result.parquet"
```

### Download multiple files in one invocation

```bash
python deep_link_http_download.py download \
    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/98a6d0f1-.../download/MyFolder?kst=...&ket=..." \
    --signature "PQDxyzI+XVyPwdwVOCDn0BdU3PME0TTpY2nuCRYbxMc=" \
    --output-dir ./downloads \
    --files "SOLUTION_DATA/file1.parquet" "SOLUTION_DATA/file2.parquet" "requirements.txt"
```
