"""
Unit tests for Pre/PLEXOS/ExtendWeatherYears/extend_weather_years.py

Tests the model registration script (Step 2 of the WeatherSample workflow).
Both eecloud and plexos_sdk are mocked since they are not installed locally.
All helper functions (validators, model path, file helpers) are inlined in the script.
"""
import argparse
import os
import sys
from pathlib import Path
from unittest.mock import call, patch, MagicMock

import pytest

# ── Add ExtendWeatherYears directory to sys.path ────────────────────────────────────────────
if str(Path(__file__).resolve().parents[1] / "Pre" / "PLEXOS" / "ExtendWeatherYears") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Pre" / "PLEXOS" / "ExtendWeatherYears"))

# ── Mock the proprietary SDKs before importing the script module ─────────────
_mock_eecloud = MagicMock()
_mock_plexos_sdk = MagicMock()
sys.modules.setdefault("eecloud", _mock_eecloud)
sys.modules.setdefault("eecloud.cloudsdk", _mock_eecloud.cloudsdk)
sys.modules.setdefault("plexos_sdk", _mock_plexos_sdk)

from .conftest import get_module

os.environ.setdefault("cloud_cli_path", "mock-cloud-cli")
MOD = get_module("extend_weather_years")


def _mock_sdk_context(mock_sdk_class):
    """Return a transaction-capable mock SDK for PLEXOSSDK context-manager tests."""
    sdk = MagicMock()
    transaction_cm = MagicMock()
    transaction_cm.__enter__.return_value = None
    transaction_cm.__exit__.return_value = None
    sdk.transaction.return_value = transaction_cm
    mock_sdk_class.return_value.__enter__.return_value = sdk
    mock_sdk_class.return_value.__exit__.return_value = None
    return sdk


# ===========================================================================
# Helper function tests (validators, model path, file helpers)
# ===========================================================================


class TestNonEmptyText:
    """Test the non_empty_text argument validator."""

    def test_valid_text(self):
        assert MOD.non_empty_text("hello") == "hello"

    def test_strips_whitespace(self):
        assert MOD.non_empty_text("  hello  ") == "hello"

    def test_empty_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="cannot be empty"):
            MOD.non_empty_text("")

    def test_whitespace_only_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="cannot be empty"):
            MOD.non_empty_text("   ")


class TestPositiveInt:
    """Test the positive_int argument validator."""

    def test_valid_positive(self):
        assert MOD.positive_int("42") == 42

    def test_one_is_valid(self):
        assert MOD.positive_int("1") == 1

    def test_zero_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            MOD.positive_int("0")

    def test_negative_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            MOD.positive_int("-5")

    def test_non_numeric_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Expected integer"):
            MOD.positive_int("abc")


class TestResolveModelPath:
    """Test model path resolution via explicit path, module-level env constants, and fallbacks."""

    def test_explicit_path_returned(self):
        result = MOD.resolve_model_path("/some/model.db")
        assert result == Path("/some/model.db")

    def test_simulation_path_with_reference_db(self, tmp_dir):
        sim_dir = tmp_dir / "sim"
        sim_dir.mkdir()
        ref_db = sim_dir / "reference.db"
        ref_db.write_text("mock")

        with patch.object(MOD, "ENV_SIMULATION_PATH", str(sim_dir)), \
             patch.object(MOD, "ENV_SQLITE_INPUT_PATH", None):
            result = MOD.resolve_model_path(None)

        assert result == ref_db

    def test_sqlite_input_path_fallback(self, tmp_dir):
        with patch.object(MOD, "ENV_SIMULATION_PATH", str(tmp_dir / "nonexistent")), \
             patch.object(MOD, "ENV_SQLITE_INPUT_PATH", str(tmp_dir / "fallback.db")):
            result = MOD.resolve_model_path(None)

        assert result == Path(tmp_dir / "fallback.db")

    def test_missing_all_raises(self, tmp_dir):
        with patch.object(MOD, "ENV_SIMULATION_PATH", None), \
             patch.object(MOD, "ENV_SQLITE_INPUT_PATH", None):
            with pytest.raises(ValueError, match="Missing model path"):
                MOD.resolve_model_path(None)


