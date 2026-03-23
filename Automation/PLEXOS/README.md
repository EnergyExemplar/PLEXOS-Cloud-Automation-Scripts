# PLEXOS Local Automation Scripts

Standalone automation utilities for local workflows that interact with PLEXOS Cloud DataHub without requiring a cloud simulation context.

---

## Overview

The `Automation/PLEXOS/` folder contains **standalone scripts** designed to run on your local machine. Unlike Pre/Post/Compute scripts that run in the cloud, these scripts:

- **Do not use environment variables** — all configuration is passed as arguments
- **Require explicit CLI path and environment** — you specify these when running
- **Can import from each other** — reuse functionality by importing classes/functions
- **Work independently** — each script is runnable on its own
- **Are not self-contained** — can share code across Automation scripts (unlike Pre/Post/Compute)

For guidance on when to use a class, see [Creating Custom Automation Scripts](#creating-custom-automation-scripts).

---

## Available Scripts

| Script | Purpose | Can Be Imported |
|--------|---------|-----------------|
| **[DownloadFromDataHub](DownloadFromDataHub/)** | Download files from DataHub to local | ✅ `DataHubDownloader` class |
| **[UploadToDataHub](UploadToDataHub/)** | Upload local files to DataHub | ✅ `DataHubUploader` class |
| **[CsvToParquet](CsvToParquet/)** | Convert CSV to compressed Parquet | ✅ `CsvParquetConverter` class |
| **[ParquetToCsv](ParquetToCsv/)** | Convert Parquet to CSV | ✅ `ParquetCsvConverter` class |
| **[TimeSeriesComparison](TimeSeriesComparison/)** | Compare 2-4 time series datasets | ✅ Imports other scripts |

---

## Creating Custom Automation Scripts

### 1. Choose Your Structure

A class is **not required** for simple scripts — put logic directly in `main()` if that's clearer. Use a class when the script is complex, has shared state, or needs to be imported by another automation script.

The example below uses a class, which is a good default for automation scripts since they can be imported by others:

```python
# my_script/my_script.py

class MyProcessor:
    """Reusable processor — importable by other automation scripts."""
    
    @staticmethod
    def process_data(input_path):
        # Your logic here
        return result

def main():
    # CLI argument parsing
    parser = argparse.ArgumentParser(...)
    args = parser.parse_args()
    
    # Use your class
    result = MyProcessor.process_data(args.input)
    
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
```

### 2. Import From Other Automation Scripts

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import any automation script
from DownloadFromDataHub.download_from_datahub import DataHubDownloader
from CsvToParquet.csv_to_parquet import CsvParquetConverter
```

### 3. Follow the Structure

```
Automation/PLEXOS/MyNewScript/
├── my_new_script.py    # Runnable + importable
└── README.md           # Documentation with "Related Scripts" section
```

### 4. Document in README

Include a "Related Scripts" section showing:
- How to import your script's classes
- Which scripts to use before/after yours
- Which scripts import your functionality

---

## Key Differences: Pre/Post/Compute vs Automation

| Aspect | Pre/Post/Compute Scripts | Automation Scripts |
|--------|-------------------------|-------------------|
| **Execution Context** | Cloud simulation | Local machine |
| **Environment Variables** | ✅ Use platform-injected | ❌ None (explicit args) |
| **Imports From Other Scripts** | ❌ **Must be self-contained** | ✅ **Can import** from other Automation scripts |
| **Authentication** | Automatic | Manual (via args) |
| **Output Path** | `/output` (auto-upload) | User-specified |
| **CLI Path** | Pre-configured | Passed as `-c` argument |

**IMPORTANT:** Pre/Post/Compute scripts must be self-contained with no imports. Automation scripts CAN import from each other.

---

## Prerequisites

- Python 3.11+
- PLEXOS Cloud CLI installed
- Valid environment credentials
- Dependencies: `pip install -r requirements.txt`

---

## Support

For issues or questions:
1. Check the script-specific README in each folder
2. Review the main [README](../../README.md)
3. Consult the [PLEXOS guide](../../PLEXOSReadme.md)
4. See [CODE-OF-CONDUCT.md](../../CODE-OF-CONDUCT.md) for contribution guidelines
