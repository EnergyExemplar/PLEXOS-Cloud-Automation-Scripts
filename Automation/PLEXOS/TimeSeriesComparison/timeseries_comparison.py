"""
Time Series Data Comparison Tool

A robust framework for comparing two datasets from various file formats (CSV, Excel, Parquet, JSON)
with automatic column detection, flexible datetime handling, and comprehensive analysis.

Use from command line: python timeseries_comparison.py -f ... -o ... -c ... -e ...

Use by importing:
  from TimeSeriesComparison.timeseries_comparison import TimeSeriesComparator, DataHubManager
  manager = DataHubManager(cli_path, environment)
  comparator = TimeSeriesComparator(file_paths=[...], output_datahub_path=..., datahub_manager=manager, ...)
  comparator.run()
"""

import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Union
import warnings
import argparse
import sys
from datetime import datetime
import json
import os
import tempfile
import shutil
import re
import time
from itertools import combinations

# Reuse DataHub logic from other automation scripts
_automation_root = Path(__file__).resolve().parent.parent
if str(_automation_root) not in sys.path:
    sys.path.insert(0, str(_automation_root))
from DownloadFromDataHub.download_from_datahub import DataHubDownloader
from UploadToDataHub.upload_to_datahub import DataHubUploader

warnings.filterwarnings('ignore')

# Set plotting style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (14, 6)

# Output paths; set in main() before running comparator
OUTPUT_PATH = None
DOWNLOAD_PATH = None

__all__ = ["TimeSeriesComparator", "DataHubManager"]