class TestCollectSampleFiles:
    """Test CSV sample file collection from a directory."""

    def test_collects_csv_files(self, tmp_dir):
        sample_dir = tmp_dir / "samples"
        sample_dir.mkdir()
        (sample_dir / "a.csv").write_text("data")
        (sample_dir / "b.csv").write_text("data")

        result = MOD.collect_sample_files(sample_dir)
        assert len(result) == 2
        names = [p.name for p in result]
        assert "a.csv" in names
        assert "b.csv" in names

    def test_nonexistent_dir_raises(self, tmp_dir):
        with pytest.raises(FileNotFoundError, match="Sample folder not found"):
            MOD.collect_sample_files(tmp_dir / "nonexistent")

    def test_empty_dir_raises(self, tmp_dir):
        empty_dir = tmp_dir / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="No CSV sample files"):
            MOD.collect_sample_files(empty_dir)

    def test_ignores_non_csv_files(self, tmp_dir):
        sample_dir = tmp_dir / "samples"
        sample_dir.mkdir()
        (sample_dir / "data.csv").write_text("data")
        (sample_dir / "readme.txt").write_text("text")

        result = MOD.collect_sample_files(sample_dir)
        assert len(result) == 1
        assert result[0].name == "data.csv"

    def test_collects_from_subdirs(self, tmp_dir):
        """rglob should find CSVs in nested subdirectories."""
        sample_dir = tmp_dir / "samples"
        sub = sample_dir / "Solar"
        sub.mkdir(parents=True)
        (sub / "loc1.csv").write_text("data")

        result = MOD.collect_sample_files(sample_dir)
        assert len(result) == 1
        assert result[0].name == "loc1.csv"


class TestGetDataFileObjectName:
    """Test Data File object naming."""

    def test_stem_name(self):
        result = MOD.get_data_file_object_name(Path("dir/loc1.csv"), use_stem=True, prefix="")
        assert result == "loc1"

    def test_full_filename(self):
        result = MOD.get_data_file_object_name(Path("dir/loc1.csv"), use_stem=False, prefix="")
        assert result == "loc1.csv"

    def test_with_prefix(self):
        result = MOD.get_data_file_object_name(Path("dir/loc1.csv"), use_stem=True, prefix="WX_")
        assert result == "WX_loc1"

    def test_empty_prefix(self):
        result = MOD.get_data_file_object_name(Path("dir/loc1.csv"), use_stem=True, prefix="")
        assert result == "loc1"


class TestGetVariableObjectName:
    """Test Variable object naming."""

    def test_default_suffix(self):
        result = MOD.get_variable_object_name("loc1", "_CY")
        assert result == "loc1_CY"

    def test_custom_suffix(self):
        result = MOD.get_variable_object_name("SolarPanel", "_VAR")
        assert result == "SolarPanel_VAR"

    def test_empty_suffix(self):
        result = MOD.get_variable_object_name("loc1", "")
        assert result == "loc1"


# ===========================================================================
# extend_weather_years.py tests
# ===========================================================================


class TestExtendNormalizeCliArgs:
    """Test Unicode dash normalization in CLI arguments."""

    def test_standard_dashes_unchanged(self):
        result = MOD._normalize_cli_args(["--sampled-dir", "ExoSampled"])
        assert result == ["--sampled-dir", "ExoSampled"]

    def test_unicode_en_dash_normalized(self):
        result = MOD._normalize_cli_args(["\u2013\u2013sampled-dir", "ExoSampled"])
        assert result == ["--sampled-dir", "ExoSampled"]

    def test_empty_list(self):
        assert MOD._normalize_cli_args([]) == []


class TestExtendRestoreSpaces:
    """Test %20 → space replacement in extend_weather_years."""

    def test_percent20_replaced(self):
        result, changed = MOD._restore_spaces_from_placeholders("Model%20Name")
        assert result == "Model Name"
        assert changed is True

    def test_no_placeholder_unchanged(self):
        result, changed = MOD._restore_spaces_from_placeholders("plain")
        assert result == "plain"
        assert changed is False


