# Workflow: Export PLEXOS reported properties to Parquet using DuckDB views

## Usecase
You have a PLEXOS simulation that has already produced solution Parquet outputs, and you want a repeatable way to extract “reported property key” metadata into a single, analysis-ready Parquet file. You also want the extraction to be robust across many solution subfolders and schema variations, without manually writing SQL against dozens of Parquet files.

This workflow configures DuckDB views over the solution Parquet directory and then exports a flattened reported-properties table to `{output_path}` for automatic platform upload.

## Problem
Without automation, you typically have to:
- Find the correct solution Parquet directory (often via a directory mapping file).
- Manually point DuckDB (or another tool) at many Parquet subfolders and handle schema drift.
- Write and maintain SQL joins across solution tables to produce a usable “reported properties” extract.

This is slow to repeat across runs, easy to mis-point at the wrong folder, and error-prone when the solution output structure changes.

## Data Flow Diagram
```mermaid
graph LR
  A["ConfigureDuckDbViews"] -->|DuckDB views| B["WriteReportedProperties"]
  B -->|Parquet export| C["Platform output upload"]
```

## Scripts Involved

| Order | Script | Phase | Purpose | Key Arguments |
|---:|---|---|---|---|
| 1 | [ConfigureDuckDbViews](../Post/PLEXOS/ConfigureDuckDbViews/README.md) | Post | Create DuckDB views over solution Parquet subdirectories based on the directory mapping JSON | `--verbose` |
| 2 | [WriteReportedProperties](../Post/PLEXOS/WriteReportedProperties/README.md) | Post | Query DuckDB views and export flattened reported property key info to a Parquet file in `{output_path}` | `--output-file` |

## Complete Task Definition
```json
[
  {
    "Name": "Configure DuckDB views for solution Parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/ConfigureDuckDbViews/configure_duck_db_views.py",
        "Version": null
      }
    ],
    "Arguments": "python3 configure_duck_db_views.py --verbose",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Export reported properties to Parquet",
    "TaskType": "Post",
    "Files": [
      {
        "Path": "Post/PLEXOS/WriteReportedProperties/write_reported_properties.py",
        "Version": null
      }
    ],
    "Arguments": "python3 write_reported_properties.py --output-file reported_properties.parquet",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

## Step-by-Step Walkthrough

### 1) ConfigureDuckDbViews
**What it does**  
This step reads a directory mapping JSON (from `directory_map_path` if set; otherwise it falls back to `{simulation_path}/splits/directorymapping.json`). It finds the first mapping entry containing `ParquetPath`, walks subdirectories under that Parquet path, and creates `CREATE OR REPLACE VIEW` statements in the DuckDB database at `duck_db_path`.

**Inputs**
- `duck_db_path` (required): DuckDB file path where views will be created.
- `directory_map_path` (optional): mapping JSON path; if not set, the script uses `{simulation_path}/splits/directorymapping.json`.

**Outputs**
- A DuckDB database file at `duck_db_path` containing views for solution subdirectories (one view per subdirectory).

**Environment variables needed**
- `duck_db_path` (required)
- `directory_map_path` (optional)

**Failure behavior**
- Exits with code `1` if `duck_db_path` is missing, the mapping file can’t be found/read, no `ParquetPath` exists in the mapping, or DuckDB view creation fails. Because `ContinueOnError` is `false`, the workflow stops here on failure.

---

### 2) WriteReportedProperties
**What it does**  
This step connects to the DuckDB database at `duck_db_path` and queries the pre-configured views (`fullkeyinfo`, `object`, `category`). It writes a flattened Parquet file of reported-property key info (enriched with child and parent object category names) into `{output_path}`.

**Inputs**
- `duck_db_path` (required): must point to the same DuckDB file created/updated in Step 1.
- `{output_path}` (optional env var `output_path`, default `/output`): destination folder for the Parquet export.
- `--output-file` (optional): output filename only (no path separators, no absolute paths).

**Outputs**
- `{output_path}/reported_properties.parquet` (or `{output_path}/flattened_data.parquet` if `--output-file` is not provided)

**Environment variables needed**
- `duck_db_path` (required)
- `output_path` (optional; defaults to `/output`)

**Failure behavior**
- Exits with code `1` if `duck_db_path` is missing, required views are not present in the database, the DuckDB query fails, the output directory can’t be created, or `--output-file` is invalid. With `ContinueOnError` set to `false`, the workflow stops on failure.

## Data Flow Between Steps
- **Step 1 writes:** a DuckDB database file at `duck_db_path`. This file contains the views that point at the solution Parquet directory resolved from the directory mapping JSON.
- **Step 2 reads:** the same DuckDB database at `duck_db_path` and expects the `fullkeyinfo`, `object`, and `category` views to exist.
- **Step 2 writes:** a single Parquet file into `{output_path}`:
  - Default naming: `flattened_data.parquet`
  - Custom naming: whatever you pass via `--output-file` (must be a plain filename, e.g., `reported_properties.parquet`)

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| ConfigureDuckDbViews exits non-zero immediately | `duck_db_path` environment variable is not set | Set `duck_db_path` for the run so the script can create/update the DuckDB file |
| ConfigureDuckDbViews fails with mapping not found | `directory_map_path` not set and `{simulation_path}/splits/directorymapping.json` does not exist | Provide `directory_map_path` pointing to the mapping JSON, or ensure the fallback mapping file exists |
| ConfigureDuckDbViews fails with “no entry has ParquetPath” | The mapping JSON is empty or does not contain a `ParquetPath` field in any entry | Fix the mapping JSON so at least one entry includes `ParquetPath` |
| WriteReportedProperties fails with missing views | Step 1 did not run successfully, or `duck_db_path` points to a different DuckDB file than Step 1 used | Ensure Step 1 completes successfully and both steps use the same `duck_db_path` |
| WriteReportedProperties fails with invalid output filename | `--output-file` contains `/`, `\`, `..`, or is an absolute path | Use a plain filename only, e.g., `reported_properties.parquet`, and rely on `{output_path}` for the directory |
| WriteReportedProperties fails creating output directory | `output_path` points to a location that cannot be created/written | Set `output_path` to a writable location provided by the platform, and verify permissions |