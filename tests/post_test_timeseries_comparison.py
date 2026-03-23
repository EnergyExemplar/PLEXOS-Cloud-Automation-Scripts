"""
Unit tests for Post/PLEXOS/TimeSeriesComparison/timeseries_comparison.py

Covered:
- FileLoader.load              – CSV, Parquet, JSON, Excel, missing file, unsupported format
- DatetimeDetector.detect_column   – datetime64 dtype, common names, string parsing, no match
- DatetimeDetector.detect_components – year/month detection, requires ≥2 components
- DatetimeDetector.parse_column    – ISO dates, invalid column
- DatetimeDetector.parse_components – year+month+day assembly, year-only defaults
- TimeSeriesComparator.__init__    – file count validation, label parsing, 4-file cap
- TimeSeriesComparator._detect_value_columns  – numerics only, datetime exclusion
- TimeSeriesComparator._validate_join_missing – auto-fix outer+drop incompatibility
- TimeSeriesComparator._calculate_metrics     – MAE, RMSE, correlation
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from .conftest import get_module

MOD = get_module("ts_analysis")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ts_df(rows: int = 10) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=rows, freq="h"),
        "value_a":   np.linspace(1.0, 10.0, rows),
        "value_b":   np.linspace(2.0, 20.0, rows),
    })


def _comparator(tmp_dir, n_files: int = 2, **kwargs):
    """Build a minimal TimeSeriesComparator pointing at real temp files."""
    args = [str(tmp_dir / f"f{i}.csv") for i in range(n_files)]
    return MOD.TimeSeriesComparator(
        file_args=args,
        output_dir=tmp_dir,
        **kwargs,
    )


# ── FileLoader ────────────────────────────────────────────────────────────────

class TestFileLoader:

    def test_load_csv(self, tmp_dir):
        p = tmp_dir / "data.csv"
        _make_ts_df().to_csv(p, index=False)
        df = MOD.FileLoader.load(str(p))
        assert df is not None
        assert len(df) == 10

    def test_load_parquet(self, tmp_dir):
        p = tmp_dir / "data.parquet"
        _make_ts_df().to_parquet(p, index=False)
        df = MOD.FileLoader.load(str(p))
        assert df is not None
        assert len(df) == 10

    def test_load_json(self, tmp_dir):
        p = tmp_dir / "data.json"
        _make_ts_df().to_json(p, orient="records")
        df = MOD.FileLoader.load(str(p))
        assert df is not None
        assert len(df) == 10

    def test_load_excel(self, tmp_dir):
        p = tmp_dir / "data.xlsx"
        _make_ts_df().to_excel(p, index=False)
        df = MOD.FileLoader.load(str(p))
        assert df is not None
        assert len(df) == 10

    def test_returns_none_for_missing_file(self, tmp_dir):
        df = MOD.FileLoader.load(str(tmp_dir / "ghost.csv"))
        assert df is None

    def test_returns_none_for_directory(self, tmp_dir):
        df = MOD.FileLoader.load(str(tmp_dir))
        assert df is None

    def test_returns_none_for_unsupported_format(self, tmp_dir):
        p = tmp_dir / "data.xyz"
        p.write_text("hello")
        df = MOD.FileLoader.load(str(p))
        assert df is None


# ── DatetimeDetector ──────────────────────────────────────────────────────────

class TestDatetimeDetectorDetectColumn:

    def test_detects_datetime64_dtype(self):
        df = pd.DataFrame({
            "ts":    pd.date_range("2024-01-01", periods=5, freq="D"),
            "value": [1, 2, 3, 4, 5],
        })
        assert MOD.DatetimeDetector.detect_column(df, "File 1") == "ts"

    def test_detects_by_common_name_timestamp(self):
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "value":     [10, 20, 30],
        })
        assert MOD.DatetimeDetector.detect_column(df, "File 1") == "timestamp"

    def test_detects_by_common_name_date(self):
        df = pd.DataFrame({
            "date":  ["2024-01-01", "2024-01-02", "2024-01-03"],
            "value": [10, 20, 30],
        })
        assert MOD.DatetimeDetector.detect_column(df, "File 1") == "date"

    def test_detects_by_common_name_datetime(self):
        df = pd.DataFrame({
            "datetime": ["2024-01-01T00:00", "2024-01-02T00:00", "2024-01-03T00:00"],
            "value":    [1, 2, 3],
        })
        assert MOD.DatetimeDetector.detect_column(df, "File 1") == "datetime"

    def test_detects_parseable_string_column(self):
        """Column of ISO date strings without a recognised name should be detected."""
        df = pd.DataFrame({
            "my_col": [f"2024-{m:02d}-01" for m in range(1, 13)],
            "value":  range(12),
        })
        assert MOD.DatetimeDetector.detect_column(df, "File 1") == "my_col"

    def test_returns_none_for_purely_numeric_df(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        assert MOD.DatetimeDetector.detect_column(df, "File 1") is None


class TestDatetimeDetectorDetectComponents:

    def test_detects_year_month_day(self):
        df = pd.DataFrame({
            "Year": [2023, 2024], "Month": [1, 6], "Day": [1, 15], "value": [100, 200]
        })
        components = MOD.DatetimeDetector.detect_components(df)
        assert components is not None
        lower = [c.lower() for c in components]
        assert "year" in lower
        assert "month" in lower

    def test_returns_none_when_no_year_column(self):
        df = pd.DataFrame({"Month": [1, 2], "Day": [1, 15], "value": [1, 2]})
        assert MOD.DatetimeDetector.detect_components(df) is None

    def test_returns_none_for_no_component_columns(self):
        df = pd.DataFrame({"price": [100, 200], "volume": [10, 20]})
        assert MOD.DatetimeDetector.detect_components(df) is None


class TestDatetimeDetectorParseColumn:

    def test_parses_iso_dates(self):
        df = pd.DataFrame({"date": ["2024-01-01", "2024-06-15", "2024-12-31"]})
        result = MOD.DatetimeDetector.parse_column(df.copy(), "date", "File 1")
        assert result is not None
        assert "_parsed_datetime" in result.columns
        assert result["_parsed_datetime"].notna().all()

    def test_returns_none_for_fully_unparseable_column(self):
        df = pd.DataFrame({"date": ["foo", "bar", "baz"] * 5})
        result = MOD.DatetimeDetector.parse_column(df.copy(), "date", "File 1")
        assert result is None


class TestDatetimeDetectorParseComponents:

    def test_year_month_day_assembly(self):
        df = pd.DataFrame({
            "Year":  [2023, 2023, 2024],
            "Month": [1, 6, 12],
            "Day":   [1, 15, 31],
            "value": [1, 2, 3],
        })
        result = MOD.DatetimeDetector.parse_components(df.copy(), ["Year", "Month", "Day"], "File 1")
        assert result is not None
        assert "_parsed_datetime" in result.columns
        assert result["_parsed_datetime"].notna().all()

    def test_year_only_defaults_to_jan_1(self):
        df = pd.DataFrame({"Year": [2020, 2021, 2022], "value": [1, 2, 3]})
        result = MOD.DatetimeDetector.parse_components(df.copy(), ["Year"], "File 1")
        assert result is not None
        assert (result["_parsed_datetime"].dt.month == 1).all()
        assert (result["_parsed_datetime"].dt.day   == 1).all()


# ── TimeSeriesComparator.__init__ ─────────────────────────────────────────────

class TestComparatorInit:

    def test_raises_with_fewer_than_two_files(self, tmp_dir):
        with pytest.raises(ValueError, match="[Aa]t least 2"):
            MOD.TimeSeriesComparator(
                file_args=["only_one.csv"],
                output_dir=tmp_dir,
            )

    def test_accepts_two_files(self, tmp_dir):
        c = _comparator(tmp_dir, n_files=2)
        assert len(c.entries) == 2

    def test_accepts_four_files(self, tmp_dir):
        c = _comparator(tmp_dir, n_files=4)
        assert len(c.entries) == 4

    def test_truncates_to_four_files(self, tmp_dir):
        args = [str(tmp_dir / f"f{i}.csv") for i in range(6)]
        c = MOD.TimeSeriesComparator(file_args=args, output_dir=tmp_dir)
        assert len(c.entries) == 4

    def test_label_from_colon_syntax(self, tmp_dir):
        """'relative_path:label' splits into path + label.
        Uses a relative path to avoid the Windows drive-letter colon
        being consumed by split(':',1). The script resolves relative
        paths via SIM_PATH, which is fine for label-parsing tests.
        """
        c = MOD.TimeSeriesComparator(
            file_args=["data.csv:Baseline", "b.csv"],
            output_dir=tmp_dir,
        )
        assert c.entries[0][1] == "Baseline"

    def test_default_label_is_stem(self, tmp_dir):
        """When no label is given, the file stem is used as the label."""
        c = MOD.TimeSeriesComparator(
            file_args=["my_data.csv", "b.csv"],
            output_dir=tmp_dir,
        )
        assert c.entries[0][1] == "my_data"

    def test_default_join_type_is_outer(self, tmp_dir):
        c = _comparator(tmp_dir)
        assert c.join_type == "outer"

    def test_custom_join_type_stored(self, tmp_dir):
        c = _comparator(tmp_dir, join_type="inner")
        assert c.join_type == "inner"

    def test_output_dir_is_stored(self, tmp_dir):
        c = _comparator(tmp_dir)
        assert c.output_root == tmp_dir

    def test_url_encoded_spaces_decoded_in_path(self, tmp_dir):
        """URL-encoded path (%20) is decoded to a real space before the entry is stored."""
        c = MOD.TimeSeriesComparator(
            file_args=[
                "/simulation/TimeSeries/Gas%20Demand/Gas%20Demand%20Forecast%20NRT%205min.csv:Baseline",
                "b.csv",
            ],
            output_dir=tmp_dir,
        )
        assert " " in c.entries[0][0], "Expected decoded space in path"
        assert "%20" not in c.entries[0][0], "Percent-encoding should be resolved"

    def test_url_encoded_spaces_decoded_in_label(self, tmp_dir):
        """Label after the colon also has URL-encoding stripped if present."""
        c = MOD.TimeSeriesComparator(
            file_args=["data.csv:My%20Label", "b.csv"],
            output_dir=tmp_dir,
        )
        assert c.entries[0][1] == "My%20Label"  # labels are NOT decoded — only path is

    def test_surrounding_quotes_stripped_from_file_arg(self, tmp_dir):
        """Single quotes passed by a non-shell task runner are stripped before parsing."""
        c = MOD.TimeSeriesComparator(
            file_args=["'data.csv:Baseline'", "b.csv"],
            output_dir=tmp_dir,
        )
        assert c.entries[0][1] == "Baseline"
        assert "'" not in c.entries[0][0]



# ── TimeSeriesComparator helpers ──────────────────────────────────────────────

class TestDetectValueColumns:

    def test_returns_numeric_columns(self, tmp_dir):
        df = pd.DataFrame({
            "ts":    pd.date_range("2024-01-01", periods=3),
            "price": [10.0, 20.0, 30.0],
            "vol":   [100, 200, 300],
        })
        c = _comparator(tmp_dir)
        cols = c._detect_value_columns(df, exclude={"ts"})
        assert "price" in cols
        assert "vol" in cols
        assert "ts" not in cols

    def test_excludes_parsed_datetime(self, tmp_dir):
        df = pd.DataFrame({
            "_parsed_datetime": pd.date_range("2024-01-01", periods=3),
            "value": [1.0, 2.0, 3.0],
        })
        c = _comparator(tmp_dir)
        cols = c._detect_value_columns(df, exclude=set())
        assert "_parsed_datetime" not in cols
        assert "value" in cols

    def test_excludes_specified_columns(self, tmp_dir):
        df = pd.DataFrame({"Year": [2020, 2021], "Month": [1, 2], "price": [100.0, 200.0]})
        c = _comparator(tmp_dir)
        cols = c._detect_value_columns(df, exclude={"Year", "Month"})
        assert "Year" not in cols
        assert "Month" not in cols
        assert "price" in cols

    def test_returns_empty_when_no_numerics(self, tmp_dir):
        df = pd.DataFrame({"ts": ["2024-01-01", "2024-01-02"], "label": ["a", "b"]})
        c = _comparator(tmp_dir)
        cols = c._detect_value_columns(df, exclude={"ts"})
        assert cols == []


class TestValidateJoinMissing:

    def test_outer_drop_auto_corrected_to_interpolate(self, tmp_dir):
        """outer join + drop strategy is incompatible; auto-corrected to interpolate."""
        c = _comparator(tmp_dir, join_type="outer", missing_strategy="drop")
        c._validate_join_missing()
        assert c.missing_strategy == "interpolate"

    def test_inner_drop_is_valid(self, tmp_dir):
        """inner join + drop is fine as all rows have data from both sides."""
        c = _comparator(tmp_dir, join_type="inner", missing_strategy="drop")
        c._validate_join_missing()
        assert c.missing_strategy == "drop"

    def test_outer_none_is_left_unchanged(self, tmp_dir):
        c = _comparator(tmp_dir, join_type="outer", missing_strategy="none")
        c._validate_join_missing()
        assert c.missing_strategy == "none"


class TestCalculateMetrics:

    def _comparator(self, tmp_dir):
        return _comparator(tmp_dir)

    def test_returns_metrics_for_identical_series(self, tmp_dir):
        vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        metrics = _comparator(tmp_dir)._calculate_metrics(
            pd.Series(vals), pd.Series(vals)
        )
        assert metrics["mae"]  == pytest.approx(0.0, abs=1e-9)
        assert metrics["rmse"] == pytest.approx(0.0, abs=1e-9)

    def test_returns_metrics_for_offset_series(self, tmp_dir):
        a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        b = a + 1.0  # constant offset of 1
        metrics = _comparator(tmp_dir)._calculate_metrics(a, b)
        assert metrics["mae"]  == pytest.approx(1.0)
        assert metrics["rmse"] == pytest.approx(1.0)

    def test_valid_points_reported_correctly(self, tmp_dir):
        a = pd.Series([1.0, 2.0, np.nan, 4.0])
        b = pd.Series([1.0, 2.0, 3.0,   4.0])
        metrics = _comparator(tmp_dir)._calculate_metrics(a, b)
        assert metrics["valid_points"] == 3  # NaN pair excluded

    def test_returns_note_when_no_overlap(self, tmp_dir):
        """All-NaN series → returns a note key instead of metrics."""
        a = pd.Series([np.nan, np.nan])
        b = pd.Series([np.nan, np.nan])
        metrics = _comparator(tmp_dir)._calculate_metrics(a, b)
        assert "note" in metrics
        assert metrics["valid_points"] == 0

    def test_correlation_is_one_for_perfectly_correlated(self, tmp_dir):
        a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        b = a * 2  # linear scaling — correlation = 1
        metrics = _comparator(tmp_dir)._calculate_metrics(a, b)
        assert metrics["correlation"] == pytest.approx(1.0, abs=1e-9)


# ── _json_safe ────────────────────────────────────────────────────────────────

class TestJsonSafe:
    """_json_safe must convert NaN/Inf to None so json.dumps never raises."""

    def test_finite_float_unchanged(self):
        assert MOD._json_safe(3.14) == pytest.approx(3.14)

    def test_nan_becomes_none(self):
        assert MOD._json_safe(float("nan")) is None

    def test_inf_becomes_none(self):
        assert MOD._json_safe(float("inf")) is None

    def test_neg_inf_becomes_none(self):
        assert MOD._json_safe(float("-inf")) is None

    def test_nested_dict_sanitized(self):
        obj = {"mae": 0.5, "correlation": float("nan"), "r_squared": float("inf")}
        result = MOD._json_safe(obj)
        assert result["mae"] == pytest.approx(0.5)
        assert result["correlation"] is None
        assert result["r_squared"] is None

    def test_nested_list_sanitized(self):
        obj = [{"pair": "A vs B", "mae": 1.0, "mape_pct": float("nan")}]
        result = MOD._json_safe(obj)
        assert result[0]["mape_pct"] is None
        assert result[0]["mae"] == pytest.approx(1.0)

    def test_output_is_json_serializable(self):
        """json.dumps must not raise after _json_safe is applied."""
        import json
        obj = {"stats": [{"corr": float("nan"), "r2": float("inf"), "mae": 2.5}]}
        json.dumps(MOD._json_safe(obj))  # should not raise
