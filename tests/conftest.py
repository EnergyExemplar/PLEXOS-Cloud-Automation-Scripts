"""
Shared pytest configuration and fixtures.

Sets up required environment variables BEFORE any script module is imported,
since the scripts read env vars at module level (and call sys.exit if missing).
"""
import os
import sys
import tempfile
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import numpy as np
import pytest

# -- Mock eecloud SDK for local testing -------------------------------------
# The eecloud SDK is pre-installed in the cloud environment but not locally.
# Mock it here so scripts can be imported without installation.
if 'eecloud' not in sys.modules:
    sys.modules['eecloud'] = MagicMock()
    sys.modules['eecloud.cloudsdk'] = MagicMock()
    sys.modules['eecloud.models'] = MagicMock()

# ── Repo layout ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]

# Pre scripts
PRE_DOWNLOAD_SCRIPT   = REPO_ROOT / "Pre"  / "PLEXOS" / "DownloadFromDataHub" / "download_from_datahub.py"
PRE_UPDATE_HORIZON    = REPO_ROOT / "Pre"  / "PLEXOS" / "UpdateHorizon"       / "update_horizon.py"
PRE_ENABLE_REPORTS = REPO_ROOT / "Pre" / "PLEXOS" / "EnableReports" / "enable_reports.py"

# Post scripts
NEW_PRE_PARQUET_CSV  = REPO_ROOT / "Pre"  / "PLEXOS" / "ParquetToCsv" / "convert_parquet_to_csv.py"
NEW_POST_CSV_PARQUET = REPO_ROOT / "Post" / "PLEXOS" / "CsvToParquet" / "convert_csv_to_parquet.py"
POST_UPLOAD_SCRIPT   = REPO_ROOT / "Post" / "PLEXOS" / "UploadToDataHub" / "upload_to_datahub.py"
POST_TS_ANALYSIS          = REPO_ROOT / "Post" / "PLEXOS" / "TimeSeriesComparison"        / "timeseries_comparison.py"
POST_CLEANUP_SCRIPT       = REPO_ROOT / "Post" / "PLEXOS" / "CleanupFiles"               / "cleanup_files.py"
POST_SOLPARQUET_UPLOADER  = REPO_ROOT / "Post" / "PLEXOS" / "DatahubSolParquetUploader"  / "datahub_solparquet_uploader.py"
POST_SOLUTION_DATA_QUERY  = REPO_ROOT / "Post" / "PLEXOS" / "SolutionDataQuery"          / "solution_data_query.py"
POST_EXTRACT_DIAGNOSTICS  = REPO_ROOT / "Post" / "PLEXOS" / "ExtractDiagnosticsXML"      / "extract_diag_xml.py"
POST_ZIP_DIAGNOSTICS      = REPO_ROOT / "Post" / "PLEXOS" / "ZipDiagnostics"             / "zip_downloaded_xmls.py"
POST_CONFIGURE_DUCK_DB_VIEWS  = REPO_ROOT / "Post" / "PLEXOS" / "ConfigureDuckDbViews"         / "configure_duck_db_views.py"
POST_QUERY_WRITE_MEMBERSHIPS    = REPO_ROOT / "Post" / "PLEXOS" / "QueryWriteMemberships"      / "query_write_memberships.py"
POST_QUERY_LMP_DATA           = REPO_ROOT / "Post" / "PLEXOS" / "QueryLmpData"                  / "query_lmp_data.py"
POST_WRITE_REPORTED_PROPERTIES  = REPO_ROOT / "Post" / "PLEXOS" / "WriteReportedProperties"   / "write_reported_properties.py"
POST_UPLOAD_SOLUTION_ZIP_TO_DATAHUB = REPO_ROOT / "Post" / "PLEXOS" / "UploadSolutionZipToDatahub" / "upload_solution_zip_to_datahub.py"

# Aurora Post scripts
POST_AURORA_TO_PARQUET    = REPO_ROOT / "Post" / "Aurora" / "AuroraToParquet" / "aurora_to_parquet.py"

# Automation scripts
AUTO_TS_SCRIPT        = REPO_ROOT / "Automation" / "PLEXOS" / "TimeSeriesComparison" / "timeseries_comparison.py"
AUTO_DOWNLOAD_SCRIPT  = REPO_ROOT / "Automation" / "PLEXOS" / "DownloadFromDataHub"  / "download_from_datahub.py"
AUTO_UPLOAD_SCRIPT    = REPO_ROOT / "Automation" / "PLEXOS" / "UploadToDataHub"       / "upload_to_datahub.py"

# ── Temporary directories for env vars ───────────────────────────────────────
# Created once per session; scripts that mkdir(exist_ok=True) will reuse them.
_SESSION_TMP = Path(tempfile.mkdtemp(prefix="plexos_test_"))
_SIM_PATH    = _SESSION_TMP / "simulation"
_OUT_PATH    = _SESSION_TMP / "output"
_SIM_PATH.mkdir(parents=True, exist_ok=True)
_OUT_PATH.mkdir(parents=True, exist_ok=True)

