# Query Write Memberships – README

## Overview

**Type:** Post (can also be used as Pre)  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** March, 2026  
**Author:** Energy Exemplar

### Purpose

Exports PLEXOS model membership relationships from the SQLite database to CSV format. Membership data shows parent-child relationships between objects (e.g., which generators belong to which regions, which fuels are used by which generators).

This is a **focused script** — it queries and exports membership data only. Use for model documentation, validation, or structure analysis.

### Key Features

- Queries PLEXOS reference.db (SQLite database) using DuckDB
- Exports comprehensive membership relationships to CSV
- Includes parent/child classes, objects, and collections
- Shows data preview in execution logs
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** None (reads from simulation files)
- **After this script:** [UploadToDataHub](../UploadToDataHub/) — upload CSV to DataHub for storage
- **After this script (optional):** [CsvToParquet](../CsvToParquet/) — convert the CSV to Parquet before uploading
- **After upload (optional):** [CleanupFiles](../CleanupFiles/) — remove intermediate files from output_path after upload

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-o`, `--output-file` | No | `memberships_data.csv` | Name of output CSV file (plain filename only; no path separators or absolute paths). The file is created in the `output_path` directory. |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `simulation_path` | Path to simulation directory containing reference.db (default: `/simulation`) |
| `output_path` | Working directory where CSV will be written (default: `/output`) |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
duckdb
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — Export and Upload Memberships

```json
[
  {
    "Name": "Export Membership Data",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/requirements.txt", "Version": null },
      { "Path": "Project/Study/query_write_memberships.py", "Version": null }
    ],
    "Arguments": "python3 query_write_memberships.py --output-file memberships.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Upload Memberships to Datahub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/ModelStructure -p memberships.csv",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

### Chain 2 — Full Pipeline (Export → Convert → Upload → Cleanup)

```json
[
  {
    "Name": "Export Membership Data",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/requirements.txt", "Version": null },
      { "Path": "Project/Study/query_write_memberships.py", "Version": null }
    ],
    "Arguments": "python3 query_write_memberships.py --output-file memberships.csv",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Convert Memberships CSV to Parquet",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/convert_csv_to_parquet.py", "Version": null }
    ],
    "Arguments": "python3 convert_csv_to_parquet.py --input-file memberships.csv",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  },
  {
    "Name": "Upload Memberships to DataHub",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/upload_to_datahub.py", "Version": null }
    ],
    "Arguments": "python3 upload_to_datahub.py -l output_path -r Project/Study/ModelStructure -p memberships.parquet",
    "ContinueOnError": true,
    "ExecutionOrder": 3
  },
  {
    "Name": "Cleanup Intermediate Files",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/cleanup_files.py", "Version": null }
    ],
    "Arguments": "python3 cleanup_files.py --patterns memberships.csv",
    "ContinueOnError": true,
    "ExecutionOrder": 4
  }
]
```

### Chain 3 — Model Documentation Workflow

```json
[
  {
    "Name": "Export Memberships",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Project/Study/query_write_memberships.py", "Version": null }
    ],
    "Arguments": "python3 query_write_memberships.py",
    "ContinueOnError": true,
    "ExecutionOrder": 1
  },
  {
    "Name": "Run Simulation",
    "TaskType": "Compute",
    "Arguments": "...",
    "ExecutionOrder": 2
  }
]
```

---

## Example Commands

```bash
# Basic usage — export to default filename
python3 query_write_memberships.py

# Export to custom filename
python3 query_write_memberships.py --output-file model_structure.csv

# Use in conjunction with upload
python3 query_write_memberships.py --output-file memberships.csv
python3 upload_to_datahub.py -l /output -r Project/Study/Docs -p memberships.csv
```

---

## Expected Behaviour

### Success

1. Script starts and logs configuration
2. Connects to `reference.db` under simulation_path (default `/simulation`) via DuckDB
3. Loads SQLite extension
4. Attaches reference database
5. Queries membership data across multiple tables
6. Exports results to CSV in output_path (default `/output`)
7. Displays data preview in logs
8. Logs row count and output file location
9. Exits with code `0` on success (or `130` if cancelled via Ctrl+C)

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| Database file (`reference.db`) not found | 1 | Verify simulation_path and ensure reference.db exists |
| DuckDB SQLite extension fails to load | 1 | Check DuckDB installation |
| Query execution fails | 1 | Check database schema compatibility |
| CSV export fails | 1 | Check output_path permissions and disk space |
| Script cancelled by user (Ctrl+C) | 130 | Expected for interactive cancellation; not a script error |

---

## Output Format

The exported CSV contains the following columns:

| Column | Description |
|---|---|
| `parent_class` | Class name of parent object (e.g., Region, Generator) |
| `child_class` | Class name of child object (e.g., Generator, Fuel) |
| `collection` | Collection name linking parent and child (e.g., Generators, Fuels) |
| `parent_object` | Name of parent object instance (e.g., "Region1") |
| `child_object` | Name of child object instance (e.g., "Coal_Gen1") |

### Example Output:

```csv
parent_class,child_class,collection,parent_object,child_object
Region,Generator,Generators,Region1,Coal_Gen1
Region,Generator,Generators,Region1,Gas_Gen1
Generator,Fuel,Fuels,Coal_Gen1,Coal
Generator,Fuel,Fuels,Gas_Gen1,Natural Gas
```

---

## Notes

- **Database Location:** The script expects `reference.db` under `simulation_path` (default: `/simulation`). This is the standard PLEXOS SQLite input database location.

- **DuckDB vs Direct SQLite:** This script uses DuckDB to query SQLite because DuckDB provides better performance, no file locking issues, and consistent SQL syntax.

- **Data Preview:** The script displays a preview of the data in the execution logs (first few rows). This helps verify the export worked correctly.

- **Use Cases:**
  - **Model Documentation:** Export structure before or after simulation
  - **Model Comparison:** Compare membership structures between model versions
  - **Validation:** Verify model structure matches expectations
  - **Analysis:** Analyze model complexity and relationships
