"""
Unit tests for Pre/PLEXOS/EnableReports/enable_reports.py

Tests the ReportExtender class and CLI argument handling.
plexos_sdk is mocked since it is not installed locally.
"""
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Mock the proprietary SDK before importing the script module ───────────────
_mock_plexos_sdk = MagicMock()
sys.modules.setdefault("plexos_sdk", _mock_plexos_sdk)

from .conftest import get_module

MOD = get_module("enable_reports")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_extender(tmp_dir: Path):
    (tmp_dir / "reference.db").write_text("mock db")
    return MOD.ReportExtender(
        cli_path="mock_cli",
        simulation_path=str(tmp_dir),
        study_id="test_study",
    )


def _mock_sdk_context(report_object_name: str = "MyReport"):
    """Return a context-manager-compatible mock SDK with a report object."""
    mock_report_object = MagicMock()
    mock_report_object.name = report_object_name

    mock_sdk = MagicMock()
    mock_sdk.get_object_by_name.return_value = mock_report_object
    mock_sdk.configure_report_properties.return_value = [MagicMock(), MagicMock()]
    mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
    mock_sdk.__exit__ = MagicMock(return_value=False)
    mock_sdk.transaction.return_value.__enter__ = MagicMock(return_value=None)
    mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)
    return mock_sdk, mock_report_object


def _mock_discovery(
    report_class_lang_id: int = 42,
    reporting_lang_ids: list[int] | None = None,
):
    """Return a pair of patch.object patches for both discovery methods on ReportExtender."""
    if reporting_lang_ids is None:
        reporting_lang_ids = [2052]
    return (
        patch.object(MOD.ReportExtender, "_discover_report_class_lang_id", return_value=report_class_lang_id),
        patch.object(MOD.ReportExtender, "_discover_reporting_lang_ids_by_name", return_value=reporting_lang_ids),
    )


# ── Argument validator tests ──────────────────────────────────────────────────

class TestPhaseMap:
    def test_st_maps_to_1(self):
        assert MOD.PHASE_MAP["ST"] == 1

    def test_mt_maps_to_2(self):
        assert MOD.PHASE_MAP["MT"] == 2

    def test_pasa_maps_to_3(self):
        assert MOD.PHASE_MAP["PASA"] == 3

    def test_lt_maps_to_4(self):
        assert MOD.PHASE_MAP["LT"] == 4

    def test_all_four_phases_present(self):
        assert set(MOD.PHASE_MAP) == {"ST", "MT", "PASA", "LT"}


class TestPhaseName:
    def test_valid_uppercase(self):
        assert MOD.phase_name("LT") == "LT"

    def test_valid_lowercase_normalised(self):
        assert MOD.phase_name("st") == "ST"

    def test_all_valid_names(self):
        for name in ["ST", "MT", "PASA", "LT"]:
            assert MOD.phase_name(name) == name

    def test_invalid_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid phase"):
            MOD.phase_name("XX")

    def test_mixed_case_normalised(self):
        assert MOD.phase_name("Lt") == "LT"


class TestParseNameList:
    def test_single(self):
        assert MOD.parse_name_list("Emissions by Generator") == ["Emissions by Generator"]

    def test_multiple(self):
        result = MOD.parse_name_list("Emissions by Generator,Fuel Offtake by Generator")
        assert result == ["Emissions by Generator", "Fuel Offtake by Generator"]

    def test_deduplicates_case_insensitive(self):
        result = MOD.parse_name_list("Emissions by Generator,emissions by generator")
        assert result == ["Emissions by Generator"]

    def test_whitespace_stripped(self):
        result = MOD.parse_name_list(" Emissions by Generator , Fuel Offtake ")
        assert result == ["Emissions by Generator", "Fuel Offtake"]

    def test_empty_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            MOD.parse_name_list("")


class TestStrToBool:
    @pytest.mark.parametrize("value", ["true", "True", "1", "yes", "y", "t"])
    def test_truthy(self, value):
        assert MOD.str_to_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "False", "0", "no", "n", "f"])
    def test_falsy(self, value):
        assert MOD.str_to_bool(value) is False

    def test_invalid_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            MOD.str_to_bool("maybe")


class TestNonEmptyText:
    def test_valid(self):
        assert MOD.non_empty_text("Generators") == "Generators"

    def test_strips_whitespace(self):
        assert MOD.non_empty_text("  Generators  ") == "Generators"

    def test_empty_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            MOD.non_empty_text("   ")