class TestExtendRestorePlaceholderSpacesInArgs:
    """Test space-placeholder restoration for extend_weather_years fields."""

    def test_restores_sampled_dir(self):
        ns = argparse.Namespace(
            sampled_dir="My%20Samples",
            object_name_prefix=None,
            data_file_category=None,
            model_path=None,
            study_id=None,
            variable_name_suffix="_CY",
            variable_category=None,
            target_class_name=None,
            scenario_name="Weather",
            scenario_category=None,
            stochastic_object_name="Stoch",
            stochastic_parent_name="Model",
            stochastic_parent_category=None,
        )
        count = MOD._restore_placeholder_spaces_in_args(ns)
        assert ns.sampled_dir == "My Samples"
        assert count == 1

    def test_restores_multiple_fields(self):
        ns = argparse.Namespace(
            sampled_dir="My%20Samples",
            object_name_prefix=None,
            data_file_category=None,
            model_path=None,
            study_id=None,
            variable_name_suffix="_CY",
            variable_category=None,
            target_class_name=None,
            scenario_name="My%20Scenario",
            scenario_category=None,
            stochastic_object_name="Stoch",
            stochastic_parent_name="i1000%20Play%20Book",
            stochastic_parent_category=None,
        )
        count = MOD._restore_placeholder_spaces_in_args(ns)
        assert ns.sampled_dir == "My Samples"
        assert ns.scenario_name == "My Scenario"
        assert ns.stochastic_parent_name == "i1000 Play Book"
        assert count == 3

    def test_no_placeholders_returns_zero(self):
        ns = argparse.Namespace(
            sampled_dir="plain",
            object_name_prefix=None,
            data_file_category=None,
            model_path=None,
            study_id=None,
            variable_name_suffix="_CY",
            variable_category=None,
            target_class_name=None,
            scenario_name="Weather",
            scenario_category=None,
            stochastic_object_name="Stoch",
            stochastic_parent_name="Model",
            stochastic_parent_category=None,
        )
        count = MOD._restore_placeholder_spaces_in_args(ns)
        assert count == 0


