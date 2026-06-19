# PLEXOS Automation Scripts – Guidelines

> For environment setup, file system layout, environment variables, DuckDB usage, script chaining, and troubleshooting, see the [main README](README.md).

## Table of Contents

- [PLEXOS-Specific Environment Variables](#plexos-specific-environment-variables)
- [Minimal Working Example](README.md#minimal-working-example)
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

See [Minimal Working Example](README.md#minimal-working-example) in the main README — the structure is the same for PLEXOS and Aurora scripts.

For PLEXOS-specific environment variables available in addition to the standard set, see [PLEXOS-Specific Environment Variables](#plexos-specific-environment-variables).

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

Start from the [Minimal Working Example](README.md#minimal-working-example). Keep it focused on a single task.

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
| DownloadFromDataHub | Downloads one or more files or folders from DataHub to a local directory before the simulation engine starts; supports glob patterns | [Pre/PLEXOS/DownloadFromDataHub/](Pre/PLEXOS/DownloadFromDataHub/) |
| ParquetToCsv | Converts Parquet files to CSV in-place using DuckDB with row-count validation | [Pre/PLEXOS/ParquetToCsv/](Pre/PLEXOS/ParquetToCsv/) |
| BidadderGeneration | Downloads net-load data from DataHub, computes a piecewise-linear markup from normalized net-load curves, applies monthly seasonal weights, and writes the modified bid adder back into the model’s `timeseries.zip`; part of the iterative calibration loop | [Pre/PLEXOS/BidadderGeneration/](Pre/PLEXOS/BidadderGeneration/) |
| CreateSensitivity | Creates scenario-based property sensitivities using a Variable expression pattern; supports numeric mode (scenario-scaled value) and expression mode (Variable + Scenario + Data File tags) and then regenerates `project.xml` | [Pre/PLEXOS/CreateSensitivity/](Pre/PLEXOS/CreateSensitivity/) |
| UpdateHorizon | Updates the simulation horizon (date range, step count, step type) in a PLEXOS model using the PLEXOS SDK, then regenerates project.xml via the Cloud CLI | [Pre/PLEXOS/UpdateHorizon/](Pre/PLEXOS/UpdateHorizon/) |
| EnableReports | Extends an existing Report object in a PLEXOS model with additional reporting properties (e.g. emissions, fuel offtake) using the PLEXOS SDK; property lang ids are resolved automatically from `reference.db`; regenerates `project.xml` via the Cloud CLI after updating the database | [Pre/PLEXOS/EnableReports/](Pre/PLEXOS/EnableReports/) |
| ExtendWeatherYears | Registers sampled weather CSVs in the PLEXOS model as Data File, Variable, and Stochastic objects using the PLEXOS SDK; links variables to generators under a scenario; updates stochastic sample count; exports updated model to `project.xml` (Step 2 of 2) | [Pre/PLEXOS/ExtendWeatherYears/](Pre/PLEXOS/ExtendWeatherYears/) |
| WeatherSample | Samples multi-year climate profiles to generate per-location CSVs with day-of-week alignment for stochastic weather simulations (Step 1 of 2) | [Pre/PLEXOS/WeatherSample/](Pre/PLEXOS/WeatherSample/) |
| ReplaceModelInputFiles | Replaces an existing property input assignment in a PLEXOS model with an alternative DataHub-backed input file using the PLEXOS SDK; supports both name-based and lang-id-based lookups for class, collection, and property resolution; regenerates `project.xml` via the Cloud CLI using `simulation_path` and `study_id` (both required) | [Pre/PLEXOS/ReplaceModelInputFiles/](Pre/PLEXOS/ReplaceModelInputFiles/) |
| IslandScript | Transmission outages island detection pipeline — downloads input files from DataHub, detects network islands caused by branch outages using graph analysis, generates SRD properties for isolated nodes and generators, writes them into the PLEXOS model database, and regenerates `project.xml` | [Pre/PLEXOS/IslandScript/](Pre/PLEXOS/IslandScript/) |

### Post-Simulation

| Script | Description | Location |
|--------|-------------|----------|
| CsvToParquet | Converts all CSV files under a folder to Parquet format in-place using DuckDB with ZSTD compression; validates row counts before deleting source CSVs | [Post/PLEXOS/CsvToParquet/](Post/PLEXOS/CsvToParquet/) |
| CalibrationEvaluation | Post-simulation script for iterative bid adder calibration: queries Region price from solution parquets via DuckDB, compares the average against a configurable threshold, and enqueues the next simulation iteration (up to 3) with escalating bid adder bands if not converged | [Post/PLEXOS/CalibrationEvaluation/](Post/PLEXOS/CalibrationEvaluation/) |
| CleanupFiles | Deletes files or folders matching a glob pattern from a specified path; use after upload to remove temporary data | [Post/PLEXOS/CleanupFiles/](Post/PLEXOS/CleanupFiles/) |
| CreateChangeSet | Clones the cloud study into `output_path/.changeset_staging`, copies the local `project.xml` from `simulation_path` into the staged study using the requested target filename, and pushes the resulting changeset to PLEXOS Cloud | [Post/PLEXOS/CreateChangeSet/](Post/PLEXOS/CreateChangeSet/) |
| TimeSeriesComparison | Compares 2–4 time-series files and writes statistical results, aligned data, and 3-panel plots to the output directory | [Post/PLEXOS/TimeSeriesComparison/](Post/PLEXOS/TimeSeriesComparison/) |
| UploadToDataHub | Uploads files from a local folder to a specific DataHub path with configurable glob pattern and versioning | [Post/PLEXOS/UploadToDataHub/](Post/PLEXOS/UploadToDataHub/) |
| SearchAndUpload | Finds a file by name or glob pattern (recursively, including inside ZIP archives), stages it to `output_path`, converts CSV to Parquet, and optionally uploads to a DataHub folder in one step | [Post/PLEXOS/SearchAndUpload/](Post/PLEXOS/SearchAndUpload/) |
| DatahubConnectorSolParquetUploader | Creates a temporary DataHub connector, uploads all `*.parquet` files for a simulation solution using the directory mapping JSON, and deletes the connector after upload; supports AzureBlob (ConnectionString, Token, SharedKey, ServicePrincipal) and AmazonS3 (AccountCreds, AssumeRole, SharedKey) auth types. Script file: `datahub_connector_solparquet_uploader.py` | [Post/PLEXOS/DatahubConnectorSolParquetUploader/](Post/PLEXOS/DatahubConnectorSolParquetUploader/) |
| DatahubSolParquetUploader | Uploads all `*.parquet` files for a simulation solution to DataHub; reads the local parquet path and model ID from the directory mapping JSON and builds a timestamped remote path | [Post/PLEXOS/DatahubSolParquetUploader/](Post/PLEXOS/DatahubSolParquetUploader/) |
| SolutionDataQuery | Builds a filtered joined solution parquet from model outputs (FullKeyInfo + data + Period) using DuckDB; supports case-insensitive filters with wildcard matching on Collection, Property, Object, and Category; stages result to `output_path` for automatic platform upload | [Post/PLEXOS/SolutionDataQuery/](Post/PLEXOS/SolutionDataQuery/) |
| ExtractDiagnosticsXML | Uploads PLEXOS diagnostics XML files from the simulation directory to a configurable DataHub path with support for phase-specific glob patterns | [Post/PLEXOS/ExtractDiagnosticsXML/](Post/PLEXOS/ExtractDiagnosticsXML/) |
| ZipDiagnostics | Downloads diagnostics XML files from DataHub, compresses them into a single ZIP archive, and re-uploads to a specified remote path | [Post/PLEXOS/ZipDiagnostics/](Post/PLEXOS/ZipDiagnostics/) |
| ConfigureDuckDbViews | Configures DuckDB views for querying PLEXOS solution parquet data; resolves the solution parquet directory from the first ParquetPath entry in the directory mapping JSON and creates one view per subdirectory using a recursive glob pattern | [Post/PLEXOS/ConfigureDuckDbViews/](Post/PLEXOS/ConfigureDuckDbViews/) |
| QueryWriteMemberships | Exports PLEXOS model membership relationships (parent-child object connections) from the SQLite input database to CSV using DuckDB; uses `simulation_path` to locate `reference.db` under the simulation directory and writes results to `output_path` for automatic upload | [Post/PLEXOS/QueryWriteMemberships/](Post/PLEXOS/QueryWriteMemberships/) |
| QueryLmpData | Queries generation-weighted LMP data from the PLEXOS solution database; joins solution parquet views with technology lookup and memberships CSVs, calculates LMPs by zone, and exports CSV reports and an optional hourly fuel chart | [Post/PLEXOS/QueryLmpData/](Post/PLEXOS/QueryLmpData/) |
| WriteReportedProperties | Exports PLEXOS reported property key information (SeriesId, DataFileId, ChildObjectName, category names, PropertyName) to Parquet by querying `fullkeyinfo`, `object`, and `category` views in the pre-configured DuckDB solution database; requires ConfigureDuckDbViews to have run first | [Post/PLEXOS/WriteReportedProperties/](Post/PLEXOS/WriteReportedProperties/) |
| UploadSolutionZipToDatahub | Resolves the model solution path from the first entry in the directory mapping JSON that defines a `Path` field and uploads all matching ZIP files from that solution path to DataHub; remote destination is constructed automatically as `{remote-path}/{execution_id}/{model_id}` | [Post/PLEXOS/UploadSolutionZipToDatahub/](Post/PLEXOS/UploadSolutionZipToDatahub/) |

### Local Automation (Standalone)

For local workflows outside of cloud simulation context, see the **[Automation Scripts Guide](Automation/PLEXOS/)** which includes:

| Script | Description | Location |
|--------|-------------|----------|
| CsvToParquet | Converts CSV files to compressed Parquet format; supports single file or batch directory conversion | [Automation/PLEXOS/CsvToParquet/](Automation/PLEXOS/CsvToParquet/) |
| DownloadFromDataHub | Downloads one or more files from DataHub to a local directory for use in local workflows | [Automation/PLEXOS/DownloadFromDataHub/](Automation/PLEXOS/DownloadFromDataHub/) |
| ParquetToCsv | Converts Parquet files to CSV format; supports single file or batch directory conversion | [Automation/PLEXOS/ParquetToCsv/](Automation/PLEXOS/ParquetToCsv/) |
| TimeSeriesComparison | Compares 2–4 time-series datasets locally with statistics, plots, and optional DataHub upload | [Automation/PLEXOS/TimeSeriesComparison/](Automation/PLEXOS/TimeSeriesComparison/) |
| UploadToDataHub | Uploads local files or directories to a DataHub path with glob pattern filtering and versioning support | [Automation/PLEXOS/UploadToDataHub/](Automation/PLEXOS/UploadToDataHub/) |
| DownloadSolutions | Downloads all solutions for a given execution ID; lists simulations, resolves solution IDs from ModelIdentifiers, and downloads each solution into a per-solution subfolder | [Automation/PLEXOS/DownloadSolutions/](Automation/PLEXOS/DownloadSolutions/) |
| DatahubSharesAndSymlinks | Create, list, and delete Datahub shares and symlinks (same-tenant and cross-tenant) | [Automation/PLEXOS/DatahubSharesAndSymlinks/](Automation/PLEXOS/DatahubSharesAndSymlinks/) |

> **Note:** Automation scripts are self-contained — they do **not** rely on platform environment variables. All configuration is passed as explicit CLI arguments. Some scripts expose importable classes for use by other automation scripts. See the [Automation README](Automation/PLEXOS/) for details.

<!-- docgen:workflows:start -->
## Available Workflows

End-to-end workflow guides showing how scripts chain together for common automation scenarios.

- [Archive PLEXOS Diagnostics XML and Store a Single ZIP in DataHub](Workflows/extract-diagnostics-xml-to-zip-diagnostics.md)
- [Iterative bid adder calibration using net load inputs and price convergence checks](Workflows/bidadder-generation-to-calibration-evaluation.md)
- [Compare time series outputs and publish the analysis to DataHub](Workflows/time-series-comparison-to-upload-to-data-hub.md)
- [Export PLEXOS reported properties to Parquet using DuckDB views](Workflows/configure-duck-db-views-to-write-reported-properties.md)
- [Export PLEXOS reported properties to Parquet, publish to DataHub, and remove staged outputs](Workflows/configure-duck-db-views-to-write-reported-properties-to-upload-to-data-hub-to-cleanup-files.md)
- [Generate generation weighted LMP reports from PLEXOS results and upload them to DataHub](Workflows/configure-duck-db-views-to-query-write-memberships-to-query-lmp-data-to-upload-to-data-hub.md)
- [Post-Simulation Results Conversion, DataHub Upload, and CSV Cleanup](Workflows/csv-to-parquet-to-upload-to-data-hub-to-cleanup-files.md)
- [Convert Aurora solution tables to Parquet and publish them to DataHub](Workflows/aurora-to-parquet-to-upload-to-data-hub.md)
- [Convert PLEXOS CSV outputs, validate against a baseline, and publish results to DataHub](Workflows/csv-to-parquet-to-time-series-comparison-to-upload-to-data-hub.md)
- [Convert PLEXOS CSV outputs to Parquet and publish results to DataHub](Workflows/csv-to-parquet-to-upload-to-data-hub.md)
- [Download DataHub Parquet Inputs and Convert Them to CSV for PLEXOS Preprocessing](Workflows/download-from-data-hub-to-parquet-to-csv.md)
- [Update a PLEXOS model input by downloading a DataHub file and replacing the assigned timeseries](Workflows/download-from-data-hub-to-replace-model-input-files.md)
- [Export PLEXOS Model Memberships and Upload the CSV to DataHub](Workflows/query-write-memberships-to-upload-to-data-hub.md)
- [Stage filtered PLEXOS solution data and upload it to DataHub](Workflows/solution-data-query-to-upload-to-data-hub.md)
- [Post simulation results upload with CSV to Parquet conversion and cleanup](Workflows/search-and-upload-to-cleanup-files.md)
- [Export PLEXOS Model Memberships, Convert to Parquet, Upload to DataHub, and Clean Up Outputs](Workflows/query-write-memberships-to-csv-to-parquet-to-upload-to-data-hub-to-cleanup-files.md)
- [Generate sampled weather year inputs and register them in a PLEXOS model](Workflows/weather-sample-to-extend-weather-years.md)
- [Stage PLEXOS Results, Upload to DataHub, and Clean Up Staged Outputs](Workflows/search-and-upload-to-upload-to-data-hub-to-cleanup-files.md)
- [Compare time series outputs against a baseline, publish the analysis to DataHub, and clean up run artifacts](Workflows/time-series-comparison-to-upload-to-data-hub-to-cleanup-files.md)
- [Upload PLEXOS Solution ZIP Outputs to DataHub and Remove Staged ZIP Files](Workflows/upload-solution-zip-to-datahub-to-cleanup-files.md)
- [Preserve PLEXOS Diagnostics and Publish Post-Simulation Outputs to DataHub](Workflows/extract-diagnostics-xml-to-upload-to-data-hub.md)
- [Generate generation weighted LMP reports and an hourly generation chart from PLEXOS solution parquet](Workflows/configure-duck-db-views-to-query-write-memberships-to-query-lmp-data.md)

<!-- docgen:workflows:end -->