"""
Replace model input timeseries for a target property using the PLEXOS SDK.

Use this script to fully replace an existing property input assignment (for
example gas price timeseries for Natural Gas Europe) with a new DataHub-backed
data file path.

Supports both name-based and lang-id-based lookups:
  - Pass --parent-class-name, --collection-name, --property-name (easy mode)
  - Or pass --parent-class-lang-id, --collection-lang-id, --property-lang-id (explicit IDs)
  - If both are given, the lang-id takes priority.

Environment variables used:
    cloud_cli_path    - path to the Cloud CLI executable; used for DB-to-XML conversion
    simulation_path   - root path for study files (contains reference.db and project.xml)
    study_id          - required; used for DB-to-XML regeneration for the current study
    sqlite_input_path - fallback model path when simulation_path is not available
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote

from eecloud.cloudsdk import CloudSDK, SDKBase
from plexos_sdk import PLEXOSSDK


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

SQLITE_INPUT_PATH = os.environ.get("sqlite_input_path")

SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")


# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION \u2014 These defaults are used when no command-line arguments are provided.
# ═══════════════════════════════════════════════════════════════════════════════
# Property band id to replace
BAND_ID = 1
# Remove existing property at the same band before adding new assignment
REPLACE_EXISTING = True

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


def _decode_argument_value(value: str) -> tuple[str, bool]:
    """Strip stray quotes and URL-decode an argument value."""
    decoded_value = unquote(value.strip("'\""))
    return decoded_value, decoded_value != value


def _decode_url_encoded_args(args: argparse.Namespace) -> int:
    """URL-decode supported string arguments and return number of changed tokens."""
    replaced_tokens = 0

    for field_name in [
        "parent_class_name", "collection_name", "property_name",
        "parent_object_name", "child_object_name",
        "data_file_path", "model_path",
        "time_slice_text",
    ]:
        field_value = getattr(args, field_name, None)
        if isinstance(field_value, str):
            restored, changed = _decode_argument_value(field_value)
            if changed:
                replaced_tokens += 1
            setattr(args, field_name, restored)

    return replaced_tokens


# ---------------------------------------------------------------------------
# Name-to-lang-id discovery (queries the model database directly)
# ---------------------------------------------------------------------------

def discover_class_lang_id(model_path: Path, class_name: str) -> int:
    """Look up a PLEXOS class lang_id by name (e.g. 'System', 'Generator')."""
    query = """
    SELECT lang_id, name
    FROM t_class
    WHERE lower(name) = lower(?)
       OR lower(name) = lower(? || 's')
    ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END, class_id
    LIMIT 1
    """
    with sqlite3.connect(str(model_path)) as conn:
        row = conn.execute(query, (class_name, class_name, class_name)).fetchone()
    if not row:
        raise ValueError(f"Class '{class_name}' not found in model.")
    lang_id, matched = row
    print(f"[OK] Resolved class '{matched}' -> lang_id={lang_id}")
    return int(lang_id)


def discover_collection_lang_id(model_path: Path, collection_name: str) -> int:
    """Look up a collection lang_id by name (e.g. 'Data Files', 'Generators')."""
    query = """
    SELECT lang_id, name
    FROM t_collection
    WHERE lower(name) = lower(?)
       OR lower(name) LIKE lower(?)
    ORDER BY CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END, collection_id
    LIMIT 1
    """
    like_pattern = f"%{collection_name}%"
    with sqlite3.connect(str(model_path)) as conn:
        row = conn.execute(query, (collection_name, like_pattern, collection_name)).fetchone()
    if not row:
        raise ValueError(f"Collection '{collection_name}' not found in model.")
    lang_id, matched = row
    print(f"[OK] Resolved collection '{matched}' -> lang_id={lang_id}")
    return int(lang_id)


def discover_property_lang_id(model_path: Path, collection_lang_id: int, property_name: str) -> int:
    """Look up a property lang_id by name within a collection (e.g. 'Filename', 'Price')."""
    query = """
    SELECT p.lang_id, p.name
    FROM t_property p
    JOIN t_collection col ON col.collection_id = p.collection_id
    WHERE col.lang_id = ?
      AND (lower(p.name) = lower(?) OR lower(p.name) LIKE lower(?))
    ORDER BY CASE WHEN lower(p.name) = lower(?) THEN 0 ELSE 1 END, p.property_id
    LIMIT 1
    """
    like_pattern = f"%{property_name}%"
    with sqlite3.connect(str(model_path)) as conn:
        row = conn.execute(query, (collection_lang_id, property_name, like_pattern, property_name)).fetchone()
    if not row:
        raise ValueError(f"Property '{property_name}' not found in collection lang_id={collection_lang_id}.")
    lang_id, matched = row
    print(f"[OK] Resolved property '{matched}' -> lang_id={lang_id}")
    return int(lang_id)


def resolve_lang_ids(
    model_path: Path,
    parent_class_lang_id: int | None,
    parent_class_name: str | None,
    collection_lang_id: int | None,
    collection_name: str | None,
    property_lang_id: int | None,
    property_name: str | None,
) -> tuple[int, int, int]:
    """Resolve all three lang IDs from names or explicit IDs. IDs take priority."""

    # --- Parent class ---
    if parent_class_lang_id is None:
        if not parent_class_name:
            raise ValueError("Provide --parent-class-lang-id or --parent-class-name.")
        parent_class_lang_id = discover_class_lang_id(model_path, parent_class_name)

    # --- Collection ---
    if collection_lang_id is None:
        if not collection_name:
            raise ValueError("Provide --collection-lang-id or --collection-name.")
        collection_lang_id = discover_collection_lang_id(model_path, collection_name)

    # --- Property ---
    if property_lang_id is None:
        if not property_name:
            raise ValueError("Provide --property-lang-id or --property-name.")
        property_lang_id = discover_property_lang_id(model_path, collection_lang_id, property_name)

    return parent_class_lang_id, collection_lang_id, property_lang_id

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


def str_to_bool(value: str) -> bool:
    """Parse user-friendly boolean values for CLI flags."""
    normalized = value.strip().lower()
    truthy = {"1", "true", "t", "yes", "y"}
    falsy = {"0", "false", "f", "no", "n"}

    if normalized in truthy:
        return True
    if normalized in falsy:
        return False

    raise argparse.ArgumentTypeError(
        f"Invalid boolean value '{value}'. Use true/false, yes/no, or 1/0"
    )


def optional_float(value: str) -> float | None:
    """Parse optional float where 'none' means no scalar value."""
    normalized = value.strip().lower()
    if normalized in {"none", "null", ""}:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid float value '{value}'. Use a number or 'none'."
        ) from exc


def resolve_model_path(explicit_model_path: str | None) -> Path:
    """Resolve model path from arg first, then simulation_path/reference.db, then sqlite_input_path."""
    if explicit_model_path:
        return Path(explicit_model_path)

    # Primary: simulation_path + reference.db (working copy used by Pre tasks)
    if SIMULATION_PATH:
        candidate = Path(SIMULATION_PATH) / "reference.db"
        if candidate.is_file():
            return candidate

    # Fallback: sqlite_input_path (DataHub staging path)
    if SQLITE_INPUT_PATH:
        return Path(SQLITE_INPUT_PATH)

    raise ValueError(
        "Missing model path. Provide --model-path, or set simulation_path / sqlite_input_path environment variable."
    )


def _regenerate_xml(db_path: Path, xml_path: Path, study_id: str) -> bool:
    """Back up project.xml, convert reference.db back to XML, and restore on failure.

    The Cloud CLI converter will not overwrite an existing XML file,
    so the old one must be renamed out of the way first.  A .bak copy
    is kept until conversion succeeds so the study is never left
    without a valid XML file.
    """
    backup_path = Path(str(xml_path) + ".bak")
    try:
        if xml_path.exists():
            os.rename(xml_path, backup_path)
            print(f"[OK] Backed up existing XML: {backup_path}")

        pxc = CloudSDK(cli_path=CLOUD_CLI_PATH)
        response = pxc.inputdata.convert_database_to_xml(
            db_file_path=str(db_path),
            xml_file_path=str(xml_path),
            study_id=study_id,
            print_message=False,
        )

        result = SDKBase.get_response_data(response)
        if result is None:
            print(f"[FAIL] DB-to-XML conversion failed: {response.Message}")
            if backup_path.exists():
                os.rename(backup_path, xml_path)
                print(f"[OK] Restored original XML: {xml_path}")
            return False

        if not xml_path.exists():
            print("[FAIL] XML creation failed.")
            if backup_path.exists():
                os.rename(backup_path, xml_path)
                print(f"[OK] Restored original XML: {xml_path}")
            return False

        if backup_path.exists():
            os.remove(backup_path)

        print(f"[OK] Regenerated XML: {xml_path}")
        return True

    except Exception as exc:
        print(f"[FAIL] {exc}")
        if backup_path.exists() and not xml_path.exists():
            os.rename(backup_path, xml_path)
            print(f"[OK] Restored original XML: {xml_path}")
        return False


def replace_property_input_file(
    model_path: Path,
    parent_class_lang_id: int,
    collection_lang_id: int,
    parent_object_name: str,
    child_object_name: str,
    property_lang_id: int,
    data_file_path: str,
    band_id: int,
    value: float | None,
    time_slice_text: str | None,
    period_type_id: int | None,
    replace_existing: bool,
) -> None:
    """Replace property input assignment with a new data file text path."""

    print(f"[OK] Replacing '{child_object_name}' property {property_lang_id} band {band_id} with '{data_file_path}'")
    print(f"[OK] Model: {model_path}, parent: '{parent_object_name}', replace_existing: {replace_existing}")

    with PLEXOSSDK(str(model_path)) as sdk:
        with sdk.transaction():
            membership = sdk.get_membership_by_names(
                parent_class_lang_id=parent_class_lang_id,
                collection_lang_id=collection_lang_id,
                parent_name=parent_object_name,
                child_name=child_object_name,
            )

            property_obj = sdk.get_property(
                parent_class_lang_id=parent_class_lang_id,
                collection_lang_id=collection_lang_id,
                property_lang_id=property_lang_id,
            )

            if replace_existing:
                removed = sdk.remove_property(
                    membership=membership,
                    property_obj=property_obj,
                    band_id=band_id,
                )
                print(f"[OK] Removed existing property assignment: {removed}")

            sdk.add_property(
                membership=membership,
                property_obj=property_obj,
                value=value,
                data_file_text=data_file_path,
                time_slice_text=time_slice_text,
                band_id=band_id,
                period_type_id=period_type_id,
            )

            print("[OK] New data file assignment applied")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace a target model property input assignment with a new DataHub file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples (using names — easy mode):\n"
            "  python replace_model_input_files.py --model-path model.db --parent-class-name System --collection-name Data%%20Files --parent-object-name System --child-object-name Solar%%20Rating --property-name Filename --data-file-path new_solar.csv\n"
            "\n"
            "Examples (using lang IDs — explicit mode):\n"
            "  python replace_model_input_files.py --model-path model.db --parent-class-lang-id 1 --collection-lang-id 16 --parent-object-name System --child-object-name Solar%%20Rating --property-lang-id 193 --data-file-path new_solar.csv\n"
            "\n"
            "Note: Spaces in names must be encoded as '%%20' because quoting is not reliable in simulation task definitions.\n"
            "\n"
            "You can mix names and IDs. If both name and ID are given for the same field, the ID takes priority."
        ),
    )

    parser.add_argument(
        "--parent-class-name",
        type=non_empty_text,
        help="Parent class name (for example System, Generator). Auto-discovers lang_id from model.",
    )
    parser.add_argument(
        "--collection-name",
        type=non_empty_text,
        help="Collection name (for example 'Data Files', 'Generators'). Auto-discovers lang_id from model. Use '%%20' in place of spaces in task definitions.",
    )
    parser.add_argument(
        "--property-name",
        type=non_empty_text,
        help="Property name (for example Filename, Price). Auto-discovers lang_id from model.",
    )

    # --- Lang-id-based arguments (explicit mode, override names) ---
    parser.add_argument(
        "--parent-class-lang-id",
        type=positive_int,
        default=None,
        help="Parent class lang id (overrides --parent-class-name if both given).",
    )
    parser.add_argument(
        "--collection-lang-id",
        type=positive_int,
        default=None,
        help="Collection lang id (overrides --collection-name if both given).",
    )
    parser.add_argument(
        "--property-lang-id",
        type=positive_int,
        default=None,
        help="Property lang id (overrides --property-name if both given).",
    )

    # --- Always required ---
    parser.add_argument(
        "--parent-object-name",
        required=True,
        type=non_empty_text,
        help="Parent object name for membership lookup (for example System).",
    )
    parser.add_argument(
        "--child-object-name",
        required=True,
        type=non_empty_text,
        help="Child object name for membership lookup (for example Solar Rating).",
    )
    parser.add_argument(
        "--data-file-path",
        required=True,
        type=non_empty_text,
        help="Relative path from simulation_path to the data file downloaded from DataHub (for example new_solar.csv). Must not be an absolute filesystem path or DataHub remote path.",
    )

    # --- Optional ---
    parser.add_argument(
        "--model-path",
        help=(
            "Path to the PLEXOS SQLite input model. If not provided, the script first "
            "tries simulation_path/reference.db and then falls back to the "
            "sqlite_input_path environment variable."
        ),
    )
    parser.add_argument(
        "--band-id",
        type=positive_int,
        default=BAND_ID,
        help="Property band id to replace (default: 1).",
    )
    parser.add_argument(
        "--value",
        type=optional_float,
        help="Optional scalar value for the property assignment. Use 'none' for no scalar value (default: none).",
    )
    parser.add_argument(
        "--time-slice-text",
        type=non_empty_text,
        default=None,
        help="Optional time slice text (for example M1-12).",
    )
    parser.add_argument(
        "--period-type-id",
        type=positive_int,
        default=None,
        help="Optional period type id.",
    )
    parser.add_argument(
        "--replace-existing",
        type=str_to_bool,
        default=REPLACE_EXISTING,
        help="Remove existing property at the same band before adding new assignment (default: true).",
    )

    args = parser.parse_args(_normalize_cli_args(sys.argv[1:]))
    replaced = _decode_url_encoded_args(args)
    if replaced:
        print(f"[OK] URL-decoded {replaced} argument(s)")

    try:
        model_path = resolve_model_path(args.model_path)
        if not model_path.is_file():
            print(f"[FAIL] Model file not found: {model_path}")
            return 1

        # Resolve names to lang IDs (or use explicit IDs if provided)
        parent_class_lang_id, collection_lang_id, property_lang_id = resolve_lang_ids(
            model_path=model_path,
            parent_class_lang_id=args.parent_class_lang_id,
            parent_class_name=args.parent_class_name,
            collection_lang_id=args.collection_lang_id,
            collection_name=args.collection_name,
            property_lang_id=args.property_lang_id,
            property_name=args.property_name,
        )

        # --- Validate data file exists  (downloaded to simulation_path) ---
        data_file_candidate = Path(SIMULATION_PATH) / args.data_file_path
        if not data_file_candidate.is_file():
            # Also try the raw path in case it's an absolute path
            if not Path(args.data_file_path).is_file():
                print(f"[FAIL] Data file not found: {data_file_candidate}")
                print(f"[FAIL] Also checked: {args.data_file_path}")
                print("[FAIL] Ensure the file has been downloaded (e.g. via DownloadFromDataHub) before running this script.")
                return 1

        replace_property_input_file(
            model_path=model_path,
            parent_class_lang_id=parent_class_lang_id,
            collection_lang_id=collection_lang_id,
            parent_object_name=args.parent_object_name,
            child_object_name=args.child_object_name,
            property_lang_id=property_lang_id,
            data_file_path=args.data_file_path,
            band_id=args.band_id,
            value=args.value,
            time_slice_text=args.time_slice_text,
            period_type_id=args.period_type_id,
            replace_existing=args.replace_existing,
        )

        print("[OK] Property input file replaced successfully")

        # --- DB-to-XML conversion is compulsory ---
        xml_path = Path(SIMULATION_PATH) / "project.xml"
        print(f"[OK] Converting DB -> XML: {model_path} -> {xml_path}")
        if not _regenerate_xml(db_path=model_path, xml_path=xml_path, study_id=STUDY_ID):
            return 1

        return 0

    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())