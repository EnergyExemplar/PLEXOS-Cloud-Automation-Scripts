"""
Unit tests for Post/PLEXOS/ConfigureDuckDbViews/configure_duck_db_views.py

Tests the DuckViewConfigurator class and main() function.
All DuckDB connections use in-memory databases — no real files are created.
"""
import json
import os
from unittest.mock import MagicMock, call, patch

import pytest

from .conftest import get_module


MOD = get_module("configure_duck_db_views")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _configurator(duck_db_path: str = ":memory:"):
    return MOD.DuckViewConfigurator(duck_db_path=duck_db_path)


def _write_parquet(directory) -> None:
    """Write a minimal parquet file into directory so DuckDB glob resolves it."""
    import duckdb as _ddb
    p = str(directory / "data.parquet").replace("\\", "/")
    _ddb.execute(f"COPY (SELECT 1 AS value) TO '{p}' (FORMAT PARQUET)")


# ---------------------------------------------------------------------------
# DuckViewConfigurator._resolve_mapping_file
# ---------------------------------------------------------------------------

class TestResolveMappingFile:

    def test_uses_env_path_when_exists(self, tmp_path):
        f = tmp_path / "mymap.json"
        f.write_text("[]")
        result = _configurator()._resolve_mapping_file(str(f))
        assert result == str(f)

    def test_falls_back_to_split_path(self):
        split_path = "/simulation/splits/directorymapping.json"
        with patch("configure_duck_db_views.os.path.exists", side_effect=lambda p: p == split_path):
            result = _configurator()._resolve_mapping_file("")
        assert result == split_path

    def test_raises_when_neither_path_exists(self):
        with patch("configure_duck_db_views.os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Mapping file not found"):
                _configurator()._resolve_mapping_file("")

    def test_env_path_ignored_if_file_not_found(self):
        split_path = "/simulation/splits/directorymapping.json"
        with patch(
            "configure_duck_db_views.os.path.exists",
            side_effect=lambda p: p == split_path,
        ):
            result = _configurator()._resolve_mapping_file("/nonexistent/map.json")
        assert result == split_path


# ---------------------------------------------------------------------------
# DuckViewConfigurator._read_parquet_path
# ---------------------------------------------------------------------------

class TestReadParquetPath:

    def test_returns_first_entry_with_parquet_path(self, tmp_path):
        mapping = [
            {"Name": "ModelA", "ParquetPath": "/data/ModelA"},
            {"Name": "ModelB", "ParquetPath": "/data/ModelB"},
        ]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        result = _configurator()._read_parquet_path(str(f))
        assert result == "/data/ModelA"

    def test_skips_entry_without_parquet_path(self, tmp_path):
        mapping = [
            {"Name": "ModelA"},
            {"Name": "ModelB", "ParquetPath": "/data/B"},
        ]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        result = _configurator()._read_parquet_path(str(f))
        assert result == "/data/B"

    def test_raises_when_no_entry_has_parquet_path(self, tmp_path):
        mapping = [{"Name": "ModelA"}, {"Name": "ModelB"}]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        with pytest.raises(ValueError, match="ParquetPath"):
            _configurator()._read_parquet_path(str(f))

    def test_raises_on_empty_mapping(self, tmp_path):
        f = tmp_path / "mapping.json"
        f.write_text("[]")

        with pytest.raises(ValueError, match="empty"):
            _configurator()._read_parquet_path(str(f))

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            _configurator()._read_parquet_path("/nonexistent/map.json")


# ---------------------------------------------------------------------------
# DuckViewConfigurator.configure — view creation
# ---------------------------------------------------------------------------

