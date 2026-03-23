"""
Unit tests for Post/Aurora/AuroraToParquet/aurora_to_parquet.py

Tests the Aurora .xdb to Parquet conversion script.
"""
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from .conftest import get_module


MOD = get_module("aurora_to_parquet")


def _create_fake_xdb(path: Path, tables: dict[str, list[tuple]]) -> None:
    """
    Create a minimal SQLite database mimicking an Aurora .xdb file.

    Args:
        path:   File path to write the .xdb file.
        tables: Mapping of table_name -> list of (col1, col2) row tuples.
    """
    con = sqlite3.connect(str(path))
    for name, rows in tables.items():
        con.execute(f"CREATE TABLE {name} (col_a TEXT, col_b REAL)")
        con.executemany(f"INSERT INTO {name} VALUES (?, ?)", rows)
    con.commit()
    con.close()


class TestAuroraToParquetConverter:
    """Test the AuroraToParquetConverter class."""

    def test_convert_single_table(self, tmp_dir):
        """A single-table .xdb produces one Parquet file."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        xdb_path = sim_dir / "test_sim.xdb"
        _create_fake_xdb(xdb_path, {"prices": [("regionA", 42.5), ("regionB", 38.1)]})

        converter = MOD.AuroraToParquetConverter(
            simulation_id="test_sim",
            simulation_path=str(sim_dir),
            output_path=str(out_dir),

        )
        success = converter.convert(xdb_filename="test_sim.xdb")

        assert success is True
        parquet_file = out_dir / "parquet" / "prices.parquet"
        assert parquet_file.exists()

    def test_convert_multiple_tables(self, tmp_dir):
        """Multiple tables each produce their own Parquet file."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        _create_fake_xdb(
            sim_dir / "test_sim.xdb",
            {
                "prices": [("A", 1.0)],
                "capacities": [("B", 2.0)],
                "emissions": [("C", 3.0)],
            },
        )

        converter = MOD.AuroraToParquetConverter(
            simulation_id="test_sim",
            simulation_path=str(sim_dir),
            output_path=str(out_dir),

        )
        success = converter.convert(xdb_filename="test_sim.xdb")

        assert success is True
        parquet_dir = out_dir / "parquet"
        assert (parquet_dir / "prices.parquet").exists()
        assert (parquet_dir / "capacities.parquet").exists()
        assert (parquet_dir / "emissions.parquet").exists()

    def test_convert_default_xdb_filename(self, tmp_dir):
        """When no xdb_filename is given, defaults to <simulation_id>.xdb."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        _create_fake_xdb(sim_dir / "my_sim.xdb", {"data": [("X", 9.0)]})

        converter = MOD.AuroraToParquetConverter(
            simulation_id="my_sim",
            simulation_path=str(sim_dir),
            output_path=str(out_dir),

        )
        success = converter.convert()  # no xdb_filename — uses default

        assert success is True
        assert (out_dir / "parquet" / "data.parquet").exists()

    def test_convert_xdb_not_found(self, tmp_dir):
        """Returns False when the .xdb file does not exist."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        converter = MOD.AuroraToParquetConverter(
            simulation_id="missing_sim",
            simulation_path=str(sim_dir),
            output_path=str(out_dir),

        )
        success = converter.convert()

        assert success is False

    def test_no_temporary_copy_created(self, tmp_dir):
        """The .xdb is read directly via read-only mode — no copy in output."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        _create_fake_xdb(sim_dir / "sim.xdb", {"t": [("a", 1.0)]})

        converter = MOD.AuroraToParquetConverter(
            simulation_id="sim",
            simulation_path=str(sim_dir),
            output_path=str(out_dir),

        )
        converter.convert(xdb_filename="sim.xdb")

        # No aurora.db copy should exist — read-only mode reads in-place
        assert not (out_dir / "aurora.db").exists()
        # Only the parquet directory should be in output
        output_contents = [p.name for p in out_dir.iterdir()]
        assert output_contents == ["parquet"]

    def test_simulation_id_appended_to_parquet(self, tmp_dir):
        """Each Parquet file includes a SimulationId column with the correct value."""
        import duckdb

        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        _create_fake_xdb(sim_dir / "run42.xdb", {"results": [("node1", 55.5)]})

        converter = MOD.AuroraToParquetConverter(
            simulation_id="run42",
            simulation_path=str(sim_dir),
            output_path=str(out_dir),

        )
        converter.convert(xdb_filename="run42.xdb")

        parquet_file = str(out_dir / "parquet" / "results.parquet")
        rows = duckdb.execute(f"SELECT SimulationId FROM '{parquet_file}'").fetchall()
        assert all(r[0] == "run42" for r in rows)


class TestMainFunction:
    """Test the main function with argument parsing."""

    def test_main_success_default_args(self, tmp_dir):
        """Main returns 0 on successful conversion with default arguments."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        _create_fake_xdb(sim_dir / "test_sim_001.xdb", {"data": [("a", 1.0)]})

        with patch("sys.argv", ["aurora_to_parquet.py"]):
            with patch.object(MOD, "SIMULATION_ID", "test_sim_001"), \
                 patch.object(MOD, "SIMULATION_PATH", str(sim_dir)), \
                 patch.object(MOD, "OUTPUT_PATH", str(out_dir)):
                exit_code = MOD.main()

        assert exit_code == 0

    def test_main_xdb_not_found(self, tmp_dir):
        """Main returns 1 when the .xdb file is missing."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        with patch("sys.argv", ["aurora_to_parquet.py"]):
            with patch.object(MOD, "SIMULATION_ID", "no_such_sim"), \
                 patch.object(MOD, "SIMULATION_PATH", str(sim_dir)), \
                 patch.object(MOD, "OUTPUT_PATH", str(out_dir)):
                exit_code = MOD.main()

        assert exit_code == 1

    def test_main_with_xdb_filename_arg(self, tmp_dir):
        """Main respects --xdb-filename argument."""
        sim_dir = tmp_dir / "simulation"
        out_dir = tmp_dir / "output"
        sim_dir.mkdir()
        out_dir.mkdir()

        _create_fake_xdb(sim_dir / "custom.xdb", {"t": [("x", 1.0)]})

        with patch("sys.argv", ["aurora_to_parquet.py", "--xdb-filename", "custom.xdb"]):
            with patch.object(MOD, "SIMULATION_ID", "test_sim_001"), \
                 patch.object(MOD, "SIMULATION_PATH", str(sim_dir)), \
                 patch.object(MOD, "OUTPUT_PATH", str(out_dir)):
                exit_code = MOD.main()

        assert exit_code == 0
        assert (out_dir / "parquet" / "t.parquet").exists()
