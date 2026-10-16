# Selecting the Python version for pre- and post-simulation tasks

Pre- and post-simulation tasks run in a container designed to provide **two Python interpreters installed side by side**. This document covers how to choose between them and what it means for existing runs. This guidance takes effect once the Simulations API change is deployed to your environment — confirm `python3 --version` and `python3.12 --version` on your deployed environment before relying on it.

## Summary

Both Python 3.10 and Python 3.12 are valid for pre/post execution. The requirement is not that every run uses one fixed version, but that the **correct interpreter is selected explicitly for the script being executed**.

- For existing scripts that remain validated on Python 3.10, use `python3`.
- For scripts that have been updated for Python 3.12, use `python3.12`.

| Command | Version | Use it when |
|---|---|---|
| `python3` | 3.10.12 | The default. The script is compatible with 3.10. |
| `python3.12` | 3.12.13 | The script has been updated for the new runtime, or the workflow specifically requires Python 3.12 compatibility. |



## 1. Python 3.10 usage

Use Python 3.10 when the pre/post script remains compatible with that runtime and has not yet been updated for Python 3.12. This is the existing default, so nothing needs to change.

```bash
python3 Pre/PLEXOS/SomeScript/some_script.py
python3 Post/PLEXOS/SomeScript/some_script.py
```

Examples:

```bash
python3 Post/PLEXOS/ConfigureDuckDbViews/configure_duck_db_views.py
python3 Post/PLEXOS/DatahubSolParquetUploader/datahub_solparquet_uploader.py -r BaseModel
```

## 2. Python 3.12 usage

Use Python 3.12 when the pre/post script has been updated for the new runtime, or the workflow specifically requires Python 3.12 compatibility.

```bash
python3.12 Pre/PLEXOS/SomeScript/some_script.py
python3.12 Post/PLEXOS/SomeScript/some_script.py
```

Examples:

```bash
python3.12 Post/PLEXOS/ConfigureDuckDbViews/configure_duck_db_views.py --verbose
python3.12 -m pytest tests/post_test_configure_duck_db_views.py
```

## 3. Key rule for all pre/post runs

Both versions are valid; the correct command depends on the script's compatibility and validation status.

- If the script is validated on Python 3.10, run it with `python3`.
- If the script is validated on Python 3.12, run it with `python3.12`.
- **Do not rely on the default `python` command** when multiple Python versions are installed. Which interpreter it resolves to is not guaranteed.
- Always specify the interpreter explicitly to avoid version mismatch and runtime instability. A mismatch surfaces as a confusing import or syntax error partway through the script rather than as a clear failure up front.

Check the active versions:

```bash
python3 --version
python3.12 --version
```

## 4. The interpreter is set per task

The interpreter is part of the task's `Arguments`, so it is chosen for each task individually. Two tasks in the same simulation can use different versions.

```json
[
  {
    "Name": "Prepare input data",
    "TaskType": "Pre",
    "Files": [
      { "Path": "Team/User/prepare_inputs.py", "Version": null },
      { "Path": "Team/User/requirements.txt", "Version": null }
    ],
    "Arguments": "python3 prepare_inputs.py",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "Query Parquet solution data",
    "TaskType": "Post",
    "Files": [
      { "Path": "Team/User/**", "Version": null }
    ],
    "Arguments": "python3.12 query_lmp_data.py",
    "ContinueOnError": false,
    "ExecutionOrder": 2
  }
]
```

## 5. Matching pip to the interpreter

Each interpreter has its own pip and its own site-packages. Using the wrong one is the most common way to end up with a package that is installed in the image but missing at import time.

| Command | Installs into |
|---|---|
| `pip`, `pip3`, `pip3.10` | Python 3.10 |
| `pip3.12`, `python3.12 -m pip` | Python 3.12 |

Both interpreters come with `pip`, `wheel`, `setuptools` and `duckdb` already available.

## 6. How requirements.txt is handled

Only one `requirements.txt` is supported per simulation. It is installed into **both** interpreters when the per-simulation image is built, but the two installs are not treated the same way.

| Interpreter | Install | If it fails |
|---|---|---|
| Python 3.10 | Required | The container build fails and the simulation does not run. |
| Python 3.12 | Best effort | A warning is logged in the build output and the simulation continues. Packages may be missing when a `python3.12` task imports them. |

The Python 3.12 install is deliberately best-effort so that a package with no 3.12 support cannot break simulations that only use 3.10.

## 7. Confirming the version at run time

To see which interpreter a task actually used, print it from the script. This is the fastest way to diagnose a package that imports locally but not in the cloud.

```python
import platform
import sys

print(f"python_version: {platform.python_version()}")
print(f"executable: {sys.executable}")
```

Or add a throwaway task that logs both interpreters before anything else runs:

```json
{
  "Name": "Log available Python versions",
  "TaskType": "Pre",
  "Arguments": "bash -c 'python3 --version; python3.12 --version'",
  "ContinueOnError": true,
  "ExecutionOrder": 0
}
```

## 8. Impact on existing runs

- `python3` still resolves to Python 3.10 — **no existing task definition needs to change**.
- Scripts in the public PLEXOS Cloud Automation Scripts repository that already call `python3` continue to work unchanged. A small number of examples still use bare `python`; those should be migrated to `python3` (or `python3.12`, if already validated on that runtime) since the bare `python` alias is not guaranteed to resolve consistently.
- Moving a script to `python3.12` is opt-in, one task at a time, and should follow validation on that runtime rather than being applied across the board.

## 9. Recommended practice

- Use `python3` for existing pre/post scripts still running on Python 3.10.
- Use `python3.12` for pre/post scripts that have been updated for Python 3.12.
- Call the interpreter explicitly in every pre/post command instead of relying on the environment default.
- Keep the command aligned with the version the script has been validated against.
- Add environment markers for any dependency that cannot install under 3.10.

