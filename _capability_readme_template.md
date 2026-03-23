# [Script Name] – README

## Overview

**Type:** [Pre | Post | Automation]
**Platform:** [PLEXOS | Aurora | Both]
**Version:** 1.0
**Last Updated:** [Date]
**Author:** [Name/Team]

### Purpose

[Brief description of what this script does. 1-2 sentences explaining the business value and use case.]

This is a **focused script** — it does one thing only. [Pair it with other scripts for a complete workflow.]

### Key Features

- [Feature 1]
- [Feature 2]
- [Feature 3]
- Proper error exit codes for CI/CD integration

### Related Scripts

> Scripts commonly chained with this one.

- **Before this script:** [Script name and link, if any]
- **After this script:** [Script name and link, if any]

---

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `-a, --arg1` | Yes | — | [Description of required argument] |
| `-o, --optional` | No | `value` | [Description of optional argument] |

---

## Environment Variables Used

For the full variable reference, see the [main README](../../README.md#environment-variables).

| Variable | Description |
|---|---|
| `output_path` | Working directory — files written here are uploaded as solution artifacts |
| `simulation_path` | Root path for study files (Read-Only in post tasks) |

> Add or remove rows based on what your script actually uses. Do not list variables your script does not read.

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`.

```
# packages used by this script
```

---

## Chaining This Script

This script is designed to be one step in a larger pipeline.

### Chain 1 — [Description of chain]

```json
[
  {
    "Name": "[Previous task name]",
    "TaskType": "[Pre | Post]",
    "Files": [
      { "Path": "Project/Study/previous_script.py", "Version": null }
    ],
    "Arguments": "python3 previous_script.py --arg value",
    "ContinueOnError": false,
    "ExecutionOrder": 1
  },
  {
    "Name": "[This task name]",
    "TaskType": "[Pre | Post]",
    "Files": [
      { "Path": "Project/Study/script_name.py", "Version": null }
    ],
    "Arguments": "python3 script_name.py --arg1 value",
    "ContinueOnError": true,
    "ExecutionOrder": 2
  }
]
```

---

## Example Commands

```bash
# [Example 1 — basic usage]
python3 script_name.py --arg1 value

# [Example 2 — with optional arguments]
python3 script_name.py --arg1 value --optional-flag
```

---

## Expected Behaviour

### Success

1. Script starts and logs its configuration.
2. [Step 2]
3. [Step 3]
4. Exits with code `0`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|---|---|---|
| Missing required argument | 1 | Check argument format |
| Missing environment variable | 1 | Verify execution environment |
| [Other condition] | 1 | [Recovery action] |
