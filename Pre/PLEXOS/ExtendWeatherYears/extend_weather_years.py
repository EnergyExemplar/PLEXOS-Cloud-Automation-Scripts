"""
Register sampled weather CSV files in a PLEXOS model as Data File, Variable,
and Stochastic objects.

Step 2 of the WeatherSample workflow. Run sample_weather_years.py first to
generate the per-location CSV files, then this script to register them.

Environment variables used:
    cloud_cli_path   - required path to Cloud CLI executable used by CloudSDK.
    simulation_path   - primary model path fallback; also base for --sampled-dir
    sqlite_input_path - secondary model path fallback
    study_id          - fallback study id when --study-id is not provided
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from eecloud.cloudsdk import CloudSDK, SDKBase
from plexos_sdk import PLEXOSSDK

SPACE_PLACEHOLDER_PATTERNS = ("%20",)

# ---------------------------------------------------------------------------
# Environment variable declarations (read once at startup; used as fallbacks)
# ---------------------------------------------------------------------------
try:
    ENV_CLOUD_CLI_PATH = os.environ["cloud_cli_path"]          # required by CloudSDK for DB→XML conversion
except KeyError:
    print("Error: Missing required environment variable: cloud_cli_path")
    sys.exit(1)

try:
    ENV_STUDY_ID = os.environ.get("study_id")
except KeyError:
    print("Error: Missing required environment variable: study_id")
    sys.exit(1)

ENV_SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")  # fallback model path base; also base for --sampled-dir
ENV_SQLITE_INPUT_PATH = os.environ.get("sqlite_input_path")    # secondary fallback model path


# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION — These defaults are used when no command-line arguments are provided.
# ═══════════════════════════════════════════════════════════════════════════════

# Folder containing sampled files (relative to simulation_path).
# Example: "ExoSampled"
SAMPLED_DIR = "ExoSampled"

# Use full filename (including extension) as object name (False = stem only).
# Example: False
USE_FULL_FILENAME = False
# Preview operations without writing to the model (True = dry run).
# Example: False
IS_DRYRUN = False
# Create Variable objects for sampled files.
# Example: False
CREATE_VARIABLES = False

# Suffix appended to variable names.
# Example: "_CY"
VARIABLE_NAME_SUFFIX = "_CY"
# Start climate year used for band count.
# Example: 1982
START_YEAR = 1982

# End climate year used for band count.
# Example: 2016
END_YEAR = 2016

# Link variables to target objects and also to a scenario.
# Example: False
LINK_VARIABLES = False
# Scenario object name used for Variable grouping.
# Example: "Weather_Variables_CY"
SCENARIO_NAME = "Weather_Variables_CY"
# Read Order value for the Scenario.
# Example: 50001
SCENARIO_READ_ORDER = 50001

# Adjust a stochastic object's sample count to match computed sample count.
# Example: False
ADJUST_STOCHASTIC = False

# Name of stochastic object to update/create.
# Example: "Weather_Stochastic"
STOCHASTIC_OBJECT_NAME = "Weather_Stochastic"

# Parent model object name used for Model.Stochastic membership.
# Example: "Model"
STOCHASTIC_PARENT_NAME = "Model"
# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════



def _normalize_cli_args(argv: list[str]) -> list[str]:
    """Normalize common Unicode dashes in option tokens to standard hyphen-minus."""
    dash_chars = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
    normalized: list[str] = []
    for arg in argv:
        if arg and arg[0] in f"-{dash_chars}":
            arg = arg.translate(str.maketrans({dash: "-" for dash in dash_chars}))
        normalized.append(arg)
    return normalized


def _restore_spaces_from_placeholders(value: str) -> tuple[str, bool]:
    """Restore spaces in argument values when supported placeholder patterns are used."""
    restored_value = value
    for pattern in SPACE_PLACEHOLDER_PATTERNS:
        restored_value = restored_value.replace(pattern, " ")
    return restored_value, restored_value != value


def _restore_placeholder_spaces_in_args(args: argparse.Namespace) -> int:
    """Replace space placeholders in string arguments and return number of changed tokens."""
    replaced_tokens = 0

    for field_name in [
        "sampled_dir", "object_name_prefix", "data_file_category",
        "model_path", "study_id",
        "variable_name_suffix", "variable_category",
        "target_class_name",
        "scenario_name", "scenario_category",
        "stochastic_object_name", "stochastic_parent_name", "stochastic_parent_category",
    ]:
        field_value = getattr(args, field_name, None)
        if isinstance(field_value, str):
            restored, changed = _restore_spaces_from_placeholders(field_value)
            if changed:
                replaced_tokens += 1
            setattr(args, field_name, restored)

    return replaced_tokens

# =============================================================================
# =============================================================================
# >>> INLINED DISCOVERY HELPERS <<<
# =============================================================================
# =============================================================================

# =============================================================================
# =============================================================================
# >>> Argument-type validators <<<
# =============================================================================
# =============================================================================

def non_empty_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise argparse.ArgumentTypeError("Value cannot be empty")
    return cleaned


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, got '{value}'") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0")
    return parsed


# =============================================================================
# =============================================================================
# >>> Model path resolution <<<
# =============================================================================
# =============================================================================

def resolve_model_path(explicit_model_path: str | None) -> Path:
    if explicit_model_path:
        return Path(explicit_model_path)

    # Primary: simulation_path + reference.db (working copy used by Pre tasks)
    if ENV_SIMULATION_PATH:
        candidate = Path(ENV_SIMULATION_PATH) / "reference.db"
        if candidate.is_file():
            return candidate

    # Fallback: sqlite_input_path (DataHub staging path)
    if ENV_SQLITE_INPUT_PATH:
        return Path(ENV_SQLITE_INPUT_PATH)

    raise ValueError(
        "Missing model path. Provide --model-path, or set simulation_path / sqlite_input_path environment variable."
    )


# =============================================================================
# =============================================================================
# >>> Class discovery <<<
# =============================================================================
# =============================================================================

def discover_class_lang_id_by_name(model_path: Path, class_name: str) -> int:
    """Look up a PLEXOS class lang_id by its human-readable name (e.g. 'Generator')."""
    query = """
    SELECT lang_id, name
    FROM t_class
    WHERE lower(name) = lower(?)
       OR lower(name) = lower(? || 's')
    ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END, class_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query, (class_name, class_name, class_name)).fetchone()

    if not row:
        raise ValueError(
            f"Could not find class '{class_name}' in model. "
            "Check spelling or provide an explicit class lang id."
        )

    lang_id, matched_name = row
    print(f"[OK]'{matched_name}' (lang_id={lang_id}) for requested '{class_name}'")
    return int(lang_id)


def discover_data_file_class_lang_id(model_path: Path) -> int:

    query = """
    SELECT lang_id, name
    FROM t_class
    WHERE lower(name) IN ('data file', 'data files')
       OR lower(name) LIKE '%data file%'
    ORDER BY CASE WHEN lower(name) IN ('data file', 'data files') THEN 0 ELSE 1 END, class_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query).fetchone()

    if not row:
        raise ValueError(
            "Could not auto-detect Data File class lang id from model."
        )

    lang_id, class_name = row
    print(f"[OK]'{class_name}' (lang_id={lang_id})")
    return int(lang_id)


def discover_variable_class_lang_id(model_path: Path) -> int:
    query = """
    SELECT lang_id, name
    FROM t_class
    WHERE lower(name) IN ('variable', 'variables')
       OR lower(name) LIKE '%variable%'
    ORDER BY CASE WHEN lower(name) IN ('variable', 'variables') THEN 0 ELSE 1 END, class_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query).fetchone()

    if not row:
        raise ValueError(
            "Could not auto-detect Variable class lang id from model."
        )

    lang_id, class_name = row
    print(f"[OK]'{class_name}' (lang_id={lang_id})")
    return int(lang_id)


