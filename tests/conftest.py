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

import pandas as pd
import numpy as np
import pytest

# ── Repo layout ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]

# Pre scripts
PRE_DOWNLOAD_SCRIPT  = REPO_ROOT / "Pre"  / "PLEXOS" / "DownloadFromDataHub" / "download_from_datahub.py"

# Post scripts
NEW_PRE_PARQUET_CSV  = REPO_ROOT / "Pre"  / "PLEXOS" / "ParquetToCsv" / "convert_parquet_to_csv.py"
NEW_POST_CSV_PARQUET = REPO_ROOT / "Post" / "PLEXOS" / "CsvToParquet" / "convert_csv_to_parquet.py"
POST_UPLOAD_SCRIPT   = REPO_ROOT / "Post" / "PLEXOS" / "UploadToDataHub" / "upload_to_datahub.py"
POST_TS_ANALYSIS     = REPO_ROOT / "Post" / "PLEXOS" / "TimeSeriesComparison" / "timeseries_comparison.py"
POST_CLEANUP_SCRIPT  = REPO_ROOT / "Post" / "PLEXOS" / "CleanupFiles" / "cleanup_files.py"

# Automation scripts
AUTO_TS_SCRIPT       = REPO_ROOT / "Automation" / "PLEXOS" / "TimeSeriesComparison" / "timeseries_comparison.py"

# ── Temporary directories for env vars ───────────────────────────────────────
# Created once per session; scripts that mkdir(exist_ok=True) will reuse them.
_SESSION_TMP = Path(tempfile.mkdtemp(prefix="plexos_test_"))
_SIM_PATH    = _SESSION_TMP / "simulation"
_OUT_PATH    = _SESSION_TMP / "output"
_SIM_PATH.mkdir(parents=True, exist_ok=True)
_OUT_PATH.mkdir(parents=True, exist_ok=True)

# Set env vars NOW so that module-level reads inside each script succeed.
os.environ.setdefault("cloud_cli_path", "mock_cli_path")
os.environ.setdefault("simulation_path", str(_SIM_PATH))
os.environ.setdefault("output_path",     str(_OUT_PATH))


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
            "cleanup_files":       (POST_CLEANUP_SCRIPT,      "cleanup_files"),
            # Automation scripts
            "ts_auto":             (AUTO_TS_SCRIPT,            "ts_comparison_auto"),
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
