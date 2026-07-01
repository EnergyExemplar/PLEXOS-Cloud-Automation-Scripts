# ERAA MVP Importer – README

## Overview

**Type:** Automation  
**Platform:** PLEXOS  
**Version:** 1.0  
**Last Updated:** 2026-06-23  
**Author:** Energy Exemplar  

### Purpose

The ERAA MVP Importer automates the ingestion and transformation of ENTSO-E's European Resource Adequacy Assessment (ERAA) 2025 dataset into PLEXOS format. It processes raw ERAA data files using Flow-Based Market Coupling (FBMC) rules and generates PLEXOS-compatible simulation scenarios for adequacy analysis and market coupling studies.

This is a **specialized Automation script** — it combines Jupyter notebook-based data processing with Python utilities to bridge ENTSO-E ERAA datasets and PLEXOS. Designed as a standalone data import workflow.

### Key Features

- **ENTSO-E ERAA Dataset Integration** — Ingests publicly available ERAA 2025 modelling data from ENTSO-E
- **FBMC Processing** — Applies Flow-Based Market Coupling rules using configurable mapping files
- **Data Transformation** — Converts ERAA data structures to PLEXOS study format
- **Mapping Support** — Flexible Excel-based mapping for:
  - Generator technology-to-fuel classification
  - FBMC zone definitions and interconnections
  - Bidding zone configuration
  - Hydro pattern templates
  - PECD (Projected Capability Evaluation Days) technology mapping
- **Scenario Definition** — JSON-based scenario configurations for automated enqueuing
- **Jupyter Notebook Interface** — Interactive data exploration and validation
- **Dependency Management** — All required packages declared in `requirements.txt`

### Related Scripts

No Pre/Post scripts directly depend on this automation. Use outputs as inputs to PLEXOS simulation workflows.

---

## Data Structure

### Required Input Files

**Source:** Download from ENTSO-E website  
https://www.entsoe.eu/eraa/2025/modelling-data/#Input%20Data

**Folder Layout:**  
See `ERAA_Dataset_Folder_Structure.pdf` for the complete expected directory structure of the downloaded ERAA dataset.

**PLEXOS Seed Database:**  
`Database/ERAA_MVP_Github.xml` is the **required seed PLEXOS database**. The notebook loads it via `PlexosDB.from_xml()`, populates it with ERAA data (regions, nodes, fuels, generators, interconnections), and saves it back in-place. **Back up this file before running the notebook** — it is modified destructively.

### Supporting Files in This Directory

| File | Purpose |
|---|---|
| `Bidding_Zone_List.xlsx` | Bidding zone identifiers and properties |
| `FBMC_Mapping_CORE.xlsx` | Core FBMC zone-to-zone interconnection rules |
| `FBMC_Mapping.xlsx` | Extended FBMC mapping configuration |
| `Generator_Technology_Fuel_Mapping.xlsx` | Technology-to-fuel classification lookup |
| `Hydro_Patterns.xlsx` | Hydro power pattern templates and seasonal factors |
| `PECD_Technology_Mapping.xlsx` | PECD technology definitions |
| `ERAA_Dataset_Folder_Structure.pdf` | Visual reference for ERAA dataset folder structure |
| `Read Me Dataset.txt` | Quick reference for ERAA data source |

---

## Arguments

Not applicable — this automation is Jupyter notebook-based. Configuration is inline within the notebook (`ERAA_MVP_FBMC_12R03.ipynb`).

For batch/CLI integration, modify the notebook's cell variables directly or convert to Python scripts as needed.

---

## Environment Variables Used

| Variable | Description |
|---|---|
| `PLEXOS_API_KEY` | API authentication for PLEXOS Cloud SDK (if uploading results) |
| `PLEXOS_TENANT_ID` | Tenant identifier for PLEXOS Cloud (if using cloud integration) |

> Note: This automation is primarily local/offline. Environment variables are optional for direct file output mode.

---

## Dependencies

All dependencies are declared in the **repository root `requirements.txt`**. No per-capability requirements file is used.

Install with:

```bash
pip install -r requirements.txt
```

Key packages used by this capability:

```
pandas            # Data manipulation and transformation
openpyxl          # Excel file reading/writing for mapping files
dataclasses-json  # JSON serialization for scenario configs
requests          # HTTP client
python-dateutil   # Date/time utilities for time series alignment
plexosdb          # PLEXOS database schema and ORM
eecloud           # PLEXOS Cloud SDK (pre-installed in cloud; install locally via PLEXOS Cloud CLI)
ipykernel         # Jupyter notebook kernel support
```

---

## Setup Instructions

### 1. Download ERAA Dataset

Visit the ENTSO-E website and download the ERAA 2025 modelling data:  
https://www.entsoe.eu/eraa/2025/modelling-data/#Input%20Data

### 2. Organize Folder Structure

Extract the dataset and organize according to the structure shown in `ERAA_Dataset_Folder_Structure.pdf`. Place the dataset in an accessible location (e.g., `~/data/ERAA_2025/`).

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Launch Jupyter Notebook

