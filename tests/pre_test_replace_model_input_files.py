"""
Unit tests for Pre/PLEXOS/ReplaceModelInputFiles/replace_model_input_files.py

Tests the model input replacement script that updates property input assignments
using the PLEXOS SDK. Both eecloud and plexos_sdk are mocked.
"""
import argparse
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Mock the proprietary SDKs before importing the script module ─────────────
_mock_eecloud = MagicMock()
_mock_plexos_sdk = MagicMock()
sys.modules.setdefault("eecloud", _mock_eecloud)
sys.modules.setdefault("eecloud.cloudsdk", _mock_eecloud.cloudsdk)
sys.modules.setdefault("plexos_sdk", _mock_plexos_sdk)

from .conftest import get_module

MOD = get_module("replace_model_input_files")


# ===========================================================================
# _normalize_cli_args
# ===========================================================================


class TestNormalizeCliArgs:
    """Test Unicode dash normalization in CLI arguments."""

    def test_standard_dashes_unchanged(self):
        result = MOD._normalize_cli_args(["--parent-class-name", "System"])
        assert result == ["--parent-class-name", "System"]

    def test_unicode_en_dash_normalized(self):
        result = MOD._normalize_cli_args(["\u2013\u2013parent-class-name", "System"])
        assert result == ["--parent-class-name", "System"]

    def test_unicode_em_dash_normalized(self):
        result = MOD._normalize_cli_args(["\u2014\u2014model-path"])
        assert result == ["--model-path"]

    def test_empty_list(self):
        assert MOD._normalize_cli_args([]) == []

    def test_non_dash_args_unchanged(self):
        result = MOD._normalize_cli_args(["System", "Solar Rating"])
        assert result == ["System", "Solar Rating"]


# ===========================================================================
# _decode_argument_value
# ===========================================================================


class TestDecodeArgumentValue:
    """Test quote-stripping and URL decoding for CLI argument values."""

    def test_percent20_replaced(self):
        result, changed = MOD._decode_argument_value("Solar%20Rating")
        assert result == "Solar Rating"
        assert changed is True

    def test_no_placeholder_unchanged(self):
        result, changed = MOD._decode_argument_value("SolarRating")
        assert result == "SolarRating"
        assert changed is False

    def test_decodes_multiple_url_sequences(self):
        result, _ = MOD._decode_argument_value("Natural%20Gas%20Europe%2FHub")
        assert result == "Natural Gas Europe/Hub"

    def test_strips_quotes_before_decoding(self):
        result, changed = MOD._decode_argument_value('"Solar%20Rating"')
        assert result == "Solar Rating"
        assert changed is True


# ===========================================================================
# _decode_url_encoded_args
# ===========================================================================


class TestDecodeUrlEncodedArgs:
    """Test URL decoding across argparse Namespace fields."""

    def _make_namespace(self, **overrides):
        defaults = dict(
            parent_class_name=None,
            collection_name=None,
            property_name=None,
            parent_object_name="System",
            child_object_name="Solar",
            data_file_path="file.csv",
            model_path=None,
            time_slice_text=None,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_restores_child_object_name(self):
        ns = self._make_namespace(child_object_name="Solar%20Rating")
        count = MOD._decode_url_encoded_args(ns)
        assert ns.child_object_name == "Solar Rating"
        assert count == 1

    def test_restores_multiple_fields(self):
        ns = self._make_namespace(
            parent_class_name="My%20Class",
            child_object_name="Solar%20Rating%2FHub",
        )
        count = MOD._decode_url_encoded_args(ns)
        assert ns.parent_class_name == "My Class"
        assert ns.child_object_name == "Solar Rating/Hub"
        assert count == 2

    def test_no_placeholders_returns_zero(self):
        ns = self._make_namespace()
        count = MOD._decode_url_encoded_args(ns)
        assert count == 0


# ===========================================================================
# Argument validators
# ===========================================================================


class TestPositiveInt:
    """Test the positive_int argument validator."""

    def test_valid(self):
        assert MOD.positive_int("42") == 42

    def test_one(self):
        assert MOD.positive_int("1") == 1

    def test_zero_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            MOD.positive_int("0")

    def test_negative_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            MOD.positive_int("-1")

    def test_non_numeric_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Expected integer"):
            MOD.positive_int("abc")


class TestNonEmptyText:
    """Test the non_empty_text argument validator."""

    def test_valid(self):
        assert MOD.non_empty_text("hello") == "hello"

    def test_strips_whitespace(self):
        assert MOD.non_empty_text("  hello  ") == "hello"

    def test_empty_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="cannot be empty"):
            MOD.non_empty_text("")

    def test_whitespace_only_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="cannot be empty"):
            MOD.non_empty_text("   ")