def discover_scenario_class_lang_id(model_path: Path) -> int:
    query = """
    SELECT lang_id, name
    FROM t_class
    WHERE lower(name) IN ('scenario', 'scenarios')
       OR lower(name) LIKE '%scenario%'
    ORDER BY CASE WHEN lower(name) IN ('scenario', 'scenarios') THEN 0 ELSE 1 END, class_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query).fetchone()

    if not row:
        raise ValueError(
            "Could not auto-detect Scenario class lang id from model. "
            "Provide --scenario-class-lang-id explicitly."
        )

    lang_id, class_name = row
    print(f"[OK]'{class_name}' (lang_id={lang_id})")
    return int(lang_id)


def discover_model_class_lang_id(model_path: Path) -> int:
    query = """
    SELECT lang_id, name
    FROM t_class
    WHERE lower(name) IN ('model', 'models')
       OR lower(name) LIKE '%model%'
    ORDER BY CASE WHEN lower(name) IN ('model', 'models') THEN 0 ELSE 1 END, class_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query).fetchone()

    if not row:
        raise ValueError(
            "Could not auto-detect Model class lang id from model. "
            "Provide --stochastic-parent-class-lang-id explicitly."
        )

    lang_id, class_name = row
    print(f"[OK]'{class_name}' (lang_id={lang_id})")
    return int(lang_id)


def discover_stochastic_class_lang_id(model_path: Path) -> int:
    query = """
    SELECT lang_id, name
    FROM t_class
    WHERE lower(name) IN ('stochastic')
       OR lower(name) LIKE '%stoch%'
    ORDER BY CASE WHEN lower(name) = 'stochastic' THEN 0 ELSE 1 END, class_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query).fetchone()

    if not row:
        raise ValueError(
            "Could not auto-detect Stochastic class lang id from model. "
            "Provide --stochastic-class-lang-id explicitly."
        )

    lang_id, class_name = row
    print(f"[OK]'{class_name}' (lang_id={lang_id})")
    return int(lang_id)


# =============================================================================
# =============================================================================
# >>> Attribute discovery <<<
# =============================================================================
# =============================================================================

def discover_stochastic_sample_attribute_lang_id(
    model_path: Path,
    stochastic_class_lang_id: int,
) -> int:
    query = """
    SELECT a.lang_id, a.name
    FROM t_attribute a
    JOIN t_class c ON c.class_id = a.class_id
    WHERE c.lang_id = ?
      AND (
            lower(a.name) IN ('risk sample count', 'reduced sample count', 'sample year count')
            OR lower(a.name) LIKE '%sample%count%'
            OR lower(a.name) LIKE '%sample%'
          )
    ORDER BY CASE
                WHEN lower(a.name) = 'risk sample count' THEN 0
                WHEN lower(a.name) = 'reduced sample count' THEN 1
                WHEN lower(a.name) = 'sample year count' THEN 2
                ELSE 3
             END,
             a.attribute_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query, (stochastic_class_lang_id,)).fetchone()

    if not row:
        raise ValueError(
            "Could not auto-detect stochastic sample-count attribute. "
            "Provide --stochastic-sample-attribute-lang-id explicitly."
        )

    lang_id, attribute_name = row
    print(f"[OK]'{attribute_name}' (lang_id={lang_id})")
    return int(lang_id)