# Set env vars NOW so that module-level reads inside each script succeed.
os.environ.setdefault("cloud_cli_path",    "mock_cli_path")
os.environ.setdefault("simulation_path",  str(_SIM_PATH))
os.environ.setdefault("output_path",      str(_OUT_PATH))
os.environ.setdefault("simulation_id",     "test_sim_001")
os.environ.setdefault("execution_id",      "test_exec_001")
os.environ.setdefault("study_id",         "test_study_001")
os.environ.setdefault("directory_map_path", str(_SIM_PATH / "directorymapping.json"))
os.environ.setdefault("duck_db_path",        str(_OUT_PATH / "solution_views.ddb"))


# ── Module loader helper ──────────────────────────────────────────────────────

def load_script(path: Path, module_name: str):
    """
    Import a script file as a module by absolute path.
    Using spec_from_file_location lets us give each script a unique module name,
    which avoids collisions between the two timeseries_comparison.py files.
    """
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Lazy module cache (loaded once per session) ───────────────────────────────

_modules: dict = {}

def get_module(key: str):
    if key not in _modules:
        mapping = {
            # Pre scripts
            "pre_download":        (PRE_DOWNLOAD_SCRIPT,      "pre_download_from_datahub"),
            # Post scripts
            "new_parquet_to_csv":  (NEW_PRE_PARQUET_CSV,      "convert_parquet_to_csv_new"),
            "new_csv_to_parquet":  (NEW_POST_CSV_PARQUET,     "convert_csv_to_parquet_new"),
            "upload_to_datahub":   (POST_UPLOAD_SCRIPT,       "upload_to_datahub"),
            "ts_analysis":         (POST_TS_ANALYSIS,         "timeseries_analysis"),
            "cleanup_files":               (POST_CLEANUP_SCRIPT,       "cleanup_files"),
            "solparquet_uploader":         (POST_SOLPARQUET_UPLOADER, "datahub_solparquet_uploader"),
            "solution_data_query":         (POST_SOLUTION_DATA_QUERY, "solution_data_query"),
            "extract_diag_xml":            (POST_EXTRACT_DIAGNOSTICS, "extract_diag_xml"),
            "zip_downloaded_xmls":         (POST_ZIP_DIAGNOSTICS,     "zip_downloaded_xmls"),
            "configure_duck_db_views":      (POST_CONFIGURE_DUCK_DB_VIEWS, "configure_duck_db_views"),
            "query_write_memberships":       (POST_QUERY_WRITE_MEMBERSHIPS,   "query_write_memberships"),
            "query_lmp_data":               (POST_QUERY_LMP_DATA,          "query_lmp_data"),
            "write_reported_properties":     (POST_WRITE_REPORTED_PROPERTIES, "write_reported_properties"),
            "upload_solution_zip_to_datahub":  (POST_UPLOAD_SOLUTION_ZIP_TO_DATAHUB, "upload_solution_zip_to_datahub"),
            # Aurora Post scripts
            "aurora_to_parquet":           (POST_AURORA_TO_PARQUET,   "aurora_to_parquet"),
            # Pre PLEXOS scripts (SDK-dependent)
            "update_horizon":              (PRE_UPDATE_HORIZON,       "update_horizon"),
            "enable_reports":             (PRE_ENABLE_REPORTS,       "enable_reports"),
            # Automation scripts
            "ts_auto":             (AUTO_TS_SCRIPT,           "ts_comparison_auto"),
            "auto_download":       (AUTO_DOWNLOAD_SCRIPT,     "auto_download_from_datahub"),
            "auto_upload":         (AUTO_UPLOAD_SCRIPT,       "auto_upload_to_datahub"),
        }
        path, name = mapping[key]
        _modules[key] = load_script(path, name)
    return _modules[key]


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_dir(tmp_path):
    """Provide a fresh per-test temp directory."""
    return tmp_path


@pytest.fixture()
def sample_dataframe():
    """Small DataFrame used across multiple tests."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10, freq="h"),
        "value_a":   np.random.default_rng(42).uniform(10, 100, 10).round(2),
        "value_b":   np.random.default_rng(43).uniform(5,  50,  10).round(2),
    })


@pytest.fixture()
def sample_csv(tmp_dir, sample_dataframe):
    """Write sample_dataframe to a CSV file and return its path."""
    path = tmp_dir / "sample.csv"
    sample_dataframe.to_csv(path, index=False)
    return path


@pytest.fixture()
def sample_parquet(tmp_dir, sample_dataframe):
    """Write sample_dataframe to a Parquet file and return its path."""
    path = tmp_dir / "sample.parquet"
    sample_dataframe.to_parquet(path, index=False)
    return path