def _json_safe(obj):
    """Recursively replace NaN/Inf floats with None for valid JSON serialization."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        val = obj.item()
        if isinstance(val, float) and not math.isfinite(val):
            return None
        return val
    return obj


class DataHubManager:
    """Thin adapter that delegates to DataHubDownloader and DataHubUploader."""

    def __init__(self, cli_path: Optional[str] = None, environment: Optional[str] = None):
        self.cli_path = cli_path
        self.environment = environment
        self._downloader = DataHubDownloader(cli_path, environment) if (cli_path and environment) else None
        self._uploader = DataHubUploader(cli_path, environment) if (cli_path and environment) else None

    def set_environment(self, environment: str) -> None:
        self.environment = environment
        if self.cli_path and environment:
            self._downloader = DataHubDownloader(self.cli_path, environment)
            self._uploader = DataHubUploader(self.cli_path, environment)

    def download(self, datahub_path: str, temp_dir: str) -> str:
        if not self._downloader:
            raise RuntimeError("DataHub manager not configured (cli_path and environment required)")
        local_path = self._downloader.download_file(datahub_path, Path(temp_dir))
        return str(local_path)

    def upload(self, local_file_path: str, datahub_path: str) -> bool:
        if not self._uploader:
            return False
        try:
            self._uploader.upload_directory(Path(local_file_path), datahub_path, pattern="*", overwrite=True)
            return True
        except Exception as e:
            print(f"❌ Failed to upload to DataHub: {str(e)}")
            return False


class TimeSeriesComparator:
    """Main class for time series comparison."""
    
    def __init__(self, file_paths: List[str],
                 output_datahub_path: str,
                 datahub_manager: Optional['DataHubManager'] = None,
                 timestamp_cols: Optional[List[Optional[str]]] = None,
                 value_cols_list: Optional[List[Optional[List[str]]]] = None,
                 datetime_components_list: Optional[List[Optional[List[str]]]] = None,
                 group_cols_list: Optional[List[Optional[List[str]]]] = None,
                 join_type: str = 'outer',
                 missing_strategy: str = 'none',
                 drop_zero_diff: bool = True,
                 value_aliases_list: Optional[List[Optional[List[str]]]] = None,
                 datetime_alias: Optional[str] = None,
                 output_folder_name: Optional[str] = None):
        """
        Initialize the comparator.
        
        Args:
            file_paths: List of file paths (2 to 4 files)
            output_datahub_path: DataHub path where results will be stored
            datahub_manager: DataHubManager instance for upload/download operations
            timestamp_cols: List of timestamp columns per file (None for auto-detect)
            value_cols_list: List of value column lists per file (None for auto-detect)
            datetime_components_list: List of datetime component lists per file
            group_cols_list: List of group column lists per file (None if already pivoted)
            join_type: Type of join ('inner', 'outer', 'left', 'right')
            missing_strategy: Strategy for missing values ('none', 'drop', 'forward_fill', 'backward_fill', 'interpolate')
            drop_zero_diff: Whether to drop records with zero difference
            value_aliases_list: Optional list of value column aliases per file (maps 1:1 to value columns)
            datetime_alias: Optional output name for the parsed datetime column
            output_folder_name: Optional custom folder name for output (default: Comparison_<timestamp>)
        """
        if len(file_paths) < 2:
            raise ValueError("file_paths must contain at least 2 files")
        
        # Limit to 4 files maximum, use only the first 4 if more are provided
        if len(file_paths) > 4:
            print(f"[WARNING] WARNING: {len(file_paths)} files provided, but maximum 4 files are supported.")
            print(f"[ACTION] Using only the first 4 files: {file_paths[:4]}")
            self.file_paths = file_paths[:4]
        else:
            self.file_paths = file_paths
        self.output_datahub_path = output_datahub_path
        self.datahub_manager = datahub_manager
        self.output_folder_name = output_folder_name
        file_count = len(self.file_paths)
        self.timestamp_cols = (timestamp_cols or [None] * file_count)[:file_count]
        self.value_cols_list = (value_cols_list or [None] * file_count)[:file_count]
        self.datetime_components_list = (datetime_components_list or [None] * file_count)[:file_count]
        self.group_cols_list = (group_cols_list or [None] * file_count)[:file_count]
        self.join_type = join_type
        self.missing_strategy = missing_strategy
        self.drop_zero_diff = drop_zero_diff
        self.value_aliases_list = (value_aliases_list or [None] * file_count)[:file_count]
        self.datetime_alias = datetime_alias
        self.file_labels = [f"File {i + 1}" for i in range(len(self.file_paths))]
        self.original_value_cols_list = [None] * len(self.file_paths)
        self.value_col_alias_maps = [None] * len(self.file_paths)
        self.pre_merge_missing_counts = []
        
        self.df_list = [None] * len(self.file_paths)
        self.aligned_df = None
        self.metrics = {}
        self.output_dir = None
        self.missing_handling_info = {}
    
    def load_data_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """Load data from CSV, Excel, Parquet, or JSON file."""
        path = Path(file_path)
        
        if not path.exists():
            print(f"❌ ERROR: File not found: {file_path}")
            return None
        
        if not path.is_file():
            print(f"❌ ERROR: Path is not a file: {file_path}")
            return None
        
        suffix = path.suffix.lower()
        
        try:
            if suffix == '.csv':
                # Specify encoding explicitly with fallback for non-UTF8 files
                try:
                    df = pd.read_csv(file_path, dtype_backend='numpy_nullable', encoding='utf-8')
                except UnicodeDecodeError:
                    print(f"[INFO] UTF-8 decoding failed, trying latin-1 encoding...")
                    df = pd.read_csv(file_path, dtype_backend='numpy_nullable', encoding='latin-1')
                print(f"[OK] Loaded CSV file: {path.name}")
            elif suffix in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
                print(f"[OK] Loaded Excel file: {path.name}")
            elif suffix == '.parquet':
                df = pd.read_parquet(file_path)
                print(f"[OK] Loaded Parquet file: {path.name}")
            elif suffix == '.json':
                df = pd.read_json(file_path)
                print(f"[OK] Loaded JSON file: {path.name}")
            else:
                print(f"❌ ERROR: Unsupported file format: {suffix}")
                print("   Supported formats: .csv, .xlsx, .xls, .parquet, .json")
                return None
            
            return df
            
        except Exception as e:
            print(f"❌ ERROR loading file {path.name}: {str(e)}")
            return None
    
    def detect_datetime_column(self, df: pd.DataFrame, file_label: str) -> Optional[str]:
        """Auto-detect datetime column in DataFrame."""
        print(f"\n[DETECT] Auto-detecting datetime column in {file_label}...")
        
        # First check for columns with datetime-like dtypes
        for col in df.columns:
            # Check for datetime64 (including timezone-aware)
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                print(f"[OK] Found datetime column by datatype: '{col}' (dtype: {df[col].dtype})")
                return col
            
            # Check for Period dtype (e.g., period[D], period[M])
            if isinstance(df[col].dtype, pd.PeriodDtype):
                print(f"[OK] Found period datetime column: '{col}' (dtype: {df[col].dtype})")
                return col
            
            # Check for object dtype that might contain datetime objects
            if df[col].dtype == 'object' and len(df[col]) > 0:
                # Sample first non-null value
                sample = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else None
                if sample is not None and isinstance(sample, (pd.Timestamp, datetime)):
                    print(f"[OK] Found datetime column (object dtype with datetime objects): '{col}'")
                    return col
        
        # Common datetime column names
        common_names = ['timestamp', 'datetime', 'date', 'time', 'dt', 'date_time', 
                       'created_at', 'updated_at', 'time_stamp']
        
        # Check for common names
        for col in df.columns:
            if col.lower() in common_names:
                print(f"[OK] Found datetime column by name: '{col}'")
                return col
        
        # Try parsing each column
        for col in df.columns:
            # Skip numeric columns to avoid false positives (e.g., year columns like 2020, 2021)
            if pd.api.types.is_numeric_dtype(df[col]):
                continue
            
            try:
                # Try to parse as datetime first (before uniqueness check)
                test_series = pd.to_datetime(df[col], errors='coerce')
                
                # If more than 70% parsed successfully, consider it a datetime column
                # Note: We check parsing FIRST before uniqueness to catch legitimate datetime columns
                # that have 100% unique values (one per row)
                valid_ratio = test_series.notna().sum() / len(df)
                if valid_ratio > 0.7:
                    print(f"[OK] Detected datetime column: '{col}' ({valid_ratio*100:.1f}% valid)")
                    return col
            except:
                continue
        
        # Check for datetime component columns
        component_patterns = {
            'year': ['year', 'yr', 'yyyy'],
            'month': ['month', 'mon', 'mm'],
            'day': ['day', 'dd'],
            'hour': ['hour', 'hr', 'hh'],
            'minute': ['minute', 'min'],
            'second': ['second', 'sec', 'ss']
        }
        
        found_components = {}
        for comp_type, patterns in component_patterns.items():
            for col in df.columns:
                if any(pattern in col.lower() for pattern in patterns):
                    found_components[comp_type] = col
                    break
        
        if 'year' in found_components:
            print(f"[OK] Found datetime components: {found_components}")
            return None  # Signal that components were found
        
        print(f"[WARNING] WARNING: Could not auto-detect datetime column in {file_label}")
        print(f"   Available columns: {', '.join(df.columns)}")
        return None
    
    def detect_datetime_components(self, df: pd.DataFrame, file_label: str) -> Optional[List[str]]:
        """Detect datetime component columns (year, month, day, etc.)."""
        component_patterns = {
            'year': ['year', 'yr', 'yyyy'],
            'month': ['month', 'mon', 'mm'],
            'day': ['day', 'dd'],
            'hour': ['hour', 'hh'],
            'minute': ['minute', 'min'],
            'second': ['second', 'sec', 'ss']
        }
        
        found_components = []
        
        # Special handling for 'period' column as hour
        for col in df.columns:
            if col.lower().strip() == 'period':
                if pd.api.types.is_numeric_dtype(df[col]):
                    min_val = df[col].min()
                    max_val = df[col].max()
                    # If values are between 0-24, treat as hour
                    if min_val >= 0 and max_val <= 24:
                        found_components.append(col)
                        print(f"[OK] Detected 'period' column as hour component in {file_label} (range: {min_val}-{max_val})")
                        # Mark this as hour so we don't detect it again
                        component_patterns['hour'].append('period')
                        break
        
        for comp_type, patterns in component_patterns.items():
            for col in df.columns:
                col_lower = col.lower().strip()
                # Skip if already found
                if col in found_components:
                    continue
                # Check if column name exactly matches or is primarily a datetime component
                # Avoid matching columns like "HR-Okoli" that just contain 'hr'
                if col_lower in patterns or any(col_lower == pattern for pattern in patterns):
                    found_components.append(col)
                    break
                # Also allow columns that start/end with the pattern and are short
                elif len(col_lower) <= 10 and any(
                    col_lower.startswith(pattern) or col_lower.endswith(pattern) 
                    for pattern in patterns
                ):
                    # Additional check: must be numeric or look like a datetime component
                    if pd.api.types.is_numeric_dtype(df[col]) or col_lower.replace('_', '').isalnum():
                        found_components.append(col)
                        break
        
        if len(found_components) >= 2:  # At least year and month/day
            print(f"[OK] Detected datetime components in {file_label}: {found_components}")
            return found_components
        
        return None
    
    def parse_datetime_column(self, df: pd.DataFrame, col: str, file_label: str) -> Optional[pd.DataFrame]:
        """Parse datetime column with flexible format detection."""
        # [OPTIMIZATION] Only copy when necessary, not at start
        
        try:
            # Try standard parsing first
            df['_parsed_datetime'] = pd.to_datetime(df[col], format='mixed', errors='coerce')
            
            valid_ratio = df['_parsed_datetime'].notna().sum() / len(df)
            
            if valid_ratio > 0.7:
                print(f"[OK] {file_label}: Parsed datetime column '{col}' ({valid_ratio*100:.1f}% valid)")
                return df
            
            # Try different formats
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%d/%m/%Y',
                '%m/%d/%Y',
                '%Y/%m/%d',
                '%d-%m-%Y',
                '%m-%d-%Y',
                '%Y%m%d',
                '%Y',  # Year only
                '%Y-%m',  # Year-month
            ]
            
            for fmt in formats:
                try:
                    parsed = pd.to_datetime(df[col], format=fmt, errors='coerce')
                    valid = parsed.notna().sum() / len(df)
                    if valid > valid_ratio:
                        df['_parsed_datetime'] = parsed
                        valid_ratio = valid
                        if valid_ratio > 0.95:
                            print(f"[OK] {file_label}: Parsed datetime using format '{fmt}'")
                            break
                except:
                    continue
            
            # Try Unix timestamp
            try:
                if pd.api.types.is_numeric_dtype(df[col]):
                    # Check if it's in seconds or milliseconds
                    sample_val = df[col].iloc[0]
                    if sample_val > 1e9 and sample_val < 1e10:  # Seconds
                        parsed = pd.to_datetime(df[col], unit='s', errors='coerce')
                    elif sample_val > 1e12:  # Milliseconds
                        parsed = pd.to_datetime(df[col], unit='ms', errors='coerce')
                    else:
                        parsed = pd.Series([pd.NaT] * len(df))
                    
                    valid = parsed.notna().sum() / len(df)
                    if valid > valid_ratio:
                        df['_parsed_datetime'] = parsed
                        valid_ratio = valid
                        print(f"[OK] {file_label}: Parsed Unix timestamp")
            except:
                pass
            
            if valid_ratio > 0.5:
                print(f"[OK] {file_label}: Final datetime parsing ({valid_ratio*100:.1f}% valid)")
                return df
            else:
                print(f"❌ {file_label}: Could not parse datetime column '{col}'")
                return None
                
        except Exception as e:
            print(f"❌ {file_label}: Error parsing datetime: {str(e)}")
            return None
    
    def create_datetime_from_components(self, df: pd.DataFrame, components: List[str],
                                       file_label: str) -> Optional[pd.DataFrame]:
        """Create datetime from component columns (year, month, day, etc.)."""
        try:
            # Build datetime from available components
            datetime_dict = {}
            
            for col in components:
                # Skip non-numeric columns
                if not pd.api.types.is_numeric_dtype(df[col]):
                    print(f"[WARNING] {file_label}: Skipping non-numeric column '{col}'")
                    continue
                    
                col_lower = col.lower().strip()
                if col_lower in ['year', 'yr', 'yyyy'] or col_lower == 'year':
                    # Convert to integer to avoid floating point issues
                    datetime_dict['year'] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif col_lower in ['month', 'mon', 'mm'] or col_lower == 'month':
                    datetime_dict['month'] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif col_lower in ['day', 'dd'] or col_lower == 'day':
                    datetime_dict['day'] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif col_lower in ['hour', 'hh'] or col_lower == 'hour':
                    datetime_dict['hour'] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif col_lower in ['minute', 'min'] or col_lower == 'minute':
                    datetime_dict['minute'] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif col_lower in ['second', 'sec', 'ss'] or col_lower == 'second':
                    datetime_dict['second'] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            
            # Set defaults for missing components (as integers)
            if 'month' not in datetime_dict:
                datetime_dict['month'] = 1
            if 'day' not in datetime_dict:
                datetime_dict['day'] = 1
            if 'hour' not in datetime_dict:
                datetime_dict['hour'] = 0
            if 'minute' not in datetime_dict:
                datetime_dict['minute'] = 0
            if 'second' not in datetime_dict:
                datetime_dict['second'] = 0
            
            # Create datetime, ensuring no fractional seconds
            df['_parsed_datetime'] = pd.to_datetime(datetime_dict, errors='coerce')
            
            # Normalize to remove any time component if only date components provided
            has_time_components = any(k in datetime_dict for k in ['hour', 'minute', 'second'])
            if not has_time_components:
                # Normalize to midnight (00:00:00) by removing time component
                df['_parsed_datetime'] = df['_parsed_datetime'].dt.normalize()
            
            valid_ratio = df['_parsed_datetime'].notna().sum() / len(df)
            print(f"[OK] {file_label}: Created datetime from components ({valid_ratio*100:.1f}% valid)")
            
            return df
            
        except Exception as e:
            print(f"❌ {file_label}: Error creating datetime from components: {str(e)}")
            return None
    
    def detect_value_columns(self, df: pd.DataFrame, datetime_col: Optional[str], 
                            datetime_components: Optional[List[str]], file_label: str) -> List[str]:
        """Auto-detect numeric value columns using vectorized operations."""
        print(f"\n[DETECT] Auto-detecting value columns in {file_label}...")
        
        # Columns to exclude
        exclude_cols = set()
        if datetime_col:
            exclude_cols.add(datetime_col)
        if datetime_components:
            exclude_cols.update(datetime_components)
        if '_parsed_datetime' in df.columns:
            exclude_cols.add('_parsed_datetime')
        
        # [OPTIMIZATION] Use vectorized select_dtypes instead of looping through columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        value_cols = [col for col in numeric_cols if col not in exclude_cols]
        
        if value_cols:
            print(f"[OK] Detected {len(value_cols)} numeric columns: {value_cols}")
        else:
            print(f"[WARNING] WARNING: No numeric value columns found in {file_label}")
        
        return value_cols

    def apply_value_aliases(self, value_cols: List[str], aliases: Optional[List[str]], 
                           file_label: str) -> Tuple[Optional[List[str]], Optional[Dict[str, str]]]:
        """Apply per-value aliases to value columns.

        Args:
            value_cols: Original value columns
            aliases: Alias list (must match length of value_cols)
            file_label: Label for logging

        Returns:
            Tuple of (aliased column list, alias map). If aliases is None, returns originals and None.
        """
        if not aliases:
            return value_cols, None

        if len(aliases) != len(value_cols):
            print(f"\n❌ FAILED: Alias count mismatch for {file_label}")
            print(f"   Value columns ({len(value_cols)}): {value_cols}")
            print(f"   Aliases ({len(aliases)}): {aliases}")
            return None, None

        cleaned_aliases = []
        for col, alias in zip(value_cols, aliases):
            if alias is None or (isinstance(alias, str) and alias.strip() == ''):
                print(f"[WARNING] WARNING: Empty alias for {file_label} column '{col}'. Using original name.")
                cleaned_aliases.append(col)
            else:
                cleaned_aliases.append(alias.strip() if isinstance(alias, str) else alias)

        alias_map = {col: alias for col, alias in zip(value_cols, cleaned_aliases)}

        # Note: Duplicate detection now happens early in main() before file downloads
        # This check remains as a safety net in case method is called independently
        if len(set(cleaned_aliases)) != len(cleaned_aliases):
            duplicates = [alias for alias in set(cleaned_aliases) if cleaned_aliases.count(alias) > 1]
            raise ValueError(f"❌ ERROR: Duplicate aliases detected for {file_label}: {duplicates}. "
                           f"Each alias must be unique to prevent column overwrites. "
                           f"All aliases: {cleaned_aliases}")

        return cleaned_aliases, alias_map
    
    def pivot_flat_data(self, df: pd.DataFrame, group_cols: List[str], 
                       value_col: str, file_label: str) -> pd.DataFrame:
        """
        Pivot flat/long format data to wide format.
        
        Args:
            df: DataFrame in flat format
            group_cols: Columns to group by (e.g., ['category', 'region'])
            value_col: The value column to pivot
            file_label: Label for messages
            
        Returns:
            Pivoted DataFrame
        """
        print(f"\n[PIVOT] Pivoting flat data for {file_label}...")
        print(f"   Group columns: {group_cols}")
        print(f"   Value column: {value_col}")
        
        try:
            # Create a pivot table
            # Assuming timestamp is already parsed as '_parsed_datetime'
            timestamp_col = '_parsed_datetime'
            
            # Build the grouping structure
            pivot_cols = group_cols.copy()
            
            # Pivot: rows=timestamp, columns=group_cols, values=value_col
            if len(pivot_cols) == 1:
                pivoted = df.pivot_table(
                    index=timestamp_col,
                    columns=pivot_cols[0],
                    values=value_col,
                    aggfunc='first'  # Use first if duplicates
                )
            else:
                # Multiple grouping columns - create hierarchical columns
                pivoted = df.pivot_table(
                    index=timestamp_col,
                    columns=pivot_cols,
                    values=value_col,
                    aggfunc='first'
                )
            
            # Flatten column names if hierarchical
            if isinstance(pivoted.columns, pd.MultiIndex):
                pivoted.columns = ['_'.join(map(str, col)).strip() for col in pivoted.columns.values]
            
            # Reset index to make timestamp a column again
            pivoted = pivoted.reset_index()
            
            print(f"[OK] Pivoted to {len(pivoted.columns)-1} value columns")
            print(f"   New columns: {[col for col in pivoted.columns if col != timestamp_col]}")
            
            return pivoted
            
        except Exception as e:
            print(f"❌ ERROR pivoting data for {file_label}: {str(e)}")
            return None
    
    def process_flat_format(self, df: pd.DataFrame, group_cols: List[str], 
                           value_cols: List[str], file_label: str) -> Tuple[pd.DataFrame, List[str]]:
        """
        Process flat format data by pivoting it.
        
        Args:
            df: DataFrame with flat format
            group_cols: Columns to group by
            value_cols: Value columns to pivot
            file_label: Label for messages
            
        Returns:
            Tuple of (pivoted DataFrame, list of new value column names)
        """
        if len(value_cols) == 0:
            print(f"[WARNING] WARNING: No value columns to pivot for {file_label}")
            return df, []
        
        all_pivoted_dfs = []
        all_new_cols = []
        
        for value_col in value_cols:
            pivoted = self.pivot_flat_data(df, group_cols, value_col, file_label)
            if pivoted is not None:
                all_pivoted_dfs.append(pivoted)
                # Get new column names (excluding timestamp)
                new_cols = [col for col in pivoted.columns if col != '_parsed_datetime']
                all_new_cols.extend(new_cols)
        
        if not all_pivoted_dfs:
            return df, []
        
        # [OPTIMIZATION] Merge all pivoted dataframes on timestamp with copy=False
        result_df = all_pivoted_dfs[0]
        for i in range(1, len(all_pivoted_dfs)):
            result_df = pd.merge(result_df, all_pivoted_dfs[i], 
                               on='_parsed_datetime', how='outer', copy=False)
        
        return result_df, all_new_cols
    
    def check_identical(self, df: pd.DataFrame, col1: str, col2: str) -> Dict[str, any]:
        """Check if two columns in a dataframe are identical."""
        # Check if values are identical
        identical = (df[col1] == df[col2]).all()
        
        if identical:
            return {'identical': True}
        
        # Find differences
        diff_count = (df[col1] != df[col2]).sum()
        diff_ratio = diff_count / len(df) * 100
        
        return {
            'identical': False,
            'reason': 'Values differ',
            'diff_count': diff_count,
            'diff_ratio': diff_ratio
        }
    
    def detect_gaps(self, df: pd.DataFrame, timestamp_col: str = '_parsed_datetime') -> pd.DataFrame:
        """Detect gaps in time series with improved frequency inference.
        
        Uses mode (most common interval) instead of median for better
        handling of irregular data. Only flags gaps significantly larger than typical.
        """
        df_sorted = df.sort_values(timestamp_col).reset_index(drop=True)
        
        # Calculate time differences
        time_diffs = df_sorted[timestamp_col].diff()
        
        # Remove NaT and filter out zero/negative diffs
        valid_diffs = time_diffs[time_diffs.notna() & (time_diffs > pd.Timedelta(0))]
        
        if len(valid_diffs) == 0:
            return pd.DataFrame()  # No valid differences to analyze
        
        # Use mode (most common interval) for frequency inference
        # This handles irregular data better than median
        try:
            # Round to nearest second to group similar timestamps
            rounded_diffs = valid_diffs.dt.round('1s')
            mode_diff = rounded_diffs.mode()[0] if len(rounded_diffs.mode()) > 0 else valid_diffs.median()
        except:
            # Fallback to median if mode calculation fails
            mode_diff = valid_diffs.median()
        
        # Use 3x threshold (more lenient than 2x) to reduce false positives
        threshold = mode_diff * 3
        gaps = df_sorted[time_diffs > threshold].copy()
        
        if len(gaps) > 0:
            gaps['gap_duration'] = time_diffs[gaps.index]
            gaps['gap_start'] = df_sorted.loc[gaps.index - 1, timestamp_col].values
            gaps['gap_end'] = gaps[timestamp_col].values
            
            print(f"\n[WARNING] Found {len(gaps)} gaps in time series")
            print(f"   Typical interval (mode): {mode_diff}")
            print(f"   Gap threshold (3x): {threshold}")
        
        return gaps
    
    def detect_anomalies(self, series: pd.Series, method: str = 'iqr') -> pd.Series:
        """Detect anomalies in a series using IQR or z-score method."""
        if method == 'iqr':
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            anomalies = (series < lower_bound) | (series > upper_bound)
        else:  # z-score
            z_scores = np.abs((series - series.mean()) / series.std())
            anomalies = z_scores > 3
        
        return anomalies
    
    def calculate_statistics(self, series: pd.Series, label: str) -> Dict[str, float]:
        """Calculate comprehensive statistics for a series using numpy for speed.
        
        [OPTIMIZATION] Uses numpy operations which are significantly faster than pandas.
        Handles NaN values gracefully.
        """
        try:
            # [OPTIMIZATION] Use numpy directly for ~5x faster computation
            valid_data = series.dropna().values
            missing_count = series.isna().sum()
            missing_pct = missing_count / len(series) * 100 if len(series) > 0 else 0
            
            if len(valid_data) == 0:
                return {
                    f'{label}_count': 0,
                    f'{label}_mean': np.nan,
                    f'{label}_median': np.nan,
                    f'{label}_std': np.nan,
                    f'{label}_min': np.nan,
                    f'{label}_max': np.nan,
                    f'{label}_q25': np.nan,
                    f'{label}_q75': np.nan,
                    f'{label}_skew': np.nan,
                    f'{label}_kurtosis': np.nan,
                    f'{label}_missing': missing_count,
                    f'{label}_missing_pct': missing_pct
                }
            
            stats = {
                f'{label}_count': len(valid_data),
                f'{label}_mean': np.mean(valid_data),
                f'{label}_median': np.median(valid_data),
                f'{label}_std': np.std(valid_data, ddof=1) if len(valid_data) > 1 else 0,
                f'{label}_min': np.min(valid_data),
                f'{label}_max': np.max(valid_data),
                f'{label}_q25': np.percentile(valid_data, 25),
                f'{label}_q75': np.percentile(valid_data, 75),
                f'{label}_skew': float(pd.Series(valid_data).skew()),
                f'{label}_kurtosis': float(pd.Series(valid_data).kurtosis()),
                f'{label}_missing': int(missing_count),
                f'{label}_missing_pct': float(missing_pct)
            }
            
            return stats
            
        except Exception as e:
            print(f"[WARNING] Error calculating statistics for '{label}': {str(e)}")
            # Return partial statistics with safe defaults
            return {
                f'{label}_count': series.count(),
                f'{label}_mean': np.nan,
                f'{label}_median': np.nan,
                f'{label}_std': np.nan,
                f'{label}_min': series.min(),
                f'{label}_max': series.max(),
                f'{label}_q25': np.nan,
                f'{label}_q75': np.nan,
                f'{label}_skew': np.nan,
                f'{label}_kurtosis': np.nan,
                f'{label}_missing': series.isna().sum(),
                f'{label}_missing_pct': series.isna().sum() / len(series) * 100 if len(series) > 0 else 0
            }
    
    def calculate_comparison_metrics(self, df: pd.DataFrame, col1: str, col2: str) -> Dict[str, float]:
        """Calculate comparison metrics between two columns.
        
        Handles NaN values gracefully by filtering them before calculations.
        """
        try:
            # Create mask for valid (non-NaN) values in both columns
            valid_mask = df[col1].notna() & df[col2].notna()
            
            if valid_mask.sum() == 0:
                # No valid data for comparison
                print(f"[WARNING] No valid (non-NaN) data points for comparison between {col1} and {col2}")
                return {
                    'MAE': np.nan,
                    'RMSE': np.nan,
                    'Correlation': np.nan,
                    'R_squared': np.nan,
                    'MAPE_pct': np.nan,
                    'Max_Error': np.nan,
                    'Mean_Bias': np.nan,
                    'Valid_Points': 0
                }
            
            # Extract valid values only
            y_true = df.loc[valid_mask, col1].values
            y_pred = df.loc[valid_mask, col2].values
            
            # Mean Absolute Error
            mae = np.mean(np.abs(y_true - y_pred))
            
            # Root Mean Squared Error
            rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
            
            # Correlation Coefficient
            if len(y_true) > 1:
                try:
                    correlation = np.corrcoef(y_true, y_pred)[0, 1]
                except:
                    correlation = np.nan
            else:
                correlation = 0
            
            # Mean Absolute Percentage Error
            # Exclude near-zero baseline values to avoid inflated MAPE
            zero_threshold = 1e-6
            non_zero_mask = np.abs(y_true) > zero_threshold
            if non_zero_mask.sum() > 0:
                mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
            else:
                mape = np.nan
            
            # Max Error
            max_error = np.max(np.abs(y_true - y_pred))
            
            # Mean Bias
            mean_bias = np.mean(y_pred - y_true)
            
            # R-squared
            ss_res = np.sum((y_true - y_pred) ** 2)
            ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            metrics = {
                'MAE': float(mae),
                'RMSE': float(rmse),
                'Correlation': float(correlation),
                'R_squared': float(r_squared),
                'MAPE_pct': float(mape),
                'Max_Error': float(max_error),
                'Mean_Bias': float(mean_bias),
                'Valid_Points': int(valid_mask.sum()),
                'Invalid_Points': int((~valid_mask).sum())
            }
            
            return metrics
            
        except Exception as e:
            print(f"[WARNING] Error calculating comparison metrics: {str(e)}")
            return {
                'MAE': np.nan,
                'RMSE': np.nan,
                'Correlation': np.nan,
                'R_squared': np.nan,
                'MAPE_pct': np.nan,
                'Max_Error': np.nan,
                'Mean_Bias': np.nan,
                'Error': str(e)
            }
    
    def align_dataframes(self, df_list: List[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Align multiple dataframes (2-4) on their datetime columns.
        
        [OPTIMIZATION] Uses copy=False to avoid unnecessary DataFrame copies during merge.
        """
        timestamp_col = '_parsed_datetime'
        
        prepared_dfs = []
        for idx, df in enumerate(df_list):
            # [OPTIMIZATION] Don't copy immediately, work with reference then select columns
            original_value_cols = self.original_value_cols_list[idx] or []
            alias_map = self.value_col_alias_maps[idx]
            
            if alias_map:
                rename_map = {col: alias_map[col] for col in original_value_cols if col in df.columns}
                df_prep = df.rename(columns=rename_map)
                renamed_cols = [rename_map[col] for col in original_value_cols if col in rename_map]
            else:
                file_suffix = str(idx + 1)
                rename_map = {col: f'{col}_{file_suffix}' for col in original_value_cols if col in df.columns}
                df_prep = df.rename(columns=rename_map)
                renamed_cols = [rename_map[col] for col in original_value_cols if col in rename_map]
            
            if len(set(renamed_cols)) != len(renamed_cols):
                print(f"[WARNING] WARNING: Duplicate value column names detected for File {idx+1}: {renamed_cols}")
            
            # Update value_cols_list to renamed columns for downstream comparisons
            self.value_cols_list[idx] = renamed_cols
            
            # [OPTIMIZATION] Keep only needed columns - this operation creates a new df automatically
            keep_cols = [timestamp_col] + [col for col in renamed_cols if col in df_prep.columns]
            df_prep = df_prep[keep_cols].drop_duplicates(subset=timestamp_col).sort_values(timestamp_col)
            prepared_dfs.append(df_prep)
        
        # [OPTIMIZATION] Use copy=False to avoid data duplication in memory
        aligned = prepared_dfs[0]
        for i in range(1, len(prepared_dfs)):
            aligned = pd.merge(aligned, prepared_dfs[i], on=timestamp_col, how=self.join_type, copy=False)
        
        print(f"\n=== Time Series Alignment ===")
        for idx, df_prep in enumerate(prepared_dfs):
            print(f"File {idx+1} time range: {df_prep[timestamp_col].min()} to {df_prep[timestamp_col].max()}")
        print(f"Join type: {self.join_type}")
        print(f"Aligned data points: {len(aligned)}")
        
        return aligned
    
    def handle_missing_values(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """Handle missing values in aligned dataframe.
        
        [OPTIMIZATION] Only copies df when necessary for in-place operations.
        Returns:
            Tuple of (processed DataFrame, dict with missing_before and missing_after counts)
        """
        # [OPTIMIZATION] Use vectorized isna().sum().sum() instead of looping
        initial_count = len(df)
        missing_before = int(df.isna().sum().sum())
        
        # Store missing counts per column before filling
        missing_per_col_before = {col: df[col].isna().sum() for col in df.columns if df[col].isna().sum() > 0}
        
        if missing_before == 0:
            print("[OK] No missing values to handle")
            return df, {'missing_before': 0, 'missing_after': 0, 'method': self.missing_strategy, 'rows_removed': 0}
        
        print(f"\n=== Handling Missing Values ===")
        print(f"Strategy: {self.missing_strategy}")
        print(f"Missing values before: {missing_before}")
        print(f"Missing by column:")
        for col, count in missing_per_col_before.items():
            print(f"  {col}: {count} NaN values")
        
        rows_removed = 0
        
        if self.missing_strategy == 'none':
            print(f"[OK] No action taken. NaN values will remain in the data.")
            print(f"   Comparison metrics will skip NaN values in calculations.")
            missing_after = missing_before
            
        elif self.missing_strategy == 'drop':
            df = df.dropna()
            rows_removed = initial_count - len(df)
            print(f"Removed {rows_removed} rows with missing values")
            missing_after = df.isna().sum().sum()
            
        elif self.missing_strategy == 'forward_fill':
            try:
                df = df.ffill()
                df = df.dropna()
                rows_removed = initial_count - len(df)
                print(f"Applied forward fill, then removed {rows_removed} remaining rows with missing values")
                missing_after = df.isna().sum().sum()
            except Exception as e:
                print(f"[WARNING] Error during forward fill: {str(e)}")
                missing_after = missing_before
            
        elif self.missing_strategy == 'backward_fill':
            try:
                df = df.bfill()
                df = df.dropna()
                rows_removed = initial_count - len(df)
                print(f"Applied backward fill, then removed {rows_removed} remaining rows with missing values")
                missing_after = df.isna().sum().sum()
            except Exception as e:
                print(f"[WARNING] Error during backward fill: {str(e)}")
                missing_after = missing_before
            
        elif self.missing_strategy == 'interpolate':
            try:
                # Exclude datetime columns from interpolation
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                datetime_cols = df.select_dtypes(include=['datetime64']).columns
                cols_to_interpolate = numeric_cols.difference(datetime_cols)
                
                if len(cols_to_interpolate) > 0:
                    df[cols_to_interpolate] = df[cols_to_interpolate].interpolate(method='linear')
                df = df.dropna()
                rows_removed = initial_count - len(df)
                print(f"Applied linear interpolation to {len(cols_to_interpolate)} numeric columns, then removed {rows_removed} remaining rows with missing values")
                missing_after = df.isna().sum().sum()
            except Exception as e:
                print(f"[WARNING] Error during interpolation: {str(e)}")
                missing_after = missing_before
        
        else:
            print(f"[WARNING] Unknown strategy: {self.missing_strategy}. Keeping data unchanged.")
            missing_after = missing_before
        
        print(f"Missing values after: {missing_after}")
        print(f"Final data points: {len(df)}")
        
        return df, {
            'missing_before': missing_before,
            'missing_after': missing_after,
            'method': self.missing_strategy,
            'rows_removed': rows_removed,
            'missing_per_column_before': missing_per_col_before
        }
    
    def plot_comparison(self, df: pd.DataFrame, col1: str, col2: str, metrics: Dict[str, float]):
        """Create comparison visualizations for two columns.
        
        Handles NaN values by plotting only valid data points and showing NaN indicators.
        """
        try:
            fig, axes = plt.subplots(3, 1, figsize=(14, 12))
            
            # Create mask for valid (non-NaN) values
            valid_mask = df[col1].notna() & df[col2].notna()
            valid_count = valid_mask.sum()
            total_count = len(df)
            
            if valid_count == 0:
                print(f"[WARNING] Cannot create plot: No valid data points for {col1} vs {col2}")
                plt.close()
                return
            
            # Plot 1: Overlaid time series
            axes[0].plot(df['_parsed_datetime'], df[col1], label=f'File 1: {col1}', 
                         color='blue', alpha=0.7, linewidth=1.5, marker='o', markersize=2)
            axes[0].plot(df['_parsed_datetime'], df[col2], label=f'File 2: {col2}', 
                         color='red', alpha=0.7, linewidth=1.5, marker='s', markersize=2)
            
            # Highlight NaN regions
            nan_regions = ~valid_mask
            if nan_regions.sum() > 0:
                axes[0].axvspan(df.loc[nan_regions, '_parsed_datetime'].min(),
                               df.loc[nan_regions, '_parsed_datetime'].max(),
                               alpha=0.2, color='gray', label='NaN regions')
            
            axes[0].set_xlabel('Timestamp', fontsize=12)
            axes[0].set_ylabel('Value', fontsize=12)
            axes[0].set_title(f'Time Series Comparison: {col1} vs {col2} (Valid: {valid_count}/{total_count})', 
                             fontsize=14, fontweight='bold')
            axes[0].legend(loc='best')
            axes[0].grid(True, alpha=0.3)
            
            # Plot 2: Difference over time (only for valid data)
            difference = df[col2] - df[col1]
            axes[1].plot(df.loc[valid_mask, '_parsed_datetime'], difference[valid_mask], 
                        color='green', linewidth=1.5, marker='o', markersize=2)
            axes[1].axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
            axes[1].fill_between(df.loc[valid_mask, '_parsed_datetime'], 0, difference[valid_mask], 
                                where=(difference[valid_mask] >= 0), color='green', alpha=0.3, label='Positive')
            axes[1].fill_between(df.loc[valid_mask, '_parsed_datetime'], 0, difference[valid_mask], 
                                where=(difference[valid_mask] < 0), color='red', alpha=0.3, label='Negative')
            axes[1].set_xlabel('Timestamp', fontsize=12)
            axes[1].set_ylabel('Difference (File2 - File1)', fontsize=12)
            axes[1].set_title('Difference Over Time', fontsize=14, fontweight='bold')
            axes[1].legend(loc='best')
            axes[1].grid(True, alpha=0.3)
            
            # Plot 3: Scatter plot (only valid data)
            axes[2].scatter(df.loc[valid_mask, col1], df.loc[valid_mask, col2], 
                           alpha=0.5, s=20, color='purple')
            
            if valid_count > 0:
                # Perfect correlation line
                valid_col1 = df.loc[valid_mask, col1]
                valid_col2 = df.loc[valid_mask, col2]
                min_val = min(valid_col1.min(), valid_col2.min())
                max_val = max(valid_col1.max(), valid_col2.max())
                axes[2].plot([min_val, max_val], [min_val, max_val], 
                            'r--', linewidth=2, label='Perfect Correlation')
                
                # Regression line (only if we have enough points)
                if valid_count > 1:
                    try:
                        z = np.polyfit(valid_col1, valid_col2, 1)
                        p = np.poly1d(z)
                        axes[2].plot(valid_col1, p(valid_col1), 
                                    'b-', linewidth=2, alpha=0.7, label=f'Fit: y={z[0]:.2f}x+{z[1]:.2f}')
                    except Exception as e:
                        print(f"[WARNING] Could not calculate regression line: {str(e)}")
            
            correlation_str = f"{metrics.get('Correlation', np.nan):.4f}" if not np.isnan(metrics.get('Correlation', np.nan)) else "N/A"
            axes[2].set_xlabel(f'File 1: {col1}', fontsize=12)
            axes[2].set_ylabel(f'File 2: {col2}', fontsize=12)
            axes[2].set_title(f'Scatter Plot (Correlation: {correlation_str}, Valid: {valid_count}/{total_count})', 
                             fontsize=14, fontweight='bold')
            axes[2].legend(loc='best')
            axes[2].grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Sanitize column names for filename (replace invalid characters)
            safe_col1 = col1.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            safe_col2 = col2.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            
            output_path = Path(self.output_dir) / f'comparison_{safe_col1}_vs_{safe_col2}.png'
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"[OK] Saved plot: {output_path.name}")
            plt.close()
            
        except Exception as e:
            print(f"[WARNING] Error creating plot for {col1} vs {col2}: {str(e)}")
            plt.close()
    
    def validate_and_adjust_parameters(self):
        """Validate join_type and missing_strategy combination.
        
        If join_type is outer/left/right and missing_strategy is 'drop',
        automatically change to 'interpolate' to prevent data loss.
        """
        print("\n" + "="*70)
        print("Parameter Validation".center(70))
        print("="*70)
        
        print(f"\nCurrent Settings:")
        print(f"  Join Type: {self.join_type}")
        print(f"  Missing Strategy: {self.missing_strategy}")
        
        # Check if join_type is not 'inner' and missing_strategy is 'drop'
        if self.join_type != 'inner' and self.missing_strategy == 'drop':
            print(f"\n[WARNING] ⚠️ Incompatible combination detected!")
            print(f"  Join Type: {self.join_type.upper()} (will create missing values)")
            print(f"  Missing Strategy: drop (will DELETE matched rows)")
            print(f"\n[ACTION] Auto-adjusting missing_strategy to 'interpolate'")
            print(f"  Reason: Using 'drop' with {self.join_type.upper()} join would lose valid data")
            print(f"  'interpolate' will fill missing values instead of dropping rows")
            
            self.missing_strategy = 'interpolate'
            
            print(f"\n[OK] New Missing Strategy: {self.missing_strategy}")
        else:
            print(f"\n[OK] Parameters are compatible")
            if self.join_type == 'inner':
                print(f"  INNER join produces minimal missing values")
                print(f"  '{self.missing_strategy}' strategy is appropriate")
            else:
                print(f"  {self.join_type.upper()} join with '{self.missing_strategy}' strategy will work correctly")
        
        print("\n" + "="*70 + "\n")
    
    def run(self):
        """Execute the complete comparison pipeline."""
        # Start overall timing
        start_time_total = time.perf_counter()
        
        print("\n" + "="*70)
        print("TIME SERIES COMPARISON TOOL".center(70))
        print("="*70 + "\n")
        
        # Create output directory with optional custom prefix
        # OUTPUT_PATH is set in main(); fall back gracefully when used as a library.
        if OUTPUT_PATH is not None:
            base_output_dir = Path(OUTPUT_PATH)
        elif getattr(self, 'output_datahub_path', None):
            base_output_dir = Path(self.output_datahub_path)
        else:
            base_output_dir = Path.cwd() / "Output"
        base_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Always generate timestamp-based folder name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if self.output_folder_name:
            # Custom prefix provided: CustomPrefix_Comparison_20260211_143522
            folder_name = f'{self.output_folder_name}_Comparison_{timestamp}'
        else:
            # No custom prefix: Comparison_20260211_143522
            folder_name = f'Comparison_{timestamp}'
        
        self.output_dir = base_output_dir / folder_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"[FILE] Output directory: {self.output_dir}\n")
        
        # Step 1: Load files
        print("[1/8] Loading data files...")
        step_start = time.perf_counter()
        self.df_list = []
        for i, file_path in enumerate(self.file_paths):
            df = self.load_data_file(file_path)
            if df is None:
                print("\n❌ FAILED: Could not load files")
                return False
            self.df_list.append(df)
            print(f"   File {i+1}: {len(df)} rows, {len(df.columns)} columns")
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Loading completed in {step_duration:.2f} seconds\n")
        
        # Validate and adjust parameters
        self.validate_and_adjust_parameters()
        
        # Step 2: Detect or use datetime columns
        print("[2/8] Processing datetime columns...")
        step_start = time.perf_counter()
        for i, df in enumerate(self.df_list):
            label = self.file_labels[i]
            if self.datetime_components_list[i]:
                print(f"Using specified datetime components for {label}: {self.datetime_components_list[i]}")
                df = self.create_datetime_from_components(df, self.datetime_components_list[i], label)
            elif self.timestamp_cols[i]:
                print(f"Using specified timestamp column for {label}: '{self.timestamp_cols[i]}'")
                df = self.parse_datetime_column(df, self.timestamp_cols[i], label)
            else:
                detected_components = self.detect_datetime_components(df, label)
                if detected_components:
                    self.datetime_components_list[i] = detected_components
                    df = self.create_datetime_from_components(df, detected_components, label)
                else:
                    detected_ts = self.detect_datetime_column(df, label)
                    if detected_ts:
                        self.timestamp_cols[i] = detected_ts
                        df = self.parse_datetime_column(df, detected_ts, label)
            
            if df is None:
                print("\n❌ FAILED: Could not parse datetime columns")
                return False
            self.df_list[i] = df
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Datetime processing completed in {step_duration:.2f} seconds")
        
        # Step 3: Detect or use value columns
        print("\n[3/8] Identifying value columns...")
        step_start = time.perf_counter()
        for i, df in enumerate(self.df_list):
            label = self.file_labels[i]
            if not self.value_cols_list[i]:
                self.value_cols_list[i] = self.detect_value_columns(
                    df, self.timestamp_cols[i], self.datetime_components_list[i], label
                )
            if not self.value_cols_list[i]:
                print(f"\n❌ FAILED: No value columns identified for {label}")
                return False
            self.original_value_cols_list[i] = list(self.value_cols_list[i])
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Value column identification completed in {step_duration:.2f} seconds")
        
        # Step 3.5: Handle flat format if group columns are specified
        for i, df in enumerate(self.df_list):
            if self.group_cols_list[i]:
                label = self.file_labels[i]
                print(f"\n[3.5/8] Processing flat format for {label}...")
                df, new_cols = self.process_flat_format(
                    df, self.group_cols_list[i], self.value_cols_list[i], label
                )
                if df is None:
                    print(f"\n❌ FAILED: Could not pivot {label}")
                    return False
                self.df_list[i] = df
                self.value_cols_list[i] = new_cols
                self.original_value_cols_list[i] = list(new_cols)

        # Step 3.6: Apply per-value aliases (if provided)
        print("\n[3.6/8] Applying value column aliases...")
        for i in range(len(self.df_list)):
            label = self.file_labels[i]
            value_cols = self.original_value_cols_list[i] or []
            aliases = self.value_aliases_list[i] if i < len(self.value_aliases_list) else None
            aliased_cols, alias_map = self.apply_value_aliases(value_cols, aliases, label)
            if aliased_cols is None:
                return False
            self.value_cols_list[i] = aliased_cols
            self.value_col_alias_maps[i] = alias_map

        # Step 3.7: Capture missing counts before merging
        print("\n[3.7/8] Capturing missing values before merge...")
        self.pre_merge_missing_counts = []
        for i, df in enumerate(self.df_list):
            original_value_cols = self.original_value_cols_list[i] or []
            alias_map = self.value_col_alias_maps[i]

            if alias_map:
                rename_map = {col: alias_map[col] for col in original_value_cols if col in df.columns}
                cols_for_count = [rename_map[col] for col in original_value_cols if col in rename_map]
                df_for_count = df.rename(columns=rename_map)
            else:
                cols_for_count = [col for col in original_value_cols if col in df.columns]
                df_for_count = df

            missing_counts = {}
            for col in cols_for_count:
                missing_count = df_for_count[col].isna().sum()
                if missing_count > 0:
                    missing_counts[col] = int(missing_count)

            self.pre_merge_missing_counts.append({
                'file_path': str(self.file_paths[i]),
                'missing_values_per_column_before_merge': missing_counts if missing_counts else 'None'
            })
        
        # Step 4: Prepare comparison pairs
        print("\n[4/8] Preparing comparison pairs...")
        step_start = time.perf_counter()
        comparison_pairs = list(combinations(range(len(self.df_list)), 2))
        print(f"[OK] Total pairwise comparisons: {len(comparison_pairs)}")
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Comparison pairs prepared in {step_duration:.2f} seconds")
        
        # Step 5: Align dataframes
        print("\n[5/8] Aligning time series...")
        step_start = time.perf_counter()
        self.aligned_df = self.align_dataframes(self.df_list)
        
        if self.aligned_df is None or len(self.aligned_df) == 0:
            print("\n❌ FAILED: Could not align dataframes")
            return False
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Data alignment completed in {step_duration:.2f} seconds")
        
        # Step 6: Handle missing values
        print("\n[6/8] Handling missing values...")
        step_start = time.perf_counter()
        self.aligned_df, self.missing_handling_info = self.handle_missing_values(self.aligned_df)
        
        if len(self.aligned_df) == 0:
            print("\n❌ FAILED: No data remaining after handling missing values")
            return False
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Missing value handling completed in {step_duration:.2f} seconds")
        
        # Step 7: Detect gaps and anomalies
        print("\n[7/8] Detecting gaps and anomalies...")
        step_start = time.perf_counter()
        gaps = self.detect_gaps(self.aligned_df)
        if len(gaps) > 0:
            print(gaps[['gap_start', 'gap_end', 'gap_duration']].head())
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Gap/anomaly detection completed in {step_duration:.2f} seconds")
        
        # Step 8: Perform comparisons
        print("\n[8/8] Performing comparisons...")
        step_start = time.perf_counter()
        
        # Perform comparisons
        all_results = []
        
        for i, j in comparison_pairs:
            file_label_i = self.file_labels[i]
            file_label_j = self.file_labels[j]
            cols_i = self.value_cols_list[i] or []
            cols_j = self.value_cols_list[j] or []
            
            matching_cols = list(set(cols_i) & set(cols_j))
            pair_cols = []
            
            if matching_cols:
                for col in matching_cols:
                    pair_cols.append((col, col))
            else:
                for k in range(min(len(cols_i), len(cols_j))):
                    pair_cols.append((cols_i[k], cols_j[k]))
            
            for col_i, col_j in pair_cols:
                col_i_aligned = col_i
                col_j_aligned = col_j
                
                if col_i_aligned not in self.aligned_df.columns or col_j_aligned not in self.aligned_df.columns:
                    continue
                
                print(f"\n{'='*70}")
                print(f"Comparing: {col_i} ({file_label_i}) vs {col_j} ({file_label_j})".center(70))
                print(f"{'='*70}")
                
                # Check if identical
                identical_check = self.check_identical(
                    self.aligned_df, col_i_aligned, col_j_aligned
                )
                
                if identical_check['identical']:
                    print("\n[OK] COLUMNS ARE IDENTICAL!")
                else:
                    print(f"\n[WARNING] Columns are NOT identical:")
                    print(f"   Reason: {identical_check.get('reason', 'Unknown')}")
                    if 'diff_count' in identical_check:
                        print(f"   Different values: {identical_check['diff_count']} ({identical_check['diff_ratio']:.2f}%)")
                
                # Calculate statistics for each column
                print(f"\n--- Statistics for {col_i} ({file_label_i}) ---")
                stats1 = self.calculate_statistics(self.aligned_df[col_i_aligned], col_i)
                for key, value in stats1.items():
                    print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")
                
                # Detect anomalies
                anomalies1 = self.detect_anomalies(self.aligned_df[col_i_aligned])
                if anomalies1.sum() > 0:
                    print(f"[WARNING] Detected {anomalies1.sum()} anomalies ({anomalies1.sum()/len(anomalies1)*100:.2f}%)")
                
                print(f"\n--- Statistics for {col_j} ({file_label_j}) ---")
                stats2 = self.calculate_statistics(self.aligned_df[col_j_aligned], col_j)
                for key, value in stats2.items():
                    print(f"{key}: {value:.4f}" if isinstance(value, float) else f"{key}: {value}")
                
                # Detect anomalies
                anomalies2 = self.detect_anomalies(self.aligned_df[col_j_aligned])
                if anomalies2.sum() > 0:
                    print(f"[WARNING] Detected {anomalies2.sum()} anomalies ({anomalies2.sum()/len(anomalies2)*100:.2f}%)")
                
                # Calculate comparison metrics
                print(f"\n--- Comparison Metrics ---")
                metrics = self.calculate_comparison_metrics(
                    self.aligned_df, col_i_aligned, col_j_aligned
                )
                
                for key, value in metrics.items():
                    print(f"{key}: {value:.6f}")
                
                # Create visualizations
                print(f"\n--- Creating Visualizations ---")
                try:
                    self.plot_comparison(self.aligned_df, col_i_aligned, col_j_aligned, metrics)
                except Exception as e:
                    print(f"[WARNING] WARNING: Could not create plots: {str(e)}")
                
                # Store results
                result = {
                    'file1_label': file_label_i,
                    'file2_label': file_label_j,
                    'col1': col_i,
                    'col2': col_j,
                    'identical': identical_check,
                    'stats1': stats1,
                    'stats2': stats2,
                    'metrics': metrics,
                    'anomalies1_count': int(anomalies1.sum()),
                    'anomalies2_count': int(anomalies2.sum())
                }
                all_results.append(result)
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Comparisons completed in {step_duration:.2f} seconds")
        
        # Save summary
        print(f"\n{'='*70}")
        print("Saving comparison summary...")
        step_start = time.perf_counter()
        
        # Calculate time series range
        timestamp_col = '_parsed_datetime'
        time_range = {
            'start': str(self.aligned_df[timestamp_col].min()),
            'end': str(self.aligned_df[timestamp_col].max()),
            'total_periods': len(self.aligned_df)
        }
        
        # Calculate missing value counts per column
        missing_counts = {}
        for col in self.aligned_df.columns:
            if col != timestamp_col:
                missing_count = self.aligned_df[col].isna().sum()
                if missing_count > 0:
                    missing_counts[col] = int(missing_count)
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'files': [str(fp) for fp in self.file_paths],
            'num_files': len(self.file_paths),
            'time_series_range': time_range,
            'aligned_rows': len(self.aligned_df),
            'missing_values_per_file_before_merge': self.pre_merge_missing_counts,
            'missing_handling': self.missing_handling_info,
            'missing_values_per_column_after': missing_counts if missing_counts else 'None',
            'individual_stats': [
                {
                    'file_path': str(self.file_paths[idx]),
                    'rows_loaded': len(self.df_list[idx]),
                    'value_columns': self.value_cols_list[idx] or [],
                    'timestamp_column': self.timestamp_cols[idx],
                    'datetime_components': self.datetime_components_list[idx]
                }
                for idx in range(len(self.file_paths))
            ],
            'comparisons': all_results
        }
        
        # Save comparison summary (no need for file prefix since folder name includes it)
        summary_path = Path(self.output_dir) / 'comparison_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(_json_safe(summary), f, indent=2)
        print(f"[OK] Saved: {summary_path}")
        
        # Save aligned data with difference columns
        aligned_data_path = Path(self.output_dir) / 'aligned_data.parquet'
        aligned_with_diff = self.aligned_df.copy()
        
        # Track difference columns for potential filtering
        diff_columns = []
        comparison_columns = ['_parsed_datetime']  # Always keep timestamp internally
        
        # Add difference columns for each compared pair
        for i, j in comparison_pairs:
            cols_i = self.value_cols_list[i] or []
            cols_j = self.value_cols_list[j] or []
            
            matching_cols = list(set(cols_i) & set(cols_j))
            pair_cols = []
            
            if matching_cols:
                for col in matching_cols:
                    pair_cols.append((col, col))
            else:
                for k in range(min(len(cols_i), len(cols_j))):
                    pair_cols.append((cols_i[k], cols_j[k]))
            
            for col_i, col_j in pair_cols:
                col_i_aligned = col_i
                col_j_aligned = col_j
                
                if col_i_aligned in aligned_with_diff.columns and col_j_aligned in aligned_with_diff.columns:
                    # Add comparison columns to keep list
                    comparison_columns.append(col_i_aligned)
                    comparison_columns.append(col_j_aligned)
                    
                    # Create difference column
                    diff_col_name = f'Diff_F{i+1}_{col_i}_vs_F{j+1}_{col_j}'
                    aligned_with_diff[diff_col_name] = aligned_with_diff[col_j_aligned] - aligned_with_diff[col_i_aligned]
                    diff_columns.append(diff_col_name)
                    comparison_columns.append(diff_col_name)
        
        # Remove duplicate columns from comparison_columns list while preserving order
        comparison_columns = list(dict.fromkeys(comparison_columns))
        
        # Keep only comparison and diff columns
        removed_columns = [col for col in aligned_with_diff.columns if col not in comparison_columns]
        if removed_columns:
            print(f"\n[CLEANUP] Removing {len(removed_columns)} unused columns: {removed_columns}")
            aligned_with_diff = aligned_with_diff[comparison_columns]
        
        print(f"[OK] Keeping {len(comparison_columns)} columns for output:")
        for col in comparison_columns:
            print(f"   - {col}")
        
        # Apply drop_zero_diff filter if enabled
        if self.drop_zero_diff and diff_columns:
            initial_rows = len(aligned_with_diff)
            # Keep rows where at least one difference is non-zero and non-NaN
            # Drop rows where all differences are either 0 or NaN (no meaningful difference)
            mask = ~(
                ((aligned_with_diff[diff_columns] == 0) | aligned_with_diff[diff_columns].isna()).all(axis=1)
            )
            aligned_with_diff = aligned_with_diff[mask].reset_index(drop=True)
            removed_rows = initial_rows - len(aligned_with_diff)
            print(f"\n[FILTER] Dropped {removed_rows} records with zero or NaN differences")
            print(f"   Remaining records: {len(aligned_with_diff)}")
        
        # Apply datetime alias for output if provided
        if self.datetime_alias and '_parsed_datetime' in aligned_with_diff.columns:
            aligned_with_diff = aligned_with_diff.rename(columns={'_parsed_datetime': self.datetime_alias})
            comparison_columns = [self.datetime_alias if c == '_parsed_datetime' else c for c in comparison_columns]

        aligned_with_diff.to_parquet(aligned_data_path, index=False, compression='snappy')
        print(f"[OK] Saved: {aligned_data_path}")
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Output files saved in {step_duration:.2f} seconds")
        
        # Upload results to DataHub
        print(f"\n[UPLOAD] Uploading results to DataHub...")
        step_start = time.perf_counter()
        upload_successful = False
        
        # Create DataHub directory path - include the comparison folder name
        comparison_folder_name = self.output_dir.name  # e.g., "Comparison_20260205_124639"
        remote_folder = f"{self.output_datahub_path}/{comparison_folder_name}"
        
        # Upload entire output directory at once
        if self.datahub_manager:
            upload_successful = self.datahub_manager.upload(str(self.output_dir), remote_folder)
        else:
            print(f"[WARNING] No DataHub manager provided, skipping upload")
            print(f"          Target path: {remote_folder}")
        
        # Delete output directory if upload was successful
        if upload_successful:
            try:
                shutil.rmtree(self.output_dir)
                print(f"[OK] Deleted local output directory: {self.output_dir}")
            except Exception as e:
                print(f"[WARNING] Could not delete output directory: {str(e)}")
        else:
            print(f"[OK] Local results preserved at: {self.output_dir}")
        step_duration = time.perf_counter() - step_start
        print(f"⏱️  Upload completed in {step_duration:.2f} seconds")
        
        # Calculate total time
        total_duration = time.perf_counter() - start_time_total
        
        print(f"\n{'='*70}")
        print("[OK] COMPARISON COMPLETED SUCCESSFULLY".center(70))
        print(f"{'='*70}")
        print(f"\n⏱️  TOTAL TIME: {total_duration:.2f} seconds ({total_duration/60:.2f} minutes)\n")
        
        return True