def discover_variable_band_attribute_lang_id(
    model_path: Path,
    variable_class_lang_id: int,
    *,
    required: bool,
) -> int | None:
    query = """
    SELECT a.lang_id, a.name
    FROM t_attribute a
    JOIN t_class c ON c.class_id = a.class_id
    WHERE c.lang_id = ?
      AND (
            lower(a.name) IN ('bands', 'band count', 'number of bands')
            OR lower(a.name) LIKE '%band%'
          )
    ORDER BY CASE
                WHEN lower(a.name) = 'bands' THEN 0
                WHEN lower(a.name) = 'band count' THEN 1
                WHEN lower(a.name) = 'number of bands' THEN 2
                ELSE 3
             END,
             a.attribute_id
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query, (variable_class_lang_id,)).fetchone()

    if not row:
        if required:
            raise ValueError(
                "Could not auto-detect a Variable band attribute in model. "
                "Provide --variable-band-attribute-lang-id explicitly."
            )
        print(
            "[WARN] No band-like Variable attribute found in model; "
            "variable objects will be created without attribute assignment."
        )
        return None

    lang_id, attribute_name = row
    print(f"[OK]'{attribute_name}' (lang_id={lang_id})")
    return int(lang_id)


# =============================================================================
# =============================================================================
# >>> Collection / property discovery <<<
# =============================================================================
# =============================================================================

def discover_collection_lang_id(
    model_path: Path,
    parent_class_lang_id: int,
    child_class_lang_id: int,
    preferred_name: str | None = None,
) -> int:
    query = """
    SELECT col.lang_id, col.name
    FROM t_collection col
    JOIN t_class pc ON pc.class_id = col.parent_class_id
    JOIN t_class cc ON cc.class_id = col.child_class_id
    WHERE pc.lang_id = ? AND cc.lang_id = ?
    ORDER BY
      CASE
        WHEN ? IS NOT NULL AND lower(col.name) = lower(?) THEN 0
        WHEN ? IS NOT NULL AND lower(col.name) LIKE lower(?) THEN 1
        ELSE 2
      END,
      col.collection_id
    LIMIT 1
    """

    preferred_like = f"%{preferred_name}%" if preferred_name else None

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(
            query,
            (
                parent_class_lang_id,
                child_class_lang_id,
                preferred_name,
                preferred_name,
                preferred_name,
                preferred_like,
            ),
        ).fetchone()

    if not row:
        raise ValueError(
            "Could not auto-detect collection lang id for parent class "
            f"{parent_class_lang_id} and child class {child_class_lang_id}."
        )

    lang_id, collection_name = row
    print(f"[OK]'{collection_name}' (lang_id={lang_id})")
    return int(lang_id)


def discover_property_lang_id(
    model_path: Path,
    parent_class_lang_id: int,
    child_class_lang_id: int,
    preferred_name: str,
) -> int:
    query = """
    SELECT p.lang_id, p.name
    FROM t_property p
    JOIN t_collection col ON col.collection_id = p.collection_id
    JOIN t_class pc ON pc.class_id = col.parent_class_id
    JOIN t_class cc ON cc.class_id = col.child_class_id
    WHERE pc.lang_id = ?
      AND cc.lang_id = ?
      AND (
            lower(p.name) = lower(?)
            OR lower(p.name) LIKE lower(?)
          )
    ORDER BY CASE WHEN lower(p.name) = lower(?) THEN 0 ELSE 1 END, p.property_id
    LIMIT 1
    """

    preferred_like = f"%{preferred_name}%"

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(
            query,
            (
                parent_class_lang_id,
                child_class_lang_id,
                preferred_name,
                preferred_like,
                preferred_name,
            ),
        ).fetchone()

    if not row:
        raise ValueError(
            f"Could not auto-detect property '{preferred_name}' for parent class "
            f"{parent_class_lang_id} and child class {child_class_lang_id}."
        )

    lang_id, property_name = row
    print(f"[OK]'{property_name}' (lang_id={lang_id})")
    return int(lang_id)


def resolve_property_mask_value(
    model_path: Path,
    property_lang_id: int,
    text_value: str,
) -> int | None:
    query = """
    SELECT input_mask
    FROM t_property
    WHERE lang_id = ?
    LIMIT 1
    """

    with sqlite3.connect(str(model_path)) as connection:
        row = connection.execute(query, (property_lang_id,)).fetchone()

    if not row:
        return None

    input_mask = row[0]
    if not input_mask:
        return None

    tokens = [token.strip().strip('"') for token in str(input_mask).split(";")]
    for index in range(0, len(tokens) - 1, 2):
        code_text = tokens[index]
        label = tokens[index + 1]
        if label.lower() == text_value.lower():
            try:
                return int(float(code_text))
            except ValueError:
                return None

    return None


# =============================================================================
# =============================================================================
# >>> Property / band queries <<<
# =============================================================================
# =============================================================================

def discover_existing_property_band_ids(
    model_path: Path,
    membership_id: int,
    property_id: int,
) -> list[int]:
    query = """
    SELECT DISTINCT COALESCE(b.band_id, 1) AS band_id
    FROM t_data d
    LEFT JOIN t_band b ON b.data_id = d.data_id
    WHERE d.membership_id = ?
      AND d.property_id = ?
    ORDER BY band_id
    """

    with sqlite3.connect(str(model_path)) as connection:
        rows = connection.execute(query, (membership_id, property_id)).fetchall()

    return [int(row[0]) for row in rows if row and row[0] is not None]


def set_scenario_read_order_in_database(
    model_path: Path,
    scenario_name: str,
    read_order_value: int,
) -> None:
    """
    Set the Read Order attribute on a Scenario object via raw SQL.

    Read Order is a *class attribute* (attribute_id 84) stored in
    ``t_attribute_data``, not a collection property in ``t_data``.
    Each Scenario object has at most one row keyed by
    (attribute_id, object_id).
    """
    with sqlite3.connect(str(model_path)) as connection:
        # Find Scenario object_id
        scenario_row = connection.execute(
            """
            SELECT o.object_id
            FROM t_object o
            JOIN t_class c ON c.class_id = o.class_id
            WHERE lower(c.name) IN ('scenario', 'scenarios')
              AND o.name = ?
            LIMIT 1
            """,
            (scenario_name,),
        ).fetchone()
        if not scenario_row:
            raise ValueError(f"Scenario object '{scenario_name}' not found in model")
        scenario_object_id = scenario_row[0]

        # Resolve the Read Order attribute_id from t_attribute
        attr_row = connection.execute(
            """
            SELECT a.attribute_id
            FROM t_attribute a
            JOIN t_class c ON c.class_id = a.class_id
            WHERE lower(a.name) = 'read order'
              AND lower(c.name) IN ('scenario', 'scenarios')
            LIMIT 1
            """,
        ).fetchone()
        if not attr_row:
            raise ValueError("Read Order attribute not found for Scenario class")
        read_order_attr_id = attr_row[0]

        # Check for an existing attribute_data row
        existing = connection.execute(
            "SELECT value FROM t_attribute_data WHERE attribute_id = ? AND object_id = ?",
            (read_order_attr_id, scenario_object_id),
        ).fetchone()

        if existing:
            connection.execute(
                "UPDATE t_attribute_data SET value = ? WHERE attribute_id = ? AND object_id = ?",
                (read_order_value, read_order_attr_id, scenario_object_id),
            )
        else:
            connection.execute(
                """
                INSERT INTO t_attribute_data (attribute_id, object_id, value)
                VALUES (?, ?, ?)
                """,
                (read_order_attr_id, scenario_object_id, read_order_value),
            )

        # Clean up any stale t_data rows for the Read Order *property*
        # (an earlier implementation mistakenly wrote to t_data instead of
        # t_attribute_data).  Look up the property_id dynamically so we
        # don't hard-code it.
        prop_row = connection.execute(
            """
            SELECT p.property_id
            FROM t_property p
            WHERE lower(p.name) = 'read order'
              AND p.collection_id IN (
                  SELECT col.collection_id
                  FROM t_collection col
                  JOIN t_class cc ON cc.class_id = col.child_class_id
                  WHERE lower(cc.name) IN ('scenario', 'scenarios')
              )
            """,
        ).fetchone()
        if prop_row:
            deleted = connection.execute(
                """
                DELETE FROM t_data
                WHERE property_id = ?
                  AND membership_id IN (
                      SELECT m.membership_id FROM t_membership m
                      WHERE m.child_object_id = ?
                  )
                """,
                (prop_row[0], scenario_object_id),
            ).rowcount
            if deleted:
                print(
                    f"[OK] Removed {deleted} stale t_data row(s) for "
                    f"Read Order property on '{scenario_name}'"
                )

        connection.commit()
        print(
            f"[OK] Set Read Order={read_order_value} "
            f"on Scenario '{scenario_name}' (object_id={scenario_object_id})"
        )


def set_property_action_in_database(
    model_path: Path,
    membership_id: int,
    property_id: int,
    band_id: int,
    action_id: int,
) -> None:
    """
    Manually set the action_id in t_tag for a property.
    Updates an existing t_tag row for this data_id to include the action_id.
    The action_id should be set on the t_tag row that references the expression object (Variable).
    """
    with sqlite3.connect(str(model_path)) as connection:
        # Find the data_id for this property
        find_data_query = """
        SELECT d.data_id
        FROM t_data d
        LEFT JOIN t_band b ON b.data_id = d.data_id
        WHERE d.membership_id = ?
          AND d.property_id = ?
          AND COALESCE(b.band_id, 1) = ?
        ORDER BY d.data_id DESC
        LIMIT 1
        """
        row = connection.execute(find_data_query, (membership_id, property_id, band_id)).fetchone()

        if not row:
            return

        data_id = row[0]

        # Find the Variable class ID to identify which t_tag entry is the expression
        variable_class_query = """
        SELECT class_id FROM t_class
        WHERE lower(name) IN ('variable', 'variables')
        LIMIT 1
        """
        var_class_row = connection.execute(variable_class_query).fetchone()

        if var_class_row:
            variable_class_id = var_class_row[0]

            # Update the t_tag row that references a Variable object (the expression)
            update_query = """
            UPDATE t_tag
            SET action_id = ?
            WHERE data_id = ?
              AND object_id IN (SELECT object_id FROM t_object WHERE class_id = ?)
            """
            connection.execute(update_query, (action_id, data_id, variable_class_id))
        else:
            # Fallback: update the second t_tag row (expression comes after scenario in add_property)
            update_query = """
            UPDATE t_tag
            SET action_id = ?
            WHERE data_id = ?
              AND rowid = (
                  SELECT rowid FROM t_tag WHERE data_id = ?
                  ORDER BY rowid DESC LIMIT 1
              )
            """
            connection.execute(update_query, (action_id, data_id, data_id))

        connection.commit()


def query_existing_property_details(
    model_path: Path,
    membership_id: int,
    property_id: int,
) -> list[dict]:
    """
    Query all existing property entries for a given membership and property.
    Returns list of dicts with: data_id, band_id, value, action_id, action_symbol (from t_tag), etc.
    """
    query = """
    SELECT DISTINCT
        d.data_id,
        COALESCE(b.band_id, 1) AS band_id,
        d.value,
        d.property_id,
        (SELECT tg.action_id FROM t_tag tg WHERE tg.data_id = d.data_id AND tg.action_id IS NOT NULL ORDER BY tg.action_id LIMIT 1) AS action_id,
        (SELECT a.action_symbol FROM t_tag tg JOIN t_action a ON a.action_id = tg.action_id WHERE tg.data_id = d.data_id AND tg.action_id IS NOT NULL ORDER BY tg.action_id LIMIT 1) AS action_symbol
    FROM t_data d
    LEFT JOIN t_band b ON b.data_id = d.data_id
    WHERE d.membership_id = ?
      AND d.property_id = ?
    ORDER BY band_id
    """

    with sqlite3.connect(str(model_path)) as connection:
        rows = connection.execute(query, (membership_id, property_id)).fetchall()

    return [
        {
            "data_id": row[0],
            "band_id": row[1],
            "value": row[2],
            "property_id": row[3],
            "action_id": row[4],
            "action_symbol": row[5],
        }
        for row in rows
    ]


# =============================================================================
# =============================================================================
# >>> File & naming helpers <<<
# =============================================================================
# =============================================================================

def collect_sample_files(sampled_dir: Path) -> list[Path]:
    if not sampled_dir.exists() or not sampled_dir.is_dir():
        raise FileNotFoundError(f"Sample folder not found: {sampled_dir}")

    sample_files = sorted(sampled_dir.rglob("*.csv"))
    sample_files = [path for path in sample_files if path.is_file()]
    if not sample_files:
        raise FileNotFoundError(f"No CSV sample files found in '{sampled_dir}'")

    return sample_files


def get_workspace_path_text(file_path: Path) -> str:
    resolved_file = file_path.resolve()
    resolved_cwd = Path.cwd().resolve()

    try:
        return str(resolved_file.relative_to(resolved_cwd))
    except ValueError:
        return str(file_path)


def get_data_file_object_name(file_path: Path, use_stem: bool, prefix: str) -> str:
    base_name = file_path.stem if use_stem else file_path.name
    return f"{prefix}{base_name}" if prefix else base_name


def get_variable_object_name(base_name: str, suffix: str) -> str:
    return f"{base_name}{suffix}"

# =============================================================================
# =============================================================================
# >>> INLINED OPERATIONS (formerly operations.py) <<<
# =============================================================================
# =============================================================================

# =============================================================================
# =============================================================================
# >>> SDK helper wrappers <<<
# =============================================================================
# =============================================================================

def add_object_with_optional_category(
    sdk: PLEXOSSDK,
    class_lang_id: int,
    object_name: str,
    category_name: str | None,
):
    if not category_name:
        return sdk.add_object(class_lang_id=class_lang_id, object_name=object_name)

    category_obj = None
    try:
        if hasattr(sdk, "get_categories"):
            categories = sdk.get_categories(class_lang_id=class_lang_id)
            category_obj = next(
                (cat for cat in categories if getattr(cat, "name", "").lower() == category_name.lower()),
                None,
            )

        if category_obj is None and hasattr(sdk, "add_category"):
            category_obj = sdk.add_category(
                class_lang_id=class_lang_id,
                category_name=category_name,
            )
            category_lang_id = getattr(category_obj, "lang_id", None)
            if category_lang_id is not None:
                print(f"[OK] '{category_name}' (lang_id={category_lang_id})")
            else:
                print(f"[OK] '{category_name}'")
    except Exception as exc:
        print(
            f"[WARN] Could not resolve/create category '{category_name}': {exc}. "
            "Proceeding without category."
        )

    try:
        if category_obj is not None:
            return sdk.add_object(
                class_lang_id=class_lang_id,
                object_name=object_name,
                category_obj=category_obj,
            )
    except TypeError:
        print(
            "[WARN] SDK add_object does not support category argument; "
            f"creating '{object_name}' without category."
        )

    return sdk.add_object(class_lang_id=class_lang_id, object_name=object_name)


def get_or_create_object_by_name(
    sdk: PLEXOSSDK,
    class_lang_id: int,
    object_name: str,
):
    try:
        return sdk.get_object_by_name(class_lang_id=class_lang_id, object_name=object_name), False
    except Exception:
        created = sdk.add_object(class_lang_id=class_lang_id, object_name=object_name)
        return created, True


def ensure_membership(
    sdk: PLEXOSSDK,
    parent_class_lang_id: int,
    collection_lang_id: int,
    parent_name: str,
    child_name: str,
) -> bool:
    try:
        sdk.get_membership_by_names(
            parent_class_lang_id=parent_class_lang_id,
            collection_lang_id=collection_lang_id,
            parent_name=parent_name,
            child_name=child_name,
        )
        return False
    except Exception:
        collection_obj = sdk.get_collection(
            parent_class_lang_id=parent_class_lang_id,
            collection_lang_id=collection_lang_id,
        )
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


def _set_variable_band_attribute(
    sdk: PLEXOSSDK,
    variable_object,
    variable_class_lang_id: int,
    attribute_lang_id: int,
    band_count: int,
) -> None:
    try:
        sdk.add_attribute_by_lang_id(
            object_obj=variable_object,
            attribute_lang_id=attribute_lang_id,
            value=float(band_count),
        )
        return
    except Exception:
        attribute_obj = sdk.get_attribute(
            class_lang_id=variable_class_lang_id,
            attribute_lang_id=attribute_lang_id,
        )
        try:
            sdk.add_attribute(
                object_obj=variable_object,
                attribute=attribute_obj,
                value=float(band_count),
            )
            return
        except Exception:
            try:
                sdk.remove_attribute(
                    object_obj=variable_object,
                    attribute=attribute_obj,
                )
            except Exception:
                pass

            sdk.add_attribute(
                object_obj=variable_object,
                attribute=attribute_obj,
                value=float(band_count),
            )


# =============================================================================
# =============================================================================
# >>> Operation 1: Create Data File objects <<<
# =============================================================================
# =============================================================================

def create_data_file_objects_for_samples(
    model_path: Path,
    sampled_dir: Path,
    object_name_from_stem: bool,
    object_name_prefix: str | None,
    data_file_category: str | None,
    start_year: int,
    end_year: int,
    dry_run: bool,
) -> None:
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    data_file_band_id = 1
    legacy_computed_band_id = end_year - start_year + 1

    print(f"[OK] Model path: {model_path}")
    print(f"[OK] Sampled dir: {sampled_dir}")
    print("[OK] File pattern: *.csv (auto)")
    print(f"[OK] Object name from stem: {object_name_from_stem}")
    print(f"[OK] Object name prefix: {object_name_prefix or ''}")
    print(f"[OK] Data File category: {data_file_category or ''}")
    print(f"[OK] Start year: {start_year}")
    print(f"[OK] End year: {end_year}")
    print(f"[OK] Data File band id: {data_file_band_id}")
    print(f"[OK] Dry run: {dry_run}")

    normalized_prefix = object_name_prefix or ""

    sample_files = collect_sample_files(sampled_dir)
    print(f"[OK] Found sample files: {len(sample_files)}")

    class_lang_id = discover_data_file_class_lang_id(model_path)
    print(f"[OK] Data File class lang_id: {class_lang_id}")

    system_data_file_collection_lang_id = discover_collection_lang_id(
        model_path=model_path,
        parent_class_lang_id=1,
        child_class_lang_id=class_lang_id,
        preferred_name="Data Files",
    )
    filename_property_lang_id = discover_property_lang_id(
        model_path=model_path,
        parent_class_lang_id=1,
        child_class_lang_id=class_lang_id,
        preferred_name="Filename",
    )

    if dry_run:
        for file_path in sample_files:
            object_name = get_data_file_object_name(
                file_path=file_path,
                use_stem=object_name_from_stem,
                prefix=normalized_prefix,
            )
            file_workspace_path = get_workspace_path_text(file_path)
            print(f"[OK] Would create Data File object '{object_name}' for {file_path}")
            print(
                f"[OK] Would set Filename text='{file_workspace_path}' with band={data_file_band_id}"
            )
        return

    created_count = 0
    existing_count = 0
    filename_updated_count = 0

    with PLEXOSSDK(str(model_path)) as sdk:
        with sdk.transaction():
            filename_property_obj = sdk.get_property(
                parent_class_lang_id=1,
                collection_lang_id=system_data_file_collection_lang_id,
                property_lang_id=filename_property_lang_id,
            )

            for file_path in sample_files:
                object_name = get_data_file_object_name(
                    file_path=file_path,
                    use_stem=object_name_from_stem,
                    prefix=normalized_prefix,
                )
                file_workspace_path = get_workspace_path_text(file_path)

                try:
                    sdk.get_object_by_name(class_lang_id=class_lang_id, object_name=object_name)
                    existing_count += 1
                except Exception:
                    add_object_with_optional_category(
                        sdk=sdk,
                        class_lang_id=class_lang_id,
                        object_name=object_name,
                        category_name=data_file_category,
                    )
                    created_count += 1

                membership = sdk.get_membership_by_names(
                    parent_class_lang_id=1,
                    collection_lang_id=system_data_file_collection_lang_id,
                    parent_name="System",
                    child_name=object_name,
                )

                band_ids_to_remove = {data_file_band_id, legacy_computed_band_id}
                membership_id = getattr(membership, "membership_id", None)
                property_id = getattr(filename_property_obj, "property_id", None)
                if membership_id is not None and property_id is not None:
                    try:
                        existing_band_ids = discover_existing_property_band_ids(
                            model_path=model_path,
                            membership_id=int(membership_id),
                            property_id=int(property_id),
                        )
                        band_ids_to_remove.update(existing_band_ids)
                    except Exception:
                        pass

                for band_id_to_remove in sorted(band_ids_to_remove):
                    try:
                        sdk.remove_property(
                            membership=membership,
                            property_obj=filename_property_obj,
                            band_id=band_id_to_remove,
                        )
                    except Exception:
                        pass

                sdk.add_property(
                    membership=membership,
                    property_obj=filename_property_obj,
                    value=None,
                    data_file_text=file_workspace_path,
                    band_id=data_file_band_id,
                )
                filename_updated_count += 1
                print(
                    f"[OK] {object_name} -> text='{file_workspace_path}', band={data_file_band_id}"
                )

    print(
        f"[OK] Created={created_count} Existing={existing_count} "
        f"FilenameUpdated={filename_updated_count} Total={len(sample_files)}"
    )


# =============================================================================
# =============================================================================
# >>> Operation 2: Create Variable objects <<<
# =============================================================================
# =============================================================================

def create_variable_objects_for_samples(
    model_path: Path,
    sampled_dir: Path,
    object_name_from_stem: bool,
    object_name_prefix: str | None,
    variable_name_suffix: str,
    variable_category: str | None,
    variable_band_attribute_lang_id: int | None,
    require_variable_band_attribute: bool,
    start_year: int,
    end_year: int,
    dry_run: bool,
) -> None:
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    band_count = end_year - start_year + 1
    sampling_method_band_id = 1
    profile_band_id = band_count
    normalized_prefix = object_name_prefix or ""

    sample_files = collect_sample_files(sampled_dir)
    variable_class_id = discover_variable_class_lang_id(model_path)
    data_file_class_id = discover_data_file_class_lang_id(model_path)

    system_variable_collection_lang_id = discover_collection_lang_id(
        model_path=model_path,
        parent_class_lang_id=1,
        child_class_lang_id=variable_class_id,
        preferred_name="Variables",
    )
    sampling_method_property_lang_id = discover_property_lang_id(
        model_path=model_path,
        parent_class_lang_id=1,
        child_class_lang_id=variable_class_id,
        preferred_name="Sampling Method",
    )
    sampling_method_user_value = resolve_property_mask_value(
        model_path=model_path,
        property_lang_id=sampling_method_property_lang_id,
        text_value="User",
    )
    profile_property_lang_id = discover_property_lang_id(
        model_path=model_path,
        parent_class_lang_id=1,
        child_class_lang_id=variable_class_id,
        preferred_name="Profile",
    )

    print(f"[OK] Variable name suffix: {variable_name_suffix}")
    print(f"[OK] Variable category: {variable_category or ''}")
    print(f"[OK] Start year: {start_year}")
    print(f"[OK] End year: {end_year}")
    print(f"[OK] Band count: {band_count}")
    print("[OK] Sampling Method target: User")
    print("[OK] Profile link target: Data File")

    band_attribute_id = (
        variable_band_attribute_lang_id
        if variable_band_attribute_lang_id is not None
        else discover_variable_band_attribute_lang_id(
            model_path,
            variable_class_id,
            required=require_variable_band_attribute,
        )
    )

    if dry_run:
        for file_path in sample_files:
            base_name = get_data_file_object_name(
                file_path=file_path,
                use_stem=object_name_from_stem,
                prefix=normalized_prefix,
            )
            variable_name = get_variable_object_name(base_name, variable_name_suffix)
            print(
                f"[OK] Would create/update Variable '{variable_name}' with bands={band_count}"
            )
            print(
                f"[OK] Would set Sampling Method='User' at band={sampling_method_band_id} "
                f"and Profile='{base_name}' at band={profile_band_id}"
            )
        return

    created_count = 0
    updated_count = 0
    properties_updated_count = 0

    with PLEXOSSDK(str(model_path)) as sdk:
        with sdk.transaction():
            sampling_method_property_obj = sdk.get_property(
                parent_class_lang_id=1,
                collection_lang_id=system_variable_collection_lang_id,
                property_lang_id=sampling_method_property_lang_id,
            )
            profile_property_obj = sdk.get_property(
                parent_class_lang_id=1,
                collection_lang_id=system_variable_collection_lang_id,
                property_lang_id=profile_property_lang_id,
            )

            for file_path in sample_files:
                base_name = get_data_file_object_name(
                    file_path=file_path,
                    use_stem=object_name_from_stem,
                    prefix=normalized_prefix,
                )
                variable_name = get_variable_object_name(base_name, variable_name_suffix)

                try:
                    variable_object = sdk.get_object_by_name(
                        class_lang_id=variable_class_id,
                        object_name=variable_name,
                    )
                except Exception:
                    variable_object = add_object_with_optional_category(
                        sdk=sdk,
                        class_lang_id=variable_class_id,
                        object_name=variable_name,
                        category_name=variable_category,
                    )
                    created_count += 1
                    print(f"[OK] Variable created: {variable_name}")

                if band_attribute_id is not None:
                    _set_variable_band_attribute(
                        sdk=sdk,
                        variable_object=variable_object,
                        variable_class_lang_id=variable_class_id,
                        attribute_lang_id=band_attribute_id,
                        band_count=band_count,
                    )

                data_file_object = sdk.get_object_by_name(
                    class_lang_id=data_file_class_id,
                    object_name=base_name,
                )
                variable_membership = sdk.get_membership_by_names(
                    parent_class_lang_id=1,
                    collection_lang_id=system_variable_collection_lang_id,
                    parent_name="System",
                    child_name=variable_name,
                )

                try:
                    sdk.remove_property(
                        membership=variable_membership,
                        property_obj=sampling_method_property_obj,
                        band_id=sampling_method_band_id,
                    )
                except Exception:
                    pass

                sampling_method_value: int | str = (
                    sampling_method_user_value if sampling_method_user_value is not None else "User"
                )
                if hasattr(sdk, "map_str_value_to_int"):
                    try:
                        sampling_method_value = sdk.map_str_value_to_int(
                            sampling_method_property_obj,
                            "User",
                        )
                    except Exception:
                        sampling_method_value = "User"

                try:
                    sdk.add_property(
                        membership=variable_membership,
                        property_obj=sampling_method_property_obj,
                        value=sampling_method_value,
                        band_id=sampling_method_band_id,
                    )
                except Exception as exc:
                    if "already exists" in str(exc).lower():
                        print(f"[OK] {variable_name} Sampling Method already set")
                    else:
                        raise

                try:
                    sdk.remove_property(
                        membership=variable_membership,
                        property_obj=profile_property_obj,
                        band_id=profile_band_id,
                    )
                except Exception:
                    pass

                try:
                    sdk.add_property(
                        membership=variable_membership,
                        property_obj=profile_property_obj,
                        value=None,
                        data_file_tag=data_file_object,
                        band_id=profile_band_id,
                    )
                except Exception as exc:
                    if "already exists" in str(exc).lower():
                        print(f"[OK] {variable_name} Profile already set to '{base_name}'")
                    else:
                        raise

                properties_updated_count += 1
                print(
                    f"[OK] {variable_name} -> Sampling Method='User' (band={sampling_method_band_id}), "
                    f"Profile='{base_name}' (band={profile_band_id})"
                )

                updated_count += 1

    print(
        f"[OK] Created={created_count} Updated={updated_count} "
        f"PropsUpdated={properties_updated_count} Total={len(sample_files)}"
    )


# =============================================================================
# =============================================================================
# >>> Operation 3: Link Variables to objects under Scenario <<<
# =============================================================================
# =============================================================================

def link_variables_to_objects_under_scenario(
    model_path: Path,
    sampled_dir: Path,
    object_name_from_stem: bool,
    object_name_prefix: str | None,
    variable_name_suffix: str,
    target_class_name: str,
    scenario_name: str,
    scenario_class_lang_id: int | None,
    scenario_category: str | None,
    scenario_read_order: int,
    start_year: int,
    end_year: int,
    dry_run: bool,
    model_parent_name: str | None = None,
    model_parent_class_lang_id: int | None = None,
) -> None:
    """
    Replicate Rating Factor properties on parent objects with new variable
    expression and scenario.

    By default, this function does not create new System->ParentObject
    memberships; it only adds property entries to existing memberships.
    However, when ``model_parent_name`` is provided, it may also create a
    membership (e.g. Model->Scenario) via ``ensure_membership(...)``.
    """
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    normalized_prefix = object_name_prefix or ""
    sample_files = collect_sample_files(sampled_dir)

    target_class_lang_id = discover_class_lang_id_by_name(model_path, target_class_name)
    variable_class_lang_id = discover_variable_class_lang_id(model_path)
    resolved_scenario_class_lang_id = (
        scenario_class_lang_id
        if scenario_class_lang_id is not None
        else discover_scenario_class_lang_id(model_path)
    )

    system_target_collection_lang_id = discover_collection_lang_id(
        model_path=model_path,
        parent_class_lang_id=1,
        child_class_lang_id=target_class_lang_id,
    )

    rating_factor_property_lang_id = discover_property_lang_id(
        model_path=model_path,
        parent_class_lang_id=1,
        child_class_lang_id=target_class_lang_id,
        preferred_name="Rating Factor",
    )

    print(f"[OK] Target class: '{target_class_name}' (lang_id={target_class_lang_id})")
    print(f"[OK] System->Target collection lang_id: {system_target_collection_lang_id}")
    print(f"[OK] Rating Factor property lang_id: {rating_factor_property_lang_id}")
    print(f"[OK] Scenario name: {scenario_name}")
    print(f"[OK] Scenario class lang_id: {resolved_scenario_class_lang_id}")
    print(f"[OK] Scenario category: {scenario_category or ''}")
    print(f"[OK] Scenario read order: {scenario_read_order}")
    print(f"[OK] Variable name suffix: {variable_name_suffix}")

    # --- Discover Model -> Scenario collection for linking scenario to model ---
    model_scenario_collection_lang_id = None
    resolved_model_parent_class_lang_id = None
    if model_parent_name:
        resolved_model_parent_class_lang_id = (
            model_parent_class_lang_id
            if model_parent_class_lang_id is not None
            else discover_model_class_lang_id(model_path)
        )
        model_scenario_collection_lang_id = discover_collection_lang_id(
            model_path=model_path,
            parent_class_lang_id=resolved_model_parent_class_lang_id,
            child_class_lang_id=resolved_scenario_class_lang_id,
            preferred_name="Scenarios",
        )
        print(f"[OK] Model parent name: {model_parent_name}")
        print(f"[OK] Model->Scenario collection lang_id: {model_scenario_collection_lang_id}")

    if dry_run:
        for file_path in sample_files:
            base_name = get_data_file_object_name(
                file_path=file_path,
                use_stem=object_name_from_stem,
                prefix=normalized_prefix,
            )
            variable_name = get_variable_object_name(base_name, variable_name_suffix)
            print(
                f"[OK] Replicate Rating Factor property on '{base_name}' "
                f"with expression='{variable_name}' and scenario='{scenario_name}'"
            )
        if model_parent_name:
            print(
                f"[OK] Would ensure membership '{model_parent_name}' -> '{scenario_name}' "
                f"in Model.Scenarios"
            )
        return

    properties_added = 0
    properties_skipped = 0
    properties_to_update_action = []  # List of (membership_id, property_id, band_id, action_id, action_symbol, base_name)

    with PLEXOSSDK(str(model_path)) as sdk:
        with sdk.transaction():
            rating_factor_property_obj = sdk.get_property(
                parent_class_lang_id=1,
                collection_lang_id=system_target_collection_lang_id,
                property_lang_id=rating_factor_property_lang_id,
            )

            try:
                scenario_obj = add_object_with_optional_category(
                    sdk=sdk,
                    class_lang_id=resolved_scenario_class_lang_id,
                    object_name=scenario_name,
                    category_name=scenario_category,
                )
                if scenario_category:
                    print(f"[OK] Scenario created: {scenario_name} (category={scenario_category})")
                else:
                    print(f"[OK] Scenario created: {scenario_name}")
            except Exception:
                scenario_obj, _ = get_or_create_object_by_name(
                    sdk=sdk,
                    class_lang_id=resolved_scenario_class_lang_id,
                    object_name=scenario_name,
                )
                print(f"[OK] Scenario exists: {scenario_name}")

            # --- Link Scenario to Model (Model.Scenarios membership) ---
            if model_parent_name and model_scenario_collection_lang_id and resolved_model_parent_class_lang_id:
                membership_created = ensure_membership(
                    sdk=sdk,
                    parent_class_lang_id=resolved_model_parent_class_lang_id,
                    collection_lang_id=model_scenario_collection_lang_id,
                    parent_name=model_parent_name,
                    child_name=scenario_name,
                )
                if membership_created:
                    print(
                        f"[OK] {model_parent_name} -> {scenario_name} "
                        f"(Model.Scenarios)"
                    )
                else:
                    print(
                        f"[OK] {model_parent_name} -> {scenario_name} "
                        f"(Model.Scenarios)"
                    )

            for file_path in sample_files:
                base_name = get_data_file_object_name(
                    file_path=file_path,
                    use_stem=object_name_from_stem,
                    prefix=normalized_prefix,
                )
                variable_name = get_variable_object_name(base_name, variable_name_suffix)

                try:
                    parent_obj = sdk.get_object_by_name(
                        class_lang_id=target_class_lang_id,
                        object_name=base_name,
                    )
                except Exception:
                    print(f"[WARN] Parent object not found: {base_name}")
                    properties_skipped += 1
                    continue

                try:
                    parent_membership = sdk.get_membership_by_names(
                        parent_class_lang_id=1,
                        collection_lang_id=system_target_collection_lang_id,
                        parent_name="System",
                        child_name=base_name,
                    )
                except Exception as exc:
                    print(f"[WARN] Membership not found for {base_name}: {exc}")
                    properties_skipped += 1
                    continue

                membership_id = getattr(parent_membership, "membership_id", None)
                property_id = getattr(rating_factor_property_obj, "property_id", None)

                band_id_to_use = 1
                action_id_to_use = None
                action_symbol_to_use = None
                if membership_id is not None and property_id is not None:
                    try:
                        existing_props = query_existing_property_details(
                            model_path=model_path,
                            membership_id=int(membership_id),
                            property_id=int(property_id),
                        )
                        if existing_props:
                            band_id_to_use = existing_props[0]["band_id"]
                            action_id_to_use = existing_props[0]["action_id"]
                            action_symbol_to_use = existing_props[0]["action_symbol"]
                            action_display = f"'{action_symbol_to_use}'" if action_symbol_to_use else "None"
                    except Exception as exc:
                        print(
                            f"[WARN] {base_name}: Failed to query existing Rating Factor properties: {exc}. "
                            "Proceeding with default band/action."
                        )

                try:
                    scenario_obj_for_property = sdk.get_object_by_name(
                        class_lang_id=resolved_scenario_class_lang_id,
                        object_name=scenario_name,
                    )

                    variable_obj = sdk.get_object_by_name(
                        class_lang_id=variable_class_lang_id,
                        object_name=variable_name,
                    )

                    sdk.add_property(
                        membership=parent_membership,
                        property_obj=rating_factor_property_obj,
                        value=None,
                        expression_tag=variable_obj,
                        scenario_tag=scenario_obj_for_property,
                        band_id=band_id_to_use,
                    )

                    properties_added += 1

                    # Collect properties to update action after transaction
                    if action_id_to_use is not None:
                        properties_to_update_action.append((
                            int(membership_id),
                            int(property_id),
                            band_id_to_use,
                            action_id_to_use,
                            action_symbol_to_use,
                            base_name,
                        ))

                    action_display = f"'{action_symbol_to_use}'" if action_symbol_to_use else "None"
                    print(
                        f"[OK] {base_name} -> Rating Factor "
                        f"(expression='{variable_name}', scenario='{scenario_name}', band={band_id_to_use}, action={action_display})"
                    )
                except Exception as exc:
                    print(f"[FAIL] Failed to add property for {base_name}: {exc}")
                    properties_skipped += 1

    # Set Read Order on the Scenario (raw SQL, outside SDK transaction)
    try:
        set_scenario_read_order_in_database(
            model_path=model_path,
            scenario_name=scenario_name,
            read_order_value=scenario_read_order,
        )
    except Exception as exc:
        print(f"[WARN] Could not set Read Order on scenario '{scenario_name}': {exc}")

    # Now update actions outside the SDK transaction
    for membership_id, property_id, band_id, action_id, action_symbol, base_name in properties_to_update_action:
        try:
            set_property_action_in_database(
                model_path=model_path,
                membership_id=membership_id,
                property_id=property_id,
                band_id=band_id,
                action_id=action_id,
            )
        except Exception as exc:
            print(f"[WARN] Failed to set action for {base_name}: {exc}")

    print(
        f"[OK] Added={properties_added} Skipped={properties_skipped} "
        f"Total={len(sample_files)}"
    )


# =============================================================================
# =============================================================================
# >>> Operation 4: Adjust stochastic sample count <<<
# =============================================================================
# =============================================================================

def adjust_stochastic_object_sample_count(
    model_path: Path,
    stochastic_object_name: str,
    stochastic_parent_name: str,
    stochastic_parent_category: str | None,
    stochastic_parent_class_lang_id: int | None,
    start_year: int,
    end_year: int,
    sample_count_override: int | None,
    stochastic_class_lang_id: int | None,
    stochastic_sample_attribute_lang_id: int | None,
    dry_run: bool,
) -> None:
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    target_sample_count = sample_count_override or (end_year - start_year + 1)

    resolved_stochastic_class_lang_id = (
        stochastic_class_lang_id
        if stochastic_class_lang_id is not None
        else discover_stochastic_class_lang_id(model_path)
    )
    resolved_stochastic_parent_class_lang_id = (
        stochastic_parent_class_lang_id
        if stochastic_parent_class_lang_id is not None
        else discover_model_class_lang_id(model_path)
    )
    model_stochastic_collection_lang_id = discover_collection_lang_id(
        model_path=model_path,
        parent_class_lang_id=resolved_stochastic_parent_class_lang_id,
        child_class_lang_id=resolved_stochastic_class_lang_id,
        preferred_name="Stochastic",
    )
    resolved_sample_attribute_lang_id = (
        stochastic_sample_attribute_lang_id
        if stochastic_sample_attribute_lang_id is not None
        else discover_stochastic_sample_attribute_lang_id(
            model_path=model_path,
            stochastic_class_lang_id=resolved_stochastic_class_lang_id,
        )
    )

    print(f"[OK] Stochastic object name: {stochastic_object_name}")
    print(f"[OK] Stochastic parent name: {stochastic_parent_name}")
    print(f"[OK] Stochastic parent category: {stochastic_parent_category or ''}")
    print(f"[OK] Model->Stochastic collection lang_id: {model_stochastic_collection_lang_id}")
    print(f"[OK] Target sample count: {target_sample_count}")
    print(f"[OK] Dry run: {dry_run}")

    if dry_run:
        print(
            f"[OK] Would set stochastic attribute lang_id={resolved_sample_attribute_lang_id} "
            f"to {target_sample_count} for object '{stochastic_object_name}'"
        )
        print(
            f"[OK] Would remove existing Model.Stochastic memberships for parent '{stochastic_parent_name}' "
            f"(except child '{stochastic_object_name}')"
        )
        print(
            f"[OK] Would ensure membership '{stochastic_parent_name}' -> '{stochastic_object_name}' "
            f"in Model.Stochastic"
        )
        return

    with PLEXOSSDK(str(model_path)) as sdk:
        with sdk.transaction():
            try:
                stochastic_object = sdk.get_object_by_name(
                    class_lang_id=resolved_stochastic_class_lang_id,
                    object_name=stochastic_object_name,
                )
                print(f"[OK] Stochastic object exists: {stochastic_object_name}")
            except Exception:
                stochastic_object = sdk.add_object(
                    class_lang_id=resolved_stochastic_class_lang_id,
                    object_name=stochastic_object_name,
                )
                print(f"[OK] Stochastic object created: {stochastic_object_name}")

            try:
                parent_obj = sdk.get_object_by_name(
                    class_lang_id=resolved_stochastic_parent_class_lang_id,
                    object_name=stochastic_parent_name,
                )
                print(f"[OK] Stochastic parent exists: {stochastic_parent_name}")
            except Exception:
                parent_obj = add_object_with_optional_category(
                    sdk=sdk,
                    class_lang_id=resolved_stochastic_parent_class_lang_id,
                    object_name=stochastic_parent_name,
                    category_name=stochastic_parent_category,
                )
                print(f"[OK] Stochastic parent created: {stochastic_parent_name}")

            try:
                existing_child_memberships = sdk.get_child_memberships(
                    parent_class_lang_id=resolved_stochastic_parent_class_lang_id,
                    collection_lang_id=model_stochastic_collection_lang_id,
                    parent_name=stochastic_parent_name,
                )
            except Exception:
                existing_child_memberships = []

            for existing_membership in existing_child_memberships:
                existing_child_name = None

                child_obj = getattr(existing_membership, "child_object", None)
                if child_obj is not None:
                    existing_child_name = getattr(child_obj, "name", None)

                if existing_child_name is None:
                    child_object_id = getattr(existing_membership, "child_object_id", None)
                    if child_object_id is not None:
                        try:
                            resolved_child_obj = sdk.get_object(object_id=int(child_object_id))
                            existing_child_name = getattr(resolved_child_obj, "name", None)
                        except Exception:
                            existing_child_name = None

                if existing_child_name and existing_child_name != stochastic_object_name:
                    membership_to_remove = sdk.get_membership_by_names(
                        parent_class_lang_id=resolved_stochastic_parent_class_lang_id,
                        collection_lang_id=model_stochastic_collection_lang_id,
                        parent_name=stochastic_parent_name,
                        child_name=existing_child_name,
                    )
                    membership_to_remove.delete_instance()
                    print(
                        f"[OK] {stochastic_parent_name} -> {existing_child_name} "
                        f"(Model.Stochastic)"
                    )

            membership_created = ensure_membership(
                sdk=sdk,
                parent_class_lang_id=resolved_stochastic_parent_class_lang_id,
                collection_lang_id=model_stochastic_collection_lang_id,
                parent_name=stochastic_parent_name,
                child_name=stochastic_object_name,
            )
            if membership_created:
                print(
                    f"[OK] {stochastic_parent_name} -> {stochastic_object_name} "
                    f"(Model.Stochastic)"
                )
            else:
                print(
                    f"[OK] {stochastic_parent_name} -> {stochastic_object_name} "
                    f"(Model.Stochastic)"
                )

            _set_variable_band_attribute(
                sdk=sdk,
                variable_object=stochastic_object,
                variable_class_lang_id=resolved_stochastic_class_lang_id,
                attribute_lang_id=resolved_sample_attribute_lang_id,
                band_count=target_sample_count,
            )

    print(
        f"[OK] {stochastic_object_name} -> sample count set to {target_sample_count}"
    )

# =============================================================================
# =============================================================================
# >>> Conversion helpers (based on anthony_horizon_update.py safe-conversion pattern) <<<
# =============================================================================
# =============================================================================

def _convert_db_to_xml(
    db_file_path: Path,
    xml_file_path: Path,
    study_id: str,
) -> Path:
    """
    Convert a PLEXOS SQLite database back to XML.

    Uses a backup-restore pattern so an existing XML is never lost:
    rename existing XML -> .bak, run conversion, then remove .bak on success,
    or restore .bak on failure.
    """
    backup_path = Path(f"{xml_file_path}.bak")
    had_existing_xml = xml_file_path.exists()

    if had_existing_xml:
        if backup_path.exists():
            raise FileExistsError(
                f"Backup file already exists; refusing to overwrite: {backup_path}"
            )
        print(f"[OK] Backing up existing XML before reconversion: {xml_file_path} -> {backup_path}")
        os.replace(xml_file_path, backup_path)

    try:
        pxc = CloudSDK(cli_path=ENV_CLOUD_CLI_PATH)
        response = pxc.inputdata.convert_database_to_xml(
            db_file_path=str(db_file_path),
            xml_file_path=str(xml_file_path),
            study_id=study_id,
            print_message=False,
        )
        result = SDKBase.get_response_data(response)
        if result is None:
            response_message = (
                getattr(response, "Message", None)
                or getattr(response[0], "Message", None)
                or "Unknown conversion error"
            )
            raise RuntimeError(f"DB-to-XML conversion failed: {response_message}")
        if not xml_file_path.exists():
            raise RuntimeError("XML creation failed.")
    except Exception:
        # Remove partial conversion output before restoring backup.
        if xml_file_path.exists():
            os.remove(xml_file_path)

        if had_existing_xml and backup_path.exists():
            os.replace(backup_path, xml_file_path)
            print(f"[WARN] Restored XML from backup after reconversion failure: {xml_file_path}")
        raise

    if had_existing_xml and backup_path.exists():
        os.remove(backup_path)
        print(f"[OK] Removed XML backup after successful reconversion: {backup_path}")

    return xml_file_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create one Data File object in the PLEXOS model for each sampled CSV file "
            "from the ExoSampled folder."
        )
    )

    parser.add_argument(
        "--sampled-dir",
        default=SAMPLED_DIR,
        help=f"Folder containing sampled files (default: {SAMPLED_DIR})",
    )
    parser.add_argument(
        "--use-full-filename",
        action=argparse.BooleanOptionalAction,
        default=USE_FULL_FILENAME,
        help="Use full filename (including extension) as object name. Default is filename stem.",
    )
    parser.add_argument(
        "--object-name-prefix",
        type=non_empty_text,
        help="Optional prefix to prepend to created Data File object names.",
    )
    parser.add_argument(
        "--data-file-category",
        type=non_empty_text,
        help="Optional category assigned when creating Data File objects.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=IS_DRYRUN,
        help="Preview operations without writing to the model or regenerating project.xml.",
    )
    parser.add_argument(
        "--model-path",
        help=(
            "Path to model .db file. Defaults to simulation_path/reference.db, "
            "then sqlite_input_path env var."
        ),
    )
    parser.add_argument(
        "--study-id",
        help="PLEXOS study ID (falls back to study_id environment variable).",
    )
    parser.add_argument(
        "--create-variables",
        action=argparse.BooleanOptionalAction,
        default=CREATE_VARIABLES,
        help="Create Variable objects for sampled files and set their band-count attribute.",
    )
    parser.add_argument(
        "--variable-name-suffix",
        default=VARIABLE_NAME_SUFFIX,
        help=f"Suffix appended to variable names (default: {VARIABLE_NAME_SUFFIX}).",
    )
    parser.add_argument(
        "--variable-category",
        type=non_empty_text,
        help="Optional category assigned when creating Variable objects.",
    )
    parser.add_argument(
        "--variable-band-attribute-lang-id",
        type=positive_int,
        default=None,
        help="Optional explicit Variable band attribute lang id. If omitted, auto-detected.",
    )
    parser.add_argument(
        "--require-variable-band-attribute",
        action="store_true",
        help="Fail if no Variable band attribute can be resolved.",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=START_YEAR,
        help=f"Start climate year used for band count (default: {START_YEAR}).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=END_YEAR,
        help=f"End climate year used for band count (default: {END_YEAR}).",
    )
    parser.add_argument(
        "--link-variables",
        action=argparse.BooleanOptionalAction,
        default=LINK_VARIABLES,
        help="Link variables to target objects and also to a scenario.",
    )
    parser.add_argument(
        "--target-class-name",
        type=non_empty_text,
        help="Parent object class name to link with Variable (for example 'Generator').",
    )
    parser.add_argument(
        "--scenario-name",
        default=SCENARIO_NAME,
        help="Scenario object name used for Variable grouping.",
    )
    parser.add_argument(
        "--scenario-category",
        type=non_empty_text,
        help="Optional category assigned when creating Scenario objects.",
    )
    parser.add_argument(
        "--scenario-read-order",
        type=positive_int,
        default=SCENARIO_READ_ORDER,
        help=f"Read Order value for the Scenario (high value = applied last, default: {SCENARIO_READ_ORDER}).",
    )
    parser.add_argument(
        "--scenario-class-lang-id",
        type=positive_int,
        default=None,
        help="Optional explicit Scenario class lang id.",
    )
    parser.add_argument(
        "--adjust-stochastic",
        action=argparse.BooleanOptionalAction,
        default=ADJUST_STOCHASTIC,
        help="Adjust a stochastic object's sample count to match computed sample count.",
    )
    parser.add_argument(
        "--stochastic-object-name",
        default=STOCHASTIC_OBJECT_NAME,
        help=f"Name of stochastic object to update/create (default: {STOCHASTIC_OBJECT_NAME}).",
    )
    parser.add_argument(
        "--stochastic-parent-name",
        default=STOCHASTIC_PARENT_NAME,
        help=f"Parent model object name used for Model.Stochastic membership (default: {STOCHASTIC_PARENT_NAME}).",
    )
    parser.add_argument(
        "--stochastic-parent-category",
        type=non_empty_text,
        help="Optional category to assign when creating the parent model object.",
    )
    parser.add_argument(
        "--stochastic-parent-class-lang-id",
        type=positive_int,
        default=None,
        help="Optional explicit parent Model class lang id for Model.Stochastic membership.",
    )
    parser.add_argument(
        "--sample-count-override",
        type=positive_int,
        help="Optional explicit sample count instead of end_year-start_year+1.",
    )
    parser.add_argument(
        "--stochastic-class-lang-id",
        type=positive_int,
        default=None,
        help="Optional explicit Stochastic class lang id.",
    )
    parser.add_argument(
        "--stochastic-sample-attribute-lang-id",
        type=positive_int,
        default=None,
        help="Optional explicit stochastic sample-count attribute lang id.",
    )

    args = parser.parse_args(_normalize_cli_args(sys.argv[1:]))
    replaced = _restore_placeholder_spaces_in_args(args)
    if replaced:
        print(f"[OK] Restored spaces in {replaced} argument(s)")

    if not args.study_id and ENV_STUDY_ID:
        args.study_id = ENV_STUDY_ID.strip()
        print("[OK] Using study ID from environment variable")

    try:
        model_path = resolve_model_path(args.model_path)
        if model_path.suffix.lower() == ".xml":
            print("[FAIL] XML model input is not supported. Provide a .db model path.")
            return 1

        if not model_path.is_file():
            print(f"[FAIL] Model file not found: {model_path}")
            return 1

        sampled_dir = Path(ENV_SIMULATION_PATH or "") / args.sampled_dir
        print(f"[OK] {sampled_dir}")
        if not sampled_dir.is_dir():
            print(f"[FAIL] Sampled directory not found: {sampled_dir}")
            return 1

        create_data_file_objects_for_samples(
            model_path=model_path,
            sampled_dir=sampled_dir,
            object_name_from_stem=not args.use_full_filename,
            object_name_prefix=args.object_name_prefix,
            data_file_category=args.data_file_category,
            start_year=args.start_year,
            end_year=args.end_year,
            dry_run=args.dry_run,
        )

        if args.create_variables:
            create_variable_objects_for_samples(
                model_path=model_path,
                sampled_dir=sampled_dir,
                object_name_from_stem=not args.use_full_filename,
                object_name_prefix=args.object_name_prefix,
                variable_name_suffix=args.variable_name_suffix,
                variable_category=args.variable_category,
                variable_band_attribute_lang_id=args.variable_band_attribute_lang_id,
                require_variable_band_attribute=args.require_variable_band_attribute,
                start_year=args.start_year,
                end_year=args.end_year,
                dry_run=args.dry_run,
            )

        if args.link_variables:
            if args.target_class_name is None:
                raise ValueError(
                    "--target-class-name is required when using --link-variables"
                )

            link_variables_to_objects_under_scenario(
                model_path=model_path,
                sampled_dir=sampled_dir,
                object_name_from_stem=not args.use_full_filename,
                object_name_prefix=args.object_name_prefix,
                variable_name_suffix=args.variable_name_suffix,
                target_class_name=args.target_class_name,
                scenario_name=args.scenario_name,
                scenario_class_lang_id=args.scenario_class_lang_id,
                scenario_category=args.scenario_category,
                scenario_read_order=args.scenario_read_order,
                start_year=args.start_year,
                end_year=args.end_year,
                dry_run=args.dry_run,
                model_parent_name=args.stochastic_parent_name,
                model_parent_class_lang_id=args.stochastic_parent_class_lang_id,
            )

        if args.adjust_stochastic:
            adjust_stochastic_object_sample_count(
                model_path=model_path,
                stochastic_object_name=args.stochastic_object_name,
                stochastic_parent_name=args.stochastic_parent_name,
                stochastic_parent_category=args.stochastic_parent_category,
                stochastic_parent_class_lang_id=args.stochastic_parent_class_lang_id,
                start_year=args.start_year,
                end_year=args.end_year,
                sample_count_override=args.sample_count_override,
                stochastic_class_lang_id=args.stochastic_class_lang_id,
                stochastic_sample_attribute_lang_id=args.stochastic_sample_attribute_lang_id,
                dry_run=args.dry_run,
            )

        print("[OK] All operations completed successfully")

        if args.dry_run:
            print("[OK] Dry run: skipping DB -> XML conversion")
            return 0


        export_xml_path = model_path.with_name("project.xml")
        print(f"[OK] DB -> XML: {model_path} -> {export_xml_path}")
        _convert_db_to_xml(
            db_file_path=model_path,
            xml_file_path=export_xml_path,
            study_id=args.study_id,
        )
        print(f"[OK] XML updated: {export_xml_path}")

        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())