class TestDecodeValue:
    def test_plain(self):
        assert MOD._decode_value("Generators") == "Generators"

    def test_url_encoded(self):
        assert MOD._decode_value("My%20Report") == "My Report"

    def test_strips_quotes(self):
        assert MOD._decode_value("'Generators'") == "Generators"

    def test_strips_double_quotes(self):
        assert MOD._decode_value('"Generators"') == "Generators"


# ── Discovery helper tests ──────────────────────────────────────────────────────────────

def _create_minimal_db(db_path: Path, report_class_lang_id: int = 42) -> None:
    """Create a minimal t_class + t_property_report SQLite DB for discovery tests."""
    with sqlite3.connect(str(db_path)) as con:
        con.execute(
            "CREATE TABLE t_class (class_id INTEGER PRIMARY KEY, lang_id INTEGER, name TEXT)"
        )
        con.execute(
            "INSERT INTO t_class VALUES (1, ?, 'Report')", (report_class_lang_id,)
        )
        con.execute(
            "CREATE TABLE t_property_report (property_id INTEGER PRIMARY KEY, lang_id INTEGER, name TEXT)"
        )
        con.executemany(
            "INSERT INTO t_property_report VALUES (?, ?, ?)",
            [(1, 2052, "Emissions by Generator"), (2, 2053, "Fuel Offtake by Generator")],
        )


class TestDiscoverReportClassLangId:
    def test_returns_lang_id(self, tmp_dir):
        db = tmp_dir / "reference.db"
        _create_minimal_db(db, report_class_lang_id=99)
        extender = MOD.ReportExtender(cli_path="mock", simulation_path=str(tmp_dir), study_id="test")
        assert extender._discover_report_class_lang_id() == 99

    def test_raises_when_not_found(self, tmp_dir):
        db = tmp_dir / "reference.db"
        with sqlite3.connect(str(db)) as con:
            con.execute("CREATE TABLE t_class (class_id INTEGER, lang_id INTEGER, name TEXT)")
        extender = MOD.ReportExtender(cli_path="mock", simulation_path=str(tmp_dir), study_id="test")
        with pytest.raises(ValueError, match="Report class lang id"):
            extender._discover_report_class_lang_id()


class TestDiscoverReportingLangIdsByName:
    def test_resolves_single_name(self, tmp_dir):
        db = tmp_dir / "reference.db"
        _create_minimal_db(db)
        extender = MOD.ReportExtender(cli_path="mock", simulation_path=str(tmp_dir), study_id="test")
        result = extender._discover_reporting_lang_ids_by_name(["Emissions by Generator"])
        assert result == [2052]

    def test_resolves_multiple_names(self, tmp_dir):
        db = tmp_dir / "reference.db"
        _create_minimal_db(db)
        extender = MOD.ReportExtender(cli_path="mock", simulation_path=str(tmp_dir), study_id="test")
        result = extender._discover_reporting_lang_ids_by_name(
            ["Emissions by Generator", "Fuel Offtake by Generator"]
        )
        assert result == [2052, 2053]

    def test_case_insensitive(self, tmp_dir):
        db = tmp_dir / "reference.db"
        _create_minimal_db(db)
        extender = MOD.ReportExtender(cli_path="mock", simulation_path=str(tmp_dir), study_id="test")
        result = extender._discover_reporting_lang_ids_by_name(["emissions by generator"])
        assert result == [2052]

    def test_raises_on_unknown_name(self, tmp_dir):
        db = tmp_dir / "reference.db"
        _create_minimal_db(db)
        extender = MOD.ReportExtender(cli_path="mock", simulation_path=str(tmp_dir), study_id="test")
        with pytest.raises(ValueError, match="not found in t_property_report"):
            extender._discover_reporting_lang_ids_by_name(["Nonexistent Property"])


# ── ReportExtender tests ─────────────────────────────────────────────────────────────────

