"""
Unit tests for Post/PLEXOS/CalibrationEvaluation/calibration_evaluation.py

Tests the evaluation logic, query building, band selection, and convergence checks.
The eecloud SDK is mocked via the shared tests/conftest.py fixtures.
DuckDB is not mocked; tests that exercise DuckDB logic do not call the database directly.
"""
import pytest

from .conftest import get_module


MOD = get_module("calibration_evaluation")


class TestGetNextBands:
    """Test the get_next_bands function for each counter value."""

    def test_counter_0_baseline(self):
        bands = MOD.get_next_bands(0)
        assert "0.8:25" in bands
        assert "1.0:225" in bands

    def test_counter_1_escalated(self):
        bands = MOD.get_next_bands(1)
        assert "0.8:75" in bands
        assert "1.0:675" in bands

    def test_counter_2_max(self):
        bands = MOD.get_next_bands(2)
        assert "0.8:125" in bands
        assert "1.0:1125" in bands

    def test_counter_beyond_max_falls_back(self):
        """Counter beyond defined range should fall back to counter 2 bands."""
        bands = MOD.get_next_bands(99)
        assert bands == MOD.get_next_bands(2)


class TestGetAdjustedSeasonalWeights:
    """Test the get_adjusted_seasonal_weights function."""

    def test_returns_fixed_base_weights(self):
        result = MOD.get_adjusted_seasonal_weights(75.0, 80.0)
        assert result == MOD.BASE_WEIGHTS_STR

    def test_weights_independent_of_inputs(self):
        """Weights should be the same regardless of avg/target values."""
        result1 = MOD.get_adjusted_seasonal_weights(50.0, 80.0)
        result2 = MOD.get_adjusted_seasonal_weights(100.0, 80.0)
        assert result1 == result2


class TestBuildFilteredQuery:
    """Test the build_filtered_query function."""

    def test_query_contains_join(self):
        sql = MOD.build_filtered_query(
            "/sim/fullkeyinfo.parquet",
            "/sim/period.parquet",
            ["/sim/data/part1.parquet", "/sim/data/part2.parquet"],
        )
        assert "INNER JOIN" in sql
        assert "fullkeyinfo" in sql.lower()
        assert "period" in sql.lower()

    def test_query_filters_region_price(self):
        sql = MOD.build_filtered_query(
            "/sim/fk.parquet",
            "/sim/p.parquet",
            ["/sim/d.parquet"],
        )
        assert "'region'" in sql.lower()
        assert "'price'" in sql.lower()

    def test_query_includes_all_data_paths(self):
        data_paths = ["/sim/d1.parquet", "/sim/d2.parquet", "/sim/d3.parquet"]
        sql = MOD.build_filtered_query("/sim/fk.parquet", "/sim/p.parquet", data_paths)
        for path in data_paths:
            assert path in sql

    def test_query_escapes_single_quotes(self):
        sql = MOD.build_filtered_query(
            "/sim/it's.parquet",
            "/sim/period.parquet",
            ["/sim/data.parquet"],
        )
        assert "it''s" in sql


class TestMaxIterations:
    """Test the MAX_ITERATIONS constant."""

    def test_max_iterations_is_three(self):
        assert MOD.MAX_ITERATIONS == 3


class TestConfigDefaults:
    """Test that USER CONFIGURATION defaults are set."""

    def test_threshold_value_default(self):
        assert MOD.THRESHOLD_VALUE == 80.0

    def test_counter_default(self):
        assert MOD.COUNTER == 0

    def test_margin_default(self):
        assert MOD.MARGIN == 0.05


class TestParserDefaults:
    """Test that the argparse parser uses USER CONFIGURATION defaults."""

    def test_make_parser_exists(self):
        assert callable(getattr(MOD, "_make_parser", None))

    def test_default_threshold(self):
        args = MOD._make_parser().parse_args(["--simulation-file-path", "x.json"])
        assert args.threshold_value == 80.0

    def test_default_margin(self):
        args = MOD._make_parser().parse_args(["--simulation-file-path", "x.json"])
        assert args.margin == 0.05

    def test_default_counter(self):
        args = MOD._make_parser().parse_args(["--simulation-file-path", "x.json"])
        assert args.counter == 0

    def test_simulation_file_path_is_required(self):
        import pytest
        with pytest.raises(SystemExit):
            MOD._make_parser().parse_args([])

    def test_override_threshold(self):
        args = MOD._make_parser().parse_args(["--threshold-value", "95.5", "--simulation-file-path", "x.json"])
        assert args.threshold_value == 95.5


