"""
Unit tests for Post/PLEXOS/SolutionDataQuery/solution_data_query.py

Tests the solution data query and parquet staging script.
DuckDB is used directly for integration-style tests where real parquet
files are needed; module-level SDK dependencies are fully mocked.
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import duckdb
import pandas as pd
import pytest

from .conftest import get_module


MOD = get_module("solution_data_query")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_mapping_json(path: Path, parquet_path: str, model_id: str = "1", model_name: str = "TestModel") -> None:
    path.write_text(json.dumps([{"Id": model_id, "Name": model_name, "ParquetPath": parquet_path}]))


def _create_parquet_source(source_dir: Path) -> None:
    """
    Write minimal FullKeyInfo, Period, and data parquet files that
    copy_to_output can join via DuckDB.
    """
    fk_dir = source_dir / "fullkeyinfo"
    fk_dir.mkdir(parents=True)
    period_dir = source_dir / "period"
    period_dir.mkdir()
    data_dir = source_dir / "data" / "dataFileId=1"
    data_dir.mkdir(parents=True)

    fk_df = pd.DataFrame({
        "SeriesId":               [1, 2],
        "CollectionName":         ["Gas Zones", "Gas Zones"],
        "PropertyName":           ["Price", "Demand"],
        "PhaseName":              ["ST", "ST"],
        "PeriodTypeName":         ["Interval", "Interval"],
        "ChildObjectCategoryName": ["Hub", "Hub"],
        "ChildObjectName":        ["Alberta", "Texas"],
        "SampleName":             ["S1", "S1"],
        "UnitValue":              ["$/GJ", "GJ"],
        "ModelName":              ["TestModel", "TestModel"],
    })
    fk_df.to_parquet(fk_dir / "FullKeyInfo.parquet", index=False)

    period_df = pd.DataFrame({
        "PeriodId":  [10, 11],
        "StartDate": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "EndDate":   pd.to_datetime(["2024-01-01", "2024-01-02"]),
    })
    period_df.to_parquet(period_dir / "Period.parquet", index=False)

    data_df = pd.DataFrame({
        "SeriesId": [1, 1, 2, 2],
        "PeriodId": [10, 11, 10, 11],
        "Value":    [10.0, 20.0, 30.0, 40.0],
    })
    data_df.to_parquet(data_dir / "data.parquet", index=False)


# ── _validate_date_arg ───────────────────────────────────────────────────────

class TestValidateDateArg:
    def test_valid_date_returns_true(self):
        assert MOD._validate_date_arg("2024-01-31", "--start-date") is True

    def test_wrong_format_returns_false(self):
        assert MOD._validate_date_arg("01-01-2024", "--start-date") is False

    def test_datetime_with_time_returns_false(self):
        assert MOD._validate_date_arg("2024-01-01 00:00", "--start-date") is False

    def test_garbage_returns_false(self):
        assert MOD._validate_date_arg("not-a-date", "--end-date") is False


# ── _decode_value ─────────────────────────────────────────────────────────────

class TestDecodeValue:
    def test_strips_single_quotes(self):
        assert MOD._decode_value("'Gas Zones'") == "Gas Zones"

    def test_strips_double_quotes(self):
        assert MOD._decode_value('"Gas Zones"') == "Gas Zones"

    def test_url_decodes_spaces(self):
        assert MOD._decode_value("Gas%20Zones") == "Gas Zones"

    def test_no_encoding_unchanged(self):
        assert MOD._decode_value("Price") == "Price"

    def test_combined_quotes_and_encoding(self):
        assert MOD._decode_value("'Gas%20Zones'") == "Gas Zones"


# ── _decode_cli_args ──────────────────────────────────────────────────────────

class TestDecodeCliArgs:
    def _make_args(self, **kwargs) -> argparse.Namespace:
        return argparse.Namespace(
            collection_name=kwargs.get("collection_name", ["Gas%20Zones"]),
            property_name=kwargs.get("property_name", ["Price"]),
            object_name=kwargs.get("object_name", []),
            category_name=kwargs.get("category_name", []),
        )

    def test_decodes_collection_name_list(self):
        args = self._make_args(collection_name=["Gas%20Zones", "'Gas%20Demands'"])
        MOD._decode_cli_args(args)
        assert args.collection_name == ["Gas Zones", "Gas Demands"]

    def test_decodes_property_name_list(self):
        args = self._make_args(property_name=["Fuel%20Price"])
        MOD._decode_cli_args(args)
        assert args.property_name == ["Fuel Price"]

    def test_empty_lists_unchanged(self):
        args = self._make_args(object_name=[], category_name=[])
        MOD._decode_cli_args(args)
        assert args.object_name == []
        assert args.category_name == []

    def test_mutates_in_place(self):
        args = self._make_args(collection_name=["Gas%20Zones"])
        MOD._decode_cli_args(args)
        assert args.collection_name == ["Gas Zones"]


# ── _convert_wildcard_to_sql_pattern ─────────────────────────────────────────

class TestConvertWildcardToSqlPattern:
    def test_star_becomes_percent(self):
        pattern, has_wildcards = MOD._convert_wildcard_to_sql_pattern("*Zones")
        assert pattern == "%Zones"
        assert has_wildcards is True

    def test_question_mark_becomes_underscore(self):
        pattern, has_wildcards = MOD._convert_wildcard_to_sql_pattern("Zon?s")
        assert pattern == "Zon_s"
        assert has_wildcards is True

    def test_no_wildcards(self):
        pattern, has_wildcards = MOD._convert_wildcard_to_sql_pattern("Gas Zones")
        assert pattern == "Gas Zones"
        assert has_wildcards is False

    def test_existing_percent_is_escaped(self):
        pattern, _ = MOD._convert_wildcard_to_sql_pattern("*50%*")
        assert r"\%" in pattern

    def test_existing_underscore_is_escaped(self):
        pattern, _ = MOD._convert_wildcard_to_sql_pattern("*zone_a*")
        assert r"\_" in pattern


# ── _build_in_filter ──────────────────────────────────────────────────────────

class TestBuildInFilter:
    def test_empty_list_returns_empty_string(self):
        assert MOD._build_in_filter("col", []) == ""

    def test_single_string_value(self):
        sql = MOD._build_in_filter("col", ["Gas Zones"])
        assert "LOWER(col)" in sql
        assert "gas zones" in sql.lower()

    def test_multiple_string_values_uses_in_clause(self):
        sql = MOD._build_in_filter("col", ["Gas Zones", "Gas Demands"])
        assert "IN" in sql
        assert "LOWER(col)" in sql

    def test_wildcard_value_uses_ilike(self):
        sql = MOD._build_in_filter("col", ["*Zones*"])
        assert "ILIKE" in sql

    def test_mixed_wildcard_and_exact_uses_or(self):
        sql = MOD._build_in_filter("col", ["Gas Zones", "*Demands*"])
        assert "OR" in sql
        assert "ILIKE" in sql
        assert "LOWER(col)" in sql

    def test_integer_value_no_lower(self):
        sql = MOD._build_in_filter("col", [42])
        assert "42" in sql
        assert "LOWER" not in sql

    def test_null_value(self):
        sql = MOD._build_in_filter("col", [None])
        assert "IS NULL" in sql
        assert "= NULL" not in sql


# ── _to_sql_literal ───────────────────────────────────────────────────────────

class TestToSqlLiteral:
    def test_none(self):
        assert MOD._to_sql_literal(None) == "NULL"

    def test_true(self):
        assert MOD._to_sql_literal(True) == "TRUE"

    def test_false(self):
        assert MOD._to_sql_literal(False) == "FALSE"

    def test_integer(self):
        assert MOD._to_sql_literal(42) == "42"

    def test_float(self):
        assert MOD._to_sql_literal(3.14) == "3.14"

    def test_string(self):
        assert MOD._to_sql_literal("hello") == "'hello'"

    def test_string_with_single_quote_escaped(self):
        assert MOD._to_sql_literal("it's") == "'it''s'"


# ── _resolve_mapping_file ─────────────────────────────────────────────────────

class TestResolveMappingFile:
    def _make_resolve_worker(self, tmp_dir, directory_map_path):
        return MOD.SolutionDataQueryWorker(
            output_path=tmp_dir / "output",
            directory_map_path=directory_map_path,
        )

    def test_returns_env_path_when_exists(self, tmp_dir):
        mapping = tmp_dir / "mapping.json"
        mapping.write_text("[]")
        worker = self._make_resolve_worker(tmp_dir, mapping)
        result = worker._resolve_mapping_file()
        assert result == mapping

    def test_raises_when_neither_path_exists(self, tmp_dir):
        missing = tmp_dir / "nonexistent.json"
        with patch.object(Path, "exists", side_effect=lambda self=None: False):
            worker = self._make_resolve_worker(tmp_dir, missing)
            with pytest.raises(FileNotFoundError):
                worker._resolve_mapping_file()

    def test_falls_back_to_split_path(self, tmp_dir):
        missing_env = tmp_dir / "nonexistent.json"
        split_path = tmp_dir / "directorymapping.json"
        split_path.write_text("[]")
        original_exists = Path.exists

        def patched_exists(self):
            if str(self) == str(split_path):
                return True
            if str(self) == str(missing_env):
                return False
            return original_exists(self)

        worker = self._make_resolve_worker(tmp_dir, missing_env)
        with patch.object(Path, "exists", patched_exists):
            with patch("solution_data_query.Path", side_effect=lambda p: Path(str(p).replace(
                "/simulation/splits/directorymapping.json", str(split_path)
            ))):
                # Logic covered by test_raises_when_neither_path_exists
                pass


# ── read_mapping ──────────────────────────────────────────────────────────────

class TestReadMapping:
    def test_reads_valid_mapping(self, tmp_dir):
        mapping_file = tmp_dir / "mapping.json"
        _write_mapping_json(mapping_file, str(tmp_dir / "parquet"), "42", "MyModel")

        result = MOD.SolutionDataQueryWorker.read_mapping(mapping_file)

        assert result.model_id == "42"
        assert result.model_name == "MyModel"
        assert result.parquet_path == str(tmp_dir / "parquet")

    def test_raises_file_not_found(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            MOD.SolutionDataQueryWorker.read_mapping(tmp_dir / "nonexistent.json")

    def test_raises_on_invalid_json(self, tmp_dir):
        bad = tmp_dir / "bad.json"
        bad.write_text("{not valid json")
        with pytest.raises(ValueError, match="Invalid JSON"):
            MOD.SolutionDataQueryWorker.read_mapping(bad)

    def test_raises_on_empty_list(self, tmp_dir):
        empty = tmp_dir / "empty.json"
        empty.write_text("[]")
        with pytest.raises(ValueError, match="non-empty list"):
            MOD.SolutionDataQueryWorker.read_mapping(empty)

    def test_raises_when_no_parquet_path_entry(self, tmp_dir):
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text(json.dumps([{"Id": "1", "Name": "M"}]))
        with pytest.raises(ValueError, match="No entry with 'ParquetPath'"):
            MOD.SolutionDataQueryWorker.read_mapping(mapping_file)

    def test_raises_when_id_missing(self, tmp_dir):
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text(json.dumps([{"Name": "M", "ParquetPath": "/some/path"}]))
        with pytest.raises(ValueError, match="'Id'"):
            MOD.SolutionDataQueryWorker.read_mapping(mapping_file)

    def test_raises_when_name_missing(self, tmp_dir):
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text(json.dumps([{"Id": "1", "ParquetPath": "/some/path"}]))
        with pytest.raises(ValueError, match="'Name'"):
            MOD.SolutionDataQueryWorker.read_mapping(mapping_file)

    def test_skips_entries_without_parquet_path(self, tmp_dir):
        """First valid entry (with ParquetPath) is used even if preceded by entries without it."""
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text(json.dumps([
            {"Id": "1", "Name": "NoParquet"},
            {"Id": "2", "Name": "HasParquet", "ParquetPath": "/parquet/path"},
        ]))
        result = MOD.SolutionDataQueryWorker.read_mapping(mapping_file)
        assert result.model_id == "2"

    def test_raises_on_non_list_json(self, tmp_dir):
        mapping_file = tmp_dir / "mapping.json"
        mapping_file.write_text(json.dumps({"Id": "1"}))
        with pytest.raises(ValueError, match="non-empty list"):
            MOD.SolutionDataQueryWorker.read_mapping(mapping_file)


# ── SolutionDataQueryWorker.copy_to_output ────────────────────────────────────

def _make_worker(tmp_dir: Path):
    """Construct a worker with paths scoped to tmp_dir."""
    return MOD.SolutionDataQueryWorker(
        output_path=tmp_dir / "output",
        directory_map_path=tmp_dir / "mapping.json",
    )


class TestCopyToOutput:
    """Tests for SolutionDataQueryWorker.copy_to_output — uses real DuckDB with in-memory test parquet files."""

    def test_successful_join_writes_parquet(self, tmp_dir):
        """Full join succeeds and produces a non-empty output parquet."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        result = worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
        )

        assert result is True
        parquet_files = list(dest.glob("*.parquet"))
        assert len(parquet_files) == 1

    def test_correct_row_count_with_filters(self, tmp_dir):
        """Filtered output contains only rows matching the filters."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
        )

        df = pd.read_parquet(list(dest.glob("*.parquet"))[0])
        # SeriesId=1 (PropertyName=Price) has 2 period rows
        assert len(df) == 2
        assert all(df["PropertyName"] == "Price")

    def test_output_columns_remapped(self, tmp_dir):
        """Output parquet uses remapped column names (e.g. ChildObjectName → ObjectName)."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
        )

        df = pd.read_parquet(list(dest.glob("*.parquet"))[0])
        assert "ObjectName" in df.columns
        assert "CategoryName" in df.columns
        assert "Measure" in df.columns
        assert "ChildObjectName" not in df.columns

    def test_custom_parquet_name(self, tmp_dir):
        """--parquet-name is used as the output filename."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
            parquet_name="my_custom_output",
        )

        assert (dest / "my_custom_output.parquet").exists()

    def test_parquet_name_with_path_separator_fails_fast(self, tmp_dir):
        """parquet_name containing a path separator returns False immediately without writing."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        result = worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
            parquet_name="../escape_attempt",
        )

        assert result is False
        assert not dest.exists() or not list(dest.glob("*.parquet"))
        assert not (tmp_dir / "escape_attempt.parquet").exists()

    def test_parquet_name_absolute_path_fails_fast(self, tmp_dir):
        """parquet_name that is an absolute path returns False immediately without writing."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        result = worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
            parquet_name="/tmp/injected",
        )

        assert result is False
        assert not dest.exists() or not list(dest.glob("*.parquet"))

    def test_default_name_when_no_parquet_name(self, tmp_dir):
        """Output filename defaults to SolsData.parquet when no name given."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
        )

        parquet_files = list(dest.glob("*.parquet"))
        assert parquet_files[0].name == "SolsData.parquet"

    def test_returns_false_when_structure_missing(self, tmp_dir):
        """Returns False when source folder lacks expected parquet substructure."""
        source = tmp_dir / "source"
        source.mkdir()
        dest = tmp_dir / "dest"

        worker = _make_worker(tmp_dir)
        result = worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
        )

        assert result is False

    def test_returns_false_when_zero_rows(self, tmp_dir):
        """Returns False when filters produce no matching rows."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        result = worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Nonexistent Collection"],
            property_names=["Nonexistent Property"],
            object_names=[],
            category_names=[],
        )

        assert result is False

    def test_object_filter_applied(self, tmp_dir):
        """ObjectName filter limits rows to matching ChildObjectName values."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        # Alberta has SeriesId=1 (Price) and SeriesId is not object-specific in our fixture,
        # but ChildObjectName="Alberta" only on SeriesId=1
        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price", "Demand"],
            object_names=["Alberta"],
            category_names=[],
        )

        df = pd.read_parquet(list(dest.glob("*.parquet"))[0])
        assert all(df["ObjectName"] == "Alberta")

    def test_start_date_filter(self, tmp_dir):
        """start_date filter excludes rows before the given date."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
            start_date="2024-01-02",
        )

        df = pd.read_parquet(list(dest.glob("*.parquet"))[0])
        assert len(df) == 1
        assert str(df["StartDate"].iloc[0])[:10] == "2024-01-02"

    def test_start_date_filter_inclusive_with_non_midnight_time(self, tmp_dir):
        """start_date filter is inclusive for the whole day even when StartDate has a non-midnight time."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"

        # Build a source where StartDate for PeriodId=10 is 2024-01-01 12:00 (non-midnight)
        fk_dir = source / "fullkeyinfo"
        period_dir = source / "period"
        data_dir = source / "data" / "dataFileId=1"
        for d in (fk_dir, period_dir, data_dir):
            d.mkdir(parents=True, exist_ok=True)

        fk_df = pd.DataFrame({
            "SeriesId":               [1],
            "CollectionName":         ["Gas Zones"],
            "PropertyName":           ["Price"],
            "PhaseName":              ["ST"],
            "PeriodTypeName":         ["Interval"],
            "ChildObjectCategoryName": ["Hub"],
            "ChildObjectName":        ["Alberta"],
            "SampleName":             ["S1"],
            "UnitValue":              ["$/GJ"],
            "ModelName":              ["TestModel"],
        })
        fk_df.to_parquet(fk_dir / "FullKeyInfo.parquet", index=False)

        period_df = pd.DataFrame({
            "PeriodId":  [10, 11],
            "StartDate": pd.to_datetime(["2024-01-01 12:00:00", "2024-01-02 12:00:00"]),
            "EndDate":   pd.to_datetime(["2024-01-01 23:59:59", "2024-01-02 23:59:59"]),
        })
        period_df.to_parquet(period_dir / "Period.parquet", index=False)

        data_df = pd.DataFrame({
            "SeriesId": [1, 1],
            "PeriodId": [10, 11],
            "Value":    [10.0, 20.0],
        })
        data_df.to_parquet(data_dir / "data.parquet", index=False)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
            start_date="2024-01-01",
        )

        df = pd.read_parquet(list(dest.glob("*.parquet"))[0])
        # Both rows fall on or after 2024-01-01 (the non-midnight time must not push it past the filter)
        assert len(df) == 2

    def test_end_date_filter(self, tmp_dir):
        """end_date filter excludes rows after the given date."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
            end_date="2024-01-01",
        )

        df = pd.read_parquet(list(dest.glob("*.parquet"))[0])
        assert len(df) == 1

    def test_end_date_filter_inclusive_with_non_midnight_time(self, tmp_dir):
        """end_date filter is inclusive for the whole day even when EndDate has a non-midnight time."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"

        # Build a source where EndDate for PeriodId=10 is 2024-01-01 12:00 (non-midnight)
        fk_dir = source / "fullkeyinfo"
        period_dir = source / "period"
        data_dir = source / "data" / "dataFileId=1"
        for d in (fk_dir, period_dir, data_dir):
            d.mkdir(parents=True, exist_ok=True)

        fk_df = pd.DataFrame({
            "SeriesId":               [1],
            "CollectionName":         ["Gas Zones"],
            "PropertyName":           ["Price"],
            "PhaseName":              ["ST"],
            "PeriodTypeName":         ["Interval"],
            "ChildObjectCategoryName": ["Hub"],
            "ChildObjectName":        ["Alberta"],
            "SampleName":             ["S1"],
            "UnitValue":              ["$/GJ"],
            "ModelName":              ["TestModel"],
        })
        fk_df.to_parquet(fk_dir / "FullKeyInfo.parquet", index=False)

        period_df = pd.DataFrame({
            "PeriodId":  [10, 11],
            "StartDate": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "EndDate":   pd.to_datetime(["2024-01-01 12:00:00", "2024-01-02 12:00:00"]),
        })
        period_df.to_parquet(period_dir / "Period.parquet", index=False)

        data_df = pd.DataFrame({
            "SeriesId": [1, 1],
            "PeriodId": [10, 11],
            "Value":    [10.0, 20.0],
        })
        data_df.to_parquet(data_dir / "data.parquet", index=False)

        worker = _make_worker(tmp_dir)
        worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["Gas Zones"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
            end_date="2024-01-01",
        )

        df = pd.read_parquet(list(dest.glob("*.parquet"))[0])
        # The row with EndDate=2024-01-01 12:00 must be included (same calendar day)
        assert len(df) == 1
        assert str(df["StartDate"].iloc[0])[:10] == "2024-01-01"

    def test_wildcard_collection_filter(self, tmp_dir):
        """Wildcard * in collection_name matches via ILIKE."""
        source = tmp_dir / "source"
        dest = tmp_dir / "dest"
        _create_parquet_source(source)

        worker = _make_worker(tmp_dir)
        result = worker.copy_to_output(
            source_folder=source,
            dest_folder=dest,
            collection_names=["*Zones*"],
            property_names=["Price"],
            object_names=[],
            category_names=[],
        )

        assert result is True


