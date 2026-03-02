"""
Unit tests for Automation/PLEXOS conversion scripts.

Tests CsvParquetConverter and ParquetCsvConverter (no DataHub required).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

# Add Automation/PLEXOS to path so we can import scripts
REPO_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_ROOT = REPO_ROOT / "Automation" / "PLEXOS"
sys.path.insert(0, str(AUTOMATION_ROOT))

from CsvToParquet.csv_to_parquet import CsvParquetConverter
from ParquetToCsv.parquet_to_csv import ParquetCsvConverter


@pytest.fixture
def sample_csv(tmp_path):
    """Sample CSV file for conversion tests."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=50, freq="h"),
        "value1": range(50),
        "value2": [x * 2 for x in range(50)],
    })
    path = tmp_path / "sample.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def sample_parquet(tmp_path):
    """Sample Parquet file for conversion tests."""
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=50, freq="h"),
        "value1": range(50),
        "value2": [x * 2 for x in range(50)],
    })
    path = tmp_path / "sample.parquet"
    df.to_parquet(path, index=False)
    return path


class TestCsvParquetConverter:
    """Tests for CsvParquetConverter."""

    def test_convert_file(self, sample_csv, tmp_path):
        out = tmp_path / "out.parquet"
        result = CsvParquetConverter.convert_file(sample_csv, parquet_path=out)
        assert result.exists()
        assert result.suffix == ".parquet"
        df = pd.read_parquet(result)
        assert len(df) == 50
        assert list(df.columns) == ["timestamp", "value1", "value2"]

    def test_convert_file_default_output_path(self, sample_csv):
        result = CsvParquetConverter.convert_file(sample_csv)
        assert result.exists()
        assert result == sample_csv.with_suffix(".parquet")

    def test_convert_file_compression(self, sample_csv, tmp_path):
        for comp in ("zstd", "gzip", "snappy", "none"):
            out = tmp_path / f"out_{comp}.parquet"
            result = CsvParquetConverter.convert_file(sample_csv, out, compression=comp)
            assert result.exists()
            assert len(pd.read_parquet(result)) == 50

    def test_convert_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            CsvParquetConverter.convert_file(Path("/nonexistent/file.csv"))

    def test_convert_directory(self, sample_csv, tmp_path):
        # Second CSV
        (tmp_path / "other.csv").write_text("a,b\n1,2\n3,4\n")
        result = CsvParquetConverter.convert_directory(tmp_path, pattern="*.csv")
        assert len(result) == 2
        for p in result:
            assert p.suffix == ".parquet"

    def test_convert_directory_recursive_glob(self, tmp_path):
        """**/*.csv pattern recurses into subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.csv").write_text("a,b\n1,2\n")
        (sub / "nested.csv").write_text("a,b\n3,4\n")

        result = CsvParquetConverter.convert_directory(tmp_path, pattern="**/*.csv")
        assert len(result) == 2
        names = {p.name for p in result}
        assert "root.parquet" in names
        assert "nested.parquet" in names

    def test_convert_directory_preserves_subdir_structure(self, tmp_path):
        """When output_dir is given, subdirectory structure is mirrored."""
        sub = tmp_path / "inputs" / "sub"
        sub.mkdir(parents=True)
        (tmp_path / "inputs" / "root.csv").write_text("a,b\n1,2\n")
        (sub / "nested.csv").write_text("a,b\n3,4\n")

        out_dir = tmp_path / "outputs"
        result = CsvParquetConverter.convert_directory(
            tmp_path / "inputs", output_dir=out_dir, pattern="**/*.csv"
        )
        assert len(result) == 2
        # root file should land directly in out_dir
        assert (out_dir / "root.parquet").exists()
        # nested file should mirror subdirectory structure
        assert (out_dir / "sub" / "nested.parquet").exists()


class TestParquetCsvConverter:
    """Tests for ParquetCsvConverter."""

    def test_convert_file(self, sample_parquet, tmp_path):
        out = tmp_path / "out.csv"
        result = ParquetCsvConverter.convert_file(sample_parquet, csv_path=out)
        assert result.exists()
        assert result.suffix == ".csv"
        df = pd.read_csv(result)
        assert len(df) == 50
        assert "value1" in df.columns

    def test_convert_file_default_output_path(self, sample_parquet):
        result = ParquetCsvConverter.convert_file(sample_parquet)
        assert result.exists()
        assert result == sample_parquet.with_suffix(".csv")

    def test_convert_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            ParquetCsvConverter.convert_file(Path("/nonexistent/file.parquet"))

    def test_convert_directory(self, sample_parquet, tmp_path):
        result = ParquetCsvConverter.convert_directory(tmp_path, pattern="*.parquet")
        assert len(result) == 1
        assert result[0].suffix == ".csv"

    def test_convert_directory_recursive_glob(self, tmp_path):
        """**/*.parquet pattern recurses into subdirectories."""
        import pandas as pd

        sub = tmp_path / "sub"
        sub.mkdir()
        df = pd.DataFrame({"x": [1, 2]})
        df.to_parquet(tmp_path / "root.parquet", index=False)
        df.to_parquet(sub / "nested.parquet", index=False)

        result = ParquetCsvConverter.convert_directory(tmp_path, pattern="**/*.parquet")
        assert len(result) == 2
        names = {p.name for p in result}
        assert "root.csv" in names
        assert "nested.csv" in names

    def test_convert_directory_preserves_subdir_structure(self, tmp_path):
        """When output_dir is given, subdirectory structure is mirrored."""
        import pandas as pd

        sub = tmp_path / "inputs" / "sub"
        sub.mkdir(parents=True)
        df = pd.DataFrame({"x": [1, 2]})
        df.to_parquet(tmp_path / "inputs" / "root.parquet", index=False)
        df.to_parquet(sub / "nested.parquet", index=False)

        out_dir = tmp_path / "outputs"
        result = ParquetCsvConverter.convert_directory(
            tmp_path / "inputs", output_dir=out_dir, pattern="**/*.parquet"
        )
        assert len(result) == 2
        assert (out_dir / "root.csv").exists()
        assert (out_dir / "sub" / "nested.csv").exists()
