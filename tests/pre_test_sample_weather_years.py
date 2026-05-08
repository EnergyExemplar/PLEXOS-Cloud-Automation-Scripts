"""
Unit tests for Pre/PLEXOS/WeatherSample/sample_weather_years.py

Tests the weather profile sampling script (Step 1 of the WeatherSample workflow).
Generates per-location sampled CSV files from multi-year weather profiles.
"""
import argparse
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from .conftest import get_module


MOD = get_module("sample_weather_years")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile_df(years: list[int], locations: list[str], periods: int = 24) -> pd.DataFrame:
    """Build a weather profile DataFrame covering all days for each year.

    Generates Year/Month/Day/Period + location columns for every day of each
    year so that the day-of-week alignment logic can map to any date without
    hitting missing-data errors.
    """
    from datetime import date as _date, timedelta as _td

    rows = []
    for year in years:
        current = _date(year, 1, 1)
        end = _date(year, 12, 31)
        while current <= end:
            for period in range(1, periods + 1):
                row = {
                    "Year": year,
                    "Month": current.month,
                    "Day": current.day,
                    "Period": period,
                }
                for loc in locations:
                    row[loc] = float(year + current.month * 0.01 + current.day * 0.001 + period * 0.0001)
                rows.append(row)
            current += _td(days=1)
    return pd.DataFrame(rows)


def _write_profile_csv(path: Path, years: list[int], locations: list[str]) -> Path:
    """Write a profile CSV file and return its path."""
    df = _make_profile_df(years, locations)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# _normalize_cli_args
# ---------------------------------------------------------------------------


class TestNormalizeCliArgs:
    """Test Unicode dash normalization in CLI arguments."""

    def test_standard_dashes_unchanged(self):
        result = MOD._normalize_cli_args(["--profiles-dir", "somepath"])
        assert result == ["--profiles-dir", "somepath"]

    def test_unicode_en_dash_normalized(self):
        """EN DASH (U+2013) is replaced with standard hyphen-minus."""
        result = MOD._normalize_cli_args(["\u2013\u2013profiles-dir", "somepath"])
        assert result == ["--profiles-dir", "somepath"]

    def test_unicode_em_dash_normalized(self):
        """EM DASH (U+2014) is replaced with standard hyphen-minus."""
        result = MOD._normalize_cli_args(["\u2014\u2014profiles-dir"])
        assert result == ["--profiles-dir"]

    def test_empty_list(self):
        assert MOD._normalize_cli_args([]) == []

    def test_non_dash_args_unchanged(self):
        result = MOD._normalize_cli_args(["value1", "value2"])
        assert result == ["value1", "value2"]


# ---------------------------------------------------------------------------
# _decode_cli_value
# ---------------------------------------------------------------------------


class TestDecodeCliValue:
    """Test CLI quote stripping and URL-decoding."""

    def test_percent20_replaced(self):
        result, changed = MOD._decode_cli_value("hello%20world")
        assert result == "hello world"
        assert changed is True

    def test_no_placeholder_unchanged(self):
        result, changed = MOD._decode_cli_value("hello_world")
        assert result == "hello_world"
        assert changed is False

    def test_quotes_are_stripped_before_decoding(self):
        result, changed = MOD._decode_cli_value("'a%20b'")
        assert result == "a b"
        assert changed is True

    def test_other_url_encoded_characters_are_decoded(self):
        result, changed = MOD._decode_cli_value("Solar%20Profiles%20CY1982%2B%20TY1.csv")
        assert result == "Solar Profiles CY1982+ TY1.csv"
        assert changed is True


# ---------------------------------------------------------------------------
# _decode_cli_args
# ---------------------------------------------------------------------------


