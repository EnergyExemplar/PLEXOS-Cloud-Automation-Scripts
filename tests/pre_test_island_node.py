"""Tests for Pre/PLEXOS/IslandScript/island_node.py."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Mock the proprietary SDK before importing the script module
_mock_plexos_sdk = MagicMock()
sys.modules.setdefault("plexos_sdk", _mock_plexos_sdk)
sys.modules.setdefault("plexos_sdk.models", _mock_plexos_sdk.models)
sys.modules.setdefault("plexos_sdk.models.plexos_models", _mock_plexos_sdk.models.plexos_models)
sys.modules.setdefault("plexos_sdk.exceptions", _mock_plexos_sdk.exceptions)

from .conftest import get_module

MOD = get_module("island_node")


# ── _normalize_date ──────────────────────────────────────────────────────────

class TestNormalizeDate:
    def test_iso_with_t_separator(self):
        assert MOD._normalize_date("2025-03-01T00:00") == "2025-03-01 00:00"

    def test_space_separated(self):
        assert MOD._normalize_date("2025-03-01 00:00") == "2025-03-01 00:00"

    def test_date_only_start_defaults_to_midnight(self):
        assert MOD._normalize_date("2025-03-01", default_time="00:00") == "2025-03-01 00:00"

    def test_date_only_end_defaults_to_2300(self):
        assert MOD._normalize_date("2025-03-31", default_time="23:00") == "2025-03-31 23:00"

    def test_list_input_joined(self):
        assert MOD._normalize_date(["2025-03-01", "00:00"]) == "2025-03-01 00:00"

    def test_strips_whitespace(self):
        assert MOD._normalize_date("  2025-03-01T12:00  ") == "2025-03-01 12:00"


# ── parse_args ───────────────────────────────────────────────────────────────

class TestParseArgs:
    def test_all_required_args(self):
        argv = [
            "--start-date", "2025-03-01T00:00",
            "--end-date", "2025-03-31T23:00",
            "--output-folder", "IslandScript/outputs",
            "--model-name", "TestModel",
            "--branch-data-file", "IslandScript/inputs/Plexos Branch Data.csv",
            "--network-data-file", "IslandScript/inputs/Network Branch Data.xlsx",
            "--plexos-input-file", "IslandScript/inputs/Island Script data 0527.xlsx",
            "--scenario", "Node off island script",
        ]
        with patch("sys.argv", ["island_node.py"] + argv):
            args = MOD.parse_args()
        assert args.start_date == "2025-03-01 00:00"
        assert args.end_date == "2025-03-31 23:00"
        assert args.output_folder == "IslandScript/outputs"
        assert args.model_name == "TestModel"
        assert args.branch_data_file == "IslandScript/inputs/Plexos Branch Data.csv"
        assert args.network_data_file == "IslandScript/inputs/Network Branch Data.xlsx"
        assert args.plexos_input_file == "IslandScript/inputs/Island Script data 0527.xlsx"
        assert args.scenario == "Node off island script"

    def test_custom_file_and_scenario_args(self):
        argv = [
            "--start-date", "2025-03-01T00:00",
            "--end-date", "2025-03-31T23:00",
            "--output-folder", "out",
            "--model-name", "M",
            "--branch-data-file", "folder/custom_branch.csv",
            "--network-data-file", "folder/custom_network.xlsx",
            "--plexos-input-file", "folder/custom_input.xlsx",
            "--scenario", "My", "Custom", "Scenario",
        ]
        with patch("sys.argv", ["island_node.py"] + argv):
            args = MOD.parse_args()
        assert args.branch_data_file == "folder/custom_branch.csv"
        assert args.network_data_file == "folder/custom_network.xlsx"
        assert args.plexos_input_file == "folder/custom_input.xlsx"
        assert args.scenario == "My Custom Scenario"

    def test_model_name_with_spaces(self):
        argv = [
            "--start-date", "2025-03-01T00:00",
            "--end-date", "2025-03-31T23:00",
            "--output-folder", "out",
            "--model-name", "WY2025", "woPTC_hourly",
            "--branch-data-file", "in/b.csv",
            "--network-data-file", "in/n.xlsx",
            "--plexos-input-file", "in/p.xlsx",
            "--scenario", "S",
        ]
        with patch("sys.argv", ["island_node.py"] + argv):
            args = MOD.parse_args()
        assert args.model_name == "WY2025 woPTC_hourly"

    def test_collect_bridging_flag_removed(self):
        """--collect-bridging was removed; passing it should cause an error."""
        argv = [
            "--start-date", "2025-03-01T00:00",
            "--end-date", "2025-03-31T23:00",
            "--output-folder", "out",
            "--model-name", "M",
            "--branch-data-file", "in/b.csv",
            "--network-data-file", "in/n.xlsx",
            "--plexos-input-file", "in/p.xlsx",
            "--scenario", "S",
            "--collect-bridging",
        ]
        with patch("sys.argv", ["island_node.py"] + argv):
            with pytest.raises(SystemExit):
                MOD.parse_args()

    def test_missing_required_arg_exits(self):
        with patch("sys.argv", ["island_node.py", "--start-date", "2025-03-01T00:00"]):
            with pytest.raises(SystemExit):
                MOD.parse_args()

    def test_date_only_start_date(self):
        argv = [
            "--start-date", "2025-03-01",
            "--end-date", "2025-03-31",
            "--output-folder", "out",
            "--model-name", "M",
            "--branch-data-file", "in/b.csv",
            "--network-data-file", "in/n.xlsx",
            "--plexos-input-file", "in/p.xlsx",
            "--scenario", "S",
        ]
        with patch("sys.argv", ["island_node.py"] + argv):
            args = MOD.parse_args()
        assert args.start_date == "2025-03-01 00:00"
        assert args.end_date == "2025-03-31 23:00"


# ── add_one_hour_to_last_month_hour ──────────────────────────────────────────

class TestAddOneHourToLastMonthHour:
    def test_adds_one_hour(self):
        df = pd.DataFrame({"to_date": ["2025-03-15 10:00"]})
        result = MOD.add_one_hour_to_last_month_hour(df)
        expected = pd.Timestamp("2025-03-15 11:00")
        assert result["to_date"].iloc[0] == expected

    def test_month_boundary_gets_extra_hour(self):
        # 2025-03-31 23:00 + 1h = 2025-04-01 00:00 (month boundary)
        # then +1h extra = 2025-04-01 01:00
        df = pd.DataFrame({"to_date": ["2025-03-31 23:00"]})
        result = MOD.add_one_hour_to_last_month_hour(df)
        expected = pd.Timestamp("2025-04-01 01:00")
        assert result["to_date"].iloc[0] == expected


# ── convert_date_format ──────────────────────────────────────────────────────

class TestConvertDateFormat:
    def test_floors_to_seconds(self):
        df = pd.DataFrame({"Date From": ["2025-03-01 12:30:45.123"]})
        result = MOD.convert_date_format(df, date_columns=["Date From"])
        assert result["Date From"].iloc[0] == pd.Timestamp("2025-03-01 12:30:45")

    def test_custom_columns(self):
        df = pd.DataFrame({"from_date": ["2025-03-01"], "to_date": ["2025-03-31"]})
        result = MOD.convert_date_format(df, date_columns=["from_date", "to_date"])
        assert pd.notna(result["from_date"].iloc[0])
        assert pd.notna(result["to_date"].iloc[0])


# ── IslandDetector ───────────────────────────────────────────────────────────

class TestIslandDetector:
    def test_empty_input_returns_empty(self):
        detector = MOD.IslandDetector()
        result = detector.detect_islands_hourly(pd.DataFrame())
        assert result.empty

    def test_single_timestamp_finds_islands(self):
        detector = MOD.IslandDetector()
        ts = pd.Timestamp("2025-03-01 00:00")
        # Two disconnected components: nodes 1-2 connected, node 3 isolated
        df = pd.DataFrame({
            "From Number": [1, 2],
            "To Number": [2, 3],
            "Circuit": [1, 1],
            "Status": [1, 0],  # edge 2-3 is out
            "timestamp": [ts, ts],
        })
        result = detector.detect_islands_hourly(df)
        assert not result.empty
        # Node 3 should be in its own island (size 1)
        node3 = result[result["node"] == 3]
        assert len(node3) == 1
        assert node3["island_size"].iloc[0] == 1


# ── OutageReportGenerator ───────────────────────────────────────────────────

class TestOutageReportGenerator:
    def test_merge_outages_no_overlap(self):
        gen = MOD.OutageReportGenerator("2025-03-01", "2025-03-31")
        periods = [
            (pd.Timestamp("2025-03-01"), pd.Timestamp("2025-03-05")),
            (pd.Timestamp("2025-03-10"), pd.Timestamp("2025-03-15")),
        ]
        merged = gen.merge_outages(periods)
        assert len(merged) == 2

    def test_merge_outages_with_overlap(self):
        gen = MOD.OutageReportGenerator("2025-03-01", "2025-03-31")
        periods = [
            (pd.Timestamp("2025-03-01"), pd.Timestamp("2025-03-10")),
            (pd.Timestamp("2025-03-05"), pd.Timestamp("2025-03-15")),
        ]
        merged = gen.merge_outages(periods)
        assert len(merged) == 1
        assert merged[0][0] == pd.Timestamp("2025-03-01")
        assert merged[0][1] == pd.Timestamp("2025-03-15")

    def test_merge_outages_empty(self):
        gen = MOD.OutageReportGenerator("2025-03-01", "2025-03-31")
        assert gen.merge_outages([]) == []


# ── DataHub helpers: correct SDK parameter names ─────────────────────────────

class TestDatahubHelpers:
    def test_download_uses_correct_params(self):
        mock_pxc = MagicMock()
        mock_result = MagicMock()
        mock_result.DatahubResourceResults = []
        mock_pxc.datahub.download.return_value = MagicMock()

        # SDKBase is imported inside the function from eecloud.cloudsdk
        with patch("eecloud.cloudsdk.SDKBase.get_response_data", return_value=mock_result):
            with pytest.raises(RuntimeError, match="No files found"):
                MOD.download_inputs_from_datahub(
                    mock_pxc,
                    ["folder/a.csv", "folder/b.xlsx"],
                    "/tmp/local",
                )

        mock_pxc.datahub.download.assert_called_once()
        call_kwargs = mock_pxc.datahub.download.call_args.kwargs
        assert "remote_glob_patterns" in call_kwargs
        assert call_kwargs["remote_glob_patterns"] == ["folder/a.csv", "folder/b.xlsx"]
        assert "output_directory" in call_kwargs
        assert "remote_folder" not in call_kwargs
        assert "local_folder" not in call_kwargs

    def test_upload_uses_correct_params(self):
        mock_pxc = MagicMock()
        mock_result = MagicMock()
        mock_result.DatahubResourceResults = []

        with patch("eecloud.cloudsdk.SDKBase.get_response_data", return_value=mock_result):
            MOD.upload_outputs_to_datahub(mock_pxc, "/tmp/local", "remote/folder")

        mock_pxc.datahub.upload.assert_called_once()
        call_kwargs = mock_pxc.datahub.upload.call_args.kwargs
        assert "local_folder" in call_kwargs
        assert "remote_folder" in call_kwargs
        assert "glob_patterns" in call_kwargs
        assert "is_versioned" in call_kwargs


# ── SRDImporter ──────────────────────────────────────────────────────────────

class TestSRDImporter:
    def test_parse_oa_date_valid(self):
        assert MOD.SRDImporter._parse_oa_date("2025-03-01 00:00") == "2025-03-01 00:00"

    def test_parse_oa_date_empty(self):
        assert MOD.SRDImporter._parse_oa_date("") is None
        assert MOD.SRDImporter._parse_oa_date("  ") is None

    def test_parse_oa_date_nan(self):
        assert MOD.SRDImporter._parse_oa_date(float("nan")) is None

    def test_init_sets_paths(self):
        importer = MOD.SRDImporter(
            model_path="/sim/reference.db",
            cloud_cli_path="/cli",
            study_id="s123",
            simulation_path="/sim",
            model_name="TestModel",
        )
        assert importer.model_path == Path("/sim/reference.db")
        assert importer.study_id == "s123"
        assert importer.model_name == "TestModel"


# ── _resolve_model_path ─────────────────────────────────────────────────────

class TestResolveModelPath:
    def test_finds_reference_db(self, tmp_path):
        db = tmp_path / "reference.db"
        db.write_text("fake")
        with patch.dict(os.environ, {"simulation_path": str(tmp_path)}):
            result = MOD._resolve_model_path()
        assert result == db

    def test_falls_back_to_sqlite_input_path(self, tmp_path):
        db = tmp_path / "model.db"
        db.write_text("fake")
        with patch.dict(os.environ, {
            "simulation_path": str(tmp_path / "nonexistent"),
            "sqlite_input_path": str(db),
        }):
            result = MOD._resolve_model_path()
        assert result == db

    def test_returns_none_when_nothing_found(self, tmp_path):
        with patch.dict(os.environ, {
            "simulation_path": str(tmp_path / "nonexistent"),
        }, clear=False):
            env = os.environ.copy()
            env.pop("sqlite_input_path", None)
            with patch.dict(os.environ, env, clear=True):
                result = MOD._resolve_model_path()
        assert result is None


# ── main() ───────────────────────────────────────────────────────────────────

class TestMain:
    def test_returns_1_on_missing_env_var(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", [
                "island_node.py",
                "--start-date", "2025-03-01T00:00",
                "--end-date", "2025-03-31T23:00",
                "--output-folder", "out",
                "--model-name", "M",
                "--branch-data-file", "in/b.csv",
                "--network-data-file", "in/n.xlsx",
                "--plexos-input-file", "in/p.xlsx",
                "--scenario", "S",
            ]):
                with pytest.raises(SystemExit):
                    MOD.main()

    def test_returns_1_when_input_file_missing(self, tmp_path):
        with patch.dict(os.environ, {
            "cloud_cli_path": "/cli",
            "output_path": str(tmp_path),
            "study_id": "s1",
            "simulation_path": str(tmp_path),
        }):
            with patch("sys.argv", [
                "island_node.py",
                "--start-date", "2025-03-01T00:00",
                "--end-date", "2025-03-31T23:00",
                "--output-folder", "out",
                "--model-name", "M",
                "--branch-data-file", "in/b.csv",
                "--network-data-file", "in/n.xlsx",
                "--plexos-input-file", "in/p.xlsx",
                "--scenario", "S",
            ]):
                mock_pxc = MagicMock()
                with patch.object(MOD, "init_cloud_sdk", return_value=mock_pxc):
                    with patch.object(MOD, "download_inputs_from_datahub"):
                        result = MOD.main()
        assert result == 1


# ── Constants ────────────────────────────────────────────────────────────────

class TestConstants:
    def test_srd_columns_count(self):
        assert len(MOD.SRD_COLUMNS) == 15

    def test_grid_output_columns_count(self):
        assert len(MOD.GRID_OUTPUT_COLUMNS) == 10

    def test_node_scenario_default_is_none(self):
        assert MOD.DEFAULT_VALUES_FOR_NODE_SRD["Scenario"] is None

    def test_dc_region_scenario_default_is_none(self):
        assert MOD.DEFAULT_DATA_DC_REGION_UNITS["Scenario"] is None

    def test_collection_mapping(self):
        assert MOD.COLLECTION_MAPPING["Generator"] == "Generators"
        assert MOD.COLLECTION_MAPPING["Battery"] == "Batteries"