class TestOperationSdkInteractions:
    """Verify the core SDK calls inside Operations 1-4."""

    def test_create_data_file_objects_writes_filename_property(self, tmp_dir):
        model_path = tmp_dir / "model.db"
        sample_file = tmp_dir / "ExoSampled" / "weather.csv"
        membership = MagicMock(membership_id=101)
        filename_property_obj = MagicMock(property_id=202)

        with patch.object(MOD, "PLEXOSSDK") as MockSDK, \
             patch.object(MOD, "collect_sample_files", return_value=[sample_file]), \
             patch.object(MOD, "discover_data_file_class_lang_id", return_value=11), \
             patch.object(MOD, "discover_collection_lang_id", return_value=22), \
             patch.object(MOD, "discover_property_lang_id", return_value=33), \
             patch.object(MOD, "get_workspace_path_text", return_value="TimeSeries/ExoSampled/weather.csv"), \
             patch.object(MOD, "discover_existing_property_band_ids", return_value=[9]), \
             patch.object(MOD, "add_object_with_optional_category") as mock_add_object:
            sdk = _mock_sdk_context(MockSDK)
            sdk.get_property.return_value = filename_property_obj
            sdk.get_membership_by_names.return_value = membership
            sdk.get_object_by_name.side_effect = Exception("missing data file")

            MOD.create_data_file_objects_for_samples(
                model_path=model_path,
                sampled_dir=tmp_dir / "ExoSampled",
                object_name_from_stem=True,
                object_name_prefix=None,
                data_file_category="Weather",
                start_year=2006,
                end_year=2007,
                dry_run=False,
            )

        mock_add_object.assert_called_once_with(
            sdk=sdk,
            class_lang_id=11,
            object_name="weather",
            category_name="Weather",
        )
        assert sdk.remove_property.call_args_list == [
            call(membership=membership, property_obj=filename_property_obj, band_id=1),
            call(membership=membership, property_obj=filename_property_obj, band_id=2),
            call(membership=membership, property_obj=filename_property_obj, band_id=9),
        ]
        sdk.add_property.assert_called_once_with(
            membership=membership,
            property_obj=filename_property_obj,
            value=None,
            data_file_text="TimeSeries/ExoSampled/weather.csv",
            band_id=1,
        )

    def test_create_variable_objects_writes_sampling_and_profile_properties(self, tmp_dir):
        model_path = tmp_dir / "model.db"
        sample_file = tmp_dir / "ExoSampled" / "weather.csv"
        sampling_method_property_obj = MagicMock()
        profile_property_obj = MagicMock()
        variable_object = MagicMock()
        data_file_object = MagicMock()
        variable_membership = MagicMock()

        with patch.object(MOD, "PLEXOSSDK") as MockSDK, \
             patch.object(MOD, "collect_sample_files", return_value=[sample_file]), \
             patch.object(MOD, "discover_variable_class_lang_id", return_value=12), \
             patch.object(MOD, "discover_data_file_class_lang_id", return_value=11), \
             patch.object(MOD, "discover_collection_lang_id", return_value=44), \
             patch.object(MOD, "discover_property_lang_id", side_effect=[55, 66]), \
             patch.object(MOD, "resolve_property_mask_value", return_value=88), \
             patch.object(MOD, "discover_variable_band_attribute_lang_id", return_value=77), \
             patch.object(MOD, "add_object_with_optional_category", return_value=variable_object) as mock_add_object, \
             patch.object(MOD, "_set_variable_band_attribute") as mock_set_band_attr:
            sdk = _mock_sdk_context(MockSDK)
            sdk.get_property.side_effect = [sampling_method_property_obj, profile_property_obj]
            sdk.get_object_by_name.side_effect = [Exception("missing variable"), data_file_object]
            sdk.get_membership_by_names.return_value = variable_membership
            sdk.map_str_value_to_int.return_value = 88

            MOD.create_variable_objects_for_samples(
                model_path=model_path,
                sampled_dir=tmp_dir / "ExoSampled",
                object_name_from_stem=True,
                object_name_prefix=None,
                variable_name_suffix="_CY",
                variable_category="Variables",
                variable_band_attribute_lang_id=None,
                require_variable_band_attribute=False,
                start_year=2006,
                end_year=2008,
                dry_run=False,
            )

        mock_add_object.assert_called_once_with(
            sdk=sdk,
            class_lang_id=12,
            object_name="weather_CY",
            category_name="Variables",
        )
        mock_set_band_attr.assert_called_once_with(
            sdk=sdk,
            variable_object=variable_object,
            variable_class_lang_id=12,
            attribute_lang_id=77,
            band_count=3,
        )
        assert sdk.add_property.call_args_list == [
            call(
                membership=variable_membership,
                property_obj=sampling_method_property_obj,
                value=88,
                band_id=1,
            ),
            call(
                membership=variable_membership,
                property_obj=profile_property_obj,
                value=None,
                data_file_tag=data_file_object,
                band_id=3,
            ),
        ]

    def test_link_variables_writes_rating_factor_with_scenario_and_expression(self, tmp_dir):
        model_path = tmp_dir / "model.db"
        sample_file = tmp_dir / "ExoSampled" / "weather.csv"
        rating_factor_property_obj = MagicMock(property_id=501)
        parent_membership = MagicMock(membership_id=601)
        scenario_obj = MagicMock()
        variable_obj = MagicMock()

        with patch.object(MOD, "PLEXOSSDK") as MockSDK, \
             patch.object(MOD, "collect_sample_files", return_value=[sample_file]), \
             patch.object(MOD, "discover_class_lang_id_by_name", return_value=20), \
             patch.object(MOD, "discover_variable_class_lang_id", return_value=12), \
             patch.object(MOD, "discover_scenario_class_lang_id", return_value=30), \
             patch.object(MOD, "discover_collection_lang_id", side_effect=[40, 41]), \
             patch.object(MOD, "discover_property_lang_id", return_value=50), \
             patch.object(MOD, "query_existing_property_details", return_value=[{"band_id": 7, "action_id": 11, "action_symbol": "="}]), \
             patch.object(MOD, "add_object_with_optional_category", return_value=scenario_obj) as mock_add_object, \
             patch.object(MOD, "ensure_membership", return_value=True) as mock_ensure_membership, \
             patch.object(MOD, "set_scenario_read_order_in_database") as mock_set_read_order, \
             patch.object(MOD, "set_property_action_in_database") as mock_set_action:
            sdk = _mock_sdk_context(MockSDK)
            sdk.get_property.return_value = rating_factor_property_obj
            sdk.get_membership_by_names.return_value = parent_membership
            sdk.get_object_by_name.side_effect = [MagicMock(), scenario_obj, variable_obj]

            MOD.link_variables_to_objects_under_scenario(
                model_path=model_path,
                sampled_dir=tmp_dir / "ExoSampled",
                object_name_from_stem=True,
                object_name_prefix=None,
                variable_name_suffix="_CY",
                target_class_name="Generator",
                scenario_name="Weather_Variables_CY",
                scenario_class_lang_id=None,
                scenario_category="Weather",
                scenario_read_order=50001,
                start_year=2006,
                end_year=2008,
                dry_run=False,
                model_parent_name="Model",
                model_parent_class_lang_id=2,
            )

        mock_add_object.assert_called_once_with(
            sdk=sdk,
            class_lang_id=30,
            object_name="Weather_Variables_CY",
            category_name="Weather",
        )
        mock_ensure_membership.assert_called_once_with(
            sdk=sdk,
            parent_class_lang_id=2,
            collection_lang_id=41,
            parent_name="Model",
            child_name="Weather_Variables_CY",
        )
        sdk.add_property.assert_called_once_with(
            membership=parent_membership,
            property_obj=rating_factor_property_obj,
            value=None,
            expression_tag=variable_obj,
            scenario_tag=scenario_obj,
            band_id=7,
        )
        mock_set_read_order.assert_called_once_with(
            model_path=model_path,
            scenario_name="Weather_Variables_CY",
            read_order_value=50001,
        )
        mock_set_action.assert_called_once_with(
            model_path=model_path,
            membership_id=601,
            property_id=501,
            band_id=7,
            action_id=11,
        )

    def test_adjust_stochastic_updates_membership_and_sample_count(self, tmp_dir):
        model_path = tmp_dir / "model.db"
        stochastic_object = MagicMock()
        parent_obj = MagicMock()
        membership_to_remove = MagicMock()
        existing_membership = MagicMock()
        existing_membership.child_object = MagicMock(name="child_object")
        existing_membership.child_object.name = "Old_Stochastic"

        with patch.object(MOD, "PLEXOSSDK") as MockSDK, \
             patch.object(MOD, "discover_stochastic_class_lang_id", return_value=70), \
             patch.object(MOD, "discover_model_class_lang_id", return_value=2), \
             patch.object(MOD, "discover_collection_lang_id", return_value=80), \
             patch.object(MOD, "discover_stochastic_sample_attribute_lang_id", return_value=90), \
             patch.object(MOD, "add_object_with_optional_category", return_value=parent_obj) as mock_add_parent, \
             patch.object(MOD, "ensure_membership", return_value=True) as mock_ensure_membership, \
             patch.object(MOD, "_set_variable_band_attribute") as mock_set_band_attr:
            sdk = _mock_sdk_context(MockSDK)
            sdk.get_object_by_name.side_effect = [Exception("missing stochastic"), Exception("missing parent")]
            sdk.add_object.return_value = stochastic_object
            sdk.get_child_memberships.return_value = [existing_membership]
            sdk.get_membership_by_names.return_value = membership_to_remove

            MOD.adjust_stochastic_object_sample_count(
                model_path=model_path,
                stochastic_object_name="Weather_Stochastic",
                stochastic_parent_name="Model",
                stochastic_parent_category="System",
                stochastic_parent_class_lang_id=None,
                start_year=2006,
                end_year=2008,
                sample_count_override=None,
                stochastic_class_lang_id=None,
                stochastic_sample_attribute_lang_id=None,
                dry_run=False,
            )

        sdk.add_object.assert_called_once_with(
            class_lang_id=70,
            object_name="Weather_Stochastic",
        )
        mock_add_parent.assert_called_once_with(
            sdk=sdk,
            class_lang_id=2,
            object_name="Model",
            category_name="System",
        )
        membership_to_remove.delete_instance.assert_called_once_with()
        mock_ensure_membership.assert_called_once_with(
            sdk=sdk,
            parent_class_lang_id=2,
            collection_lang_id=80,
            parent_name="Model",
            child_name="Weather_Stochastic",
        )
        mock_set_band_attr.assert_called_once_with(
            sdk=sdk,
            variable_object=stochastic_object,
            variable_class_lang_id=70,
            attribute_lang_id=90,
            band_count=3,
        )