class TestDecodeCliArgs:
    """Test CLI decoding across argparse Namespace fields."""

    def test_restores_profiles_dir(self):
        ns = argparse.Namespace(
            profiles_dir="My%20Folder",
            profile_type="Weather",
            start_date="2025-01-01 00:00",
            end_date="2025-12-31 23:00",
            files=None,
        )
        count = MOD._decode_cli_args(ns)
        assert ns.profiles_dir == "My Folder"
        assert count == 1

    def test_restores_files_list(self):
        ns = argparse.Namespace(
            profiles_dir="plain",
            profile_type="Weather",
            start_date="2025-01-01 00:00",
            end_date="2025-12-31 23:00",
            files=["Solar%20Profiles.csv", "Wind%20Profiles.csv", "plain.csv"],
        )
        count = MOD._decode_cli_args(ns)
        assert ns.files == ["Solar Profiles.csv", "Wind Profiles.csv", "plain.csv"]
        assert count == 2

    def test_strips_quotes_and_decodes_all_string_fields(self):
        ns = argparse.Namespace(
            profiles_dir="'My%20Folder'",
            profile_type="'Weather%20Sample'",
            start_date="'2025-01-01%2000:00'",
            end_date="'2025-12-31%2023:00'",
            files=['"Solar%20Profiles%20CY1982%2B%20TY1.csv"'],
        )
        count = MOD._decode_cli_args(ns)
        assert ns.profiles_dir == "My Folder"
        assert ns.profile_type == "Weather Sample"
        assert ns.start_date == "2025-01-01 00:00"
        assert ns.end_date == "2025-12-31 23:00"
        assert ns.files == ["Solar Profiles CY1982+ TY1.csv"]
        assert count == 5

    def test_no_placeholders_returns_zero(self):
        ns = argparse.Namespace(
            profiles_dir="plain",
            profile_type="Weather",
            start_date="2025-01-01 00:00",
            end_date="2025-12-31 23:00",
            files=["file.csv"],
        )
        count = MOD._decode_cli_args(ns)
        assert count == 0


# ---------------------------------------------------------------------------
# CSVProcessor
# ---------------------------------------------------------------------------


class TestCSVProcessor:
    """Test CSV read/write with encoding detection and caching."""

    def test_read_csv_returns_dataframe(self, tmp_dir):
        csv_path = tmp_dir / "data.csv"
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df.to_csv(csv_path, index=False)

        # Clear cache to avoid cross-test state
        MOD.CSVProcessor._cache.clear()

        result = MOD.CSVProcessor.read_csv(str(csv_path))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["A", "B"]

    def test_read_csv_caches_result(self, tmp_dir):
        csv_path = tmp_dir / "data.csv"
        df = pd.DataFrame({"X": [10]})
        df.to_csv(csv_path, index=False)

        MOD.CSVProcessor._cache.clear()

        first = MOD.CSVProcessor.read_csv(str(csv_path), use_cache=True)
        second = MOD.CSVProcessor.read_csv(str(csv_path), use_cache=True)
        # Cached copy should equal original
        assert first.equals(second)

    def test_read_csv_no_cache(self, tmp_dir):
        csv_path = tmp_dir / "data.csv"
        df = pd.DataFrame({"X": [10]})
        df.to_csv(csv_path, index=False)

        MOD.CSVProcessor._cache.clear()

        MOD.CSVProcessor.read_csv(str(csv_path), use_cache=False)
        assert str(csv_path) not in MOD.CSVProcessor._cache

    def test_write_csv_creates_file(self, tmp_dir):
        output_path = tmp_dir / "sub" / "output.csv"
        df = pd.DataFrame({"Col": [1, 2, 3]})
        MOD.CSVProcessor.write_csv(df, str(output_path))

        assert output_path.exists()
        result = pd.read_csv(output_path)
        assert len(result) == 3

    def test_write_csv_utf8_sig_encoding(self, tmp_dir):
        output_path = tmp_dir / "encoded.csv"
        df = pd.DataFrame({"Name": ["TestÉ"]})
        MOD.CSVProcessor.write_csv(df, str(output_path))

        # UTF-8-sig starts with BOM
        raw_bytes = output_path.read_bytes()
        assert raw_bytes.startswith(b"\xef\xbb\xbf")