def parse_quoted_items(text):
    """Parse comma-separated items, respecting double quotes for items with commas/spaces.
    
    Example: '"Total Demand","Power Output",SimpleCol' 
    Returns: ['Total Demand', 'Power Output', 'SimpleCol']
    """
    if not text or not text.strip():
        return None
    
    # Match either quoted strings or non-comma sequences
    pattern = r'"([^"]*)"|([^,]+)'
    matches = re.findall(pattern, text)
    
    # Extract non-empty groups from matches and strip whitespace
    items = [(group[0] if group[0] else group[1]).strip() for group in matches if any(group)]
    # Filter out empty items
    items = [item for item in items if item]
    return items if items else None


class FileConfigAction(argparse.Action):
    """Parse file configuration string with colon-delimited sections and comma-delimited items.
    
    Format: filepath:file_type:timestamp_cols:data_cols:group_cols:aliases
    Example: "my file.csv":datahub-filepath:year,month,day:"Total Demand","Total Supply":Category:actual,forecast
    
    Note: 
    - Use : to separate major sections (no quotes needed for entire arg)
    - Use , (comma) to separate items within sections
    - Quote only items with commas or spaces using double quotes (like "Total Demand")
    """
    def __call__(self, parser, namespace, values, option_string=None):
        current = getattr(namespace, self.dest, None)
        if current is None:
            current = []
        
        # Safer parsing for paths with colons (Windows paths, URIs, etc.)
        # Strategy: Split on ':', but rejoin if we detect a Windows drive letter pattern
        sections = values.split(':')
        
        # Handle Windows drive letters (e.g., C:\path or C:/path)
        # Pattern: single letter, followed by section starting with \ or /
        if len(sections) >= 2 and len(sections[0]) == 1 and sections[0].isalpha():
            if sections[1].startswith('\\') or sections[1].startswith('/'):
                # Recombine drive letter with path
                sections[0] = sections[0] + ':' + sections[1]
                sections.pop(1)
        
        # Ensure we have at least filepath
        if len(sections) < 1 or not sections[0].strip():
            parser.error(f"Invalid file configuration: missing filepath in '{values}'")
        
        # Pad sections to ensure we have 6 elements
        sections = sections + [''] * (6 - len(sections))
        
        # Strip leading/trailing whitespace from sections
        sections = [s.strip() for s in sections]
        
        file_config = {
            'filepath': sections[0],  # Keep filepath as-is (can contain spaces)
            'file_type': sections[1] if sections[1] else 'datahub-filepath',
            # Parse space-separated items, respecting double quotes for items with spaces
            'timestamp_cols': parse_quoted_items(sections[2]),
            'data_cols': parse_quoted_items(sections[3]),
            'group_cols': parse_quoted_items(sections[4]),
            'aliases': parse_quoted_items(sections[5])
        }
        
        current.append(file_config)
        setattr(namespace, self.dest, current)


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Compare 2-4 time-series datasets with automatic column detection and flexible file input',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Minimal - two files with auto-detection (creates Comparison_20260211_143522/)
  python timeseries_comparison.py \\
    -f "my file 1.csv":datahub-filepath \\
    -f "data set 2.csv":datahub-filepath \\
    -o /output/path -c /path/to/cli -e <your-environment>
  
  # Custom prefix - creates EU_Comparison_20260211_143522/
  python timeseries_comparison.py \\
    -f file1.csv:datahub-filepath \\
    -f file2.csv:local-filepath \\
    -o "/output/path:EU_Comparison" -c /path/to/cli -e <your-environment>
  
    # Full specification - comma-separated columns, quote items with commas/spaces!
    python timeseries_comparison.py \
        -f "forecast data.csv":datahub-filepath:year,month,day:"Total Demand","Total Supply":"Region Name":actual,forecast \
        -f "my local file.csv":local-filepath:year,month,day:"Power Output":"Fuel Type",Category:forecast \
        -f "C:/path with spaces/data.csv":local-filepath:timestamp:"Actual Value"::estimate \
        -o "/output/path:MyComparison" -c /path/to/cli -e <your-environment> \
        -ta DateTime -j outer -m interpolate -k
  
  # Mixed - some with full config, others with defaults
  python timeseries_comparison.py \\
    -f "forecast data.csv":local-filepath::demand,supply \\
    -f f2.csv::date \\
    -o /output/path -c /path/to/cli -e <your-environment>
  
  # No quotes needed when no commas or spaces!
  python timeseries_comparison.py \\
    -f file1.csv:datahub-filepath:year,month,day:demand,supply:Category:actual,forecast \\
    -f file2.csv:local-filepath:date:load,export \\
    -o "/output/path:LNG_Analysis" -c /path/to/cli -e <your-environment>

  # File Format: filepath:file_type:timestamp_cols:data_cols:group_cols:aliases
  # - filepath: Required (quote if spaces: "my file.csv")
  # - file_type: datahub-filepath (default), local-filepath
  # - timestamp_cols: Comma-separated columns or components
  # - data_cols: Comma-separated column names (quote items with commas/spaces: "Total Demand")
  # - group_cols: Comma-separated grouping columns (quote items with commas/spaces: "Region Name")
  # - aliases: Comma-separated aliases (1:1 with data_cols)
  # - Use : to separate sections, comma to separate items
  # - Quote only values with commas or spaces using double quotes (like "Total Demand")
  # - Empty sections (::) use auto-detection or defaults
  
  # Output Path Format:
  # - /path/to/output                    Creates: /path/to/output/Comparison_20260211_143522/
  # - /path/to/output:CustomPrefix       Creates: /path/to/output/CustomPrefix_Comparison_20260211_143522/
        """
    )
    
    # File configuration arguments (NEW FORMAT)
    parser.add_argument('-f', '--file', action=FileConfigAction, dest='file_configs',
                       help='File configuration: filepath:type:timestamp:data_cols:group_cols:aliases. '
                            'Use : for sections, comma for items. Quote values with commas/spaces. '
                            'Example: "my file.csv":datahub-filepath:year,month,day:"Total Demand",supply. '
                            'Repeat for each file.')
    
    # Required arguments
    parser.add_argument('-o', '--output-path', required=True, dest='output_path',
                       help='DataHub path where comparison results will be stored. '
                            'Optional custom prefix: /path/to/output or /path/to/output:CustomPrefix. '
                            'Will always create timestamped subfolder: /path/CustomPrefix_Comparison_20260211_143522/')
    parser.add_argument('-c', '--cli-path', required=True, dest='cli_path',
                       help='Path to PLEXOS Cloud CLI executable')
    parser.add_argument('-e', '--environment', required=True, dest='environment',
                       help='Cloud environment name (contact your Energy Exemplar administrator for the correct value)')
    
    # Output configuration
    parser.add_argument('-ta', '--timestamp-alias', default=None, dest='timestamp_alias',
                       help='Output name for timestamp column (default: _parsed_datetime)')
    
    # Processing options
    parser.add_argument('-j', '--alignment', default='union', dest='alignment',
                       choices=['intersection', 'union', 'use-first-file', 'use-last-file'],
                       help='Alignment method: intersection (matching dates only), union (all dates), use-first-file (keep first file dates), use-last-file (keep last file dates) (default: union)')
    parser.add_argument('-m', '--handle-missing', default='none', dest='handle_missing',
                       choices=['none', 'drop', 'forward_fill', 'backward_fill', 'interpolate'],
                       help='Missing value strategy: none/drop/forward_fill/backward_fill/interpolate (default: none)')
    parser.add_argument('-k', '--keep-diff-unchanged', dest='keep_diff_unchanged', action='store_true', default=False,
                       help='Keep records with zero/unchanged differences (default: remove them)')
    
    args = parser.parse_args()
    
    # Validate file configurations
    if not args.file_configs or len(args.file_configs) < 2:
        parser.error("Please provide at least 2 files using -f/--file argument")
    
    # Limit to 4 files maximum
    if len(args.file_configs) > 4:
        print(f"\n[WARNING] WARNING: {len(args.file_configs)} files provided, but maximum 4 files are supported.")
        print(f"[ACTION] Using only the first 4 files\n")
        args.file_configs = args.file_configs[:4]
    
    num_files = len(args.file_configs)
    
    # Parse output path and custom prefix from combined argument
    # Format: /path/to/output or /path/to/output:CustomPrefix
    output_path_parts = args.output_path.rsplit(':', 1)
    if len(output_path_parts) == 2:
        datahub_output_path = output_path_parts[0]
        custom_folder_prefix = output_path_parts[1]
    else:
        datahub_output_path = output_path_parts[0]
        custom_folder_prefix = None
    
    # Extract file paths and per-file configurations
    input_files = []
    file_types = []
    timestamp_cols = []
    datetime_components_list = []
    value_cols_list = []
    group_cols_list = []
    value_aliases_list = []
    
    for idx, config in enumerate(args.file_configs):
        input_files.append(config['filepath'])
        file_types.append(config['file_type'])
        
        # Handle timestamp columns (single col vs components)
        ts_cols = config['timestamp_cols']
        if ts_cols and len(ts_cols) == 1:
            timestamp_cols.append(ts_cols[0])
            datetime_components_list.append(None)
        elif ts_cols and len(ts_cols) > 1:
            timestamp_cols.append(None)
            datetime_components_list.append(ts_cols)
        else:
            timestamp_cols.append(None)
            datetime_components_list.append(None)
        
        value_cols_list.append(config['data_cols'])
        group_cols_list.append(config['group_cols'])
        value_aliases_list.append(config['aliases'])
    
    # EARLY VALIDATION: Check for duplicate aliases before downloading files
    # This saves time by failing fast before expensive file operations
    print(f"\n[VALIDATE] Checking aliases for duplicates...")
    for idx, (aliases, value_cols) in enumerate(zip(value_aliases_list, value_cols_list)):
        if aliases and len(aliases) > 0:
            # Clean aliases (handle empty/None values)
            cleaned_aliases = []
            for alias in aliases:
                if alias is None or (isinstance(alias, str) and alias.strip() == ''):
                    # Empty alias will use original column name - skip for now
                    continue
                cleaned_aliases.append(alias.strip() if isinstance(alias, str) else alias)
            
            # Check for duplicates in cleaned aliases
            if len(cleaned_aliases) > 0 and len(set(cleaned_aliases)) != len(cleaned_aliases):
                duplicates = [alias for alias in set(cleaned_aliases) if cleaned_aliases.count(alias) > 1]
                raise ValueError(f"❌ ERROR: Duplicate aliases detected in File {idx+1} configuration: {duplicates}. "
                               f"Each alias must be unique to prevent column overwrites. "
                               f"All aliases: {aliases}")
    print(f"[OK] All aliases are unique\n")
    
    # Map user-friendly alignment names to pandas join types
    alignment_mapping = {
        'intersection': 'inner',
        'union': 'outer',
        'use-first-file': 'left',
        'use-last-file': 'right'
    }
    join_type = alignment_mapping.get(args.alignment, 'outer')
    
    # Set module-level paths for local output and downloads (no environment variables)
    global OUTPUT_PATH, DOWNLOAD_PATH
    OUTPUT_PATH = Path('./Output').resolve()
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_PATH = Path(tempfile.mkdtemp(prefix='timeseries_comparison_datahub_'))
    
    # Initialize DataHub manager reusing DownloadFromDataHub and UploadToDataHub logic
    datahub_manager = DataHubManager(args.cli_path, args.environment)
    
    # Resolve file paths based on type
    file_paths = []
    failed_files = []
    valid_indices = []
    
    try:
        print(f"\n[INFO] Processing {num_files} files:\n")
        
        # Check if we need to download from DataHub
        needs_datahub_download = any(ft == 'datahub-filepath' for ft in file_types)
        if needs_datahub_download:
            print(f"[FILE] Using download directory: {DOWNLOAD_PATH}\n")
        
        # Resolve each file path
        for idx, (input_file, file_type) in enumerate(zip(input_files, file_types)):
            print(f"[FILE] File {idx+1}: {input_file} (type: {file_type})")
            
            try:
                if file_type == 'local-filepath':
                    resolved_path = input_file
                    if not Path(resolved_path).exists():
                        raise Exception(f"File not found: {resolved_path}")
                        
                elif file_type == 'datahub-filepath':
                    # Use the already-initialized datahub_manager
                    resolved_path = datahub_manager.download(input_file, DOWNLOAD_PATH)
                    
                else:
                    raise Exception(f"Unsupported file type: {file_type}")
                
                # If we got here, file was successfully resolved
                file_paths.append(resolved_path)
                valid_indices.append(idx)
                print(f"[OK] File {idx+1} successfully resolved\n")
                
            except Exception as e:
                # Skip this file and continue with others
                print(f"[WARNING] ⚠️ Skipping File {idx+1}: {str(e)}\n")
                failed_files.append({
                    'index': idx + 1,
                    'filepath': input_file,
                    'type': file_type,
                    'reason': str(e)
                })
        
        # Validate we have 2-4 valid files
        valid_count = len(file_paths)
        print("="*70)
        print(f"[INFO] File Resolution Summary:")
        print(f"   Total files provided: {num_files}")
        print(f"   Successfully resolved: {valid_count}")
        print(f"   Failed/Skipped: {len(failed_files)}")
        
        if failed_files:
            print(f"\n[INFO] Skipped Files:")
            for failed in failed_files:
                print(f"   File {failed['index']}: {failed['filepath']}")
                print(f"      Type: {failed['type']}")
                print(f"      Reason: {failed['reason']}")
        
        print("="*70 + "\n")
        
        if valid_count < 2:
            error_msg = f"❌ ERROR: Need at least 2 valid files for comparison, but only {valid_count} {'file was' if valid_count == 1 else 'files were'} successfully resolved."
            if failed_files:
                error_msg += f"\n\nFailed files ({len(failed_files)}):"
                for failed in failed_files:
                    error_msg += f"\n   • File {failed['index']}: {failed['filepath']} - {failed['reason']}"
            raise Exception(error_msg)
        
        if valid_count > 4:
            error_msg = f"❌ ERROR: Maximum 4 files supported, but {valid_count} files were successfully resolved."
            raise Exception(error_msg)
        
        print(f"[OK] Proceeding with {valid_count} valid files for comparison\n")
        
        # Filter configuration lists to only include valid files
        filtered_timestamp_cols = [timestamp_cols[i] for i in valid_indices]
        filtered_value_cols_list = [value_cols_list[i] for i in valid_indices]
        filtered_datetime_components_list = [datetime_components_list[i] for i in valid_indices]
        filtered_group_cols_list = [group_cols_list[i] for i in valid_indices]
        filtered_value_aliases_list = [value_aliases_list[i] for i in valid_indices]
        
        # Create comparator with resolved file paths and filtered configurations
        comparator = TimeSeriesComparator(
            file_paths=file_paths,
            output_datahub_path=datahub_output_path,
            datahub_manager=datahub_manager,
            timestamp_cols=filtered_timestamp_cols,
            value_cols_list=filtered_value_cols_list,
            datetime_components_list=filtered_datetime_components_list,
            group_cols_list=filtered_group_cols_list,
            join_type=join_type,
            missing_strategy=args.handle_missing,
            drop_zero_diff=not args.keep_diff_unchanged,
            value_aliases_list=filtered_value_aliases_list,
            datetime_alias=args.timestamp_alias,
            output_folder_name=custom_folder_prefix
        )
        
        # Run comparison
        success = comparator.run()
        
        sys.exit(0 if success else 1)
        
    finally:
        # Clean up DOWNLOAD_PATH in both cases (container and local)
        # Downloads are temporary and should be removed after comparison completes
        try:
            if os.path.exists(DOWNLOAD_PATH):
                shutil.rmtree(DOWNLOAD_PATH)
                print(f"\n[CLEANUP] Cleaned up download directory: {DOWNLOAD_PATH}")
        except Exception as e:
            print(f"[WARNING] Warning: Could not clean up download directory: {str(e)}")


if __name__ == '__main__':
    main()
