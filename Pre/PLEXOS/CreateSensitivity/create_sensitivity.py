"""
Create a Variable-expression sensitivity on a target property using the PLEXOS SDK.

Creates or reuses a Variable object and a Scenario, then tags the target
property with the Variable expression under that Scenario.
When a Data File name is supplied, the script links expression evaluation to the
existing Data File object in the model.

Focused script - creates one sensitivity expression for one target property.
Chain multiple task entries when applying sensitivities to many properties.

Environment variables used:
    cloud_cli_path  - required; path to the Cloud CLI executable
    study_id        - required; identifies the current study
    simulation_path - root path for study files; reference.db is read, project.xml is written here
"""

import argparse
import os
import sqlite3
import sys
from urllib.parse import unquote

from eecloud.cloudsdk import CloudSDK, SDKBase
from plexos_sdk import PLEXOSSDK
from plexos_sdk.models.plexos_models import Collection, Property

try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("[FAIL] Missing required environment variable: cloud_cli_path")
    sys.exit(1)

try:
    STUDY_ID = os.environ["study_id"]
except KeyError:
    print("[FAIL] Missing required environment variable: study_id")
    sys.exit(1)

SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")


# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION — These defaults are used when no command-line arguments are provided.
# ═══════════════════════════════════════════════════════════════════════════════
# Parent object name for membership lookup.
# Example: "System"
PARENT_OBJECT_NAME = "System"
# Name for the Scenario object to create or reuse.
# Example: "Sensitivity"
SCENARIO_NAME = "Sensitivity"

# Class name for scenario objects.
# Example: "Scenario"
SCENARIO_CLASS_NAME = "Scenario"

# Property band id to write the expression tag on.
# Example: 1
BAND_ID = 1

# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════


# ── Argument decoder ──────────────────────────────────────────────────────────

def _decode_value(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


# ── Argument validators ───────────────────────────────────────────────────────

def positive_int(value: str) -> int:
    """Validate positive integer argument values."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, got '{value}'") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0")

    return parsed


def non_empty_text(value: str) -> str:
    """Validate non-empty text argument values."""
    cleaned = value.strip()
    if not cleaned:
        raise argparse.ArgumentTypeError("Value cannot be empty")
    return cleaned


def parse_sensitivity_delta(value: str) -> float:
    """Parse a single sensitivity percentage into a decimal delta."""
    normalized = _decode_value(value).strip()
    if not normalized:
        raise argparse.ArgumentTypeError("Value cannot be empty")

    if normalized.endswith("%"):
        normalized = normalized[:-1].strip()

    try:
        percent_value = float(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid sensitivity value '{value}'. Use values like +5%, -5%, 5, or 2.5"
        ) from exc

    return round(percent_value / 100.0, 8)


# ── Raw SQLite helpers ────────────────────────────────────────────────────────

def _query_class_lang_id(db_path: str, class_name: str) -> int:
    """Look up a class lang_id by name (exact or plural form)."""
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            """
            SELECT lang_id FROM t_class
            WHERE lower(name) = lower(?)
               OR lower(name) = lower(? || 's')
            ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (class_name, class_name, class_name),
        ).fetchone()
    if not row:
        raise ValueError(f"Class '{class_name}' not found in model.")
    return int(row[0])


def _query_collection_lang_id(
    db_path: str,
    parent_class_lang_id: int,
    child_class_lang_id: int,
    preferred_name: str | None = None,
) -> int:
    """Look up a collection lang_id by parent/child class lang_ids."""
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            """
            SELECT col.lang_id FROM t_collection col
            JOIN t_class pc ON pc.class_id = col.parent_class_id
            JOIN t_class cc ON cc.class_id = col.child_class_id
            WHERE pc.lang_id = ? AND cc.lang_id = ?
            ORDER BY
              CASE WHEN ? IS NOT NULL AND lower(col.name) = lower(?) THEN 0 ELSE 1 END,
              col.collection_id
            LIMIT 1
            """,
            (parent_class_lang_id, child_class_lang_id, preferred_name, preferred_name),
        ).fetchone()
    if not row:
        raise ValueError(
            f"Collection not found for parent_class_lang_id={parent_class_lang_id}, "
            f"child_class_lang_id={child_class_lang_id}."
        )
    return int(row[0])


def _query_property_lang_id(db_path: str, collection_lang_id: int, name: str) -> int:
    """Look up a property lang_id by collection lang_id and property name."""
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            """
            SELECT p.lang_id FROM t_property p
            JOIN t_collection c ON c.collection_id = p.collection_id
            WHERE c.lang_id = ? AND lower(p.name) = lower(?)
            LIMIT 1
            """,
            (collection_lang_id, name),
        ).fetchone()
    if not row:
        raise ValueError(
            f"Property '{name}' not found in collection lang_id={collection_lang_id}."
        )
    return int(row[0])


def _query_first_object_name_by_class_lang_id(db_path: str, class_lang_id: int) -> str:
    """Return the first object name for a class lang_id."""
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            """
            SELECT o.name
            FROM t_object o
            JOIN t_class c ON c.class_id = o.class_id
            WHERE c.lang_id = ?
            ORDER BY o.object_id
            LIMIT 1
            """,
            (class_lang_id,),
        ).fetchone()
    if not row:
        raise ValueError(f"No object found for class lang_id={class_lang_id}.")
    return str(row[0])


