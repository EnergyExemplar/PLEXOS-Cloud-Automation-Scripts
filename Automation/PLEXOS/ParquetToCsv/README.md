# Parquet to CSV – README

## Overview

**Type:** Automation (Local)
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026

### Purpose

Converts Parquet files to CSV format for compatibility with tools that require CSV input. Supports single file or batch directory conversion, with optional upload to DataHub.

**Use Cases:**
- Convert Parquet files to CSV for Excel or legacy tool compatibility
- Export compressed data to human-readable format
- Prepare files for tools that don't support Parquet

---

## Arguments

### Input Selection (one required)

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `-i, --input` | str | Input Parquet file path | `-i input.parquet` |
| `--input-dir` | str | Input directory containing Parquet files | `--input-dir ./parquet_files` |

### Output Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `-o, --output` | str | Same name + `.csv` | Output CSV file path (single file mode only) |
| `--output-dir` | str | Same as input-dir | Output directory for CSV files |
| `--pattern` | str | `*.parquet` | Glob pattern for Parquet files in directory mode |

### DataHub Upload (optional)

| Argument | Type | Description |
|----------|------|-------------|
| `-c, --cli-path` | str | Full path to PLEXOS Cloud CLI (required if uploading) |
| `-e, --environment` | str | Cloud environment name (required if uploading) |
| `--upload` | str | DataHub path to upload converted files |

---

## Environment Variables Used

**None.** This script does not rely on environment variables.

---

## Dependencies

See root `requirements.txt`. This script uses:
- `pandas>=1.3.0`
- `pyarrow>=6.0.0`
- `eecloud` SDK (if uploading to DataHub)

---

## Example Usage

### Convert single file

```bash
python parquet_to_csv.py -i data.parquet
# Creates data.csv
```

### Convert with custom output path

```bash
python parquet_to_csv.py -i input.parquet -o output/results.csv
```

### Convert directory of Parquet files

```bash
python parquet_to_csv.py --input-dir ./parquet_data --output-dir ./csv_data
```

### Convert and upload to DataHub

```bash
python parquet_to_csv.py \
  --input-dir ./results \
  --pattern "*.parquet" \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  --upload Project/Study/Results
```

---

## Expected Behaviour

### Success

1. Validates input paths exist
2. Converts Parquet file(s) to CSV format
3. Displays row counts and file sizes for converted files
4. Optionally uploads to DataHub if requested
5. Exits with code `0`

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| No input specified | 1 | Use `-i` or `--input-dir` |
| Input file/directory not found | 1 | Verify paths are correct |
| Upload requested without CLI path/environment | 1 | Provide `-c` and `-e` arguments |
| Conversion failed (corrupted Parquet file) | 1 | Check Parquet file integrity |

---

## Output

CSV files with the same base name as input Parquet files.

**Note:** CSV files are typically larger than compressed Parquet files. The conversion is useful for compatibility but may increase storage requirements.

---

## Related Scripts

**Relies on:** [UploadToDataHub](../UploadToDataHub/) when using the `--upload` option.