class TestReportExtender:
    def test_extend_success(self, tmp_dir):
        """Successful call configures report properties and returns True."""
        extender = _make_extender(tmp_dir)
        mock_sdk, mock_report_object = _mock_sdk_context("MyReport")
        p1, p2 = _mock_discovery()

        with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            result = extender.extend(
                report_object_name="MyReport",
                reporting_property_names=["Emissions by Generator"],
            )

        assert result is True

    def test_get_object_called_with_resolved_lang_id(self, tmp_dir):
        """get_object_by_name is called with the discovered class lang id and the object name."""
        extender = _make_extender(tmp_dir)
        mock_sdk, _ = _mock_sdk_context()
        p1, p2 = _mock_discovery(report_class_lang_id=99)

        with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            extender.extend(
                report_object_name="Generators",
                reporting_property_names=["Emissions by Generator"],
            )

        mock_sdk.get_object_by_name.assert_called_once_with(99, "Generators")

    def test_configure_report_properties_called_with_correct_params(self, tmp_dir):
        """configure_report_properties receives all expected keyword arguments."""
        extender = _make_extender(tmp_dir)
        mock_sdk, mock_report_object = _mock_sdk_context()
        p1, p2 = _mock_discovery(reporting_lang_ids=[2052, 2053])

        with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            extender.extend(
                report_object_name="Generators",
                reporting_property_names=["Emissions by Generator", "Fuel Offtake by Generator"],
                phase_id=3,
                report_period=True,
                report_samples=True,
                report_statistics=True,
                report_summary=False,
                write_flat_files=True,
            )

        call_kwargs = mock_sdk.configure_report_properties.call_args.kwargs
        assert call_kwargs["object_obj"] is mock_report_object
        assert call_kwargs["reporting_lang_ids"] == [2052, 2053]
        assert call_kwargs["phase_id"] == 3
        assert call_kwargs["report_period"] is True
        assert call_kwargs["report_samples"] is True
        assert call_kwargs["report_statistics"] is True
        assert call_kwargs["report_summary"] is False
        assert call_kwargs["write_flat_files"] is True

    def test_extend_runs_inside_transaction(self, tmp_dir):
        """configure_report_properties is called inside a transaction context."""
        extender = _make_extender(tmp_dir)
        mock_sdk, _ = _mock_sdk_context()
        p1, p2 = _mock_discovery()

        with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            extender.extend(
                report_object_name="Generators",
                reporting_property_names=["Emissions by Generator"],
            )

        mock_sdk.transaction.assert_called_once()

    def test_extend_returns_false_on_object_not_found(self, tmp_dir):
        """An exception from get_object_by_name is caught and returns False."""
        extender = _make_extender(tmp_dir)
        mock_sdk, _ = _mock_sdk_context()
        mock_sdk.get_object_by_name.side_effect = RuntimeError("Object not found")
        p1, p2 = _mock_discovery()

        with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            result = extender.extend(
                report_object_name="Missing",
                reporting_property_names=["Emissions by Generator"],
            )

        assert result is False


# ── main() tests ──────────────────────────────────────────────────────────────