def _set_property_action(
    db_path: str,
    membership_id: int,
    property_id: int,
    band_id: int,
    action_id: int,
    expression_object_id: int,
) -> None:
    """Set action_id on the exact expression-tag row for a property data entry."""
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            """
            SELECT d.data_id FROM t_data d
            LEFT JOIN t_band b ON b.data_id = d.data_id
            WHERE d.membership_id = ? AND d.property_id = ?
              AND COALESCE(b.band_id, 1) = ?
            ORDER BY d.data_id DESC LIMIT 1
            """,
            (membership_id, property_id, band_id),
        ).fetchone()
        if not row:
            print(
                f"[WARN] No data entry found for membership_id={membership_id}, "
                f"property_id={property_id}, band_id={band_id}"
            )
            return
        data_id = row[0]

        result = con.execute(
            """
            UPDATE t_tag
            SET action_id = ?
            WHERE data_id = ?
              AND object_id = ?
            """,
            (action_id, data_id, expression_object_id),
        )
        if result.rowcount == 0:
            print(
                f"[WARN] No expression tag row found for data_id={data_id}, "
                f"expression_object_id={expression_object_id}"
            )
            return
        con.commit()
    print(f"[OK] Action id={action_id} set on property (data_id={data_id})")


# ── Scenario helper ───────────────────────────────────────────────────────────

def get_or_create_scenario_object(sdk, scenario_class_lang_id: int, scenario_name: str):
    """Get existing scenario object by name or create it if missing."""
    try:
        return sdk.get_object_by_name(
            class_lang_id=scenario_class_lang_id,
            object_name=scenario_name,
        )
    except Exception as exc:
        print(
            f"[WARN] Scenario lookup failed for '{scenario_name}' "
            f"(class_lang_id={scenario_class_lang_id}); attempting create. Error: {exc}"
        )
        return sdk.add_object(
            class_lang_id=scenario_class_lang_id,
            object_name=scenario_name,
        )


def ensure_membership(
    sdk,
    parent_class_lang_id: int,
    collection_lang_id: int,
    parent_name: str,
    child_name: str,
) -> bool:
    """Ensure a membership exists; return True only when a new one is created."""
    try:
        sdk.get_membership_by_names(
            parent_class_lang_id=parent_class_lang_id,
            collection_lang_id=collection_lang_id,
            parent_name=parent_name,
            child_name=child_name,
        )
        return False
    except Exception as exc:
        print(
            f"[WARN] Membership lookup failed for {parent_name}/{child_name} "
            f"(parent_class_lang_id={parent_class_lang_id}, collection_lang_id={collection_lang_id}); "
            f"attempting create. Error: {exc}"
        )
        if hasattr(sdk, "get_collection"):
            collection_obj = sdk.get_collection(
                parent_class_lang_id=parent_class_lang_id,
                collection_lang_id=collection_lang_id,
            )
        else:
            collection_obj = Collection.get(Collection.lang_id == collection_lang_id)

        parent_obj = sdk.get_object_by_name(
            class_lang_id=parent_class_lang_id,
            object_name=parent_name,
        )
        child_class_lang_id = collection_obj.child_class.lang_id
        child_obj = sdk.get_object_by_name(
            class_lang_id=child_class_lang_id,
            object_name=child_name,
        )
        sdk.add_membership(collection=collection_obj, parent=parent_obj, child=child_obj)
        return True


# ── SensitivityCreator ────────────────────────────────────────────────────────

