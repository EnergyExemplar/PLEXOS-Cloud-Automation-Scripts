"""
Unit tests for Pre/PLEXOS/BidadderGeneration/bid_adder_generation.py

Tests the parsing helpers and piecewise-linear interpolation logic.
eecloud SDK is mocked since it is not installed locally.
"""
import pytest

from .conftest import get_module


MOD = get_module("bid_adder_generation")


class TestParseBands:
    """Test the parse_bands helper."""

    def test_single_band(self):
        result = MOD.parse_bands("0.5:100")
        assert result == [(0.5, 100.0)]

    def test_multiple_bands(self):
        result = MOD.parse_bands("0.0:0,0.6:0,0.8:125,0.9:625,1.0:1125")
        assert len(result) == 5
        assert result[0] == (0.0, 0.0)
        assert result[2] == (0.8, 125.0)
        assert result[4] == (1.0, 1125.0)

    def test_fractional_values(self):
        result = MOD.parse_bands("0.25:12.5,0.75:37.5")
        assert result == [(0.25, 12.5), (0.75, 37.5)]

    def test_out_of_order_bands_are_sorted(self):
        result = MOD.parse_bands("1.0:225,0.0:0,0.5:50")
        assert result == [(0.0, 0.0), (0.5, 50.0), (1.0, 225.0)]

    def test_duplicate_x_values_rejected(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="unique x-values"):
            MOD.parse_bands("0.5:10,0.5:20")


