"""
Unit tests for Automation/PLEXOS/TimeSeriesComparison/timeseries_comparison.py

Covered:
- TimeSeriesComparator.__init__    – file count validation, 4-file cap
- load_data_file                   – CSV, Parquet, JSON, Excel, missing file, bad format
- detect_datetime_column           – dtype, name-based, parsing
- detect_datetime_components       – year/month/day column discovery
- detect_value_columns             – numeric column detection, exclusion of datetime cols
- parse_datetime_column            – standard formats, multi-format fallback
- create_datetime_from_components  – year+month+day assembly
- apply_value_aliases              – alias mapping, count mismatch, duplicate detection
"""
import pandas as pd
import numpy as np
import pytest

from .conftest import get_module

MOD = get_module("ts_auto")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _comparator(file_paths, **kwargs):
    return MOD.TimeSeriesComparator(
        file_paths=file_paths,
        output_datahub_path="Project/Study/Results",
        **kwargs,
    )


# ── __init__ validation ───────────────────────────────────────────────────────

class TestComparatorInit:

    def test_raises_with_fewer_than_two_files(self):
        with pytest.raises(ValueError, match="at least 2"):
            _comparator(["only_one.csv"])

    def test_accepts_two_files(self):
        c = _comparator(["a.csv", "b.csv"])
        assert len(c.file_paths) == 2

    def test_accepts_four_files(self):
        c = _comparator(["a.csv", "b.csv", "c.csv", "d.csv"])
        assert len(c.file_paths) == 4

    def test_truncates_to_four_files(self):
        """More than 4 files: only the first 4 are kept."""
        paths = [f"file{i}.csv" for i in range(6)]
        c = _comparator(paths)
        assert len(c.file_paths) == 4
        assert c.file_paths == paths[:4]

    def test_default_join_type_is_outer(self):
        c = _comparator(["a.csv", "b.csv"])
        assert c.join_type == "outer"

    def test_custom_join_type_stored(self):
        c = _comparator(["a.csv", "b.csv"], join_type="inner")
        assert c.join_type == "inner"


# ── load_data_file ────────────────────────────────────────────────────────────

class TestLoadDataFile:

    def test_load_csv(self, sample_csv):
        c = _comparator([str(sample_csv), "b.csv"])
        df = c.load_data_file(str(sample_csv))
        assert df is not None
        assert len(df) == 10

    def test_load_parquet(self, sample_parquet):
        c = _comparator([str(sample_parquet), "b.csv"])
        df = c.load_data_file(str(sample_parquet))
        assert df is not None
        assert len(df) == 10

    def test_load_json(self, tmp_dir, sample_dataframe):
        json_path = tmp_dir / "data.json"
        sample_dataframe.to_json(json_path, orient="records")
        c = _comparator([str(json_path), "b.csv"])
        df = c.load_data_file(str(json_path))
        assert df is not None
        assert len(df) == 10

    def test_load_excel(self, tmp_dir, sample_dataframe):
        xlsx_path = tmp_dir / "data.xlsx"
        sample_dataframe.to_excel(xlsx_path, index=False)
        c = _comparator([str(xlsx_path), "b.csv"])
        df = c.load_data_file(str(xlsx_path))
        assert df is not None
        assert len(df) == 10

    def test_returns_none_for_missing_file(self, tmp_dir):
        c = _comparator(["a.csv", "b.csv"])
        assert c.load_data_file(str(tmp_dir / "ghost.csv")) is None

    def test_returns_none_for_unsupported_format(self, tmp_dir):
        bad_file = tmp_dir / "data.xyz"
        bad_file.write_text("hello")
        c = _comparator(["a.csv", "b.csv"])
        assert c.load_data_file(str(bad_file)) is None

    def test_returns_none_for_path_to_directory(self, tmp_dir):
        c = _comparator(["a.csv", "b.csv"])
        assert c.load_data_file(str(tmp_dir)) is None