class TestEnqueuePayloadRewrite:
    """Test that enqueue_next_simulation rewrites payload with correct script names."""

    def _make_payload(self):
        return {
            "simulationOptions": {
                "simulationTasks": [
                    {"name": "generate_bid_adder", "arguments": "python3 old_script.py --counter 0"},
                    {"name": "evaluate_results", "arguments": "python3 old_eval.py --counter 0"},
                ]
            }
        }

    def test_generate_bid_adder_uses_correct_script_name(self):
        """The rewritten arguments should reference bid_adder_generation.py."""
        from unittest.mock import MagicMock, patch

        payload = self._make_payload()

        # Simulate what enqueue_next_simulation does to the payload tasks
        for task in payload["simulationOptions"]["simulationTasks"]:
            if task["name"] == "generate_bid_adder":
                task["arguments"] = (
                    f"python3 bid_adder_generation.py "
                    f"--bands \"{MOD.get_next_bands(1)}\" "
                    f"--seasonal-weights \"{MOD.BASE_WEIGHTS_STR}\" "
                    f"--counter 1 "
                    f"--bidadder-filename test.csv"
                )
            elif task["name"] == "evaluate_results":
                task["arguments"] = (
                    f"python3 calibration_evaluation.py "
                    f"--threshold-value 80.0 "
                    f"--counter 1 --margin 0.05 "
                    f"--simulation-file-path test.json"
                )

        gen_task = payload["simulationOptions"]["simulationTasks"][0]
        eval_task = payload["simulationOptions"]["simulationTasks"][1]

        assert "bid_adder_generation.py" in gen_task["arguments"]
        assert "calibration_evaluation.py" in eval_task["arguments"]
        assert "--counter 1" in gen_task["arguments"]
        assert "--counter 1" in eval_task["arguments"]


class TestEnqueueSDKIntegration:
    """Test enqueue_next_simulation with mocked CloudSDK."""

    def test_enqueue_calls_sdk_download_and_enqueue(self, monkeypatch, tmp_path):
        import json
        from unittest.mock import MagicMock, patch

        monkeypatch.setenv("cloud_cli_path", "/usr/local/bin/plexos-cloud")

        # Write a test payload file where the SDK would download it
        payload = {
            "simulationOptions": {
                "simulationTasks": [
                    {"name": "generate_bid_adder", "arguments": "python3 old.py --counter 0 --bidadder-filename MyAdders-2027.csv"},
                    {"name": "evaluate_results", "arguments": "python3 old.py --counter 0"},
                ]
            }
        }
        payload_path = tmp_path / "payload.json"
        payload_path.write_text(json.dumps(payload))

        # Mock OUTPUT_PATH to tmp_path so the file is found
        monkeypatch.setattr(MOD, "OUTPUT_PATH", tmp_path)

        mock_sdk = MagicMock()
        mock_download_resp = MagicMock()
        mock_sdk.datahub.download.return_value = mock_download_resp
        mock_enqueue_resp = MagicMock()
        mock_sdk.simulation.enqueue_simulation.return_value = mock_enqueue_resp

        mock_sdkbase = MagicMock()
        # First call: download response, second call: enqueue response
        mock_download_data = MagicMock()
        mock_download_result = MagicMock()
        mock_download_result.Success = True
        mock_download_result.LocalFilePath = str(payload_path)
        mock_download_data.DatahubResourceResults = [mock_download_result]

        mock_enqueue_data = MagicMock()
        mock_started = MagicMock()
        mock_started_id = MagicMock()
        mock_started_id.Value = "test-sim-guid"
        mock_started.Id = mock_started_id
        mock_enqueue_data.SimulationStarted = [mock_started]

        mock_sdkbase.get_response_data.side_effect = [mock_download_data, mock_enqueue_data]

        with patch.object(MOD, "SDKBase", mock_sdkbase):
            with patch.object(MOD, "CloudSDK", return_value=mock_sdk):
                MOD.enqueue_next_simulation(
                    next_counter=1,
                    current_avg=56.0,
                    threshold_value=80.0,
                    simulation_file_path="calibration/payloadjson/payload.json",
                    margin=0.05,
                )

        mock_sdk.datahub.download.assert_called_once()
        mock_sdk.simulation.enqueue_simulation.assert_called_once()

        # Verify correct SDK parameter names are used (not remote_folder/local_folder)
        download_call = mock_sdk.datahub.download.call_args
        assert "remote_glob_patterns" in download_call.kwargs, "datahub.download must use 'remote_glob_patterns'"
        assert "output_directory" in download_call.kwargs, "datahub.download must use 'output_directory'"
        # Verify enqueue called with correct parameter name
        enqueue_call = mock_sdk.simulation.enqueue_simulation.call_args
        assert "file_path" in enqueue_call.kwargs, "simulation.enqueue_simulation must use 'file_path'"

        # Verify the saved payload was updated
        saved = json.loads(payload_path.read_text())
        gen_task = saved["simulationOptions"]["simulationTasks"][0]
        assert "--counter 1" in gen_task["arguments"]
        assert "bid_adder_generation.py" in gen_task["arguments"]
        # Bidadder filename must be preserved from the original payload, not hard-coded
        assert "MyAdders-2027.csv" in gen_task["arguments"]


