# [Script Name] – README

## Overview

**Type:** [Pre | Post | Automation]
**Platform:** [PLEXOS | Aurora | Both]
**Version:** 1.0
**Last Updated:** [Date]
**Author:** [Name/Team]

### Purpose

[Brief description of what this script does. 1-2 sentences explaining the business value and use case.]

**Use Cases:**
- [Use case 1]
- [Use case 2]

---

## Script Location

```
[Pre|Post|Automation]/[PLEXOS|Aurora]/[ScriptName]/
├── script_name.py    # Main script
└── README.md         # This file
```

---

## Arguments

### Required Arguments

| Argument | Type | Description | Example |
|----------|------|-------------|---------|
| `--arg1` | str | Description | `value` |

### Optional Arguments

| Argument | Type | Default | Description | Example |
|----------|------|---------|-------------|---------|
| `--verbose` | flag | `False` | Enable verbose logging | (no value needed) |

---

## Environment Variables Used

List only the variables this script actually reads. For the full variable reference, see the [main README](../../README.md#environment-variables).

| Variable | Description |
|----------|-------------|
| `output_path` | Working directory — files written here are uploaded as solution artifacts |
| `simulation_path` | Root path for study files (Read-Only in post tasks) |

> Add or remove rows based on what your script actually uses. Do not list variables your script does not read.

---

## Dependencies

All dependencies are declared in the repository root `requirements.txt`. If your script requires additional packages, add them there.

```
# In root requirements.txt
pandas>=1.3.0
duckdb
```

---

## Example Task Definition

```json
{
  "Name": "[Descriptive name for this task]",
  "TaskType": "[Pre | Post]",
  "Files": [
    {
      "Path": "Project/Study/script_name.py",
      "Version": null
    }
  ],
  "Arguments": "python3 script_name.py --arg1 value",
  "ContinueOnError": true,
  "ExecutionOrder": 1
}
```

---

## Expected Behaviour

### Success

1. Script starts and logs its configuration.
2. [Step 2]
3. [Step 3]
4. Script exits with code `0`.
5. Output written to `{output_path}/[output_filename]`.

### Failure Conditions

| Condition | Exit Code | Recovery |
|-----------|-----------|----------|
| Invalid arguments | 1 | Check argument format |
| Missing environment variable | 1 | Verify execution environment |
| [Other condition] | 1 | [Recovery action] |

---

## Related Scripts

> List scripts that are commonly chained before or after this one.

- **Before this script:** [Script name and link, if any]
- **After this script:** [Script name and link, if any]