# ── detect_datetime_column ────────────────────────────────────────────────────

class TestDetectDatetimeColumn:

    def test_detects_datetime64_dtype(self):
        df = pd.DataFrame({
            "ts":    pd.date_range("2024-01-01", periods=5, freq="D"),
            "value": [1, 2, 3, 4, 5],
        })
        assert _comparator(["a.csv", "b.csv"]).detect_datetime_column(df, "File 1") == "ts"

    def test_detects_by_common_name_timestamp(self):
        df = pd.DataFrame({"timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"], "value": [10, 20, 30]})
        assert _comparator(["a.csv", "b.csv"]).detect_datetime_column(df, "File 1") == "timestamp"

    def test_detects_by_common_name_date(self):
        df = pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2024-01-03"], "value": [10, 20, 30]})
        assert _comparator(["a.csv", "b.csv"]).detect_datetime_column(df, "File 1") == "date"

    def test_detects_by_parsing_string_dates(self):
        """A column of parseable date strings without a recognised name should be detected."""
        df = pd.DataFrame({
            "my_custom_col": [f"2024-{m:02d}-01" for m in range(1, 13)],
            "value":         range(12),
        })
        assert _comparator(["a.csv", "b.csv"]).detect_datetime_column(df, "File 1") == "my_custom_col"

    def test_returns_none_for_purely_numeric_df(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        assert _comparator(["a.csv", "b.csv"]).detect_datetime_column(df, "File 1") is None


# ── detect_datetime_components ────────────────────────────────────────────────

class TestDetectDatetimeComponents:

    def test_detects_year_month_day(self):
        df = pd.DataFrame({"Year": [2023, 2024], "Month": [1, 6], "Day": [1, 15], "value": [100, 200]})
        components = _comparator(["a.csv", "b.csv"]).detect_datetime_components(df, "File 1")
        assert components is not None
        col_lower = [c.lower() for c in components]
        assert "year" in col_lower
        assert "month" in col_lower

    def test_returns_none_when_no_components(self):
        df = pd.DataFrame({"value_a": [1, 2], "value_b": [3, 4]})
        assert _comparator(["a.csv", "b.csv"]).detect_datetime_components(df, "File 1") is None

    def test_requires_at_least_two_components(self):
        df = pd.DataFrame({"Year": [2023, 2024], "value": [1, 2]})
        assert _comparator(["a.csv", "b.csv"]).detect_datetime_components(df, "File 1") is None


# ── detect_value_columns ──────────────────────────────────────────────────────

class TestDetectValueColumns:

    def test_returns_numeric_columns(self):
        df = pd.DataFrame({
            "ts":    pd.date_range("2024-01-01", periods=3),
            "price": [10.0, 20.0, 30.0],
            "vol":   [100, 200, 300],
        })
        cols = _comparator(["a.csv", "b.csv"]).detect_value_columns(df, "ts", None, "File 1")
        assert "price" in cols
        assert "vol" in cols
        assert "ts" not in cols

    def test_excludes_datetime_column(self):
        df = pd.DataFrame({
            "_parsed_datetime": pd.date_range("2024-01-01", periods=3),
            "value": [1.0, 2.0, 3.0],
        })
        cols = _comparator(["a.csv", "b.csv"]).detect_value_columns(df, "_parsed_datetime", None, "File 1")
        assert "_parsed_datetime" not in cols
        assert "value" in cols

    def test_excludes_datetime_components(self):
        df = pd.DataFrame({"Year": [2023, 2024, 2025], "Month": [1, 2, 3], "value": [10.0, 20.0, 30.0]})
        cols = _comparator(["a.csv", "b.csv"]).detect_value_columns(df, None, ["Year", "Month"], "File 1")
        assert "Year" not in cols
        assert "Month" not in cols
        assert "value" in cols

    def test_returns_empty_when_no_numeric(self):
        df = pd.DataFrame({"ts": ["2024-01-01", "2024-01-02"], "label": ["a", "b"]})
        cols = _comparator(["a.csv", "b.csv"]).detect_value_columns(df, "ts", None, "File 1")
        assert cols == []


# ── parse_datetime_column ─────────────────────────────────────────────────────

class TestParseDatetimeColumn:

    def test_iso_dates_parsed(self):
        df = pd.DataFrame({"date": ["2024-01-01", "2024-06-15", "2024-12-31"]})
        result = _comparator(["a.csv", "b.csv"]).parse_datetime_column(df.copy(), "date", "File 1")
        assert result is not None
        assert "_parsed_datetime" in result.columns
        assert result["_parsed_datetime"].notna().all()

    def test_mixed_formats_partially_parsed(self):
        """At least 70 % valid should succeed."""
        dates = [f"2024-{m:02d}-01" for m in range(1, 11)]
        df = pd.DataFrame({"date": dates + ["not_a_date"]})
        result = _comparator(["a.csv", "b.csv"]).parse_datetime_column(df.copy(), "date", "File 1")
        assert result is not None

    def test_returns_none_for_unparseable_column(self):
        df = pd.DataFrame({"date": ["foo", "bar", "baz"] * 5})
        result = _comparator(["a.csv", "b.csv"]).parse_datetime_column(df.copy(), "date", "File 1")
        assert result is None


# ── create_datetime_from_components ──────────────────────────────────────────

class TestCreateDatetimeFromComponents:

    def test_year_month_day_assembly(self):
        df = pd.DataFrame({"Year": [2023, 2023, 2024], "Month": [1, 6, 12], "Day": [1, 15, 31], "value": [1, 2, 3]})
        result = _comparator(["a.csv", "b.csv"]).create_datetime_from_components(df.copy(), ["Year", "Month", "Day"], "File 1")
        assert result is not None
        assert "_parsed_datetime" in result.columns
        assert result["_parsed_datetime"].notna().all()

    def test_year_only_defaults_to_jan_1(self):
        df = pd.DataFrame({"Year": [2020, 2021, 2022], "value": [1, 2, 3]})
        result = _comparator(["a.csv", "b.csv"]).create_datetime_from_components(df.copy(), ["Year"], "File 1")
        assert result is not None
        assert (result["_parsed_datetime"].dt.month == 1).all()
        assert (result["_parsed_datetime"].dt.day   == 1).all()


# ── apply_value_aliases ───────────────────────────────────────────────────────

class TestApplyValueAliases:

    def test_maps_aliases_correctly(self):
        aliased, alias_map = _comparator(["a.csv", "b.csv"]).apply_value_aliases(
            ["col_a", "col_b"], ["Demand", "Supply"], "File 1"
        )
        assert aliased == ["Demand", "Supply"]
        assert alias_map == {"col_a": "Demand", "col_b": "Supply"}

    def test_no_aliases_returns_originals(self):
        aliased, alias_map = _comparator(["a.csv", "b.csv"]).apply_value_aliases(
            ["col_a", "col_b"], None, "File 1"
        )
        assert aliased == ["col_a", "col_b"]
        assert alias_map is None

    def test_count_mismatch_returns_none(self):
        aliased, alias_map = _comparator(["a.csv", "b.csv"]).apply_value_aliases(
            ["col_a", "col_b", "col_c"], ["Alias1"], "File 1"
        )
        assert aliased is None
        assert alias_map is None

    def test_duplicate_aliases_raise_value_error(self):
        with pytest.raises(ValueError, match="Duplicate aliases"):
            _comparator(["a.csv", "b.csv"]).apply_value_aliases(
                ["col_a", "col_b"], ["SameName", "SameName"], "File 1"
            )

    def test_empty_string_alias_falls_back_to_original(self):
        aliased, _ = _comparator(["a.csv", "b.csv"]).apply_value_aliases(
            ["col_a", "col_b"], ["", "Supply"], "File 1"
        )
        assert aliased[0] == "col_a"
        assert aliased[1] == "Supply"
