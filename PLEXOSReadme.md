# PLEXOS Automation Scripts – Guidelines

> For environment setup, file system layout, environment variables, DuckDB usage, and script chaining, see the [main README](README.md).

## Table of Contents

- [PLEXOS-Specific Environment Variables](#plexos-specific-environment-variables)
- [Minimal Working Example](#minimal-working-example)
- [Contributing New Automation Scripts](#contributing-new-automation-scripts)
- [Available PLEXOS Automation Scripts](#available-plexos-automation-scripts)

---

## PLEXOS-Specific Environment Variables

In addition to the [platform environment variables](README.md#environment-variables), PLEXOS tasks also receive:

| Variable | Description | Why It Exists |
|----------|-------------|---------------|
| `sqlite_input_path` | Path to the PLEXOS SQLite project file | Query or modify the input database directly without knowing its location |
| `xml_input_path` | Path to the XML file PLEXOS will use as input | Read or patch the XML input before the engine starts |

---

## Minimal Working Example

The simplest correct structure for a PLEXOS automation script. Only include the environment variables your script actually uses.

```python
import argparse
import os


# Platform-provided — injected automatically. Do not set these manually.
simulation_path = os.environ.get('simulation_path', '/simulation')
output_path     = os.environ.get('output_path', '/output')


def main() -> int:
    parser = argparse.ArgumentParser(description='Brief description of what this script does')
    parser.add_argument('--input-path', required=True, help='DataHub path to the input file')
    args = parser.parse_args()

    try:
        print(f"Starting script. Input: {args.input_path}, Output: {output_path}")

        # Your logic here

        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
```

**Key points:**
- Environment variables are read from `os.environ` — provided by the platform, not hardcoded.
- Script inputs use `argparse` — kept separate from environment variables.
- No shared imports — fully self-contained.
- Explicit exit code so the task runner detects success or failure.

For coding standards and security requirements, see [CODE-OF-CONDUCT.md](CODE-OF-CONDUCT.md).

---

## Contributing New Automation Scripts

### 1. Choose the right folder

| Folder | Use When |
|--------|----------|
| `Pre/PLEXOS/<ScriptName>/` | Must run before the PLEXOS engine starts |
| `Post/PLEXOS/<ScriptName>/` | Processes results after the engine and ETL complete |
| `Automation/PLEXOS/<ScriptName>/` | Runs independently (local use, standalone DataHub operations) |

**Naming convention:** Folder `ParquetToCsvConversion` → file `parquet_to_csv_conversion.py`

### 2. Create the folder structure

```
Pre/PLEXOS/MyScriptName/
├── my_script_name.py     # Main script
└── README.md             # From _capability_readme_template.md
```

### 3. Write the script

Start from the [Minimal Working Example](#minimal-working-example). Keep it focused on a single task.

### 4. Add dependencies

Add packages to the root `requirements.txt` — do not create a per-script file.

### 5. Write the README

Copy `_capability_readme_template.md` into your script folder and fill in purpose, arguments, environment variables used, and an example task definition.

### 6. Test locally

Set up your local environment to match cloud execution:

```bash
# Install dependencies
pip install -r requirements.txt

# Install SDK wheel files from your CLI installation
pip install <cli-path>/eecloud-*.whl
pip install <cli-path>/plexos-*.whl

# Run your script with test data
python Pre/PLEXOS/MyScriptName/my_script_name.py --input-path /test/data
```

### 7. Write unit tests (recommended)

Add tests to validate your script's core logic:

```python
# Pre/PLEXOS/MyScriptName/test_my_script_name.py
import unittest
from my_script_name import process_data

class TestMyScript(unittest.TestCase):
    def test_valid_input(self):
        result = process_data("test_input.csv")
        self.assertIsNotNone(result)
    
    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            process_data("invalid.csv")

if __name__ == '__main__':
    unittest.main()
```

Run tests before submission:
```bash
python -m pytest Pre/PLEXOS/MyScriptName/test_my_script_name.py
```

---

## Available PLEXOS Automation Scripts

### Pre-Simulation

| Script | Description | Location |
|--------|-------------|----------|
| ParquetToCsv | Converts Parquet files to CSV in-place using DuckDB with row-count validation | [Pre/PLEXOS/ParquetToCsv/](Pre/PLEXOS/ParquetToCsv/) |

### Post-Simulation

| Script | Description | Location |
|--------|-------------|----------|
| UploadToDataHub | Uploads files from a local folder to a specific DataHub path with configurable glob pattern and versioning | [Post/PLEXOS/UploadToDataHub/](Post/PLEXOS/UploadToDataHub/) |

### Local Automation (Standalone)

For local workflows outside of cloud simulation context, see the **[Automation Scripts Guide](Automation/PLEXOS/)** which includes:

| Script | Description | Location |
|--------|-------------|----------|
| UploadToDataHub | Upload local files or directories to DataHub | [Automation/PLEXOS/UploadToDataHub/](Automation/PLEXOS/UploadToDataHub/) |
| CsvToParquet | Convert CSV files to compressed Parquet format | [Automation/PLEXOS/CsvToParquet/](Automation/PLEXOS/CsvToParquet/) |

> **Note:** Automation scripts use **shared utilities** (reusable functions) and do **not** rely on environment variables. All configuration is passed as explicit arguments. See the [Automation README](Automation/PLEXOS/) for details.