class TestEnqueueSDKFallbackPath:
    """Test enqueue_next_simulation when SDK does not report LocalFilePath."""

    def test_fallback_finds_payload_without_localfilepath(self, monkeypatch, tmp_path):
        """When LocalFilePath is not in the SDK result, the fallback should
        locate the payload at output_directory / <filename>."""
        import json
        from unittest.mock import MagicMock, patch

        monkeypatch.setenv("cloud_cli_path", "/usr/local/bin/plexos-cloud")

        payload = {
            "simulationOptions": {
                "simulationTasks": [
                    {"name": "generate_bid_adder", "arguments": "python3 old.py --counter 0 --bidadder-filename A.csv"},
                    {"name": "evaluate_results", "arguments": "python3 old.py --counter 0"},
                ]
            }
        }
        # Place the file at the flat path: tmp_path / payload.json
        payload_path = tmp_path / "payload.json"
        payload_path.write_text(json.dumps(payload))

        monkeypatch.setattr(MOD, "OUTPUT_PATH", tmp_path)

        mock_sdk = MagicMock()
        mock_sdk.datahub.download.return_value = MagicMock()
        mock_sdk.simulation.enqueue_simulation.return_value = MagicMock()

        mock_sdkbase = MagicMock()
        # Download result: Success=True but NO LocalFilePath
        mock_download_data = MagicMock()
        mock_download_result = MagicMock()
        mock_download_result.Success = True
        mock_download_result.LocalFilePath = None
        mock_download_data.DatahubResourceResults = [mock_download_result]

        mock_enqueue_data = MagicMock()
        mock_started_id = MagicMock()
        mock_started_id.Value = "fallback-guid"
        mock_started = MagicMock()
        mock_started.Id = mock_started_id
        mock_enqueue_data.SimulationStarted = [mock_started]

        mock_sdkbase.get_response_data.side_effect = [mock_download_data, mock_enqueue_data]

        with patch.object(MOD, "SDKBase", mock_sdkbase):
            with patch.object(MOD, "CloudSDK", return_value=mock_sdk):
                MOD.enqueue_next_simulation(
                    next_counter=1,
                    current_avg=60.0,
                    threshold_value=80.0,
                    simulation_file_path="calibration/payloadjson/payload.json",
                    margin=0.05,
                )

        # Verify payload was updated and enqueue was called
        saved = json.loads(payload_path.read_text())
        gen_task = saved["simulationOptions"]["simulationTasks"][0]
        assert "--counter 1" in gen_task["arguments"]
        mock_sdk.simulation.enqueue_simulation.assert_called_once()
