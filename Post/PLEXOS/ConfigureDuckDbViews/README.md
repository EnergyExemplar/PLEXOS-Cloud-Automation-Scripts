# ConfigureDuckDbViews – README

## Overview

**Type:** Post  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** 2026-03-11  
**Author:** IDC Energy Exemplar

### Purpose

Configures DuckDB views for querying PLEXOS solution parquet data. The script resolves the
solution parquet directory from the first `ParquetPath` entry in the directory mapping JSON,
walks all subdirectories, and creates a `CREATE OR REPLACE VIEW` statement in the DuckDB file
for each subdirectory — pointing at all `*.parquet` files in that subtree.

This is a **focused script** — view creation only. No DataHub upload.

### Key Features

- Resolves the directory mapping JSON from `directory_map_path` if set, otherwise falls back to
  `/simulation/splits/directorymapping.json`.
- Uses the first entry in the mapping that contains a `ParquetPath` field.
- Creates one DuckDB view per subdirectory using a recursive glob (`**/*.parquet`) with
  `union_by_name=true` to handle schema variation across files.
- Quoted view identifiers handle any directory-name characters safely.
- Optional `--verbose` flag prints each `CREATE VIEW` statement and a 2-row sample.
- Exits with code `0` on success, `1` on any failure.

### Related Scripts

- **After this script:** Any task that queries the DuckDB views to extract or summarise solution data.

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--verbose` | No | `false` | Print each `CREATE VIEW` statement and a 2-row sample query result |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `duck_db_path` | Required. Path to the DuckDB file where views will be created (platform default: `/output/solution_views.ddb`) |
| `directory_map_path` | Optional. Path to directory mapping JSON. Falls back to `/simulation/splits/directorymapping.json` |

> Expected JSON format: a list of objects where each item optionally contains a `ParquetPath`
> field. The script uses the **first entry** that has a `ParquetPath`.

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
```

- Python 3.11+

---

## Chaining This Script

This script is designed to run after the PLEXOS simulation and ETL have completed.

### Chain — Configure views, then query

```json
[
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
]
```

---

## Example Commands

```bash
# Configure views (uses first ParquetPath entry in the mapping)
python3 configure_duck_db_views.py

# Configure with verbose output (prints each CREATE VIEW and a 2-row sample)
python3 configure_duck_db_views.py --verbose
```

---

## Expected Behaviour

### Success

1. Reads `duck_db_path` from env — exits with code `1` immediately if missing.
2. Resolves the directory mapping JSON: uses `directory_map_path` if set, otherwise falls back to `/simulation/splits/directorymapping.json`.
3. Reads the first entry with a `ParquetPath` field to find the solution directory.
4. Walks all subdirectories under `ParquetPath`.
5. Creates a `CREATE OR REPLACE VIEW` in the DuckDB file for each subdirectory.
6. Prints a summary of how many views were created.
7. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `duck_db_path` env var missing | 1 | Set the `duck_db_path` environment variable |
| Mapping file not found at either path | 1 | Set `directory_map_path` or ensure `/simulation/splits/directorymapping.json` exists |
| Mapping JSON empty or malformed | 1 | Fix JSON formatting |
| No entry with `ParquetPath` in mapping | 1 | Ensure the mapping JSON contains an entry with a `ParquetPath` field |
| DuckDB connection or view creation fails | 1 | Check DuckDB file permissions and path validity |