class TestParseSeasonalWeights:
    """Test the parse_seasonal_weights helper."""

    def test_all_twelve_months(self):
        weights_str = "1:0.50,2:0.55,3:1.30,4:1.50,5:1.57,6:1.30,7:1.40,8:1.47,9:1.10,10:1.15,11:1.10,12:1.05"
        result = MOD.parse_seasonal_weights(weights_str)
        assert len(result) == 12
        assert result[1] == 0.50
        assert result[6] == 1.30
        assert result[12] == 1.05

    def test_single_month(self):
        result = MOD.parse_seasonal_weights("3:1.25")
        assert result == {3: 1.25}

    def test_integer_weights(self):
        result = MOD.parse_seasonal_weights("1:1,2:2,3:3")
        assert result == {1: 1.0, 2: 2.0, 3: 3.0}

    def test_malformed_token_raises_argparse_error(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid seasonal weights"):
            MOD.parse_seasonal_weights("1:0.5,bad_token")

    def test_month_out_of_range_raises_argparse_error(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="out of range"):
            MOD.parse_seasonal_weights("0:0.5,1:1.0")

    def test_month_13_out_of_range(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="out of range"):
            MOD.parse_seasonal_weights("13:1.0")


class TestParseBandsValidation:
    """Test parse_bands error handling for malformed inputs."""

    def test_malformed_band_raises_argparse_error(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid bands"):
            MOD.parse_bands("not_a_band")


class TestPiecewiseLinear:
    """Test the piecewise_linear interpolation function."""

    def test_at_breakpoints(self):
        """Values at exact breakpoints should return exact y values."""
        bands = [(0.0, 0), (0.5, 50), (1.0, 100)]
        assert MOD.piecewise_linear(0.0, bands) == 0.0
        assert MOD.piecewise_linear(0.5, bands) == 50.0
        assert MOD.piecewise_linear(1.0, bands) == 100.0

    def test_midpoint_interpolation(self):
        """Midpoint between breakpoints should interpolate linearly."""
        bands = [(0.0, 0), (1.0, 100)]
        assert MOD.piecewise_linear(0.5, bands) == pytest.approx(50.0)

    def test_quarter_interpolation(self):
        bands = [(0.0, 0), (1.0, 200)]
        assert MOD.piecewise_linear(0.25, bands) == pytest.approx(50.0)

    def test_flat_segment(self):
        """Flat segment should return constant value."""
        bands = [(0.0, 0), (0.6, 0), (1.0, 100)]
        assert MOD.piecewise_linear(0.0, bands) == 0.0
        assert MOD.piecewise_linear(0.3, bands) == 0.0
        assert MOD.piecewise_linear(0.6, bands) == 0.0

    def test_below_range(self):
        """Value below range should clamp to first y."""
        bands = [(0.2, 10), (0.8, 80)]
        assert MOD.piecewise_linear(0.0, bands) == 10.0

    def test_above_range(self):
        """Value above range should clamp to last y."""
        bands = [(0.2, 10), (0.8, 80)]
        assert MOD.piecewise_linear(1.0, bands) == 80.0

    def test_realistic_bands(self):
        """Test with the actual default band configuration."""
        bands = MOD.parse_bands("0.0:0,0.6:0,0.8:25,0.9:125,1.0:225")
        # At 0.0 and 0.6 → 0
        assert MOD.piecewise_linear(0.0, bands) == 0.0
        assert MOD.piecewise_linear(0.6, bands) == 0.0
        # At 0.8 → 25
        assert MOD.piecewise_linear(0.8, bands) == 25.0
        # At 0.7 → midpoint between (0.6, 0) and (0.8, 25) = 12.5
        assert MOD.piecewise_linear(0.7, bands) == pytest.approx(12.5)
        # At 1.0 → 225
        assert MOD.piecewise_linear(1.0, bands) == 225.0


class TestDownloadInputs:
    """Test the download_inputs function."""

    def test_local_mode_skips_download(self, capsys):
        """Local mode should skip DataHub download without error."""
        MOD.download_inputs(local_mode=True)
        captured = capsys.readouterr()
        assert "Local mode enabled" in captured.out


class TestConfigDefaults:
    """Test that USER CONFIGURATION defaults are set."""

    def test_bands_default_exists(self):
        assert hasattr(MOD, "BANDS")
        assert isinstance(MOD.BANDS, str)
        assert ":" in MOD.BANDS

    def test_seasonal_weights_default_exists(self):
        assert hasattr(MOD, "SEASONAL_WEIGHTS")
        assert isinstance(MOD.SEASONAL_WEIGHTS, str)

    def test_counter_default(self):
        assert MOD.COUNTER == 0

    def test_local_mode_default(self):
        assert MOD.IS_LOCAL_MODE is False


class TestBandsByCounter:
    """Test the BANDS_BY_COUNTER canonical lookup."""

    def test_counter_0_is_1x(self):
        bands = MOD.BANDS_BY_COUNTER[0]
        # 1× baseline: last band y=225
        assert bands[-1] == (1.0, 225.0)

    def test_counter_1_is_3x(self):
        bands = MOD.BANDS_BY_COUNTER[1]
        # 3×: last band y=675
        assert bands[-1] == (1.0, 675.0)

    def test_counter_2_is_5x(self):
        bands = MOD.BANDS_BY_COUNTER[2]
        # 5×: last band y=1125
        assert bands[-1] == (1.0, 1125.0)

    def test_monotonic_increase(self):
        """Each counter's bands should have larger max y than the previous."""
        for i in range(1, len(MOD.BANDS_BY_COUNTER)):
            prev_max = MOD.BANDS_BY_COUNTER[i - 1][-1][1]
            curr_max = MOD.BANDS_BY_COUNTER[i][-1][1]
            assert curr_max > prev_max, f"Counter {i} max ({curr_max}) not > counter {i-1} max ({prev_max})"


class TestDownloadInputsSDK:
    """Test download_inputs with mocked CloudSDK."""

    def test_cloud_mode_calls_sdk(self, monkeypatch):
        from unittest.mock import MagicMock, patch

        monkeypatch.setenv("cloud_cli_path", "/usr/local/bin/plexos-cloud")

        mock_sdk_instance = MagicMock()
        mock_response = MagicMock()
        mock_sdk_instance.datahub.download.return_value = mock_response

        with patch.object(MOD, "SDKBase") as mock_sdkbase:
            mock_data = MagicMock()
            mock_result = MagicMock()
            mock_result.Success = True
            mock_result.LocalFilePath = "/simulation/calibration/inputs/Netload_2027.xlsx"
            mock_data.DatahubResourceResults = [mock_result]
            mock_sdkbase.get_response_data.return_value = mock_data

            with patch.object(MOD, "CloudSDK", return_value=mock_sdk_instance):
                result_path = MOD.download_inputs(local_mode=False)

        mock_sdk_instance.datahub.download.assert_called_once()
        call_kwargs = mock_sdk_instance.datahub.download.call_args
        assert "calibration/inputs/Netload_2027.xlsx" in call_kwargs.kwargs["remote_glob_patterns"]
        assert "output_directory" in call_kwargs.kwargs, "datahub.download must use 'output_directory'"
        assert call_kwargs.kwargs["output_directory"] == str(MOD.OUTPUT_PATH)
        # Return value should be the LocalFilePath reported by the SDK
        from pathlib import Path
        assert result_path == Path("/simulation/calibration/inputs/Netload_2027.xlsx")