class TestStrToBool:
    """Test the str_to_bool argument validator."""

    def test_true_values(self):
        for val in ["true", "True", "TRUE", "yes", "y", "1", "t"]:
            assert MOD.str_to_bool(val) is True

    def test_false_values(self):
        for val in ["false", "False", "FALSE", "no", "n", "0", "f"]:
            assert MOD.str_to_bool(val) is False

    def test_invalid_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid boolean"):
            MOD.str_to_bool("maybe")


class TestOptionalFloat:
    """Test the optional_float argument validator."""

    def test_numeric(self):
        assert MOD.optional_float("3.14") == pytest.approx(3.14)

    def test_integer_string(self):
        assert MOD.optional_float("42") == 42.0

    def test_none_string(self):
        assert MOD.optional_float("none") is None

    def test_null_string(self):
        assert MOD.optional_float("null") is None

    def test_empty_string(self):
        assert MOD.optional_float("") is None

    def test_invalid_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid float"):
            MOD.optional_float("abc")


# ===========================================================================
# resolve_model_path
# ===========================================================================


class TestResolveModelPath:
    """Test model path resolution via explicit path, env vars, and fallbacks."""

    def test_explicit_path_returned(self):
        result = MOD.resolve_model_path("/some/model.db")
        assert result == Path("/some/model.db")

    def test_simulation_path_with_reference_db(self, tmp_dir):
        sim_dir = tmp_dir / "sim"
        sim_dir.mkdir()
        ref_db = sim_dir / "reference.db"
        ref_db.write_text("mock")

        with patch.object(MOD, "SIMULATION_PATH", str(sim_dir)), \
             patch.object(MOD, "SQLITE_INPUT_PATH", None):
            result = MOD.resolve_model_path(None)

        assert result == ref_db

    def test_sqlite_input_path_fallback(self, tmp_dir):
        with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir / "nonexistent")), \
             patch.object(MOD, "SQLITE_INPUT_PATH", str(tmp_dir / "fallback.db")):
            result = MOD.resolve_model_path(None)

        assert result == Path(tmp_dir / "fallback.db")

    def test_missing_all_raises(self):
        with patch.object(MOD, "SIMULATION_PATH", ""), \
             patch.object(MOD, "SQLITE_INPUT_PATH", None):
            with pytest.raises(ValueError, match="Missing model path"):
                MOD.resolve_model_path(None)


# ===========================================================================
# resolve_lang_ids
# ===========================================================================


class TestResolveLangIds:
    """Test lang ID resolution from names and/or explicit IDs."""

    def test_explicit_ids_returned_directly(self, tmp_dir):
        """When all three IDs are provided, names are not needed."""
        result = MOD.resolve_lang_ids(
            model_path=tmp_dir / "dummy.db",
            parent_class_lang_id=1,
            parent_class_name=None,
            collection_lang_id=16,
            collection_name=None,
            property_lang_id=193,
            property_name=None,
        )
        assert result == (1, 16, 193)

    def test_missing_class_id_and_name_raises(self, tmp_dir):
        with pytest.raises(ValueError, match="parent-class"):
            MOD.resolve_lang_ids(
                model_path=tmp_dir / "dummy.db",
                parent_class_lang_id=None,
                parent_class_name=None,
                collection_lang_id=16,
                collection_name=None,
                property_lang_id=193,
                property_name=None,
            )

    def test_missing_collection_id_and_name_raises(self, tmp_dir):
        with pytest.raises(ValueError, match="collection"):
            MOD.resolve_lang_ids(
                model_path=tmp_dir / "dummy.db",
                parent_class_lang_id=1,
                parent_class_name=None,
                collection_lang_id=None,
                collection_name=None,
                property_lang_id=193,
                property_name=None,
            )

    def test_missing_property_id_and_name_raises(self, tmp_dir):
        with pytest.raises(ValueError, match="property"):
            MOD.resolve_lang_ids(
                model_path=tmp_dir / "dummy.db",
                parent_class_lang_id=1,
                parent_class_name=None,
                collection_lang_id=16,
                collection_name=None,
                property_lang_id=None,
                property_name=None,
            )

    def test_names_resolved_via_discovery(self, tmp_dir):
        """When names are given, discover_* functions are called."""
        with patch.object(MOD, "discover_class_lang_id", return_value=1) as mock_cls, \
             patch.object(MOD, "discover_collection_lang_id", return_value=16) as mock_col, \
             patch.object(MOD, "discover_property_lang_id", return_value=193) as mock_prop:
            result = MOD.resolve_lang_ids(
                model_path=tmp_dir / "dummy.db",
                parent_class_lang_id=None,
                parent_class_name="System",
                collection_lang_id=None,
                collection_name="Data Files",
                property_lang_id=None,
                property_name="Filename",
            )

        assert result == (1, 16, 193)
        mock_cls.assert_called_once()
        mock_col.assert_called_once()
        mock_prop.assert_called_once()

    def test_explicit_id_overrides_name(self, tmp_dir):
        """When both ID and name are provided, ID takes priority (no discovery call)."""
        with patch.object(MOD, "discover_class_lang_id") as mock_cls:
            result = MOD.resolve_lang_ids(
                model_path=tmp_dir / "dummy.db",
                parent_class_lang_id=99,
                parent_class_name="System",
                collection_lang_id=16,
                collection_name="Data Files",
                property_lang_id=193,
                property_name="Filename",
            )

        assert result[0] == 99
        mock_cls.assert_not_called()


