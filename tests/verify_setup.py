"""
Verify that Automation/PLEXOS scripts can import from each other.

Run from repo root: python tests/verify_setup.py
Or: python -m tests.verify_setup
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_PLEXOS = REPO_ROOT / "Automation" / "PLEXOS"


def test_imports():
    """Test that automation scripts can be imported."""
    print("Testing automation script imports...")
    if str(AUTOMATION_PLEXOS) not in sys.path:
        sys.path.insert(0, str(AUTOMATION_PLEXOS))
    try:
        from DownloadFromDataHub.download_from_datahub import DataHubDownloader
        print("[OK] DataHubDownloader imported")
        from UploadToDataHub.upload_to_datahub import DataHubUploader
        print("[OK] DataHubUploader imported")
        from CsvToParquet.csv_to_parquet import CsvParquetConverter
        print("[OK] CsvParquetConverter imported")
        from ParquetToCsv.parquet_to_csv import ParquetCsvConverter
        print("[OK] ParquetCsvConverter imported")
        from TimeSeriesComparison.timeseries_comparison import TimeSeriesComparator, DataHubManager
        print("[OK] TimeSeriesComparator, DataHubManager imported")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("Automation Scripts Verification")
    print("=" * 60)
    ok = test_imports()
    print("\n" + "=" * 60)
    if ok:
        print("[SUCCESS] Automation scripts are importable.")
    else:
        print("[ERROR] Some imports failed.")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
