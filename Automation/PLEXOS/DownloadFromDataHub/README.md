# Download From DataHub – README

## Overview

**Type:** Automation (Local)
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026

### Purpose

Downloads one or more files from DataHub to a local directory. This is a standalone utility for local workflows that need to retrieve files from DataHub without running in a cloud simulation context.

**Use Cases:**
- Download simulation inputs for local analysis
- Retrieve historical data for comparison
- Fetch results from previous runs for post-processing

---

## Arguments

### Required Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `-c, --cli-path` | str | Full path to PLEXOS Cloud CLI executable | `-c /usr/local/bin/plexos-cloud` |
| `-e, --environment` | str | Cloud environment name | `-e <your-environment>` |
| `-f, --file` | str | DataHub file path to download (repeat for multiple files) | `-f Project/Study/input.csv` |
| `-o, --output-dir` | str | Local output directory | `-o ./downloads` |

---

## Environment Variables Used

**None.** This script does not rely on environment variables.

---

## Dependencies

See root `requirements.txt`. This script uses:
- `eecloud` SDK (Python SDK for PLEXOS Cloud)

---

## Example Usage

### Download single file

```bash
python download_from_datahub.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -f Project/Study/input.csv \
  -o ./downloads
```

### Download multiple files

```bash
python download_from_datahub.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -f Project/Study/forecast.csv \
  -f Project/Study/actual.csv \
  -f Project/Study/reference.parquet \
  -o ./local_data
```

---

## Expected Behaviour

### Success

1. Creates output directory if it doesn't exist
2. Authenticates with specified environment
3. Downloads each specified file from DataHub
4. Prints summary of successful and failed downloads
5. Exits with code `0`

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| Invalid CLI path | 1 | Verify `-c` path is correct |
| Authentication failure | 1 | Check environment name and credentials |
| File not found in DataHub | 1 | Verify DataHub path is correct |
| All downloads failed | 1 | Check network connectivity and permissions |

---

## Output

Downloaded files are saved to the specified output directory with their original filenames.

---

## Related Scripts

**Relies on:** None.