class TestConfigure:

    def _write_mapping(self, tmp_path, parquet_path: str) -> str:
        mapping = [{"Name": "TestModel", "ParquetPath": parquet_path}]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))
        return str(f)

    def test_creates_views_for_each_subdir(self, tmp_path):
        parquet_root = tmp_path / "solution"
        (parquet_root / "Generators").mkdir(parents=True)
        (parquet_root / "Lines").mkdir(parents=True)
        _write_parquet(parquet_root / "Generators")
        _write_parquet(parquet_root / "Lines")

        mapping_file = self._write_mapping(tmp_path, str(parquet_root))
        db_path = str(tmp_path / "views.ddb")

        with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", mapping_file):
            c = MOD.DuckViewConfigurator(duck_db_path=db_path)
            success = c.configure()

        assert success is True

        import duckdb as _ddb
        with _ddb.connect(db_path) as con:
            views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert "Generators" in views
        assert "Lines" in views

    def test_returns_true_when_no_subdirs(self, tmp_path):
        parquet_root = tmp_path / "solution"
        parquet_root.mkdir()

        mapping_file = self._write_mapping(tmp_path, str(parquet_root))
        db_path = str(tmp_path / "views.ddb")

        with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", mapping_file):
            c = MOD.DuckViewConfigurator(duck_db_path=db_path)
            success = c.configure()

        assert success is True

    def test_returns_false_on_missing_mapping_file(self):
        with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", "/nonexistent/map.json"):
            with patch("configure_duck_db_views.os.path.exists", return_value=False):
                c = MOD.DuckViewConfigurator(duck_db_path=":memory:")
                success = c.configure()
        assert success is False

    def test_returns_false_when_no_parquet_path_in_mapping(self, tmp_path):
        mapping = [{"Name": "ModelA"}]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))

        with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", str(f)):
            c = MOD.DuckViewConfigurator(duck_db_path=":memory:")
            success = c.configure()

        assert success is False

    def test_skips_datadatafileid_directories(self, tmp_path):
        parquet_root = tmp_path / "solution"
        (parquet_root / "Generators").mkdir(parents=True)
        (parquet_root / "datadataFileId=abc123").mkdir(parents=True)
        _write_parquet(parquet_root / "Generators")
        _write_parquet(parquet_root / "datadataFileId=abc123")

        mapping_file = self._write_mapping(tmp_path, str(parquet_root))
        db_path = str(tmp_path / "views.ddb")

        with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", mapping_file):
            c = MOD.DuckViewConfigurator(duck_db_path=db_path)
            success = c.configure()

        assert success is True
        import duckdb as _ddb
        with _ddb.connect(db_path) as con:
            views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert "Generators" in views
        assert not any("datadataFileId" in v for v in views)

    def test_nested_subdirs_use_double_underscore_separator(self, tmp_path):
        parquet_root = tmp_path / "solution"
        (parquet_root / "Results" / "Day1").mkdir(parents=True)
        _write_parquet(parquet_root / "Results" / "Day1")

        mapping_file = self._write_mapping(tmp_path, str(parquet_root))
        db_path = str(tmp_path / "views.ddb")

        with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", mapping_file):
            c = MOD.DuckViewConfigurator(duck_db_path=db_path)
            success = c.configure()

        assert success is True
        import duckdb as _ddb
        with _ddb.connect(db_path) as con:
            views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert any("Results__Day1" in v for v in views)


# ---------------------------------------------------------------------------
# main() — argument parsing, URL-decode, and exit codes
# ---------------------------------------------------------------------------

class TestMain:

    def test_exits_zero_on_success(self, tmp_path):
        parquet_root = tmp_path / "solution"
        parquet_root.mkdir()
        mapping = [{"ParquetPath": str(parquet_root)}]
        f = tmp_path / "mapping.json"
        f.write_text(json.dumps(mapping))
        db_path = str(tmp_path / "views.ddb")

        with patch("configure_duck_db_views.DUCK_DB_PATH", db_path):
            with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", str(f)):
                with patch("sys.argv", ["configure_duck_db_views.py"]):
                    result = MOD.main()

        assert result == 0

    def test_exits_one_on_failure(self, tmp_path):
        db_path = str(tmp_path / "views.ddb")
        with patch("configure_duck_db_views.DUCK_DB_PATH", db_path):
            with patch("configure_duck_db_views.DIRECTORY_MAP_PATH", ""):
                with patch("configure_duck_db_views.os.path.exists", return_value=False):
                    with patch("sys.argv", ["configure_duck_db_views.py"]):
                        result = MOD.main()

        assert result == 1