class TestMainFunction:
    def test_main_missing_required_args(self):
        """Exits with error when required arguments are missing."""
        with patch("sys.argv", ["enable_reports.py"]):
            with pytest.raises(SystemExit) as exc:
                MOD.main()
        assert exc.value.code != 0

    def test_main_model_not_found(self, tmp_dir):
        """Returns 1 when reference.db does not exist."""
        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with patch("sys.argv", [
                "enable_reports.py",
                "--report-object-name", "Generators",
                "--reporting-property-names", "Emissions by Generator",
            ]):
                result = MOD.main()
        assert result == 1

    def test_main_success(self, tmp_dir):
        """Returns 0 when extend succeeds."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context("Generators")
        p1, p2 = _mock_discovery()

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator,Fuel Offtake by Generator",
                ]):
                    result = MOD.main()

        assert result == 0

    def test_main_returns_1_on_sdk_error(self, tmp_dir):
        """Returns 1 when the SDK raises an exception."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context()
        mock_sdk.get_object_by_name.side_effect = RuntimeError("SDK error")
        p1, p2 = _mock_discovery()

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator",
                ]):
                    result = MOD.main()

        assert result == 1

    def test_main_returns_1_on_discovery_failure(self, tmp_dir):
        """Returns 1 when a discovery method raises ValueError."""
        (tmp_dir / "reference.db").write_text("mock db")

        with patch.object(MOD, "SIMULATION_PATH", str(tmp_dir)):
            with patch.object(
                MOD.ReportExtender, "_discover_report_class_lang_id",
                side_effect=ValueError("Report class lang id not found"),
            ):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator",
                ]):
                    result = MOD.main()

        assert result == 1

    def test_main_url_encoded_report_name_decoded(self, tmp_dir):
        """URL-encoded report object name is decoded before being passed to extend."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context("My Generators")
        p1, p2 = _mock_discovery(report_class_lang_id=42)

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "My%20Generators",
                    "--reporting-property-names", "Emissions by Generator",
                ]):
                    result = MOD.main()

        assert result == 0
        mock_sdk.get_object_by_name.assert_called_once_with(42, "My Generators")

    def test_main_default_phase_is_lt_maps_to_4(self, tmp_dir):
        """Default --phase of LT maps to phase_id=4 when --phase is not specified."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context()
        p1, p2 = _mock_discovery()

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator",
                ]):
                    MOD.main()

        call_kwargs = mock_sdk.configure_report_properties.call_args.kwargs
        assert call_kwargs["phase_id"] == 4

    def test_main_phase_st_maps_to_1(self, tmp_dir):
        """--phase ST maps to phase_id=1."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context()
        p1, p2 = _mock_discovery()

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator",
                    "--phase", "ST",
                ]):
                    MOD.main()

        call_kwargs = mock_sdk.configure_report_properties.call_args.kwargs
        assert call_kwargs["phase_id"] == 1

    def test_main_phase_mt_maps_to_2(self, tmp_dir):
        """--phase MT maps to phase_id=2."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context()
        p1, p2 = _mock_discovery()

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator",
                    "--phase", "MT",
                ]):
                    MOD.main()

        call_kwargs = mock_sdk.configure_report_properties.call_args.kwargs
        assert call_kwargs["phase_id"] == 2

    def test_main_phase_lowercase_accepted(self, tmp_dir):
        """--phase accepts lowercase values (e.g. 'lt')."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context()
        p1, p2 = _mock_discovery()

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator",
                    "--phase", "lt",
                ]):
                    result = MOD.main()

        assert result == 0
        call_kwargs = mock_sdk.configure_report_properties.call_args.kwargs
        assert call_kwargs["phase_id"] == 4

    def test_main_correct_sdk_param_names(self, tmp_dir):
        """configure_report_properties is called with the correct parameter names."""
        (tmp_dir / "reference.db").write_text("mock db")
        mock_sdk, _ = _mock_sdk_context()
        p1, p2 = _mock_discovery(reporting_lang_ids=[2052, 2053])

        with patch.object(MOD, "SIMULATION_PATH", tmp_dir):
            with p1, p2, patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
                with patch("sys.argv", [
                    "enable_reports.py",
                    "--report-object-name", "Generators",
                    "--reporting-property-names", "Emissions by Generator,Fuel Offtake by Generator",
                    "--report-samples", "true",
                    "--report-statistics", "true",
                    "--write-flat-files", "true",
                ]):
                    MOD.main()

        call_kwargs = mock_sdk.configure_report_properties.call_args.kwargs
        assert "object_obj" in call_kwargs
        assert "reporting_lang_ids" in call_kwargs
        assert "phase_id" in call_kwargs
        assert "report_period" in call_kwargs
        assert "report_samples" in call_kwargs
        assert "report_statistics" in call_kwargs
        assert "report_summary" in call_kwargs
        assert "write_flat_files" in call_kwargs
        assert call_kwargs["reporting_lang_ids"] == [2052, 2053]
        assert call_kwargs["report_samples"] is True
        assert call_kwargs["report_statistics"] is True
        assert call_kwargs["write_flat_files"] is True


# ── _regenerate_xml tests ─────────────────────────────────────────────────────

class TestRegenerateXml:
    def test_xml_restored_from_backup_when_conversion_fails(self, tmp_dir):
        """
        When db-to-xml conversion fails (SDKBase.get_response_data returns None),
        the original project.xml is restored from the .bak file and the method
        returns False — leaving the study with a valid XML.
        """
        xml_path = tmp_dir / "project.xml"
        bak_path = tmp_dir / "project.xml.bak"
        xml_original_content = "<original xml content>"
        xml_path.write_text(xml_original_content)

        extender = MOD.ReportExtender(
            cli_path="mock_cli",
            simulation_path=str(tmp_dir),
            study_id="test_study",
        )

        with patch.object(MOD.SDKBase, "get_response_data", return_value=None):
            result = extender._regenerate_xml()

        assert result is False
        assert xml_path.exists(), "project.xml must be restored after a failed conversion"
        assert xml_path.read_text() == xml_original_content
        assert not bak_path.exists(), ".bak file must be cleaned up after restore"

    def test_xml_restored_from_backup_when_sdk_raises(self, tmp_dir):
        """
        When an exception is raised after the rename (e.g. CloudSDK init or
        convert_database_to_xml raises), the backup is restored and the method
        returns False — the study is never left without project.xml.
        """
        xml_path = tmp_dir / "project.xml"
        bak_path = tmp_dir / "project.xml.bak"
        xml_original_content = "<original xml content>"
        xml_path.write_text(xml_original_content)

        extender = MOD.ReportExtender(
            cli_path="mock_cli",
            simulation_path=str(tmp_dir),
            study_id="test_study",
        )

        with patch.object(MOD, "CloudSDK", side_effect=RuntimeError("SDK init failed")):
            result = extender._regenerate_xml()

        assert result is False
        assert xml_path.exists(), "project.xml must be restored after an exception"
        assert xml_path.read_text() == xml_original_content
        assert not bak_path.exists(), ".bak file must be cleaned up after restore"