class SensitivityCreator:
    """Creates a Variable-expression sensitivity on a target property and regenerates XML."""

    # SDK action IDs written to the tag row after the transaction.
    # Numeric mode (no Data File): '=' — the Variable.Profile value replaces the property.
    # Expression mode (with Data File): '×' — the Variable.Profile value multiplies the Data File.
    ACTION_ASSIGN = 0
    ACTION_MULTIPLY = 1

    # Variable.Profile is always written at band 1, independent of the target
    # property's --band-id setting.
    VARIABLE_PROFILE_BAND_ID = 1

    def __init__(self, cli_path: str, simulation_path: str, study_id: str) -> None:
        """
        Args:
            cli_path:        Path to the Cloud CLI executable.
            simulation_path: Root path containing reference.db and project.xml.
            study_id:        Current study identifier (needed for db-to-xml conversion).
        """
        self.cli_path = cli_path
        self.simulation_path = simulation_path
        self.study_id = study_id
        self.db_path = os.path.join(simulation_path, "reference.db")
        self.xml_path = os.path.join(simulation_path, "project.xml")

    def create(
        self,
        collection_name: str,
        parent_object_name: str,
        child_object_name: str,
        property_name: str,
        sensitivity: float,
        data_file_name: str | None = None,
        variable_name: str | None = None,
        scenario_name: str = "Sensitivity",
        scenario_class_name: str = "Scenario",
        band_id: int = 1,
    ) -> bool:
        """
        Write a sensitivity on the target property and regenerate XML.

                - data_file_name is None (default): reads the base property value,
                    sets Variable.Profile = base * (1 + sensitivity) with a Scenario tag,
                    then writes expression + Scenario tags on the target property.
                - data_file_name is set: looks up the existing Data File object,
                    sets Variable.Profile = (1 + sensitivity) with a Scenario tag,
                    then writes expression + Scenario + Data File tags on the target property.

        Returns:
            True if the sensitivity was created and XML regenerated successfully.
        """
        if not os.path.exists(self.db_path):
            print(f"[FAIL] Model database not found: {self.db_path}")
            return False

        try:
            self._create_sensitivity(
                collection_name=collection_name,
                parent_object_name=parent_object_name,
                child_object_name=child_object_name,
                property_name=property_name,
                sensitivity=sensitivity,
                data_file_name=data_file_name,
                variable_name=variable_name,
                scenario_name=scenario_name,
                scenario_class_name=scenario_class_name,
                band_id=band_id,
            )
        except Exception as exc:
            print(f"[FAIL] Failed to create sensitivity: {exc}")
            return False

        if not self._regenerate_xml():
            return False

        print("[OK] Sensitivity created and XML regenerated")
        return True

    def _resolve_ids(self, collection_name: str, property_name: str) -> tuple[int, int, int]:
        """
        Resolve collection and property names to lang IDs.

        Must be called inside an active PLEXOSSDK context so that Peewee models
        are bound to the database.

        Args:
            collection_name: Name of the collection, optionally prefixed with the
                             parent class (e.g. ``"System.Generators"``). The
                             prefix is used to disambiguate when multiple
                             collections share the same bare name.
            property_name:   Name of the property within that collection
                             (e.g. ``"MaxCapacity"``).

        Returns:
            ``(parent_class_lang_id, collection_lang_id, property_lang_id)``

        Raises:
            ValueError: If the collection or property name cannot be resolved
                        to a unique lang ID.
        """
        parent_class_filter = None
        bare_name = collection_name
        if "." in collection_name:
            parent_class_filter, bare_name = collection_name.split(".", 1)

        try:
            coll_rows = list(Collection.select().where(Collection.name == bare_name))
        except Exception as exc:
            raise ValueError(f"Failed to query collection '{bare_name}': {exc}") from exc
        if parent_class_filter:
            coll_rows = [r for r in coll_rows if r.parent_class.name == parent_class_filter]

        if not coll_rows:
            raise ValueError(
                f"Collection '{collection_name}' not found in model."
            )

        # Multiple parent classes can share the same collection lang_id (e.g. every class
        # that owns a 'Generators' child collection gets lang_id=36).  Uniqueness must be
        # checked on the (parent_class_lang_id, collection_lang_id) pair so that bare names
        # like "Generators" are rejected as ambiguous while disambiguated names like
        # "System.Generators" resolve cleanly.
        unique_pairs = {(r.parent_class.lang_id, r.lang_id) for r in coll_rows}
        if len(unique_pairs) != 1:
            parent_names = sorted({r.parent_class.name for r in coll_rows})
            raise ValueError(
                f"Cannot uniquely resolve collection '{collection_name}': "
                f"found {len(unique_pairs)} (parent_class, collection) combinations "
                f"(parent classes: {parent_names}). "
                f"Use 'ParentClass.CollectionName' format to disambiguate "
                f"(for example 'System.{bare_name}')."
            )

        coll_row = coll_rows[0]
        parent_class_lang_id = coll_row.parent_class.lang_id
        collection_lang_id = coll_row.lang_id

        try:
            prop_rows = list(
                Property.select()
                .join(Collection)
                .where(Collection.lang_id == collection_lang_id)
                .where(Property.name == property_name)
            )
        except Exception as exc:
            raise ValueError(
                f"Failed to query property '{property_name}' in collection '{collection_name}': {exc}"
            ) from exc
        unique_prop_ids = {r.lang_id for r in prop_rows}
        if len(unique_prop_ids) != 1:
            raise ValueError(
                f"Cannot uniquely resolve property '{property_name}' "
                f"in collection '{collection_name}': found lang_ids {unique_prop_ids}."
            )

        property_lang_id = prop_rows[0].lang_id
        print(
            f"[OK] Resolved '{collection_name}' -> "
            f"parent_class_lang_id={parent_class_lang_id}, "
            f"collection_lang_id={collection_lang_id}, "
            f"property_lang_id={property_lang_id}"
        )
        return parent_class_lang_id, collection_lang_id, property_lang_id

    def _get_or_create_variable(self, sdk, variable_class_lang_id: int, variable_name: str):
        """Get an existing Variable object by name or create it if missing."""
        try:
            var_obj = sdk.get_object_by_name(
                class_lang_id=variable_class_lang_id,
                object_name=variable_name,
            )
            print(f"[OK] Variable '{variable_name}' already exists (object_id={var_obj.object_id})")
            return var_obj
        except Exception as exc:
            print(
                f"[WARN] Variable lookup failed for '{variable_name}' "
                f"(class_lang_id={variable_class_lang_id}); attempting create. Error: {exc}"
            )
            var_obj = sdk.add_object(
                class_lang_id=variable_class_lang_id,
                object_name=variable_name,
            )
            print(f"[OK] Variable '{variable_name}' created (object_id={var_obj.object_id})")
            return var_obj

    def _get_or_create_system_variable_membership(
        self,
        sdk,
        system_class_lang_id: int,
        system_var_coll_lang_id: int,
        variable_name: str,
        var_obj,
        system_object_name: str = "System",
    ):
        """Ensure System/Variable membership exists and return it."""
        try:
            var_membership = sdk.get_membership_by_names(
                parent_class_lang_id=system_class_lang_id,
                collection_lang_id=system_var_coll_lang_id,
                parent_name=system_object_name,
                child_name=variable_name,
            )
            print(
                f"[OK] Variable membership found: {system_object_name}/{variable_name} "
                f"(membership_id={var_membership.membership_id})"
            )
            return var_membership
        except Exception as exc:
            print(
                f"[WARN] Variable membership lookup failed for {system_object_name}/{variable_name} "
                f"(parent_class_lang_id={system_class_lang_id}, "
                f"collection_lang_id={system_var_coll_lang_id}); attempting create. Error: {exc}"
            )
            system_obj = sdk.get_object_by_name(
                class_lang_id=system_class_lang_id,
                object_name=system_object_name,
            )
            var_coll_obj = Collection.get(Collection.lang_id == system_var_coll_lang_id)
            var_membership = sdk.add_membership(
                collection=var_coll_obj,
                parent=system_obj,
                child=var_obj,
            )
            print(
                f"[OK] Variable membership created: {system_object_name}/{variable_name} "
                f"(membership_id={var_membership.membership_id})"
            )
            return var_membership

    def _get_variable_profile_property(
        self,
        sdk,
        system_class_lang_id: int,
        system_var_coll_lang_id: int,
        profile_prop_lang_id: int,
    ):
        """Return Variable.Profile property object for System.Variables."""
        profile_property_obj = sdk.get_property(
            parent_class_lang_id=system_class_lang_id,
            collection_lang_id=system_var_coll_lang_id,
            property_lang_id=profile_prop_lang_id,
        )
        print(f"[OK] Variable.Profile property retrieved (property_id={profile_property_obj.property_id})")
        return profile_property_obj

    def _set_variable_profile(
        self,
        sdk,
        var_membership,
        profile_property_obj,
        profile_value: float,
        scenario_obj,
        variable_name: str,
        scenario_name: str,
    ) -> None:
        """Set Variable.Profile for the scenario, tolerating existing rows.

        Variable.Profile is a scalar expression value, not a banded property.
        It is always written at band_id=1 regardless of the target property's
        --band-id, which controls only which band of the target property is read
        and tagged.  These are two distinct band namespaces and must not be
        conflated.
        """
        print(f"[OK] Setting Variable.Profile = {profile_value} (scenario='{scenario_name}')")
        try:
            sdk.add_property(
                membership=var_membership,
                property_obj=profile_property_obj,
                value=profile_value,
                scenario_tag=scenario_obj,
                band_id=1,
            )
            print(
                f"[OK] Variable '{variable_name}' Profile set to {profile_value} "
                f"(scenario='{scenario_name}')"
            )
        except Exception as exc:
            if "already exists" in str(exc).lower():
                print(f"[WARN] Variable '{variable_name}' Profile already exists - skipping")
            else:
                raise

    def _create_sensitivity(
        self,
        collection_name: str,
        parent_object_name: str,
        child_object_name: str,
        property_name: str,
        sensitivity: float,
        data_file_name: str | None,
        variable_name: str | None,
        scenario_name: str,
        scenario_class_name: str,
        band_id: int,
    ) -> None:
        """
        Open the model and write the sensitivity.

        Both modes create a Variable object and tag the target property with it.

        Branch A (data_file_name is None) - numeric, action=0 (=):
            Reads the existing base property value, computes base*(1+sensitivity),
            sets Variable.Profile = that value (scenario-tagged), then tags the target
            property with expression=Variable + scenario. PLEXOS evaluates:
            property = Variable.Profile = base*(1+sensitivity).

        Branch B (data_file_name is set) - expression, action=1 (×):
            Sets Variable.Profile = (1+sensitivity) (scenario-tagged), looks up the
            existing Data File object, then tags the target property with
            expression=Variable + scenario + data_file. PLEXOS evaluates:
            property = Variable.Profile × DataFile = (1+sensitivity) × DataFile.
        """
        if not variable_name:
            raise ValueError("Variable name resolved to empty value.")

        mode = "expression" if data_file_name is not None else "numeric"

        # Numeric: action = '=' (id=0); Expression: action = '×' (id=1).
        # profile_value is the Variable.Profile value; for numeric it is computed
        # after reading the base property value inside the transaction.
        if data_file_name is not None:
            action_id = self.ACTION_MULTIPLY
            profile_value: float | None = round(1.0 + sensitivity, 8)
        else:
            action_id = self.ACTION_ASSIGN
            profile_value = None  # determined after reading base value

        print(f"\n{'='*80}")
        print("[OK] Step  INITIALIZING SENSITIVITY CREATION")
        print(f"{'='*80}")
        print(f"[OK] Model:             {self.db_path}")
        print(f"[OK] Mode:              {mode}")
        print(f"[OK] Collection:        {collection_name}")
        print(f"[OK] Parent:            {parent_object_name}")
        print(f"[OK] Child:             {child_object_name}")
        print(f"[OK] Property:          {property_name}")
        print(f"[OK] Sensitivity:       {sensitivity * 100:g}%")
        print(f"[OK] Variable name:     {variable_name}")
        if data_file_name is not None:
            print(f"[OK] Data file name:    {data_file_name}")
            print(f"[OK] Profile value:     {profile_value} (= 1 + {sensitivity * 100:g}%)")
            print("[OK] Action:            × (multiply, id=1)")
        else:
            print(f"[OK] Profile value:     base × (1 + {sensitivity * 100:g}%) - read from DB")
            print("[OK] Action:            = (assign, id=0)")
        print(f"[OK] Scenario:          {scenario_name}")
        print(f"[OK] Band id:           {band_id}")

        # Step 1: Always resolve scenario class ID.
        print("\n[OK] Step  RESOLVING SCENARIO CLASS")
        scenario_class_lang_id = _query_class_lang_id(self.db_path, scenario_class_name)
        print(f"[OK] Scenario class '{scenario_class_name}' resolved: lang_id={scenario_class_lang_id}")

        print("\n[OK] Step  RESOLVING MODEL AND MODEL.SCENARIOS")
        model_class_lang_id = _query_class_lang_id(self.db_path, "Model")
        model_object_name = _query_first_object_name_by_class_lang_id(
            self.db_path,
            model_class_lang_id,
        )
        model_scenario_collection_lang_id = _query_collection_lang_id(
            self.db_path,
            model_class_lang_id,
            scenario_class_lang_id,
            "Scenarios",
        )
        print(f"[OK] Model class resolved: lang_id={model_class_lang_id}")
        print(f"[OK] Model object resolved: {model_object_name}")
        print(
            f"[OK] Model.Scenarios collection resolved: "
            f"lang_id={model_scenario_collection_lang_id}"
        )

        # Step 1B: Pre-resolve Variable / System class IDs (needed for both modes).
        print("\n[OK] Step  RESOLVING VARIABLE AND SYSTEM CLASSES")
        system_class_lang_id = _query_class_lang_id(self.db_path, "System")
        system_object_name = _query_first_object_name_by_class_lang_id(
            self.db_path, system_class_lang_id
        )
        print(f"[OK] System class resolved: lang_id={system_class_lang_id}")
        print(f"[OK] System object resolved: {system_object_name}")

        variable_class_lang_id = _query_class_lang_id(self.db_path, "Variable")
        print(f"[OK] Variable class resolved: lang_id={variable_class_lang_id}")

        system_var_coll_lang_id = _query_collection_lang_id(
            self.db_path, system_class_lang_id, variable_class_lang_id, "Variables"
        )
        print(f"[OK] System.Variables collection resolved: lang_id={system_var_coll_lang_id}")

        profile_prop_lang_id = _query_property_lang_id(
            self.db_path, system_var_coll_lang_id, "Profile"
        )
        print(f"[OK] Variable.Profile property resolved: lang_id={profile_prop_lang_id}")

        data_file_class_lang_id: int | None = None
        if data_file_name is not None:
            data_file_class_lang_id = _query_class_lang_id(self.db_path, "Data File")
            print(f"[OK] Data File class resolved: lang_id={data_file_class_lang_id}")

        membership_id_for_action: int | None = None
        property_id_for_action: int | None = None
        expression_object_id_for_action: int | None = None

        # Step 2: SDK context for all object and property operations.
        print("\n[OK] Step  OPENING SDK CONTEXT AND TRANSACTION")

        # Temporarily rename the System object to "System" so the SDK
        # can find it during init.  Restored in the finally block below.
        _sys_renamed = False
        _original_system_object_name = system_object_name
        if system_object_name != "System":
            # Self-healing: if a previous run was killed between rename and
            # restore, the object may already be named "System".  Detect
            # this and skip the rename (the finally block will restore it).
            try:
                with sqlite3.connect(self.db_path) as _con:
                    _leftover = _con.execute(
                        """
                        SELECT 1 FROM t_object
                        WHERE name = 'System' AND class_id IN (
                            SELECT class_id FROM t_class WHERE lang_id = ?
                        )
                        LIMIT 1
                        """,
                        (system_class_lang_id,),
                    ).fetchone()
                    if _leftover:
                        # Already named "System" — likely leftover from a
                        # killed run.  Treat as renamed so finally restores it.
                        _sys_renamed = True
                        system_object_name = "System"
                        if parent_object_name.lower() == _original_system_object_name.lower():
                            parent_object_name = "System"
                        print(
                            f"[WARN] System object already named 'System' "
                            f"(expected '{_original_system_object_name}') — "
                            f"recovering from previous interrupted run"
                        )
                    else:
                        _cur = _con.execute(
                            """
                            UPDATE t_object SET name = 'System'
                            WHERE name = ? AND class_id IN (
                                SELECT class_id FROM t_class WHERE lang_id = ?
                            )
                            """,
                            (system_object_name, system_class_lang_id),
                        )
                        if _cur.rowcount:
                            _con.commit()
                            _sys_renamed = True
                            # Update all name variables so SDK lookups use "System"
                            system_object_name = "System"
                            if parent_object_name.lower() == _original_system_object_name.lower():
                                parent_object_name = "System"
                            print(
                                f"[OK] Temporarily renamed System object "
                                f"'{_original_system_object_name}' -> 'System' for SDK context"
                            )
            except Exception as _rename_exc:
                print(f"[WARN] Could not rename System object: {_rename_exc}")
        elif parent_object_name.lower() != "system":
            # Recovery: system_object_name resolved to "System" from the DB,
            # but the user supplied a different parent name.  If no object
            # with that name exists, this is likely a leftover rename from a
            # killed previous run — rewrite parent_object_name so the
            # membership lookup succeeds and restore the original name after.
            try:
                with sqlite3.connect(self.db_path) as _con:
                    _parent_exists = _con.execute(
                        "SELECT 1 FROM t_object WHERE name = ? LIMIT 1",
                        (parent_object_name,),
                    ).fetchone()
                    if not _parent_exists:
                        _original_system_object_name = parent_object_name
                        parent_object_name = "System"
                        _sys_renamed = True
                        print(
                            f"[WARN] No object '{_original_system_object_name}' "
                            f"found and System object is 'System' — recovering "
                            f"from previous interrupted run"
                        )
            except Exception as _recovery_exc:
                print(
                    f"[WARN] Could not check for leftover System rename: "
                    f"{_recovery_exc}"
                )

        try:
            with PLEXOSSDK(self.db_path) as sdk:
                # Fallback: if the SDK still has no system_object (rename didn't
                # help or name was already "System"), try direct assignment.
                if sdk.system_object is None:
                    try:
                        _patched_sys_obj = sdk.get_object_by_name(
                            class_lang_id=system_class_lang_id,
                            object_name=system_object_name,
                        )
                        sdk.system_object = _patched_sys_obj
                        print(f"[OK] SDK system_object patched via get_object_by_name: '{system_object_name}'")
                    except Exception as _patch_exc:
                        print(f"[WARN] Could not patch SDK system_object: {_patch_exc}")
                print("[OK] SDK context initialized")

                print("\n[OK] Step  RESOLVING TARGET COLLECTION AND PROPERTY")
                parent_class_lang_id, collection_lang_id, property_lang_id = self._resolve_ids(
                    collection_name, property_name
                )
                print("[OK] Target collection and property IDs resolved")

                with sdk.transaction():
                    print("\n[OK] Step  CREATING/RETRIEVING SCENARIO")
                    # Always: create/get scenario.
                    scenario_obj = get_or_create_scenario_object(
                        sdk, scenario_class_lang_id, scenario_name
                    )
                    print(f"[OK] Scenario '{scenario_name}' ready (object_id={scenario_obj.object_id})")

                    print("\n[OK] Step  ENSURING MODEL.SCENARIOS MEMBERSHIP")
                    scenario_membership_created = ensure_membership(
                        sdk,
                        parent_class_lang_id=model_class_lang_id,
                        collection_lang_id=model_scenario_collection_lang_id,
                        parent_name=model_object_name,
                        child_name=scenario_name,
                    )
                    if scenario_membership_created:
                        print(
                            f"[OK] Scenario membership created: "
                            f"{model_object_name}/{scenario_name} (Model.Scenarios)"
                        )
                    else:
                        print(
                            f"[OK] Scenario membership exists: "
                            f"{model_object_name}/{scenario_name} (Model.Scenarios)"
                        )

                    # Always: get main membership and property object.
                    print("\n[OK] Step  RETRIEVING TARGET MEMBERSHIP")
                    try:
                        main_membership = sdk.get_membership_by_names(
                            parent_class_lang_id=parent_class_lang_id,
                            collection_lang_id=collection_lang_id,
                            parent_name=parent_object_name,
                            child_name=child_object_name,
                        )
                        print(
                            f"[OK] Membership retrieved: {parent_object_name}/{child_object_name} "
                            f"(membership_id={main_membership.membership_id})"
                        )
                    except Exception as exc:
                        raise ValueError(
                            f"Membership not found for '{parent_object_name}'/'{child_object_name}' "
                            f"in collection '{collection_name}': {exc}"
                        ) from exc

                    print("\n[OK] Step  RETRIEVING TARGET PROPERTY")
                    try:
                        main_property_obj = sdk.get_property(
                            parent_class_lang_id=parent_class_lang_id,
                            collection_lang_id=collection_lang_id,
                            property_lang_id=property_lang_id,
                        )
                        print(
                            f"[OK] Property retrieved: '{property_name}' "
                            f"(property_id={main_property_obj.property_id})"
                        )
                    except Exception as exc:
                        raise ValueError(
                            f"Failed to retrieve property '{property_name}': {exc}"
                        ) from exc

                    if data_file_name is None:
                        # Branch A: numeric mode - compute profile value from current base value.
                        print("\n[OK] Step  NUMERIC MODE: READING BASE PROPERTY VALUE")
                        try:
                            base_value = sdk.get_property_value(
                                membership=main_membership,
                                property_obj=main_property_obj,
                                band_id=band_id,
                            )
                        except Exception as exc:
                            raise ValueError(f"Failed to read base property value: {exc}") from exc

                        if base_value is None:
                            raise ValueError(
                                "Base property value not found for the target membership/property/band combination."
                            )
                        profile_value = round(float(base_value) * (1.0 + sensitivity), 8)
                        print(f"[OK] Base value read: {base_value} (band_id={band_id})")
                        print(f"[OK] Profile value: {base_value} × (1 + {sensitivity * 100:g}%) = {profile_value}")

                    print("\n[OK] Step  PREPARING VARIABLE PROFILE CONTEXT")
                    var_obj = self._get_or_create_variable(
                        sdk,
                        variable_class_lang_id=variable_class_lang_id,
                        variable_name=variable_name,
                    )

                    var_membership = self._get_or_create_system_variable_membership(
                        sdk,
                        system_class_lang_id=system_class_lang_id,
                        system_var_coll_lang_id=system_var_coll_lang_id,
                        variable_name=variable_name,
                        var_obj=var_obj,
                        system_object_name=system_object_name,
                    )

                    profile_property_obj = self._get_variable_profile_property(
                        sdk,
                        system_class_lang_id=system_class_lang_id,
                        system_var_coll_lang_id=system_var_coll_lang_id,
                        profile_prop_lang_id=profile_prop_lang_id,
                    )

                    self._set_variable_profile(
                        sdk,
                        var_membership=var_membership,
                        profile_property_obj=profile_property_obj,
                        profile_value=float(profile_value),
                        scenario_obj=scenario_obj,
                        variable_name=variable_name,
                        scenario_name=scenario_name,
                    )

                    if data_file_name is None:
                        print("\n[OK] Step  NUMERIC MODE: TAGGING TARGET PROPERTY WITH EXPRESSION")
                        print(f"[OK] Tagging property '{property_name}' with:")
                        print(f"  - expression: '{variable_name}'")
                        print(f"  - scenario: '{scenario_name}'")
                        print("  - action: = (assign, id=0)")
                        print(f"  - band_id: {band_id}")
                        try:
                            sdk.add_property(
                                membership=main_membership,
                                property_obj=main_property_obj,
                                expression_tag=var_obj,
                                scenario_tag=scenario_obj,
                                band_id=band_id,
                            )
                            print(
                                f"[OK] Property '{property_name}' tagged with expression='{variable_name}' "
                                f"for scenario='{scenario_name}'"
                            )
                        except Exception as exc:
                            if "already exists" in str(exc).lower():
                                print(f"[WARN] Property '{property_name}' expression tag already exists - skipping")
                            else:
                                raise
                    else:
                        print("\n[OK] Step  EXPRESSION MODE: LOOKING UP DATA FILE")
                        try:
                            data_file_obj = sdk.get_object_by_name(
                                class_lang_id=data_file_class_lang_id,
                                object_name=data_file_name,
                            )
                            print(f"[OK] Data File '{data_file_name}' found (object_id={data_file_obj.object_id})")
                        except Exception as exc:
                            raise ValueError(
                                f"Data File object '{data_file_name}' not found in model. "
                                f"Ensure the Data File exists before running this script: {exc}"
                            ) from exc

                        print("\n[OK] Step  EXPRESSION MODE: TAGGING TARGET PROPERTY WITH EXPRESSION")
                        print(f"[OK] Tagging property '{property_name}' with:")
                        print(f"  - expression: '{variable_name}'")
                        print(f"  - scenario:   '{scenario_name}'")
                        print(f"  - data_file:  '{data_file_name}'")
                        print("  - action:     × (multiply, id=1)")
                        print(f"  - band_id:    {band_id}")
                        try:
                            sdk.add_property(
                                membership=main_membership,
                                property_obj=main_property_obj,
                                expression_tag=var_obj,
                                scenario_tag=scenario_obj,
                                data_file_tag=data_file_obj,
                                band_id=band_id,
                            )
                            print(
                                f"[OK] Property '{property_name}' tagged with expression='{variable_name}' "
                                f"(scenario='{scenario_name}', data_file='{data_file_name}')"
                            )
                        except Exception as exc:
                            if "already exists" in str(exc).lower():
                                print(f"[WARN] Property '{property_name}' expression tag already exists - skipping")
                            else:
                                raise

                    membership_id_for_action = getattr(main_membership, "membership_id", None)
                    property_id_for_action = getattr(main_property_obj, "property_id", None)
                    expression_object_id_for_action = getattr(var_obj, "object_id", None)

        finally:
            # Restore original System object name after SDK context closes.
            if _sys_renamed:
                try:
                    with sqlite3.connect(self.db_path) as _con:
                        _con.execute(
                            """
                            UPDATE t_object SET name = ?
                            WHERE name = 'System' AND class_id IN (
                                SELECT class_id FROM t_class WHERE lang_id = ?
                            )
                            """,
                            (_original_system_object_name, system_class_lang_id),
                        )
                        _con.commit()
                    print(
                        f"[OK] Restored System object name: "
                        f"'System' -> '{_original_system_object_name}'"
                    )
                except Exception as _restore_exc:
                    print(
                        f"[WARN] Failed to restore System object name "
                        f"'System' -> '{_original_system_object_name}': {_restore_exc}. "
                        f"The model database may need manual correction."
                    )

        # Step 4: Set action outside SDK context (both modes).
        print("\n[OK] Step  SETTING PROPERTY ACTION")
        if (
            membership_id_for_action is not None
            and property_id_for_action is not None
            and expression_object_id_for_action is not None
        ):
            action_symbol = "×" if action_id == 1 else "="
            print(f"[OK] Setting action_id={action_id} ({action_symbol}) on target property...")
            try:
                _set_property_action(
                    self.db_path,
                    membership_id_for_action,
                    property_id_for_action,
                    band_id,
                    action_id,
                    expression_object_id_for_action,
                )
            except Exception as exc:
                raise ValueError(f"Failed to set action id={action_id}: {exc}") from exc
        else:
            print("[WARN] Could not resolve membership/property/expression object id - action not set")

        print(f"\n{'='*80}")
        print("[OK] Step  SENSITIVITY CREATION COMPLETE")
        print(f"{'='*80}\n")

    def _regenerate_xml(self) -> bool:
        """Safely convert database back to XML using backup/restore semantics."""
        backup_path = f"{self.xml_path}.bak"
        backup_created = False

        if os.path.exists(self.xml_path):
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    print(f"[WARN] Removed stale XML backup: {backup_path}")
                os.replace(self.xml_path, backup_path)
                backup_created = True
                print(f"[OK] Backed up existing XML to: {backup_path}")
            except OSError as exc:
                print(f"[FAIL] Could not back up existing XML: {exc}")
                return False

        def _restore_backup() -> bool:
            if not backup_created:
                return True
            try:
                os.replace(backup_path, self.xml_path)
                print(f"[WARN] Restored XML backup after conversion failure: {self.xml_path}")
                return True
            except OSError as restore_exc:
                print(f"[FAIL] Failed to restore XML backup: {restore_exc}")
                return False

        try:
            pxc = CloudSDK(cli_path=self.cli_path)
            response = pxc.inputdata.convert_database_to_xml(
                db_file_path=self.db_path,
                xml_file_path=self.xml_path,
                study_id=self.study_id,
                print_message=False,
            )
            result = SDKBase.get_response_data(response)
        except Exception as exc:
            print(f"[FAIL] db-to-xml conversion error: {exc}")
            _restore_backup()
            return False

        if result is None:
            print(f"[FAIL] db-to-xml conversion failed: {response.Message}")
            _restore_backup()
            return False

        if backup_created and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                print(f"[OK] Removed XML backup: {backup_path}")
            except OSError as exc:
                print(f"[WARN] Could not remove XML backup '{backup_path}': {exc}")

        print(f"[OK] Regenerated XML: {self.xml_path}")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a Variable-expression sensitivity on a target property in a PLEXOS model. "
            "Creates or reuses a Variable object and a Scenario, then tags the "
            "target property with expression-based sensitivity data."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 create_sensitivity.py --collection-name System.Generators"
            " --child-object-name Gen1 --property-name MaxCapacity"
            " --sensitivity +5%% --data-file-name gen1_sensitivity\n"
            "  python3 create_sensitivity.py --collection-name System.Nodes"
            " --child-object-name Node1 --property-name Load"
            " --sensitivity -10%% --data-file-name load_sens"
            " --scenario-name LoadSens_minus_10pct"
        ),
    )

    parser.add_argument(
        "--collection-name",
        required=True,
        type=non_empty_text,
        help=(
            "Collection name for membership/property lookup "
            "(for example System.Generators). "
            "Use 'ParentClass.CollectionName' format to disambiguate when multiple "
            "collections share the same bare name."
        ),
    )
    parser.add_argument(
        "--parent-object-name",
        type=non_empty_text,
        default=PARENT_OBJECT_NAME,
        help="Parent object name for membership lookup (default: System). Override this if the parent object name differs from the default.",
    )
    parser.add_argument(
        "--child-object-name",
        required=True,
        type=non_empty_text,
        help="Child object name (for example a generator or demand object).",
    )
    parser.add_argument(
        "--property-name",
        required=True,
        type=non_empty_text,
        help="Property name to sensitivity-test (for example MaxCapacity).",
    )
    parser.add_argument(
        "--sensitivity",
        required=True,
        type=parse_sensitivity_delta,
        help=(
            "Single sensitivity delta as a percentage (for example +5%%, -10%%, 2.5). "
            "Used to calculate the Variable.Profile adjustment in numeric and expression modes."
        ),
    )
    parser.add_argument(
        "--data-file-name",
        type=non_empty_text,
        help=(
            "Name of an existing Data File PLEXOS object to reference. "
            "When omitted, numeric mode sets Variable.Profile to base * (1 + sensitivity) and "
            "tags the target property with expression + Scenario. When provided, expression "
            "mode sets Variable.Profile to (1 + sensitivity) and tags the target property with "
            "expression + Scenario + Data File."
        ),
    )
    parser.add_argument(
        "--variable-name",
        type=non_empty_text,
        help=(
            "Name for the PLEXOS Variable object. "
            "Defaults to '<data-file-name>_Var' in expression mode, otherwise "
            "'<child-object-name>_<property-name>_Var'."
        ),
    )
    parser.add_argument(
        "--scenario-name",
        type=non_empty_text,
        default=SCENARIO_NAME,
        help="Name for the Scenario object to create or reuse (default: Sensitivity).",
    )
    parser.add_argument(
        "--scenario-class-name",
        type=non_empty_text,
        default=SCENARIO_CLASS_NAME,
        help="Class name for scenario objects to create or reuse (default: Scenario).",
    )
    parser.add_argument(
        "--band-id",
        type=positive_int,
        default=BAND_ID,
        help="Property band id to write the expression tag on (default: 1).",
    )
    print(f"[OK] Received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()

    # Decode URL-encoded arguments (e.g. from non-shell task runners)
    args.collection_name = _decode_value(args.collection_name)
    args.parent_object_name = _decode_value(args.parent_object_name)
    args.child_object_name = _decode_value(args.child_object_name)
    args.property_name = _decode_value(args.property_name)
    if args.data_file_name:
        args.data_file_name = _decode_value(args.data_file_name)
    args.variable_name = _decode_value(args.variable_name) if args.variable_name else args.variable_name
    args.scenario_name = _decode_value(args.scenario_name)
    args.scenario_class_name = _decode_value(args.scenario_class_name)

    # Derive Variable name for both numeric and expression modes.
    data_file_name = args.data_file_name
    if args.variable_name:
        variable_name = args.variable_name
    elif data_file_name is not None:
        variable_name = f"{data_file_name}_Var"
    else:
        variable_name = f"{args.child_object_name}_{args.property_name}_Var"

    print(f"[OK] Parsed arguments: {args}")

    try:
        creator = SensitivityCreator(
            cli_path=CLOUD_CLI_PATH,
            simulation_path=SIMULATION_PATH,
            study_id=STUDY_ID,
        )
        success = creator.create(
            collection_name=args.collection_name,
            parent_object_name=args.parent_object_name,
            child_object_name=args.child_object_name,
            property_name=args.property_name,
            sensitivity=args.sensitivity,
            data_file_name=data_file_name,
            variable_name=variable_name,
            scenario_name=args.scenario_name,
            scenario_class_name=args.scenario_class_name,
            band_id=args.band_id,
        )
        return 0 if success else 1

    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