# ---------------------------------------------------------------------------
# build_year_location_lookup
# ---------------------------------------------------------------------------


class TestBuildYearLocationLookup:
    """Test the year → (Month, Day, Period) → value lookup builder."""

    def test_returns_dict_keyed_by_year(self):
        df = pd.DataFrame({
            "Year": [2000, 2000, 2001],
            "Month": [1, 1, 1],
            "Day": [1, 1, 1],
            "Period": [1, 2, 1],
            "LocationA": [10.0, 20.0, 30.0],
        })
        result = MOD.build_year_location_lookup(df, "LocationA")
        assert 2000 in result
        assert 2001 in result
        assert result[2000][(1, 1, 1)] == 10.0
        assert result[2000][(1, 1, 2)] == 20.0
        assert result[2001][(1, 1, 1)] == 30.0


# ---------------------------------------------------------------------------
# get_value_with_fallback
# ---------------------------------------------------------------------------


class TestGetValueWithFallback:
    """Test hourly value lookup with Feb 29 fallback."""

    def test_exact_match(self):
        lookup = {(3, 15, 1): 42.0}
        assert MOD.get_value_with_fallback(lookup, 2000, 3, 15, 1) == 42.0

    def test_feb29_fallback_to_feb28(self):
        lookup = {(2, 28, 5): 99.0}
        assert MOD.get_value_with_fallback(lookup, 2001, 2, 29, 5) == 99.0

    def test_missing_data_raises_key_error(self):
        lookup = {}
        with pytest.raises(KeyError, match="Missing data"):
            MOD.get_value_with_fallback(lookup, 2000, 6, 15, 1)

    def test_feb29_no_feb28_raises_key_error(self):
        lookup = {}
        with pytest.raises(KeyError, match="Missing data"):
            MOD.get_value_with_fallback(lookup, 2001, 2, 29, 1)


# ---------------------------------------------------------------------------
# build_target_segments
# ---------------------------------------------------------------------------


class TestBuildTargetSegments:
    """Test master datetime index and segment generation."""

    def test_single_day(self):
        master, segments = MOD.build_target_segments("2025-01-01 00:00", "2025-01-01 23:00")
        assert len(master) == 24
        assert len(segments) == 1
        year, dates = segments[0]
        assert year == 2025
        assert len(dates) == 24

    def test_cross_year_boundary(self):
        master, segments = MOD.build_target_segments("2024-12-31 00:00", "2025-01-01 23:00")
        assert len(segments) == 2
        years = [s[0] for s in segments]
        assert years == [2024, 2025]

    def test_master_index_matches_segments_total(self):
        master, segments = MOD.build_target_segments("2025-01-01 00:00", "2025-01-02 23:00")
        total = sum(len(dates) for _, dates in segments)
        assert total == len(master)


# ---------------------------------------------------------------------------
# find_initial_aligned_date
# ---------------------------------------------------------------------------


class TestFindInitialAlignedDate:
    """Test day-of-week alignment for climate years."""

    def test_same_dow_returns_same_date(self):
        """When the same month/day in climate year has matching DOW, return it directly."""
        # 2025-01-01 is a Wednesday
        horizon = date(2025, 1, 1)
        # Find a climate year where Jan 1 is also Wednesday
        # 2014-01-01 is a Wednesday
        result = MOD.find_initial_aligned_date(horizon, 2014)
        assert result.weekday() == horizon.weekday()
        assert result.year == 2014

    def test_different_dow_finds_nearby(self):
        """When DOW differs, the returned date stays in-year and matches DOW."""
        horizon = date(2025, 10, 1)  # Wednesday
        result = MOD.find_initial_aligned_date(horizon, 1990)
        assert result.year == 1990
        assert result.weekday() == horizon.weekday()

    def test_jan_1_boundary_can_require_five_day_forward_search(self):
        """If the closer backward match falls outside the year, search forward within the year."""
        horizon = date(2025, 1, 1)  # Wednesday
        result = MOD.find_initial_aligned_date(horizon, 1999)
        assert result == date(1999, 1, 6)
        assert result.weekday() == horizon.weekday()

    def test_year_boundary_prefers_closest_in_year_match(self):
        """A valid in-year match near Jan 1 can be farther than three days away."""
        horizon = date(2025, 1, 1)  # Wednesday
        result = MOD.find_initial_aligned_date(horizon, 2010)
        assert result == date(2010, 1, 6)
        assert result.weekday() == horizon.weekday()

    def test_returned_date_in_climate_year(self):
        result = MOD.find_initial_aligned_date(date(2026, 6, 15), 2000)
        assert result.year == 2000

    def test_feb29_horizon_in_non_leap_climate_year(self):
        """Feb 29 horizon date clamps to Feb 28 in a non-leap climate year, then
        searches nearby in-year dates for a matching day-of-week."""
        horizon = date(2000, 2, 29)  # leap year — valid horizon date; Tuesday
        result = MOD.find_initial_aligned_date(horizon, 1999)  # non-leap year
        assert result.year == 1999
        assert result.weekday() == horizon.weekday()  # DOW must be preserved


