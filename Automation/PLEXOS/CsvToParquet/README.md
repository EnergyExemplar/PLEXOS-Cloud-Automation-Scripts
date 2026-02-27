# CSV to Parquet – README

## Overview

**Type:** Automation (Local)
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** February 2026

### Purpose

Converts CSV files to compressed Parquet format for efficient storage and faster processing. Supports single file or batch directory conversion, with optional upload to DataHub.

**Use Cases:**
- Convert large CSV datasets to Parquet for improved performance
- Reduce file storage size with compression
- Prepare files for upload to DataHub in optimal format

---

## Arguments

### Input Selection (one required)

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `-i, --input` | str | Input CSV file path | `-i input.csv` |
| `--input-dir` | str | Input directory containing CSV files | `--input-dir ./csv_files` |

### Output Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `-o, --output` | str | Same name + `.parquet` | Output Parquet file path (single file mode only) |
| `--output-dir` | str | Same as input-dir | Output directory for Parquet files |
| `--pattern` | str | `*.csv` | Glob pattern for CSV files in directory mode |
| `--compression` | choice | `zstd` | Compression: `zstd`/`gzip`/`snappy`/`none` |

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
python csv_to_parquet.py -i forecast.csv
# Creates forecast.parquet with ZSTD compression
```

### Convert with custom output path

```bash
python csv_to_parquet.py -i input.csv -o output/data.parquet
```

### Convert directory of CSV files

```bash
python csv_to_parquet.py --input-dir ./csv_data --output-dir ./parquet_data
```

### Convert and upload to DataHub

```bash
python csv_to_parquet.py \
  --input-dir ./results \
  --pattern "*.csv" \
  --compression gzip \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  --upload Project/Study/Results
```

---

## Expected Behaviour

### Success

1. Validates input paths exist
2. Converts CSV file(s) to Parquet with specified compression
3. Displays row counts and file sizes for converted files
4. Optionally uploads to DataHub if requested
5. Exits with code `0`

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| No input specified | 1 | Use `-i` or `--input-dir` |
| Input file/directory not found | 1 | Verify paths are correct |
| Upload requested without CLI path/environment | 1 | Provide `-c` and `-e` arguments |
| Conversion failed (invalid CSV format) | 1 | Check CSV file structure |

---

## Output

Parquet files with the same base name as input CSV files, compressed using the specified algorithm.

**Compression comparison:**
- `zstd`: Best compression ratio, fast (recommended)
- `gzip`: Good compression, widely compatible
- `snappy`: Fast, moderate compression
- `none`: No compression, fastest but largest files

---

## Related Scripts

**Relies on:** [UploadToDataHub](../UploadToDataHub/) when using the `--upload` option.