# ---------------------------------------------------------------------------
# main() tests
# ---------------------------------------------------------------------------


class TestMain:
    """Test the main() entry point with simulated CLI arguments."""

    def test_model_file_not_found_returns_1(self, tmp_dir, capsys):
        """Returns 1 when model DB file does not exist."""
        model_path = tmp_dir / "missing.db"

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_path),
            "--sampled-dir", "ExoSampled",
        ]):
            result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "ERROR" in captured.out

    def test_missing_study_id_returns_1(self, tmp_dir, capsys):
        """Returns 1 when --study-id is not provided and study_id/STUDY_ID env constants are not set."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        sampled_dir = tmp_dir / "ExoSampled"
        sampled_dir.mkdir()

        with patch.object(MOD, "ENV_STUDY_ID", None), \
             patch.object(MOD.sys, "argv", [
                 "extend_weather_years.py",
                 "--model-path", str(model_db),
                 "--sampled-dir", str(sampled_dir),
             ]):
            result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "study" in captured.out.lower()

    def test_successful_run_calls_create_data_files(self, tmp_dir, capsys):
        """Successful run calls create_data_file_objects_for_samples."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")

        sampled_dir = tmp_dir / "ExoSampled"
        sampled_dir.mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(sampled_dir),
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples") as mock_create:
                result = MOD.main()

        assert result == 0
        mock_create.assert_called_once()
        captured = capsys.readouterr()
        assert "All operations completed successfully" in captured.out

    def test_create_variables_flag(self, tmp_dir):
        """--create-variables triggers create_variable_objects_for_samples."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--create-variables",
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples"), \
                 patch.object(MOD, "create_variable_objects_for_samples") as mock_vars:
                result = MOD.main()

        assert result == 0
        mock_vars.assert_called_once()

    def test_link_variables_without_target_class_returns_1(self, tmp_dir, capsys):
        """--link-variables without --target-class-name raises ValueError → return 1."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--link-variables",
        ]):
            with patch.object(MOD, "create_data_file_objects_for_samples"):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "target-class-name" in captured.out.lower()

    def test_link_variables_with_target_class(self, tmp_dir):
        """--link-variables with --target-class-name invokes link operation."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--link-variables",
            "--target-class-name", "Generator",
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples"), \
                 patch.object(MOD, "link_variables_to_objects_under_scenario") as mock_link:
                result = MOD.main()

        assert result == 0
        mock_link.assert_called_once()
        assert mock_link.call_args.kwargs["target_class_name"] == "Generator"

    def test_adjust_stochastic_flag(self, tmp_dir):
        """--adjust-stochastic triggers adjust_stochastic_object_sample_count."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--adjust-stochastic",
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples"), \
                 patch.object(MOD, "adjust_stochastic_object_sample_count") as mock_stoch:
                result = MOD.main()

        assert result == 0
        mock_stoch.assert_called_once()

    def test_dry_run_passes_flag(self, tmp_dir):
        """--dry-run skips XML export and does not require study-id."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD, "ENV_STUDY_ID", None), \
             patch.object(MOD.sys, "argv", [
                 "extend_weather_years.py",
                 "--model-path", str(model_db),
                 "--sampled-dir", str(tmp_dir / "ExoSampled"),
                 "--dry-run",
             ]):
            with patch.object(MOD, "_convert_db_to_xml") as mock_convert, \
                 patch.object(MOD, "create_data_file_objects_for_samples") as mock_create:
                result = MOD.main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["dry_run"] is True
        mock_convert.assert_not_called()

    def test_default_start_end_year(self, tmp_dir):
        """Default start-year=1982 and end-year=2016 are passed to operations."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples") as mock_create:
                result = MOD.main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["start_year"] == 1982
        assert call_kwargs["end_year"] == 2016

    def test_custom_start_end_year(self, tmp_dir):
        """Custom --start-year and --end-year are propagated."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--start-year", "2000",
            "--end-year", "2010",
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples") as mock_create:
                result = MOD.main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["start_year"] == 2000
        assert call_kwargs["end_year"] == 2010

    def test_space_placeholder_in_stochastic_parent(self, tmp_dir):
        """main() restores %20 in --stochastic-parent-name."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--adjust-stochastic",
            "--stochastic-parent-name", "i1000%20Play%20Book",
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples"), \
                 patch.object(MOD, "adjust_stochastic_object_sample_count") as mock_stoch:
                result = MOD.main()

        assert result == 0
        call_kwargs = mock_stoch.call_args[1]
        assert call_kwargs["stochastic_parent_name"] == "i1000 Play Book"

    def test_use_full_filename_flag(self, tmp_dir):
        """--use-full-filename sets object_name_from_stem=False."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--use-full-filename",
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples") as mock_create:
                result = MOD.main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["object_name_from_stem"] is False

    def test_without_use_full_filename_defaults_to_stem(self, tmp_dir):
        """Without --use-full-filename, object_name_from_stem=True."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples") as mock_create:
                result = MOD.main()

        assert result == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["object_name_from_stem"] is True

    def test_all_operations_together(self, tmp_dir, capsys):
        """All four operations are invoked when all flags are set."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "ExoSampled").mkdir()

        with patch.object(MOD.sys, "argv", [
            "extend_weather_years.py",
            "--model-path", str(model_db),
            "--sampled-dir", str(tmp_dir / "ExoSampled"),
            "--create-variables",
            "--link-variables",
            "--target-class-name", "Generator",
            "--adjust-stochastic",
        ]):
            with patch.object(MOD, "_convert_db_to_xml"), \
                 patch.object(MOD, "create_data_file_objects_for_samples") as m1, \
                 patch.object(MOD, "create_variable_objects_for_samples") as m2, \
                 patch.object(MOD, "link_variables_to_objects_under_scenario") as m3, \
                 patch.object(MOD, "adjust_stochastic_object_sample_count") as m4:
                result = MOD.main()

        assert result == 0
        m1.assert_called_once()
        m2.assert_called_once()
        m3.assert_called_once()
        m4.assert_called_once()

        captured = capsys.readouterr()
        assert "All operations completed successfully" in captured.out


# ---------------------------------------------------------------------------
# XML conversion tests
# ---------------------------------------------------------------------------


class TestConvertDbToXml:
    """Test the _convert_db_to_xml helper."""

    def test_raises_when_conversion_fails(self, tmp_dir):
        """RuntimeError raised when CloudSDK reports failure."""
        db_path = tmp_dir / "model.db"
        xml_path = tmp_dir / "model.xml"
        db_path.write_text("mock db")

        mock_response = MagicMock()
        mock_response.Message = "DB error"

        with patch.object(MOD, "CloudSDK") as MockSDK, patch.object(MOD.SDKBase, "get_response_data", return_value=None):
            MockSDK.return_value.inputdata.convert_database_to_xml.return_value = [mock_response]
            with pytest.raises(RuntimeError, match="DB-to-XML conversion failed"):
                MOD._convert_db_to_xml(db_path, xml_path, "study-1")

            MockSDK.return_value.inputdata.convert_database_to_xml.assert_called_once_with(
                db_file_path=str(db_path),
                xml_file_path=str(xml_path),
                study_id="study-1",
                print_message=False,
            )

    def test_removes_existing_xml_before_conversion(self, tmp_dir, capsys):
        """Existing XML file is backed up and backup removed after success."""
        db_path = tmp_dir / "model.db"
        xml_path = tmp_dir / "model.xml"
        backup_path = tmp_dir / "model.xml.bak"
        db_path.write_text("mock db")
        xml_path.write_text("<old/>")

        mock_response = MagicMock()

        with patch.object(MOD, "CloudSDK") as MockSDK, patch.object(MOD.SDKBase, "get_response_data", return_value={"ok": True}):
            def _convert_and_create_xml(*_args, **_kwargs):
                xml_path.write_text("<new/>")
                return [mock_response]

            MockSDK.return_value.inputdata.convert_database_to_xml.side_effect = _convert_and_create_xml
            MOD._convert_db_to_xml(db_path, xml_path, "study-1")

            MockSDK.return_value.inputdata.convert_database_to_xml.assert_called_once_with(
                db_file_path=str(db_path),
                xml_file_path=str(xml_path),
                study_id="study-1",
                print_message=False,
            )

        assert xml_path.exists()
        assert not backup_path.exists()

        captured = capsys.readouterr()
        assert "Backing up existing XML" in captured.out
        assert "Removed XML backup" in captured.out

    def test_restores_backup_when_conversion_fails(self, tmp_dir):
        """If conversion fails, original XML is restored from .bak."""
        db_path = tmp_dir / "model.db"
        xml_path = tmp_dir / "model.xml"
        backup_path = tmp_dir / "model.xml.bak"
        db_path.write_text("mock db")
        xml_path.write_text("<old/>")

        mock_response = MagicMock()
        mock_response.Message = "DB error"

        with patch.object(MOD, "CloudSDK") as MockSDK, patch.object(MOD.SDKBase, "get_response_data", return_value=None):
            MockSDK.return_value.inputdata.convert_database_to_xml.return_value = [mock_response]
            with pytest.raises(RuntimeError, match="DB-to-XML conversion failed"):
                MOD._convert_db_to_xml(db_path, xml_path, "study-1")

        assert xml_path.exists()
        assert xml_path.read_text() == "<old/>"
        assert not backup_path.exists()