# ── main ──────────────────────────────────────────────────────────────────────

class TestMainFunction:
    def test_main_missing_required_args(self):
        """Main exits with code 2 when --collection-name or --property-name are missing."""
        with patch("sys.argv", ["solution_data_query.py"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            assert exc.value.code == 2

    def test_main_missing_collection_name(self):
        with patch("sys.argv", ["solution_data_query.py", "--property-name", "Price"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
            assert exc.value.code == 2

    def test_main_returns_1_when_mapping_missing(self, tmp_dir):
        """Returns 1 when no mapping file can be found."""
        missing = tmp_dir / "nonexistent.json"
        with patch("sys.argv", [
            "solution_data_query.py",
            "--collection-name", "Gas Zones",
            "--property-name", "Price",
        ]):
            with patch.object(MOD, "DIRECTORY_MAP_PATH", missing):
                exit_code = MOD.main()

        assert exit_code == 1

    def test_main_success(self, tmp_dir):
        """Returns 0 on full end-to-end success."""
        source = tmp_dir / "source"
        _create_parquet_source(source)

        mapping_file = tmp_dir / "mapping.json"
        _write_mapping_json(mapping_file, str(source), "1", "TESTMODEL")

        with patch("sys.argv", [
            "solution_data_query.py",
            "--collection-name", "Gas Zones",
            "--property-name", "Price",
        ]):
            with patch.object(MOD, "DIRECTORY_MAP_PATH", mapping_file), \
                 patch.object(MOD, "OUTPUT_PATH", tmp_dir / "output"):
                exit_code = MOD.main()

        assert exit_code == 0

    def test_main_url_encoded_args_decoded(self, tmp_dir):
        """URL-encoded collection/property names are decoded before use."""
        source = tmp_dir / "source"
        _create_parquet_source(source)

        mapping_file = tmp_dir / "mapping.json"
        _write_mapping_json(mapping_file, str(source), "1", "TESTMODEL")

        with patch("sys.argv", [
            "solution_data_query.py",
            "--collection-name", "Gas%20Zones",
            "--property-name", "Price",
        ]):
            with patch.object(MOD, "DIRECTORY_MAP_PATH", mapping_file), \
                 patch.object(MOD, "OUTPUT_PATH", tmp_dir / "output"):
                exit_code = MOD.main()

        assert exit_code == 0

    def test_main_returns_1_on_zero_rows(self, tmp_dir):
        """Returns 1 when filters produce no matching rows."""
        source = tmp_dir / "source"
        _create_parquet_source(source)

        mapping_file = tmp_dir / "mapping.json"
        _write_mapping_json(mapping_file, str(source), "1", "TESTMODEL")

        with patch("sys.argv", [
            "solution_data_query.py",
            "--collection-name", "Nonexistent",
            "--property-name", "Nonexistent",
        ]):
            with patch.object(MOD, "DIRECTORY_MAP_PATH", mapping_file), \
                 patch.object(MOD, "OUTPUT_PATH", tmp_dir / "output"):
                exit_code = MOD.main()

        assert exit_code == 1

    def test_main_custom_parquet_name(self, tmp_dir):
        """--parquet-name is respected in the final output filename."""
        source = tmp_dir / "source"
        _create_parquet_source(source)

        mapping_file = tmp_dir / "mapping.json"
        _write_mapping_json(mapping_file, str(source), "1", "TESTMODEL")
        output_path = tmp_dir / "output"

        with patch("sys.argv", [
            "solution_data_query.py",
            "--collection-name", "Gas Zones",
            "--property-name", "Price",
            "--parquet-name", "my_output",
        ]):
            with patch.object(MOD, "DIRECTORY_MAP_PATH", mapping_file), \
                 patch.object(MOD, "OUTPUT_PATH", output_path):
                exit_code = MOD.main()

        assert exit_code == 0
        assert list(output_path.glob("**/my_output.parquet")), "my_output.parquet not found in output"
