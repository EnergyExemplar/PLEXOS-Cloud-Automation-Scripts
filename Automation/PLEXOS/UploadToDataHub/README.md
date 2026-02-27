# Upload To DataHub – README

## Overview

**Type:** Automation (Local)
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026

### Purpose

Uploads one or more local files or an entire directory to DataHub. This is a standalone utility for local workflows that need to push files to DataHub without running in a cloud simulation context.

**Use Cases:**
- Upload analysis results to DataHub for sharing
- Push locally processed data to cloud storage
- Batch upload multiple output files after local processing

---

## Arguments

### Required Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `-c, --cli-path` | str | Full path to PLEXOS Cloud CLI executable | `-c /usr/local/bin/plexos-cloud` |
| `-e, --environment` | str | Cloud environment name | `-e <your-environment>` |
| `-d, --datahub-path` | str | Target DataHub directory path | `-d Project/Study/Results` |

### File Selection (at least one required)

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `-f, --file` | str | Local file path to upload (repeat for multiple files) | `-f ./output.csv` |
| `--directory` | str | Upload all files from this directory | `--directory ./results` |

### Optional Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--pattern` | str | `*` | Glob pattern for files when using --directory | `--pattern "*.csv"` |
| `--no-overwrite` | flag | False | Do not overwrite existing files in DataHub |

---

## Environment Variables Used

**None.** This script does not rely on environment variables.

---

## Dependencies

See root `requirements.txt`. This script uses:
- `eecloud` SDK (Python SDK for PLEXOS Cloud)

---

## Example Usage

### Upload single file

```bash
python upload_to_datahub.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -f ./results/comparison.csv \
  -d Project/Study/Results
```

### Upload multiple files

```bash
python upload_to_datahub.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -f ./output1.csv \
  -f ./output2.parquet \
  -f ./summary.json \
  -d Project/Study/Results
```

### Upload entire directory

```bash
python upload_to_datahub.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  --directory ./results \
  --pattern "*.csv" \
  -d Project/Study/Results
```

### Upload directory without overwriting

```bash
python upload_to_datahub.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  --directory ./results \
  -d Project/Study/Results \
  --no-overwrite
```

---

## Expected Behaviour

### Success

1. Authenticates with specified environment
2. Validates all local file paths exist
3. Uploads each file to DataHub
4. Prints summary of successful and failed uploads
5. Exits with code `0`

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| Invalid CLI path | 1 | Verify `-c` path is correct |
| Authentication failure | 1 | Check environment name and credentials |
| Local file not found | 1 | Verify file paths are correct |
| No files specified | 1 | Use `-f` or `--directory` |
| All uploads failed | 1 | Check network connectivity and DataHub permissions |

---

## Output

Files are uploaded to the specified DataHub path with their original filenames.

---

## Related Scripts

**Relies on:** None.
