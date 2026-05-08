"""
Unit tests for Pre/PLEXOS/CreateSensitivity/create_sensitivity.py

Tests argument validators, helper utilities, Variable/DataFile creation logic, and main().
plexos_sdk is mocked since it is not installed locally.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Mock the proprietary SDK before importing the script module
_mock_plexos_sdk = MagicMock()
sys.modules.setdefault("plexos_sdk", _mock_plexos_sdk)
sys.modules.setdefault("plexos_sdk.models", _mock_plexos_sdk.models)
sys.modules.setdefault("plexos_sdk.models.plexos_models", _mock_plexos_sdk.models.plexos_models)

from .conftest import get_module

MOD = get_module("create_sensitivity")


def _mock_sdk_context(base_value=100.0):
    """Return a context-manager-compatible mock SDK.

    base_value is returned by get_property_value (Branch A).  Pass None to
    simulate a missing base value.  It is unused in Branch B tests.
    """
    mock_membership = MagicMock()
    mock_membership.membership_id = 42

    mock_variable_membership = MagicMock()
    mock_variable_membership.membership_id = 43

    mock_scenario_membership = MagicMock()
    mock_scenario_membership.membership_id = 44

    mock_property_obj = MagicMock()
    mock_property_obj.property_id = 201

    mock_scenario_obj = MagicMock()
    mock_scenario_obj.object_id = 501
    mock_df_obj = MagicMock()
    mock_df_obj.object_id = 601
    mock_var_obj = MagicMock()
    mock_var_obj.object_id = 701
    mock_model_obj = MagicMock()
    mock_model_obj.object_id = 801
    mock_system_obj = MagicMock()
    mock_system_obj.object_id = 1
    mock_collection_obj = MagicMock()
    mock_collection_obj.child_class.lang_id = 10

    mock_sdk = MagicMock()

    def get_membership_by_names(*, parent_class_lang_id, collection_lang_id, parent_name, child_name):
        if parent_name == "Model":
            raise Exception("not found")
        if child_name and str(child_name).endswith("_Var"):
            return mock_variable_membership
        return mock_membership

    def get_object_by_name(*, class_lang_id, object_name):
        if class_lang_id == 10:
            return mock_scenario_obj
        if class_lang_id == 11:
            return mock_model_obj
        if class_lang_id == 1 and object_name == "System":
            return mock_system_obj
        if class_lang_id == 2:
            return mock_df_obj
        if class_lang_id == 3:
            return mock_var_obj
        raise Exception(f"Unexpected object lookup: class_lang_id={class_lang_id}, object_name={object_name}")

    def add_object(*, class_lang_id, object_name, **_kwargs):
        if class_lang_id == 10:
            return mock_scenario_obj
        if class_lang_id == 3:
            return mock_var_obj
        return MagicMock()

    mock_sdk.get_membership_by_names.side_effect = get_membership_by_names
    mock_sdk.get_property.return_value = mock_property_obj
    mock_sdk.get_property_value.return_value = base_value
    mock_sdk.get_object_by_name.side_effect = get_object_by_name
    mock_sdk.add_object.side_effect = add_object
    mock_sdk.get_collection.return_value = mock_collection_obj
    mock_sdk.add_membership.return_value = mock_scenario_membership
    mock_sdk.__enter__ = MagicMock(return_value=mock_sdk)
    mock_sdk.__exit__ = MagicMock(return_value=False)
    mock_sdk.transaction.return_value.__enter__ = MagicMock(return_value=None)
    mock_sdk.transaction.return_value.__exit__ = MagicMock(return_value=False)
    return (
        mock_sdk,
        mock_membership,
        mock_property_obj,
        mock_scenario_obj,
        mock_df_obj,
        mock_var_obj,
        mock_model_obj,
        mock_system_obj,
        mock_variable_membership,
    )


def _make_creator(tmp_dir: Path):
    """Return a SensitivityCreator with a pre-created reference.db in tmp_dir."""
    (tmp_dir / "reference.db").write_text("mock db")
    return MOD.SensitivityCreator(
        cli_path="mock_cli_path",
        simulation_path=str(tmp_dir),
        study_id="test_study_001",
    )






# ── positive_int tests ───────────────────────────────────────────────────────

class TestPositiveInt:
    def test_valid_integer(self):
        assert MOD.positive_int("5") == 5

    def test_one_is_valid(self):
        assert MOD.positive_int("1") == 1

    def test_large_integer(self):
        assert MOD.positive_int("999") == 999

    def test_zero_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            MOD.positive_int("0")

    def test_negative_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            MOD.positive_int("-1")

    def test_non_integer_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="Expected integer"):
            MOD.positive_int("abc")

    def test_float_string_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="Expected integer"):
            MOD.positive_int("1.5")


# ── non_empty_text tests ───────────────────────────────────────────────────────

class TestNonEmptyText:
    def test_valid_text(self):
        assert MOD.non_empty_text("System") == "System"

    def test_strips_whitespace(self):
        assert MOD.non_empty_text("  Zone1  ") == "Zone1"

    def test_empty_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="cannot be empty"):
            MOD.non_empty_text("   ")

    def test_empty_string_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            MOD.non_empty_text("")


# ── parse_sensitivity_delta tests ───────────────────────────────────────────────────────

class TestParseSensitivityDelta:
    def test_positive_percent(self):
        assert MOD.parse_sensitivity_delta("+5%") == pytest.approx(0.05)

    def test_negative_percent(self):
        assert MOD.parse_sensitivity_delta("-10%") == pytest.approx(-0.10)

    def test_no_percent_sign(self):
        assert MOD.parse_sensitivity_delta("2.5") == pytest.approx(0.025)

    def test_whitespace_stripped(self):
        assert MOD.parse_sensitivity_delta("  +5%  ") == pytest.approx(0.05)

    def test_zero(self):
        assert MOD.parse_sensitivity_delta("0%") == pytest.approx(0.0)

    def test_decimal_percent(self):
        assert MOD.parse_sensitivity_delta("+2.5%") == pytest.approx(0.025)

    def test_url_encoded_percent(self):
        assert MOD.parse_sensitivity_delta("%2B5%25") == pytest.approx(0.05)

    def test_url_encoded_percent_with_wrapping_quotes(self):
        assert MOD.parse_sensitivity_delta("'%2B5%25'") == pytest.approx(0.05)

    def test_empty_string_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError):
            MOD.parse_sensitivity_delta("")

    def test_invalid_raises(self):
        import argparse
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid sensitivity value"):
            MOD.parse_sensitivity_delta("abc%")

    def test_returns_float(self):
        result = MOD.parse_sensitivity_delta("5%")
        assert isinstance(result, float)


# ── get_or_create_scenario_object tests ───────────────────────────────────────────────────────

class TestGetOrCreateScenarioObject:
    def test_returns_existing_object_when_found(self):
        existing = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.get_object_by_name.return_value = existing

        result = MOD.get_or_create_scenario_object(mock_sdk, 10, "Sensitivity_plus_5pct")

        mock_sdk.get_object_by_name.assert_called_once_with(
            class_lang_id=10, object_name="Sensitivity_plus_5pct"
        )
        mock_sdk.add_object.assert_not_called()
        assert result is existing

    def test_creates_object_when_not_found(self):
        created = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.get_object_by_name.side_effect = Exception("not found")
        mock_sdk.add_object.return_value = created

        result = MOD.get_or_create_scenario_object(mock_sdk, 10, "Sensitivity_plus_5pct")

        mock_sdk.add_object.assert_called_once_with(
            class_lang_id=10, object_name="Sensitivity_plus_5pct"
        )
        assert result is created


# ---- _set_property_action tests --------------------------------------------------------------------

class TestSetPropertyAction:
    def test_updates_only_expression_tag(self, tmp_dir):
        import sqlite3

        db = str(tmp_dir / "action_test.db")
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE t_data (data_id INTEGER, membership_id INTEGER, property_id INTEGER)")
            con.execute("CREATE TABLE t_band (data_id INTEGER, band_id INTEGER)")
            con.execute("CREATE TABLE t_tag (data_id INTEGER, object_id INTEGER, action_id INTEGER)")

            con.execute("INSERT INTO t_data VALUES (1001, 42, 201)")
            con.execute("INSERT INTO t_band VALUES (1001, 1)")
            con.execute("INSERT INTO t_tag VALUES (1001, 701, NULL)")  # Variable expression tag
            con.execute("INSERT INTO t_tag VALUES (1001, 601, NULL)")  # Data File tag

        MOD._set_property_action(
            db_path=db,
            membership_id=42,
            property_id=201,
            band_id=1,
            action_id=1,
            expression_object_id=701,
        )

        with sqlite3.connect(db) as con:
            rows = con.execute(
                "SELECT object_id, action_id FROM t_tag WHERE data_id = 1001 ORDER BY object_id"
            ).fetchall()

        assert rows == [(601, None), (701, 1)]

    def test_warns_when_expression_tag_not_found(self, tmp_dir, capsys):
        import sqlite3

        db = str(tmp_dir / "action_test_missing_expr.db")
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE t_data (data_id INTEGER, membership_id INTEGER, property_id INTEGER)")
            con.execute("CREATE TABLE t_band (data_id INTEGER, band_id INTEGER)")
            con.execute("CREATE TABLE t_tag (data_id INTEGER, object_id INTEGER, action_id INTEGER)")

            con.execute("INSERT INTO t_data VALUES (1001, 42, 201)")
            con.execute("INSERT INTO t_band VALUES (1001, 1)")
            con.execute("INSERT INTO t_tag VALUES (1001, 601, NULL)")

        MOD._set_property_action(
            db_path=db,
            membership_id=42,
            property_id=201,
            band_id=1,
            action_id=1,
            expression_object_id=701,
        )
        captured = capsys.readouterr()
        assert "No expression tag row found" in captured.out

        with sqlite3.connect(db) as con:
            action = con.execute(
                "SELECT action_id FROM t_tag WHERE data_id = 1001 AND object_id = 601"
            ).fetchone()[0]
        assert action is None

# ---- SensitivityCreator._create_sensitivity tests ------------------------------------------------------------

class TestSensitivityCreatorCreateSensitivity:
    """Tests for _create_sensitivity, covering both Branch A and Branch B."""

    def _call(self, tmp_dir, mock_sdk, query_first_object_names=None, **overrides):
        """Patch all raw-SQL helpers and call _create_sensitivity.

        Defaults to Branch A (data_file_name=None).  Pass data_file_name/variable_name
        overrides to exercise Branch B.
        """
        creator = _make_creator(tmp_dir)
        kwargs = dict(
            collection_name="System.Generators",
            parent_object_name="System",
            child_object_name="Gen1",
            property_name="MaxCapacity",
            sensitivity=0.05,
            data_file_name=None,        # Branch A by default
            variable_name=None,
            scenario_name="MySensitivity",
            scenario_class_name="Scenario",
            band_id=1,
        )
        kwargs.update(overrides)

        if kwargs["variable_name"] is None:
            if kwargs["data_file_name"] is not None:
                kwargs["variable_name"] = f"{kwargs['data_file_name']}_Var"
            else:
                kwargs["variable_name"] = f"{kwargs['child_object_name']}_{kwargs['property_name']}_Var"

        name_map = query_first_object_names or {1: "System", 11: "Model"}

        def query_class_lang_id(_db_path, class_name):
            return {
                "Scenario": 10,
                "Model": 11,
                "System": 1,
                "Data File": 2,
                "Variable": 3,
            }[class_name]

        def query_collection_lang_id(_db_path, parent_class_lang_id, child_class_lang_id, preferred_name=None):
            if preferred_name == "Scenarios":
                return 210
            return 200

        def query_property_lang_id(_db_path, _collection_lang_id, name):
            return {
                "Profile": 70,
            }[name]

        with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            with patch.object(creator, "_resolve_ids", return_value=(1, 195, 201)):
                with patch.object(MOD, "_query_class_lang_id", side_effect=query_class_lang_id):
                    with patch.object(MOD, "_query_first_object_name_by_class_lang_id", side_effect=lambda _db, cid: name_map[cid]):
                        with patch.object(MOD, "_query_collection_lang_id", side_effect=query_collection_lang_id):
                            with patch.object(MOD, "_query_property_lang_id", side_effect=query_property_lang_id):
                                with patch.object(MOD, "_set_property_action"):
                                    creator._create_sensitivity(**kwargs)

    # ── Branch A (no data file — numeric value) ────────────────────────────────

    def test_branch_a_writes_computed_numeric_value(self, tmp_dir):
        mock_sdk, _, _, mock_scenario_obj, *_ = _mock_sdk_context(base_value=200.0)
        self._call(tmp_dir, mock_sdk, sensitivity=0.10)
        # add_property called once with computed value and scenario_tag; no expression_tag
        calls = [
            c for c in mock_sdk.add_property.call_args_list
            if c.kwargs.get("value") == pytest.approx(220.0)
        ]
        assert len(calls) == 1
        assert calls[0].kwargs.get("scenario_tag") is mock_scenario_obj
        assert "expression_tag" not in calls[0].kwargs

    def test_branch_a_reads_base_value(self, tmp_dir):
        mock_sdk, mock_membership, mock_property_obj, *_ = _mock_sdk_context(base_value=100.0)
        self._call(tmp_dir, mock_sdk)
        mock_sdk.get_property_value.assert_called_once_with(
            membership=mock_membership,
            property_obj=mock_property_obj,
            band_id=1,
        )

    def test_branch_a_raises_when_base_value_is_none(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context(base_value=None)
        with pytest.raises(ValueError, match="Base property value not found"):
            self._call(tmp_dir, mock_sdk)

    def test_branch_a_does_not_look_up_data_file(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context(base_value=100.0)
        self._call(tmp_dir, mock_sdk)  # data_file_path=None
        looked_up_names = {
            call.kwargs["object_name"]
            for call in mock_sdk.get_object_by_name.call_args_list
            if "object_name" in call.kwargs
        }
        assert looked_up_names == {"Model", "MySensitivity", "Gen1_MaxCapacity_Var"}
        assert "s" not in looked_up_names

    def test_branch_a_numeric_value_uses_correct_band_id(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context(base_value=100.0)
        self._call(tmp_dir, mock_sdk, band_id=3)
        expression_calls = [
            c for c in mock_sdk.add_property.call_args_list
            if c.kwargs.get("expression_tag") is not None
        ]
        assert expression_calls[0].kwargs["band_id"] == 3

    # ── Branch B (data file provided — expression + variable) ─────────────────

    def test_branch_b_looks_up_existing_data_file(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context()
        self._call(tmp_dir, mock_sdk,
                   data_file_name="s", variable_name="s_Var")
        looked_up_names = [
            call.kwargs["object_name"]
            for call in mock_sdk.get_object_by_name.call_args_list
            if "object_name" in call.kwargs
        ]
        assert "s" in looked_up_names
        assert "s_Var" in looked_up_names

    def test_branch_b_raises_when_data_file_not_found_in_model(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context()
        original_get_object = mock_sdk.get_object_by_name.side_effect

        def get_object_by_name(*, class_lang_id, object_name):
            if class_lang_id == 2 and object_name == "s":
                raise Exception("not found")
            return original_get_object(
                class_lang_id=class_lang_id,
                object_name=object_name,
            )

        mock_sdk.get_object_by_name.side_effect = get_object_by_name
        with pytest.raises(ValueError, match="Data File object"):
            self._call(tmp_dir, mock_sdk,
                       data_file_name="s", variable_name="s_Var")

    def test_branch_b_creates_variable_when_not_found(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context()
        original_get_object = mock_sdk.get_object_by_name.side_effect

        def get_object_by_name(*, class_lang_id, object_name):
            if class_lang_id == 3 and object_name == "s_Var":
                raise Exception("not found")
            return original_get_object(
                class_lang_id=class_lang_id,
                object_name=object_name,
            )

        mock_sdk.get_object_by_name.side_effect = get_object_by_name
        self._call(tmp_dir, mock_sdk,
                   data_file_name="s", variable_name="s_Var")
        assert mock_sdk.add_object.call_count == 1

    def test_branch_b_variable_profile_linked_to_data_file(self, tmp_dir):
        mock_sdk, _, _, _, mock_df_obj, _, *_ = _mock_sdk_context()
        self._call(tmp_dir, mock_sdk,
                   data_file_name="s", variable_name="s_Var")
        calls_with_df_tag = [
            c for c in mock_sdk.add_property.call_args_list
            if c.kwargs.get("data_file_tag") is mock_df_obj
        ]
        assert len(calls_with_df_tag) == 1

    def test_branch_b_profile_value_is_set_with_scenario_tag(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context()
        self._call(tmp_dir, mock_sdk,
                   data_file_name="s", variable_name="s_Var")
        profile_calls = [
            c for c in mock_sdk.add_property.call_args_list
            if c.kwargs.get("value") == pytest.approx(1.05)
        ]
        assert len(profile_calls) == 1
        assert profile_calls[0].kwargs.get("scenario_tag") is not None

    def test_branch_b_property_tagged_with_expression_and_scenario(self, tmp_dir):
        mock_sdk, _, _, mock_scenario_obj, _, mock_var_obj, *_ = _mock_sdk_context()
        self._call(tmp_dir, mock_sdk,
                   data_file_name="s", variable_name="s_Var")
        calls = [
            c for c in mock_sdk.add_property.call_args_list
            if c.kwargs.get("expression_tag") is mock_var_obj
            and c.kwargs.get("scenario_tag") is mock_scenario_obj
        ]
        assert len(calls) == 1

    def test_branch_b_expression_uses_correct_band_id(self, tmp_dir):
        mock_sdk, _, _, _, _, mock_var_obj, *_ = _mock_sdk_context()
        self._call(tmp_dir, mock_sdk,
                   data_file_name="s", variable_name="s_Var",
                   band_id=3)
        calls = [c for c in mock_sdk.add_property.call_args_list if c.kwargs.get("expression_tag") is mock_var_obj]
        assert calls[0].kwargs["band_id"] == 3

    def test_branch_b_set_action_called_with_multiply(self, tmp_dir):
        """Expression mode always calls _set_property_action with action_id=1 (×)."""
        mock_sdk, *_ = _mock_sdk_context()

        def query_class_lang_id(_db_path, class_name):
            return {
                "Scenario": 10,
                "Model": 11,
                "System": 1,
                "Data File": 2,
                "Variable": 3,
            }[class_name]

        def query_collection_lang_id(_db_path, parent_class_lang_id, child_class_lang_id, preferred_name=None):
            if preferred_name == "Scenarios":
                return 210
            return 200

        def query_property_lang_id(_db_path, _collection_lang_id, name):
            return {
                "Profile": 70,
            }[name]

        with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            creator = _make_creator(tmp_dir)
            with patch.object(creator, "_resolve_ids", return_value=(1, 195, 201)):
                with patch.object(MOD, "_query_class_lang_id", side_effect=query_class_lang_id):
                    with patch.object(MOD, "_query_first_object_name_by_class_lang_id", side_effect=lambda _db, cid: {1: "System", 11: "Model"}[cid]):
                        with patch.object(MOD, "_query_collection_lang_id", side_effect=query_collection_lang_id):
                            with patch.object(MOD, "_query_property_lang_id", side_effect=query_property_lang_id):
                                with patch.object(MOD, "_set_property_action") as mock_action:
                                    creator._create_sensitivity(
                                        collection_name="System.Generators",
                                        parent_object_name="System",
                                        child_object_name="Gen1",
                                        property_name="MaxCapacity",
                                        sensitivity=0.05,
                                        data_file_name="f",
                                        variable_name="f_Var",
                                        scenario_name="S",
                                        scenario_class_name="Scenario",
                                        band_id=1,
                                    )
        assert mock_action.call_count == 1
        _, call_args, _ = mock_action.mock_calls[0]
        assert call_args[4] == 1  # action_id is always 1 (×) in expression mode
        assert call_args[5] == 701  # expression_object_id (Variable.object_id)

    def test_branch_a_set_action_called_with_assign(self, tmp_dir):
        """Numeric mode must call _set_property_action with action_id=0 (=)."""
        mock_sdk, *_ = _mock_sdk_context(base_value=100.0)

        def query_class_lang_id(_db_path, class_name):
            return {
                "Scenario": 10,
                "Model": 11,
                "System": 1,
                "Variable": 3,
            }[class_name]

        def query_collection_lang_id(_db_path, parent_class_lang_id, child_class_lang_id, preferred_name=None):
            if preferred_name == "Scenarios":
                return 210
            return 200

        with patch.object(MOD, "PLEXOSSDK", return_value=mock_sdk):
            creator = _make_creator(tmp_dir)
            with patch.object(creator, "_resolve_ids", return_value=(1, 195, 201)):
                with patch.object(MOD, "_query_class_lang_id", side_effect=query_class_lang_id):
                    with patch.object(MOD, "_query_first_object_name_by_class_lang_id", side_effect=lambda _db, cid: {1: "System", 11: "Model"}[cid]):
                        with patch.object(MOD, "_query_collection_lang_id", side_effect=query_collection_lang_id):
                            with patch.object(MOD, "_query_property_lang_id", side_effect=[60, 70]):
                                with patch.object(MOD, "_set_property_action") as mock_action:
                                    creator._create_sensitivity(
                                        collection_name="System.Generators",
                                        parent_object_name="System",
                                        child_object_name="Gen1",
                                        property_name="MaxCapacity",
                                        sensitivity=0.05,
                                        data_file_name=None,
                                        variable_name="Gen1_MaxCapacity_Var",
                                        scenario_name="S",
                                        scenario_class_name="Scenario",
                                        band_id=1,
                                    )
        assert mock_action.call_count == 1
        _, call_args, _ = mock_action.mock_calls[0]
        assert call_args[4] == 0
        assert call_args[5] == 701

    def test_raises_when_membership_not_found(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context(base_value=100.0)

        def get_membership_by_names(*, parent_class_lang_id, collection_lang_id, parent_name, child_name):
            if parent_name == "Model":
                raise Exception("not found")
            raise Exception("not found")

        mock_sdk.get_membership_by_names.side_effect = get_membership_by_names
        with pytest.raises(ValueError, match="Membership not found"):
            self._call(tmp_dir, mock_sdk)

    def test_system_object_name_resolved_from_db(self, tmp_dir):
        """When the System-class object is not named 'System', the resolved name is used."""
        mock_sdk, *_ = _mock_sdk_context(base_value=100.0)

        # Make System-class object named "DEMO" instead of "System"
        mock_demo_obj = MagicMock(object_id=99)

        original_get_object = mock_sdk.get_object_by_name.side_effect

        def get_object_by_name(*, class_lang_id, object_name):
            if class_lang_id == 1 and object_name == "DEMO":
                return mock_demo_obj
            return original_get_object(class_lang_id=class_lang_id, object_name=object_name)

        mock_sdk.get_object_by_name.side_effect = get_object_by_name

        # Force membership lookup to fail so the fallback path calls get_object_by_name("DEMO")
        original_get_membership = mock_sdk.get_membership_by_names.side_effect

        def get_membership_by_names(*, parent_class_lang_id, collection_lang_id, parent_name, child_name):
            if parent_name == "DEMO":
                raise Exception("not found")
            return original_get_membership(
                parent_class_lang_id=parent_class_lang_id,
                collection_lang_id=collection_lang_id,
                parent_name=parent_name,
                child_name=child_name,
            )

        mock_sdk.get_membership_by_names.side_effect = get_membership_by_names

        self._call(tmp_dir, mock_sdk,
                   query_first_object_names={1: "DEMO", 11: "Model"})

        # Verify get_object_by_name was called with "DEMO" (not "System")
        demo_calls = [
            c for c in mock_sdk.get_object_by_name.call_args_list
            if c.kwargs.get("class_lang_id") == 1 and c.kwargs.get("object_name") == "DEMO"
        ]
        assert len(demo_calls) == 1

    def test_creates_model_scenario_membership_when_missing(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context(base_value=100.0)
        self._call(tmp_dir, mock_sdk)
        mock_sdk.add_membership.assert_called_once()

    def test_skips_model_scenario_membership_when_present(self, tmp_dir):
        mock_sdk, *_ = _mock_sdk_context(base_value=100.0)

        def get_membership_by_names(*, parent_class_lang_id, collection_lang_id, parent_name, child_name):
            if parent_name == "Model":
                return MagicMock(membership_id=99)
            if child_name and str(child_name).endswith("_Var"):
                return MagicMock(membership_id=43)
            return MagicMock(membership_id=42)

        mock_sdk.get_membership_by_names.side_effect = get_membership_by_names
        self._call(tmp_dir, mock_sdk)
        mock_sdk.add_membership.assert_not_called()


# ---- main() tests ----------------------------------------------------------------------------------------------------------------------------

class TestMain:
    # Branch A base args — no --data-file-path (optional, defaults to None)
    _BASE_ARGS = [
        "create_sensitivity.py",
        "--collection-name", "System.Generators",
        "--parent-object-name", "Generator1",
        "--child-object-name", "Zone1",
        "--property-name", "MaxCapacity",
        "--sensitivity", "+5%",
    ]

    # Branch B base args — data file name provided
    _BASE_ARGS_B = [
        "create_sensitivity.py",
        "--collection-name", "System.Generators",
        "--parent-object-name", "Generator1",
        "--child-object-name", "Zone1",
        "--property-name", "MaxCapacity",
        "--sensitivity", "+5%",
        "--data-file-name", "sens",
    ]

    def test_returns_1_when_model_file_not_found(self, tmp_dir, monkeypatch):
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)
        assert MOD.main() == 1

    def test_returns_0_on_success(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity"):
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                result = MOD.main()

        assert result == 0

    def test_returns_1_on_sdk_exception(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)

        with patch.object(
            MOD.SensitivityCreator,
            "_create_sensitivity",
            side_effect=RuntimeError("SDK boom"),
        ):
            result = MOD.main()

        assert result == 1

    def test_returns_1_when_regenerate_xml_fails(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity"):
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=False):
                result = MOD.main()

        assert result == 1

    def test_branch_a_passes_none_for_data_file_fields(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)  # no --data-file-name

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity") as mock_fn:
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                MOD.main()

        _, kwargs = mock_fn.call_args
        assert kwargs["data_file_name"] is None
        assert kwargs["variable_name"] == "Zone1_MaxCapacity_Var"

    def test_branch_b_passes_correct_args(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", [
            "create_sensitivity.py",
            "--collection-name", "System.Nodes",
            "--parent-object-name", "MyParent",
            "--child-object-name", "MyChild",
            "--property-name", "Load",
            "--sensitivity", "+10%",
            "--data-file-name", "load_sens",
            "--variable-name", "load_sens_Var",
            "--scenario-name", "LoadSens",
            "--band-id", "2",
        ])

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity") as mock_fn:
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                MOD.main()

        _, kwargs = mock_fn.call_args
        assert kwargs["collection_name"] == "System.Nodes"
        assert kwargs["parent_object_name"] == "MyParent"
        assert kwargs["child_object_name"] == "MyChild"
        assert kwargs["property_name"] == "Load"
        assert kwargs["sensitivity"] == pytest.approx(0.10)
        assert kwargs["data_file_name"] == "load_sens"
        assert kwargs["variable_name"] == "load_sens_Var"
        assert kwargs["scenario_name"] == "LoadSens"
        assert kwargs["band_id"] == 2

    def test_variable_name_defaults_to_data_file_name_var(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS_B)

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity") as mock_fn:
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                MOD.main()

        _, kwargs = mock_fn.call_args
        assert kwargs["variable_name"] == "sens_Var"

    def test_default_scenario_name_is_sensitivity(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity") as mock_fn:
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                MOD.main()

        _, kwargs = mock_fn.call_args
        assert kwargs["scenario_name"] == "Sensitivity"

    def test_default_band_id_is_1(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity") as mock_fn:
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                MOD.main()

        _, kwargs = mock_fn.call_args
        assert kwargs["band_id"] == 1

    def test_branch_a_does_not_pass_data_file_name(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", self._BASE_ARGS)

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity") as mock_fn:
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                MOD.main()

        _, kwargs = mock_fn.call_args
        assert kwargs["data_file_name"] is None
        assert "action_id" not in kwargs

    def test_main_accepts_url_encoded_sensitivity(self, tmp_dir, monkeypatch):
        (tmp_dir / "reference.db").write_text("db")
        monkeypatch.setattr(MOD, "SIMULATION_PATH", str(tmp_dir))
        monkeypatch.setattr(sys, "argv", [
            "create_sensitivity.py",
            "--collection-name", "System.Generators",
            "--parent-object-name", "Generator1",
            "--child-object-name", "Zone1",
            "--property-name", "MaxCapacity",
            "--sensitivity", "%2B5%25",
        ])

        with patch.object(MOD.SensitivityCreator, "_create_sensitivity") as mock_fn:
            with patch.object(MOD.SensitivityCreator, "_regenerate_xml", return_value=True):
                result = MOD.main()

        _, kwargs = mock_fn.call_args
        assert result == 0
        assert kwargs["sensitivity"] == pytest.approx(0.05)

    def test_help_describes_sensitivity_as_calculation_only(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["create_sensitivity.py", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            MOD.main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "calculate the" in captured.out
        assert "Variable.Profile adjustment" in captured.out
        assert "Used to label the scenario and Variable objects" not in captured.out


# ---- _regenerate_xml tests -------------------------------------------------------------------------------------------------

class TestRegenerateXml:
    def test_success_removes_backup_after_conversion(self, tmp_dir):
        creator = _make_creator(tmp_dir)
        xml_path = Path(creator.xml_path)
        backup_path = Path(f"{creator.xml_path}.bak")
        xml_path.write_text("old xml")

        mock_response = MagicMock()
        mock_pxc = MagicMock()

        def convert_side_effect(**_kwargs):
            xml_path.write_text("new xml")
            return mock_response

        mock_pxc.inputdata.convert_database_to_xml.side_effect = convert_side_effect

        with patch.object(MOD, "CloudSDK", return_value=mock_pxc):
            with patch.object(MOD.SDKBase, "get_response_data", return_value={"ok": True}):
                result = creator._regenerate_xml()

        assert result is True
        assert xml_path.exists()
        assert xml_path.read_text() == "new xml"
        assert not backup_path.exists()

    def test_restores_backup_when_conversion_returns_none(self, tmp_dir):
        creator = _make_creator(tmp_dir)
        xml_path = Path(creator.xml_path)
        backup_path = Path(f"{creator.xml_path}.bak")
        xml_path.write_text("old xml")

        mock_response = MagicMock()
        mock_response.Message = "conversion failed"
        mock_pxc = MagicMock()
        mock_pxc.inputdata.convert_database_to_xml.return_value = mock_response

        with patch.object(MOD, "CloudSDK", return_value=mock_pxc):
            with patch.object(MOD.SDKBase, "get_response_data", return_value=None):
                result = creator._regenerate_xml()

        assert result is False
        assert xml_path.exists()
        assert xml_path.read_text() == "old xml"
        assert not backup_path.exists()

    def test_restores_backup_when_conversion_raises(self, tmp_dir):
        creator = _make_creator(tmp_dir)
        xml_path = Path(creator.xml_path)
        backup_path = Path(f"{creator.xml_path}.bak")
        xml_path.write_text("old xml")

        mock_pxc = MagicMock()
        mock_pxc.inputdata.convert_database_to_xml.side_effect = RuntimeError("boom")

        with patch.object(MOD, "CloudSDK", return_value=mock_pxc):
            result = creator._regenerate_xml()

        assert result is False
        assert xml_path.exists()
        assert xml_path.read_text() == "old xml"
        assert not backup_path.exists()