# ===========================================================================
# _regenerate_xml
# ===========================================================================


class TestRegenerateXml:
    """Test the DB-to-XML regeneration helper."""

    def test_backs_up_existing_xml_and_regenerates(self, tmp_dir, capsys):
        db_path = tmp_dir / "reference.db"
        xml_path = tmp_dir / "project.xml"
        db_path.write_text("mock db")
        xml_path.write_text("<old/>")
        backup_path = Path(str(xml_path) + ".bak")

        # Any non-None parsed response indicates success.
        mock_parsed_response = object()

        def _convert_side_effect(**_kwargs):
            # Simulate CLI writing the new XML file.
            xml_path.write_text("<new/>")
            return MagicMock()

        with patch.object(MOD, "CloudSDK") as MockSDK, patch.object(
            MOD, "SDKBase"
        ) as MockSDKBase:
            MockSDK.return_value.inputdata.convert_database_to_xml.side_effect = _convert_side_effect
            MockSDKBase.get_response_data.return_value = mock_parsed_response
            result = MOD._regenerate_xml(db_path, xml_path, "study-1")

        MockSDK.assert_called_once_with(cli_path=MOD.CLOUD_CLI_PATH)
        MockSDK.return_value.inputdata.convert_database_to_xml.assert_called_once_with(
            db_file_path=str(db_path),
            xml_file_path=str(xml_path),
            study_id="study-1",
            print_message=False,
        )

        captured = capsys.readouterr()
        assert "Backed up existing XML" in captured.out
        assert result is True
        assert xml_path.exists()
        assert not backup_path.exists()

    def test_returns_false_on_conversion_failure(self, tmp_dir, capsys):
        db_path = tmp_dir / "reference.db"
        xml_path = tmp_dir / "project.xml"
        db_path.write_text("mock db")
        xml_path.write_text("<old/>")

        # result=None indicates failure via SDKBase.get_response_data.
        mock_raw_response = MagicMock()
        mock_raw_response.Message = "Bad study ID"

        with patch.object(MOD, "CloudSDK") as MockSDK, patch.object(
            MOD, "SDKBase"
        ) as MockSDKBase:
            MockSDK.return_value.inputdata.convert_database_to_xml.return_value = mock_raw_response
            MockSDKBase.get_response_data.return_value = None
            result = MOD._regenerate_xml(db_path, xml_path, "bad-id")

        MockSDK.assert_called_once_with(cli_path=MOD.CLOUD_CLI_PATH)
        MockSDK.return_value.inputdata.convert_database_to_xml.assert_called_once_with(
            db_file_path=str(db_path),
            xml_file_path=str(xml_path),
            study_id="bad-id",
            print_message=False,
        )

        assert result is False
        captured = capsys.readouterr()
        assert "DB-to-XML conversion failed" in captured.out
        assert xml_path.exists()


# ===========================================================================
# replace_property_input_file
# ===========================================================================


