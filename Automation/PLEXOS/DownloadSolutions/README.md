# Download Solutions – README

## Overview

**Type:** Automation (Local)
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** March 2026

### Purpose

Downloads all solutions for a given execution ID to a local directory. For each simulation in the execution that has `ModelIdentifiers`, the script resolves the solution IDs and calls the solution download API. Each solution is saved in its own subfolder named by its solution ID. Simulations without `ModelIdentifiers` (typically incomplete) are skipped with a warning.

This is a **focused script** — it downloads solutions only. Pair it with `DownloadFromDataHub` or `UploadToDataHub` for broader local workflows.

### Key Features

- Lists all simulations for an execution ID automatically
- Extracts solution IDs from `ModelIdentifiers` (no manual ID lookup needed)
- Downloads each solution to a per-solution subfolder under the output directory
- Supports configurable solution type (`Raw`, `Standard`, etc.)
- Proper error exit codes for CI/CD integration

### Related Scripts

- **After this script:** [UploadToDataHub](../UploadToDataHub/) — upload downloaded solution files back to DataHub

---

## Arguments

### Required Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `-c, --cli-path` | str | Full path to PLEXOS Cloud CLI executable | `-c /usr/local/bin/plexos-cloud` |
| `-e, --environment` | str | Cloud environment name | `-e <your-environment>` |
| `-x, --execution-id` | str | Execution ID to download all solutions for | `-x <execution-id>` |
| `-o, --output-dir` | str | Local root directory for downloaded solutions | `-o ./solutions` |

### Optional Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `-t, --solution-type` | str | `Raw` | Solution type to download (`Raw`, `Standard`, etc.) |
| `--client-id` | str | `None` | Client ID for client-credentials login. If all three client-credentials args are supplied, SSO is skipped. |
| `--client-secret` | str | `None` | Client secret for client-credentials login. |
| `--tenant-id` | str | `None` | Tenant ID for client-credentials login. |

---

## Environment Variables Used

**None.** This script does not rely on environment variables. All configuration is passed as CLI arguments.

---

## Dependencies

See root `requirements.txt`. This script uses:
- `eecloud` SDK (Python SDK for PLEXOS Cloud)

---

## Example Usage

### Download all solutions (Raw type)

```bash
python download_solutions.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -x <execution-id> \
  -o ./solutions
```

### Download Standard solutions

```bash
python download_solutions.py \
  -c /usr/local/bin/plexos-cloud \
  -e <your-environment> \
  -x <execution-id> \
  -o ./solutions \
  --solution-type Standard
```

---

## Expected Behaviour

### Success

1. Authenticates with the specified environment.
2. Lists all simulations for the given execution ID (`list_simulations`).
3. For each simulation, extracts solution IDs from `ModelIdentifiers`.
4. Downloads each solution to `<output-dir>/<solution-id>/`.
5. Prints a summary and exits with code `0`.

### Output Structure

```
<output-dir>/
  <solution-id-1>/      # files for model 1
  <solution-id-2>/      # files for model 2
  ...
```

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| No simulations found for execution ID | 1 | Verify the execution ID and ensure simulations have run |
| No ModelIdentifiers on any simulation | 1 | Ensure simulations completed successfully before downloading |
| Solution download API failure | 1 | Check solution ID validity and environment connectivity |
| Authentication failure | 1 | Verify CLI path and environment name |
| Missing required argument | 1 | Check argument format |