# ---------------------------------------------------------------------------
# process_weather_profiles
# ---------------------------------------------------------------------------


class TestProcessWeatherProfiles:
    """Test the main profile processing function."""

    def test_nonexistent_profiles_path_returns_early(self, tmp_dir, capsys):
        """When profiles_path doesn't exist, prints warning and returns False."""
        result = MOD.process_weather_profiles(
            profiles_path=str(tmp_dir / "nonexistent.csv"),
            output_dir=str(tmp_dir / "out"),
            profile_type="Test",
        )
        assert result is False
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_generates_output_files(self, tmp_dir):
        """Profile processing creates one CSV per location."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "output"

        # Create full-year profile data for 2 climate years and 2 locations
        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982, 1983],
            locations=["LocA", "LocB"],
        )

        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Solar.csv"),
            output_dir=str(output_dir),
            profile_type="Solar",
            start_date="1982-01-01 00:00",
            end_date="1982-01-02 23:00",
            min_climate_year=1982,
            max_climate_year=1983,
        )

        assert result is True
        assert (output_dir / "LocA.csv").exists()
        assert (output_dir / "LocB.csv").exists()

    def test_output_csv_has_expected_columns(self, tmp_dir):
        """Output CSV has Year, Month, Day, Period, plus numbered sample columns."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "output"

        _write_profile_csv(
            profiles_dir / "Wind.csv",
            years=[1990, 1991],
            locations=["Site1"],
        )

        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Wind.csv"),
            output_dir=str(output_dir),
            profile_type="Wind",
            start_date="1990-01-01 00:00",
            end_date="1990-01-01 23:00",
            min_climate_year=1990,
            max_climate_year=1991,
        )

        assert result is True
        df = pd.read_csv(output_dir / "Site1.csv")
        assert "Year" in df.columns
        assert "Month" in df.columns
        assert "Day" in df.columns
        assert "Period" in df.columns
        # 2 climate years → 2 sample columns ("1" and "2")
        assert "1" in df.columns
        assert "2" in df.columns

    def test_output_csv_row_count_matches_hours(self, tmp_dir):
        """Number of rows equals the number of hours in the horizon."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "output"

        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982],
            locations=["LocX"],
        )

        # 2 days = 48 hours
        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Solar.csv"),
            output_dir=str(output_dir),
            start_date="1982-01-01 00:00",
            end_date="1982-01-02 23:00",
            min_climate_year=1982,
            max_climate_year=1982,
        )

        assert result is True
        df = pd.read_csv(output_dir / "LocX.csv")
        assert len(df) == 48

    def test_creates_output_dir_if_missing(self, tmp_dir):
        """Output directory is created automatically."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "nested" / "deep" / "output"

        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982],
            locations=["A"],
        )

        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Solar.csv"),
            output_dir=str(output_dir),
            start_date="1982-01-01 00:00",
            end_date="1982-01-01 23:00",
            min_climate_year=1982,
            max_climate_year=1982,
        )

        assert result is True
        assert output_dir.exists()

    def test_no_matching_climate_years_prints_fail(self, tmp_dir, capsys):
        """When min/max filter excludes all years in the CSV, prints [FAIL] and returns."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "output"

        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982, 1983],
            locations=["LocA"],
        )

        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Solar.csv"),
            output_dir=str(output_dir),
            start_date="1982-01-01 00:00",
            end_date="1982-01-01 23:00",
            min_climate_year=2000,
            max_climate_year=2010,
        )

        assert result is False
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out
        # No location CSVs written (early return after dir creation)
        assert not any(output_dir.glob("*.csv"))

    def test_invalid_date_range_returns_fail(self, tmp_dir, capsys):
        """When start_date is after end_date, prints [FAIL] and returns False."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "output"

        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982],
            locations=["LocA"],
        )

        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Solar.csv"),
            output_dir=str(output_dir),
            start_date="1982-01-02 00:00",
            end_date="1982-01-01 23:00",
            min_climate_year=1982,
            max_climate_year=1982,
        )

        assert result is False
        captured = capsys.readouterr()
        assert "[FAIL] Invalid date range" in captured.out
        assert not any(output_dir.glob("*.csv"))

    def test_invalid_datetime_format_returns_fail(self, tmp_dir, capsys):
        """Malformed datetime strings return False with a clear [FAIL] message."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "output"

        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982],
            locations=["LocA"],
        )

        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Solar.csv"),
            output_dir=str(output_dir),
            start_date="1982/01/01 00:00",
            end_date="1982-01-01 23:00",
            min_climate_year=1982,
            max_climate_year=1982,
        )

        assert result is False
        captured = capsys.readouterr()
        assert "[FAIL] Invalid datetime format" in captured.out
        assert not any(output_dir.glob("*.csv"))

    def test_feb29_horizon_reuses_feb28_for_non_leap_climate_year(self, tmp_dir):
        """Leap-day targets reuse Feb 28 values when the aligned climate year is non-leap."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        output_dir = tmp_dir / "output"

        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1999],
            locations=["LocA"],
        )

        result = MOD.process_weather_profiles(
            profiles_path=str(profiles_dir / "Solar.csv"),
            output_dir=str(output_dir),
            profile_type="Solar",
            start_date="2016-02-27 00:00",
            end_date="2016-03-01 23:00",
            min_climate_year=1999,
            max_climate_year=1999,
        )

        assert result is True

        df = pd.read_csv(output_dir / "LocA.csv")
        first_period = df[df["Period"] == 1].reset_index(drop=True)

        feb_27_value = round(1999 + 2 * 0.01 + 27 * 0.001 + 1 * 0.0001, 3)
        feb_28_value = round(1999 + 2 * 0.01 + 28 * 0.001 + 1 * 0.0001, 3)
        mar_1_value = round(1999 + 3 * 0.01 + 1 * 0.001 + 1 * 0.0001, 3)

        assert first_period[["Month", "Day"]].values.tolist() == [[2, 27], [2, 28], [2, 29], [3, 1]]
        assert first_period.loc[0, "1"] == pytest.approx(feb_27_value, rel=0, abs=1e-9)
        assert first_period.loc[1, "1"] == pytest.approx(feb_28_value, rel=0, abs=1e-9)
        assert first_period.loc[2, "1"] == pytest.approx(feb_28_value, rel=0, abs=1e-9)
        assert first_period.loc[3, "1"] == pytest.approx(mar_1_value, rel=0, abs=1e-9)


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------