class TestReplacePropertyInputFile:
    """Test the SDK-driven property replacement function."""

    def _make_mock_sdk(self):
        mock_sdk = MagicMock()
        mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
        mock_sdk.__exit__ = MagicMock(return_value=False)
        mock_sdk.transaction.return_value.__enter__ = MagicMock()
        mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)
        return mock_sdk

    def test_calls_add_property(self, tmp_dir, capsys):
        """Verifies add_property is called with correct data_file_text."""
        mock_sdk = self._make_mock_sdk()

        with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            MOD.replace_property_input_file(
                model_path=tmp_dir / "model.db",
                parent_class_lang_id=1,
                collection_lang_id=16,
                parent_object_name="System",
                child_object_name="Solar Rating",
                property_lang_id=193,
                data_file_path="Project/Study/new_solar.csv",
                band_id=1,
                value=None,
                time_slice_text=None,
                period_type_id=None,
                replace_existing=True,
            )

        mock_sdk.add_property.assert_called_once()
        call_kwargs = mock_sdk.add_property.call_args[1]
        assert call_kwargs["data_file_text"] == "Project/Study/new_solar.csv"
        assert call_kwargs["band_id"] == 1

        captured = capsys.readouterr()
        assert "New data file assignment applied" in captured.out

    def test_replace_existing_removes_first(self, tmp_dir):
        """When replace_existing=True, remove_property is called before add_property."""
        mock_sdk = self._make_mock_sdk()

        with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            MOD.replace_property_input_file(
                model_path=tmp_dir / "model.db",
                parent_class_lang_id=1,
                collection_lang_id=16,
                parent_object_name="System",
                child_object_name="Solar",
                property_lang_id=193,
                data_file_path="new.csv",
                band_id=1,
                value=None,
                time_slice_text=None,
                period_type_id=None,
                replace_existing=True,
            )

        mock_sdk.remove_property.assert_called_once()
        mock_sdk.add_property.assert_called_once()

    def test_no_replace_skips_remove(self, tmp_dir):
        """When replace_existing=False, remove_property is NOT called."""
        mock_sdk = self._make_mock_sdk()

        with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            MOD.replace_property_input_file(
                model_path=tmp_dir / "model.db",
                parent_class_lang_id=1,
                collection_lang_id=16,
                parent_object_name="System",
                child_object_name="Solar",
                property_lang_id=193,
                data_file_path="new.csv",
                band_id=1,
                value=None,
                time_slice_text=None,
                period_type_id=None,
                replace_existing=False,
            )

        mock_sdk.remove_property.assert_not_called()
        mock_sdk.add_property.assert_called_once()

    def test_passes_optional_params(self, tmp_dir):
        """Optional value, time_slice_text, period_type_id are forwarded."""
        mock_sdk = self._make_mock_sdk()

        with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            MOD.replace_property_input_file(
                model_path=tmp_dir / "model.db",
                parent_class_lang_id=1,
                collection_lang_id=16,
                parent_object_name="System",
                child_object_name="Solar",
                property_lang_id=193,
                data_file_path="new.csv",
                band_id=2,
                value=3.14,
                time_slice_text="M1-12",
                period_type_id=5,
                replace_existing=False,
            )

        call_kwargs = mock_sdk.add_property.call_args[1]
        assert call_kwargs["value"] == 3.14
        assert call_kwargs["time_slice_text"] == "M1-12"
        assert call_kwargs["band_id"] == 2
        assert call_kwargs["period_type_id"] == 5


# ===========================================================================
# main()
# ===========================================================================


