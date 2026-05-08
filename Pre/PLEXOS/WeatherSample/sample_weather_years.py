"""
Generate per-location weather sample CSV files from weather profile inputs.

Step 1 of the WeatherSample workflow. This script reads one or more weather
profile CSV files, applies climate-year day-of-week alignment, and writes
sampled outputs under ExoSampled/<input-file-stem>/.

Environment variables used:
    simulation_path - base path used to resolve --profiles-dir.
"""

import os
import sys
import argparse
import calendar
from datetime import date, datetime, timedelta
from urllib.parse import unquote

import pandas as pd

SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")

# --- Domain constants ---
DEFAULT_MIN_CLIMATE_YEAR = 1982
DEFAULT_MAX_CLIMATE_YEAR = 2016
DEFAULT_START_DATE = "2025-10-01 00:00"
DEFAULT_END_DATE = "2030-12-31 23:00"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
SAMPLE_ROUNDING_PRECISION = 3


# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION \u2014 These defaults are used when no command-line arguments are provided.
# ═══════════════════════════════════════════════════════════════════════════════
# Label for logs
PROFILE_TYPE = "Weather"

# Start datetime (YYYY-MM-DD HH:MM)
START_DATE = "2025-10-01 00:00"

# End datetime (YYYY-MM-DD HH:MM)
END_DATE = "2030-12-31 23:00"

# Minimum climate year for sampling
MIN_CLIMATE_YEAR = 1982

# Maximum climate year for sampling
MAX_CLIMATE_YEAR = 2016

# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════


def _normalize_cli_args(argv: list[str]) -> list[str]:
    """Normalize common Unicode dashes in option tokens to standard hyphen-minus."""
    dash_chars = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
    normalized: list[str] = []
    for arg in argv:
        if arg and arg[0] in f"-{dash_chars}":
            arg = arg.translate(str.maketrans({dash: "-" for dash in dash_chars}))
        normalized.append(arg)
    return normalized


def _decode_cli_value(value: str) -> tuple[str, bool]:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    decoded_value = unquote(value.strip("'\""))
    return decoded_value, decoded_value != value


def _decode_cli_args(args: argparse.Namespace) -> int:
    """URL-decode string arguments and return the number of changed tokens."""
    changed_tokens = 0

    for field_name in ["profiles_dir", "profile_type", "start_date", "end_date"]:
        field_value = getattr(args, field_name, None)
        if isinstance(field_value, str):
            restored, changed = _decode_cli_value(field_value)
            if changed:
                changed_tokens += 1
            setattr(args, field_name, restored)

    # Handle list arguments (e.g. --files)
    for field_name in ["files"]:
        field_value = getattr(args, field_name, None)
        if isinstance(field_value, list):
            restored_list = []
            for item in field_value:
                if isinstance(item, str):
                    restored, changed = _decode_cli_value(item)
                    if changed:
                        changed_tokens += 1
                    restored_list.append(restored)
                else:
                    restored_list.append(item)
            setattr(args, field_name, restored_list)

    return changed_tokens


def _resolve_path_within(base_path: str, user_path: str, arg_name: str) -> str | None:
    """Resolve a user path and ensure it stays within the allowed base path."""
    if os.path.isabs(user_path):
        print(f"[FAIL] {arg_name} must be a relative path: {user_path}")
        return None

    resolved_base = os.path.abspath(base_path)
    resolved_path = os.path.abspath(os.path.join(resolved_base, user_path))

    try:
        if os.path.commonpath([resolved_base, resolved_path]) != resolved_base:
            print(f"[FAIL] {arg_name} escapes the allowed directory: {user_path}")
            return None
    except ValueError:
        print(f"[FAIL] {arg_name} escapes the allowed directory: {user_path}")
        return None

    return resolved_path