class TestMain:
    """Test the main() entry point with simulated CLI arguments."""

    def test_profiles_dir_absolute_path_returns_early(self, tmp_dir, capsys):
        """main() rejects absolute profiles directories that bypass simulation_path."""
        absolute_profiles_dir = str((tmp_dir / "profiles").resolve())

        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", absolute_profiles_dir,
            "--files", "SomeFile.csv",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "[FAIL] --profiles-dir must be a relative path" in captured.out

    def test_profiles_dir_parent_traversal_returns_early(self, tmp_dir, capsys):
        """main() rejects profiles_dir values that escape simulation_path."""
        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "../outside",
            "--files", "SomeFile.csv",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "[FAIL] --profiles-dir escapes the allowed directory" in captured.out

    def test_profiles_dir_not_found_returns_early(self, tmp_dir, capsys):
        """main() prints error and returns 1 when profiles directory doesn't exist."""
        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "nonexistent",
            "--files", "SomeFile.csv",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_file_not_found_returns_early(self, tmp_dir, capsys):
        """main() prints error and returns 1 when a specified file doesn't exist in profiles directory."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()

        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "profiles",
            "--files", "nonexistent.csv",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_file_parent_traversal_returns_early(self, tmp_dir, capsys):
        """main() rejects file arguments that escape the resolved profiles directory."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()

        outside_file = tmp_dir / "outside.csv"
        outside_file.write_text("x", encoding="utf-8")

        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "profiles",
            "--files", "../outside.csv",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "[FAIL] --files escapes the allowed directory" in captured.out

    def test_successful_run(self, tmp_dir):
        """End-to-end: main() processes profiles and creates output CSVs in ExoSampled."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982, 1983],
            locations=["LocA"],
        )

        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "profiles",
            "--files", "Solar.csv",
            "--start-date", "1982-01-01 00:00",
            "--end-date", "1982-01-01 23:00",
            "--min-climate-year", "1982",
            "--max-climate-year", "1983",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 0
        # Output goes to ExoSampled sibling of profiles-dir
        output_csv = tmp_dir / "ExoSampled" / "Solar" / "LocA.csv"
        assert output_csv.exists()

    def test_multiple_files(self, tmp_dir):
        """main() processes multiple specified files."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982],
            locations=["LocA"],
        )
        _write_profile_csv(
            profiles_dir / "Wind.csv",
            years=[1982],
            locations=["LocB"],
        )

        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "profiles",
            "--files", "Solar.csv", "Wind.csv",
            "--start-date", "1982-01-01 00:00",
            "--end-date", "1982-01-01 23:00",
            "--min-climate-year", "1982",
            "--max-climate-year", "1982",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 0
        assert (tmp_dir / "ExoSampled" / "Solar" / "LocA.csv").exists()
        assert (tmp_dir / "ExoSampled" / "Wind" / "LocB.csv").exists()

    def test_no_matching_climate_years_returns_1(self, tmp_dir, capsys):
        """main() returns 1 when min/max filter excludes all years in a CSV."""
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()
        _write_profile_csv(
            profiles_dir / "Solar.csv",
            years=[1982, 1983],
            locations=["LocA"],
        )

        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "profiles",
            "--files", "Solar.csv",
            "--start-date", "1982-01-01 00:00",
            "--end-date", "1982-01-01 23:00",
            "--min-climate-year", "2000",
            "--max-climate-year", "2010",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out

    def test_url_encoded_args_are_decoded_in_main(self, tmp_dir):
        """main() strips task-runner quotes and URL-decodes directory and file arguments."""
        profiles_dir = tmp_dir / "my profiles"
        profiles_dir.mkdir()
        _write_profile_csv(
            profiles_dir / "Solar Profiles.csv",
            years=[1982],
            locations=["X"],
        )

        with patch.object(MOD.sys, "argv", [
            "sample_weather_years.py",
            "--profiles-dir", "'my%20profiles'",
            "--files", '"Solar%20Profiles.csv"',
            "--start-date", "1982-01-01 00:00",
            "--end-date", "1982-01-01 23:00",
            "--min-climate-year", "1982",
            "--max-climate-year", "1982",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
                result = MOD.main()

        assert result == 0
        # Output goes to ExoSampled sibling of "my profiles"
        output_csv = tmp_dir / "ExoSampled" / "Solar Profiles" / "X.csv"
        assert output_csv.exists()