class TestMain:
    """Test the main() entry point with simulated CLI arguments."""

    def test_model_file_not_found_returns_1(self, tmp_dir, capsys):
        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(tmp_dir / "missing.db"),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar",
            "--data-file-path", "new.csv",
        ]):
            result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_data_file_not_found_returns_1(self, tmp_dir, capsys):
        """main() returns 1 when the data file has not been downloaded."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar",
            "--data-file-path", "missing_data.csv",
        ]):
            with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", ""):
                result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "data file not found" in captured.out.lower()

    def test_successful_run_with_explicit_ids(self, tmp_dir, capsys):
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "Project" / "Study").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "Project" / "Study" / "new_solar.csv").write_text("mock data")

        mock_sdk = MagicMock()
        mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
        mock_sdk.__exit__ = MagicMock(return_value=False)
        mock_sdk.transaction.return_value.__enter__ = MagicMock()
        mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar Rating",
            "--data-file-path", "Project/Study/new_solar.csv",
        ]):
            with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk), \
                 patch.object(MOD, "_regenerate_xml", return_value=True):
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", "test-study-123"):
                    result = MOD.main()

        assert result == 0
        captured = capsys.readouterr()
        assert "replaced successfully" in captured.out

    def test_successful_run_with_names(self, tmp_dir, capsys):
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "Project" / "Study").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "Project" / "Study" / "new_solar.csv").write_text("mock data")

        mock_sdk = MagicMock()
        mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
        mock_sdk.__exit__ = MagicMock(return_value=False)
        mock_sdk.transaction.return_value.__enter__ = MagicMock()
        mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-name", "System",
            "--collection-name", "Data Files",
            "--property-name", "Filename",
            "--parent-object-name", "System",
            "--child-object-name", "Solar Rating",
            "--data-file-path", "Project/Study/new_solar.csv",
        ]):
            with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk), \
                 patch.object(MOD, "discover_class_lang_id", return_value=1), \
                 patch.object(MOD, "discover_collection_lang_id", return_value=16), \
                 patch.object(MOD, "discover_property_lang_id", return_value=193), \
                 patch.object(MOD, "_regenerate_xml", return_value=True):
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", "test-study-123"):
                    result = MOD.main()

        assert result == 0
        captured = capsys.readouterr()
        assert "replaced successfully" in captured.out

    def test_db_to_xml_conversion_triggered(self, tmp_dir, capsys):
        """When simulation_path and study_id are set, DB-to-XML runs after replacement."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "new.csv").write_text("mock data")

        mock_sdk = MagicMock()
        mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
        mock_sdk.__exit__ = MagicMock(return_value=False)
        mock_sdk.transaction.return_value.__enter__ = MagicMock()
        mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar",
            "--data-file-path", "new.csv",
        ]):
            with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk), \
                 patch.object(MOD, "_regenerate_xml", return_value=True) as mock_regen:
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", "test-study-123"):
                    result = MOD.main()

        assert result == 0
        mock_regen.assert_called_once()

    def test_replace_existing_false_via_cli(self, tmp_dir):
        """--replace-existing false skips remove_property."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "new.csv").write_text("mock data")

        mock_sdk = MagicMock()
        mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
        mock_sdk.__exit__ = MagicMock(return_value=False)
        mock_sdk.transaction.return_value.__enter__ = MagicMock()
        mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar",
            "--data-file-path", "new.csv",
            "--replace-existing", "false",
        ]):
            with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk), \
                 patch.object(MOD, "_regenerate_xml", return_value=True):
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", "test-study-123"):
                    result = MOD.main()

        assert result == 0
        mock_sdk.remove_property.assert_not_called()

    def test_url_decodes_child_object(self, tmp_dir, capsys):
        """main() URL-decodes --child-object-name."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "new.csv").write_text("mock data")

        mock_sdk = MagicMock()
        mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
        mock_sdk.__exit__ = MagicMock(return_value=False)
        mock_sdk.transaction.return_value.__enter__ = MagicMock()
        mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar%20Rating",
            "--data-file-path", "new.csv",
        ]):
            with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk), \
                 patch.object(MOD, "_regenerate_xml", return_value=True):
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", "test-study-123"):
                    result = MOD.main()

        assert result == 0
        captured = capsys.readouterr()
        assert "[OK] URL-decoded 1 argument(s)" in captured.out
        assert "Solar Rating" in captured.out

    def test_band_id_and_value_cli(self, tmp_dir):
        """--band-id and --value are forwarded to replace_property_input_file."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "new.csv").write_text("mock data")

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar",
            "--data-file-path", "new.csv",
            "--band-id", "3",
            "--value", "42.5",
        ]):
            with patch.object(MOD, "replace_property_input_file") as mock_replace, \
                 patch.object(MOD, "_regenerate_xml", return_value=True):
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", "test-study-123"):
                    result = MOD.main()

        assert result == 0
        call_kwargs = mock_replace.call_args[1]
        assert call_kwargs["band_id"] == 3
        assert call_kwargs["value"] == 42.5

    def test_exception_returns_1(self, tmp_dir, capsys):
        """Any unhandled exception in main returns 1."""
        model_db = tmp_dir / "model.db"
        model_db.write_text("mock db")
        (tmp_dir / "new.csv").write_text("mock data")

        with patch.object(MOD.sys, "argv", [
            "replace_model_input_files.py",
            "--model-path", str(model_db),
            "--parent-class-lang-id", "1",
            "--collection-lang-id", "16",
            "--property-lang-id", "193",
            "--parent-object-name", "System",
            "--child-object-name", "Solar",
            "--data-file-path", "new.csv",
        ]):
            with patch.object(MOD, "PLEXOSSDK", side_effect=RuntimeError("SDK broke")):
                with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)), patch.object(MOD, "STUDY_ID", "test-study-123"):
                    result = MOD.main()

        assert result == 1
        captured = capsys.readouterr()
        assert "SDK broke" in captured.out
