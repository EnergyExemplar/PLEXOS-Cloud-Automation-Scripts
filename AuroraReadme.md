# Aurora Automation Scripts – Guidelines

> For environment setup, file system layout, environment variables, DuckDB usage, script chaining, and troubleshooting, see the [main README](README.md).

## Table of Contents

- [Aurora-Specific Notes](#aurora-specific-notes)
- [Minimal Working Example](README.md#minimal-working-example)
- [Python Script Standards](#python-script-standards)
- [Contributing New Automation Scripts](#contributing-new-automation-scripts)
- [Available Aurora Automation Scripts](#available-aurora-automation-scripts)

---

## Aurora-Specific Notes

Aurora automation scripts follow the same environment, file system, and variable conventions described in the [main README](README.md). There are no Aurora-specific environment variables beyond the [standard platform set](README.md#environment-variables).

Aurora scripts are located under:

```
Pre/Aurora/<ScriptName>/
Post/Aurora/<ScriptName>/
Automation/Aurora/<ScriptName>/
```

---

## Minimal Working Example

See [Minimal Working Example](README.md#minimal-working-example) in the main README — the structure is the same for Aurora and PLEXOS scripts.

---

## Python Script Standards

### Argument Handling
- Use `argparse` for all script-level inputs.
- Define and validate all arguments explicitly.
- Never rely on implicit assumptions about the environment.

### Environment Variables
- Read environment variables at module level so they are visible and auditable.
- Only read variables your script actually needs.
- Never hardcode paths, IDs, or credentials.

### Output
- Write all output files to `output_path`. Files written there are automatically uploaded as solution artifacts.
- Use `print()` for logging — output appears in the task log in Cloud Web.

### Error Handling
- Wrap main logic in a `try/except` block.
- Print a clear error message and return a non-zero exit code on failure.
- Use `ContinueOnError: false` in the task definition if downstream tasks depend on this script succeeding.

### Code Quality
- Keep functions small and focused.
- One script, one job — if you need two jobs, write two scripts and chain them.
- Avoid duplicating logic across scripts; if two scripts share a pattern, they likely belong as two steps in a chain.

---

## Contributing New Automation Scripts

### 1. Choose the Right Location

| Folder | Use When |
|--------|----------|
| `Pre/Aurora/<ScriptName>/` | Script must run before the Aurora engine starts |
| `Post/Aurora/<ScriptName>/` | Script processes results after the engine and ETL complete |
| `Automation/Aurora/<ScriptName>/` | Script can run independently (e.g. local use, standalone DataHub operations) |

**Naming convention:** Folder `ExportResultsToCsv` → File `export_results_to_csv.py`

### 2. Create the Script Folder

```
Post/Aurora/MyScriptName/
├── my_script_name.py     # Main script
└── README.md             # Script documentation (from template)
```

### 3. Write the Script

Follow the [Minimal Working Example](README.md#minimal-working-example) as your starting point. Keep the script focused on a single task.

### 4. Add Dependencies

Add any new Python packages your script needs to the root `requirements.txt`:

```
# requirements.txt
duckdb
pandas>=1.3.0
```

> Do not create a per-script `requirements.txt`. One file is supported per simulation — all dependencies must be consolidated there.

### 5. Write a README

Copy `_capability_readme_template.md` into your script folder as `README.md` and fill in the purpose, arguments, environment variables used, and an example task definition.

### 6. Test Locally

```bash
pip install -r requirements.txt
python Post/Aurora/MyScriptName/my_script_name.py --input-path /test/data
```

---

## Available Aurora Automation Scripts

### Pre-Simulation

| Script | Description | Location |
|--------|-------------|----------|
| *(none yet — [contribute one!](#contributing-new-automation-scripts))* | | |

### Post-Simulation

| Script | Description | Location |
|--------|-------------|----------|
| AuroraToParquet | Converts all tables in an Aurora `.xdb` solution database to compressed Parquet files with an appended `SimulationId` column | [Post/Aurora/AuroraToParquet/](Post/Aurora/AuroraToParquet/) |

### General Automation

| Script | Description | Location |
|--------|-------------|----------|
| *(none yet — [contribute one!](#contributing-new-automation-scripts))* | | |