```bash
jupyter notebook ERAA_MVP_Importer/ERAA_MVP_FBMC_12R03.ipynb
```

### 5. Configure Paths

In the notebook's first cell, set:
- `eraa_data_root` = path to your extracted ERAA dataset
- `mapping_files_dir` = path to this directory (for Excel mapping files)
- `output_dir` = destination for generated PLEXOS study files

### 6. Run Notebook Cells

Execute cells sequentially:
1. **Load Configuration** — Initialize paths and parameters
2. **Load Mapping Files** — Read Excel-based mappings
3. **Parse ERAA Data** — Ingest raw ERAA files
4. **Apply FBMC Rules** — Transform using Flow-Based Market Coupling
5. **Generate PLEXOS Datasets** — Write PLEXOS-compatible files
6. **Validate Output** — Review generated scenarios

---

## Example Workflow

```
1. Download ERAA 2025 data from ENTSO-E
   └─ Extract to ~/data/ERAA_2025/

2. Launch Jupyter notebook
   └─ jupyter notebook ERAA_MVP_FBMC_12R03.ipynb

3. Update path variables in first cell
   ├─ eraa_data_root = ~/data/ERAA_2025/
   ├─ mapping_files_dir = /path/to/this/ERAA/folder
   └─ output_dir = ~/output/PLEXOS_ERAA/

4. Execute all cells
   ├─ Cell 1: Load configuration
   ├─ Cell 2: Load mappings
   ├─ Cell 3: Parse ERAA dataset
   ├─ Cell 4: Apply FBMC
   ├─ Cell 5: Generate PLEXOS output
   └─ Cell 6: Validate scenarios

5. Review output files
   └─ Generated PLEXOS study databases ready for simulation

6. (Optional) Enqueue scenarios to PLEXOS Cloud
   └─ Use scenario JSON configs + eecloud SDK
```

---

## Scenario Configuration

Pre-defined scenario enqueue configurations are included:

- `Enqueue_Adequacy_-_TY2035_-_36_WS_-_S1_-_Post_EVA_LP.json` — Scenario for 2035 adequacy assessment
- `Enqueue_EVA_TY28-35_3WS_S1_Fitted_Light.json` — EVA fitted scenario 2028-2035

These JSON files define simulation parameters for the PLEXOS Cloud SDK (`eecloud`). Customize as needed before enqueuing.

---

## Expected Behaviour

### Success

1. **Notebook launches** successfully with all dependencies available
2. **Mapping files load** from Excel without errors
3. **ERAA data is parsed** and validated (row counts logged for each file type)
4. **FBMC transformation** applies interconnection rules consistently
5. **PLEXOS output** is generated in the specified output directory
6. **Validation cell** confirms all required fields are populated
7. **Process completes** with summary of generated scenarios

### Failure Conditions

| Condition | Recovery |
|---|---|
| ERAA data folder not found | Verify path in first cell; check folder structure against `ERAA_Dataset_Folder_Structure.pdf` |
| Excel mapping file missing | Download latest mapping files from Energy Exemplar or regenerate from specifications |
| Pandas import error | Run `pip install -r requirements.txt` in environment |
| PLEXOS output permission denied | Ensure output directory is writable; check file permissions |
| Newer ERAA dataset incompatible | Review `Read Me Dataset.txt`; minor adjustments to cell logic may be required |

---

## Troubleshooting

**Q: The notebook fails on the ERAA data parsing cell**

A: Check the folder structure matches `ERAA_Dataset_Folder_Structure.pdf`. Newer ERAA releases may have different file layouts. Review the cell's error log and adjust the parsing logic as needed.

**Q: Mapping files show mismatched columns**

A: Excel mapping files use specific column headers. Ensure no manual edits have changed column names. Re-download from the repository if corrupted.

**Q: PLEXOS SDK not found**

A: `eecloud` is **not** installed via `pip install -r requirements.txt` — it is pre-installed in the PLEXOS Cloud execution environment. For local use, install it from the PLEXOS Cloud CLI wheel file (e.g., `pip install eecloud-*.whl`) or obtain it from your Energy Exemplar administrator. Verify it is installed with `pip show eecloud`.

**Q: Output directory fills with intermediate files**

A: This is normal during processing. Intermediate CSV/JSON files are generated during transformation. Delete them manually after validation if disk space is needed.

---

## Notes

- This automation is **versioned for ERAA 2025** dataset. Future ERAA releases may require updates.
- The notebook is **interactive and exploratory** — designed for data scientists and analysts, not pure CLI automation.
- For batch processing, consider converting the notebook to a Python script using `nbconvert` or `papermill`.
- Mapping files are maintained centrally; keep them version-controlled to ensure reproducibility.

---

## Links

- [ENTSO-E ERAA 2025 Data](https://www.entsoe.eu/eraa/2025/modelling-data/#Input%20Data)
- [PLEXOS Documentation](https://www.energyexemplar.com/plexos)
- [eecloud SDK Reference](../../../Documentation/CloudSDK.md)
