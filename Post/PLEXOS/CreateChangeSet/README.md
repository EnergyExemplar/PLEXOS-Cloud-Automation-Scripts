# Create ChangeSet - README

## Overview

**Type:** Post
**Platform:** PLEXOS
**Version:** 1.0
**Last Updated:** April 2026
**Author:** Energy Exemplar

### Purpose

Clones the target cloud study into a staging folder under the output directory, copies the local `project.xml` from the simulation directory into that staging clone, and pushes the resulting changeset back to PLEXOS Cloud.

This is a **focused script**. It only prepares and pushes a changeset for an already-known study. Pair it with any earlier task that modifies `project.xml` before this step runs.

### Key Features

- Fails fast if required platform environment variables are missing
- Recreates the staging folder at `output_path/.changeset_staging` on each run to avoid stale files
- Supports writing the local `project.xml` into a different target XML filename inside the staging clone
- URL-decodes supported CLI argument values so `%20` can be used for spaces when required by a task runner
- Revalidates decoded `--target-file` values so encoded paths such as `%2F` are rejected as standard CLI argument errors
- Accepts optional `--retries` and `--retry-interval` arguments, defaulting to `3` and `30` when omitted
- Skips the push when no file changes are detected
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** Any earlier task that modifies the local `project.xml`

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--message` | Yes | — | Commit message used when pushing the new study changeset; URL-encoded spaces such as `%20` are decoded automatically |
| `--retries` | No | `3` | Optional CLI argument for the number of push retry attempts; defaults to `3` when omitted |
| `--retry-interval` | No | `30` | Optional CLI argument for seconds to wait between retry attempts; defaults to `30` when omitted |
| `--target-file` | No | `project.xml` | Target XML filename written inside the staging clone; must be a simple filename ending in `.xml`; decoded values are revalidated so encoded path separators such as `%2F` are rejected |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `cloud_cli_path` | Path to the PLEXOS Cloud CLI executable used by `CloudSDK` |
| `simulation_path` | Simulation working directory that contains the local `project.xml` source file |
| `output_path` | Writable output directory that receives the `.changeset_staging` clone |
| `study_id` | Cloud study ID to clone and push |

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
eecloud
```

---

## Example Task Chain

```json
[
  {
    "Name": "Push updated study changeset",
    "TaskType": "Post",
    "Files": [
      { "Path": "Project/Study/create_changeset.py", "Version": null }
    ],
    "Arguments": "python3 create_changeset.py --message 'Push%20updated%20gas%20price%20input%20changeset'",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  }
]
```

---

## Example Commands

```bash
# Push local project.xml as project.xml in the staging clone
python3 create_changeset.py --message 'Update study inputs'

# Retry up to 5 times with a 10 second wait between attempts
python3 create_changeset.py --message 'Retry%20push%20example' --retries 5 --retry-interval 10

# Copy local project.xml into a different target filename inside staging before push
python3 create_changeset.py --message 'Push%20alternate%20XML%20target' --target-file testcommit1.xml

```

---

## Expected Behaviour

### Success

1. Reads `cloud_cli_path`, `simulation_path`, `output_path`, and `study_id` from the environment.
2. Connects to PLEXOS Cloud and removes any existing `output_path/.changeset_staging` folder.
3. Reclones the specified study into a clean staging directory.
4. Compares the local `project.xml` in `simulation_path` against the target XML file in staging.
5. Copies the file into staging only when the content differs or the target file is missing.
6. Pushes the staged changeset with the supplied commit message when staged content changed.
7. If no staged changes are detected, logs that nothing needs to be pushed and exits with code `0`.
8. Exits with code `0` on success.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| `cloud_cli_path` env var missing | 1 | Ensure the execution environment provides the Cloud CLI path |
| `simulation_path` env var missing | 1 | Ensure the simulation working directory is injected by the platform |
| `output_path` env var missing | 1 | Ensure the writable output directory is injected by the platform |
| `study_id` env var missing | 1 | Ensure the task is running in a study context with `study_id` available |
| `--target-file` is not a simple `.xml` filename, including after URL decoding | 2 | Pass a filename such as `project.xml` or `testcommit1.xml`; do not include directory separators directly or via encoded values such as `%2F` |
| Study clone fails | 1 | Verify `study_id` and inspect the task log for the SDK message |
| Push fails after all retries | 1 | Check the final SDK error message and rerun with a valid study state |