class CSVProcessor:
    """Handles CSV reading/writing with encoding detection and caching."""

    ENCODINGS = ['utf-8-sig', 'windows-1252', 'latin-1', 'cp1252', 'utf-8']
    _cache = {}

    @classmethod
    def read_csv(cls, file_path: str, use_cache: bool = True, **kwargs) -> pd.DataFrame:
        """Read CSV file trying multiple encodings. Optionally cache results."""
        if use_cache and file_path in cls._cache:
            return cls._cache[file_path].copy()

        for encoding in cls.ENCODINGS:
            try:
                df = pd.read_csv(file_path, encoding=encoding, **kwargs)
                if use_cache:
                    cls._cache[file_path] = df.copy()
                return df
            except (UnicodeDecodeError, UnicodeError, LookupError):
                continue
            except Exception:
                raise

        print(f"[WARN] Using errors='replace' for {file_path} due to encoding issues")
        df = pd.read_csv(file_path, encoding='utf-8', errors='replace', **kwargs)
        if use_cache:
            cls._cache[file_path] = df.copy()
        return df

    @staticmethod
    def write_csv(df: pd.DataFrame, file_path: str, create_dir: bool = True, **kwargs):
        """Write DataFrame to CSV with UTF-8-sig encoding."""
        if create_dir:
            dir_name = os.path.dirname(file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
        df.to_csv(file_path, index=False, encoding='utf-8-sig', **kwargs)


def build_year_location_lookup(df, location_col):
    """Create lookup dictionaries per year for fast (month, day, period) access."""
    return {
        year: group.set_index(['Month', 'Day', 'Period'])[location_col].to_dict()
        for year, group in df.groupby('Year')
    }


def get_value_with_fallback(year_lookup, climate_year, month, day, period):
    """Fetch hourly value for the requested keys; fallback for Feb 29 if needed."""
    key = (month, day, period)
    if key in year_lookup:
        return year_lookup[key]
    if month == 2 and day == 29:
        fallback_key = (2, 28, period)
        if fallback_key in year_lookup:
            return year_lookup[fallback_key]
    raise KeyError(f"Missing data for {climate_year} - {month}/{day} period {period}")


def build_target_segments(start_date, end_date):
    """Return master datetime index plus yearly segments between the provided bounds."""
    master_index = pd.date_range(start=start_date, end=end_date, freq='h')
    segments = []
    for year in master_index.year.unique():
        mask = master_index.year == year
        segments.append((year, master_index[mask]))
    return master_index, segments


def find_initial_aligned_date(horizon_start_date: date, climate_year: int) -> date:
    """
    Find the closest date in climate_year that matches the day of week of horizon_start_date.

    Args:
        horizon_start_date: The first date of the simulation horizon (e.g., Dec 10, 2025)
        climate_year: The climate year to search in (e.g., 1982)

    Returns:
        The closest date in climate_year with the same day of week as horizon_start_date
    """
    target_dow = horizon_start_date.weekday()

    try:
        same_date = date(climate_year, horizon_start_date.month, horizon_start_date.day)
        if same_date.weekday() == target_dow:
            return same_date
    except ValueError:
        last_day = calendar.monthrange(climate_year, horizon_start_date.month)[1]
        same_date = date(climate_year, horizon_start_date.month, min(horizon_start_date.day, last_day))

    for offset in range(1, 7):
        candidate = same_date - timedelta(days=offset)
        if candidate.year == climate_year and candidate.weekday() == target_dow:
            return candidate

        candidate = same_date + timedelta(days=offset)
        if candidate.year == climate_year and candidate.weekday() == target_dow:
            return candidate

    raise ValueError(
        f"Could not find an aligned start date for {horizon_start_date} in climate year {climate_year}"
    )


def process_weather_profiles(
    profiles_path,
    output_dir,
    profile_type="",
    start_date=DEFAULT_START_DATE,
    end_date=DEFAULT_END_DATE,
    min_climate_year=DEFAULT_MIN_CLIMATE_YEAR,
    max_climate_year=DEFAULT_MAX_CLIMATE_YEAR,
):
    """Generate per-location sample files from weather profiles."""
    if not os.path.exists(profiles_path):
        print(f"[WARN] {profile_type} profiles file not found: {profiles_path}")
        return False

    os.makedirs(output_dir, exist_ok=True)

    profiles_df = CSVProcessor.read_csv(profiles_path)

    meta_columns = {'Year', 'Month', 'Day', 'Period'}
    location_columns = [col for col in profiles_df.columns if col not in meta_columns]

    all_climate_years = sorted(profiles_df['Year'].unique().tolist())
    climate_years = [y for y in all_climate_years if min_climate_year <= y <= max_climate_year]
    total_samples = len(climate_years)

    if not climate_years:
        print(f"[FAIL] No climate years found in range [{min_climate_year}, {max_climate_year}] in {profiles_path}")
        return False

    profiles_df = profiles_df[profiles_df['Year'].isin(climate_years)]

    try:
        start_datetime = datetime.strptime(start_date, DATETIME_FORMAT)
        end_datetime = datetime.strptime(end_date, DATETIME_FORMAT)
    except ValueError:
        print(
            "[FAIL] Invalid datetime format. Expected 'YYYY-MM-DD HH:MM' "
            f"for start_date and end_date, got start_date={start_date!r}, end_date={end_date!r}"
        )
        return False

    if start_datetime > end_datetime:
        print(f"[FAIL] Invalid date range: start_date {start_date} is after end_date {end_date}")
        return False

    master_index, target_segments = build_target_segments(start_date, end_date)

    horizon_start_date = start_datetime.date()

    print(f"[OK] Generating {profile_type} samples for {len(location_columns)} locations...")
    print(f"[OK] Using {total_samples} climate years: {climate_years[0]} to {climate_years[-1]}")
    print(f"[OK] Horizon start: {horizon_start_date.strftime('%A %Y-%m-%d')}")

    print("[OK] Pre-computing date alignments...")
    alignment_cache = {}

    unique_dates = sorted({ts.date() for ts in master_index})

    for sample_idx in range(total_samples):
        starting_climate_year = climate_years[sample_idx]
        initial_aligned_date = find_initial_aligned_date(horizon_start_date, starting_climate_year)

        current_aligned_date = initial_aligned_date
        current_climate_year = starting_climate_year
        climate_year_idx = sample_idx

        prev_target_date = None

        for target_date in unique_dates:
            if prev_target_date is not None:
                days_diff = (target_date - prev_target_date).days
                if not (
                    target_date.month == 2
                    and target_date.day == 29
                    and not calendar.isleap(current_climate_year)
                ):
                    current_aligned_date = current_aligned_date + timedelta(days=days_diff)

                    if current_aligned_date.year > current_climate_year:
                        dec_31 = date(current_climate_year, 12, 31)
                        days_into_new_year = (current_aligned_date - dec_31).days

                        climate_year_idx = (climate_year_idx + 1) % total_samples
                        current_climate_year = climate_years[climate_year_idx]

                        current_aligned_date = date(current_climate_year, 1, days_into_new_year)
                    elif current_aligned_date.year < current_climate_year:
                        jan_1 = date(current_climate_year, 1, 1)
                        days_before_jan_1 = (current_aligned_date - jan_1).days

                        climate_year_idx = (climate_year_idx - 1) % total_samples
                        current_climate_year = climate_years[climate_year_idx]

                        dec_31_prev_year = date(current_climate_year, 12, 31)
                        current_aligned_date = dec_31_prev_year + timedelta(days=days_before_jan_1 + 1)

            alignment_cache[(sample_idx, target_date)] = (current_climate_year, current_aligned_date)
            prev_target_date = target_date

    print(f"[OK] Pre-computed {len(alignment_cache)} date alignments")

    for location in location_columns:
        location_lookup = build_year_location_lookup(
            profiles_df[['Year', 'Month', 'Day', 'Period', location]], location
        )

        samples = {}

        for sample_idx in range(total_samples):
            sample_values = []

            for segment_year, segment_dates in target_segments:
                for timestamp in segment_dates:
                    period = timestamp.hour + 1
                    target_date = timestamp.date()

                    aligned_year, aligned_date = alignment_cache[(sample_idx, target_date)]
                    year_lookup = location_lookup[aligned_year]

                    value = get_value_with_fallback(
                        year_lookup, aligned_year, aligned_date.month, aligned_date.day, period
                    )
                    sample_values.append(value)

            samples[str(sample_idx + 1)] = sample_values

        samples_df = pd.DataFrame(samples, index=master_index)
        samples_df = samples_df.apply(pd.to_numeric, errors='coerce').round(SAMPLE_ROUNDING_PRECISION)
        metadata = pd.DataFrame(
            {
                'Year': master_index.year.astype(int),
                'Month': master_index.month.astype(int),
                'Day': master_index.day.astype(int),
                'Period': (master_index.hour + 1).astype(int),
            }
        )
        output_df = pd.concat([metadata.reset_index(drop=True), samples_df.reset_index(drop=True)], axis=1)

        output_path = os.path.join(output_dir, f"{location}.csv")
        CSVProcessor.write_csv(output_df, output_path)
        print(f"[OK] Saved samples for {location} to {output_path}")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate per-location weather sample CSVs.")
    parser.add_argument("--profiles-dir", required=True, help="Folder containing weather profile CSV files")
    parser.add_argument("--files", nargs="+", required=True, help="One or more CSV file names inside profiles-dir to process")
    parser.add_argument("--profile-type", default=PROFILE_TYPE, help="Label for logs")
    parser.add_argument("--start-date", default=START_DATE, help="Start datetime (YYYY-MM-DD HH:MM)")
    parser.add_argument("--end-date", default=END_DATE, help="End datetime (YYYY-MM-DD HH:MM)")
    parser.add_argument("--min-climate-year", type=int, default=MIN_CLIMATE_YEAR, help="Minimum climate year")
    parser.add_argument("--max-climate-year", type=int, default=MAX_CLIMATE_YEAR, help="Maximum climate year")

    args = parser.parse_args(_normalize_cli_args(sys.argv[1:]))
    replaced = _decode_cli_args(args)
    if replaced:
        print(f"[OK] Decoded {replaced} argument(s)")

    simulation_path = SIMULATION_PATH
    profiles_dir = _resolve_path_within(simulation_path, args.profiles_dir, "--profiles-dir")
    if profiles_dir is None:
        return 1

    if not os.path.isdir(profiles_dir):
        print(f"[FAIL] Profiles directory not found: {profiles_dir}")
        return 1

    # Validate that all specified files exist
    csv_files = []
    for file_name in args.files:
        file_path = _resolve_path_within(profiles_dir, file_name, "--files")
        if file_path is None:
            return 1
        if not os.path.isfile(file_path):
            print(f"[FAIL] File not found: {file_path}")
            return 1
        csv_files.append((file_name, file_path))

    # Output to "ExoSampled" folder at the same level as profiles-dir
    base_output_dir = os.path.join(os.path.dirname(profiles_dir), "ExoSampled")
    print(f"[OK] {base_output_dir}")
    print(f"[OK] {len(csv_files)} CSV file(s): {', '.join(file_name for file_name, _ in csv_files)}")

    failed = False
    for csv_file, profiles_path in csv_files:
        file_label = os.path.splitext(csv_file)[0]
        output_dir = os.path.join(base_output_dir, file_label)

        print(f"\n{'='*60}")
        print(f"[OK] {csv_file}")
        print(f"[OK] {output_dir}")

        ok = process_weather_profiles(
            profiles_path=profiles_path,
            output_dir=output_dir,
            profile_type=f"{args.profile_type} - {file_label}",
            start_date=args.start_date,
            end_date=args.end_date,
            min_climate_year=args.min_climate_year,
            max_climate_year=args.max_climate_year,
        )
        if ok is False:
            failed = True

    if failed:
        return 1
    print("[OK] All weather profiles processed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
