# DuckDB — Solution Queries

## What It Is

DuckDB is a high-performance local analytical database used to query PLEXOS solution data after a simulation completes. It reads Parquet, SQLite, and CSV files directly using standard SQL, so you can run queries against solution outputs without moving data into another system or loading everything into memory.

In this repository, DuckDB is the standard tool for inspecting post-simulation results. The platform provides a pre-configured DuckDB database file via the `{duck_db_path}` environment variable, and post-simulation scripts connect to it to query views over solution data.

Key scripts that rely on DuckDB include [Configure Duck Db Views](../Post/PLEXOS/ConfigureDuckDbViews/README.md), [Query Write Memberships](../Post/PLEXOS/QueryWriteMemberships/README.md), [Query Lmp Data](../Post/PLEXOS/QueryLmpData/README.md), [Solution Data Query](../Post/PLEXOS/SolutionDataQuery/README.md), and [Write Reported Properties](../Post/PLEXOS/WriteReportedProperties/README.md).

## How Scripts Use It

Scripts use DuckDB to read solution artifacts that are already available on the simulation file system under `{simulation_path}`. The `{duck_db_path}` environment variable points to a pre-configured database file, and post-simulation scripts connect to it to query views over solution data.

A common pattern is to configure views early in the post-simulation chain, then run one or more query scripts that export results to `{output_path}`. For example:

1. [Configure Duck Db Views](../Post/PLEXOS/ConfigureDuckDbViews/README.md) reads the directory mapping JSON (`{directory_map_path}`) to find the solution Parquet directory, walks all subdirectories, and creates a `CREATE OR REPLACE VIEW` for each one in the DuckDB file — pointing at all `*.parquet` files in that subtree with `union_by_name=true` to handle schema variation.
2. [Query Write Memberships](../Post/PLEXOS/QueryWriteMemberships/README.md) then queries the PLEXOS `reference.db` (SQLite) using DuckDB to export parent-child membership relationships to CSV in `{output_path}`.
3. [Query Lmp Data](../Post/PLEXOS/QueryLmpData/README.md) joins the configured views to extract generation-weighted LMP reports.
4. [Solution Data Query](../Post/PLEXOS/SolutionDataQuery/README.md) joins FullKeyInfo + data + Period parquet files with case-insensitive wildcard filters, producing a single compressed output Parquet in `{output_path}`.

## Key Patterns

Use the platform-provided DuckDB database path from the environment:

```python
import os

duck_db_path = os.environ.get('duck_db_path')
output_path  = os.environ.get('output_path', '{output_path}')
```

Query solution data and write results to `{output_path}`:

```python
import duckdb

with duckdb.connect(duck_db_path) as con:
    con.execute(f"COPY (SELECT * FROM membershipinfo) TO '{output_path}/memberships.csv' WITH (HEADER, DELIMITER ',')")
```

Set up views before any query scripts run — this should be an early post-simulation task:

```bash
plexos-cloud solution query configure-views --name 'YOUR MODEL NAME'
```

Or use the [Configure Duck Db Views](../Post/PLEXOS/ConfigureDuckDbViews/README.md) script, which resolves the Parquet directory from `{directory_map_path}` automatically:

```json
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
```

For ephemeral or in-memory queries (e.g. format conversions that do not need the solution database), use `duckdb.connect()` with no path argument:

```python
with duckdb.connect() as con:
    con.execute("COPY (SELECT * FROM read_parquet('input.parquet')) TO 'output.csv' WITH (HEADER, DELIMITER ',')")
```

Always close connections — prefer `with` blocks to ensure cleanup.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `duck_db_path` | Path to the pre-configured DuckDB database file shared by all post-simulation scripts |
| `directory_map_path` | Path to directory mapping JSON containing model `Name`, `Id`, and `ParquetPath`. Falls back to `{simulation_path}/splits/directorymapping.json` for distributed runs |
| `output_path` | Working directory where query results are written — files here are auto-uploaded as solution artifacts |
| `simulation_path` | Root path for study files, including solution Parquet data under `{simulation_path}/splits/` |

## Common Pitfalls

- **Querying before views are configured.** The source material explicitly says to run view setup as an early post-simulation task (low `ExecutionOrder`) before any scripts that read results. Without views, queries against solution tables will fail.

- **Assuming DuckDB is a remote service.** In this repository it is a local file-based database accessed through the `{duck_db_path}` environment variable. No server, no network — it reads Parquet files directly from disk.

- **Writing query output outside `{output_path}`.** Files written elsewhere are not automatically captured as solution artifacts. Always write to `{output_path}`.

- **Forgetting that the solution data is already in Parquet under `{simulation_path}`.** You do not need to manually stage it into another database first. DuckDB reads Parquet files natively.

- **Not closing DuckDB connections.** Always use `with duckdb.connect(...)` blocks. Leaving connections open can lock the database file and cause subsequent scripts in the chain to fail.
