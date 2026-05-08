"""Push local PLEXOS study changes as a new cloud changeset.

Focused script - changeset push only. No model editing.
Chain with another pre-simulation script if you need to modify project.xml
before staging and push.

Environment variables used:
    cloud_cli_path  - required; path to the Cloud CLI executable
    simulation_path - required; root path containing project.xml
    output_path     - required; writable root path used for staging the clone
    study_id        - required; identifies the cloud study to clone and push
"""
import argparse
import filecmp
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import unquote

from eecloud.cloudsdk import CloudSDK

try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("[FAIL] Missing required environment variable: cloud_cli_path")
    sys.exit(1)

try:
    SIMULATION_PATH = os.environ["simulation_path"]
except KeyError:
    print("[FAIL] Missing required environment variable: simulation_path")
    sys.exit(1)

try:
    OUTPUT_PATH = os.environ["output_path"]
except KeyError:
    print("[FAIL] Missing required environment variable: output_path")
    sys.exit(1)

try:
    STUDY_ID = os.environ["study_id"]
except KeyError:
    print("[FAIL] Missing required environment variable: study_id")
    sys.exit(1)


MODEL_XML_SOURCE_FILE = "project.xml"
STAGING_DIRECTORY_NAME = ".changeset_staging"


# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION \u2014 These defaults apply when the corresponding CLI flag is omitted.
# ═══════════════════════════════════════════════════════════════════════════════
# Number of retry attempts on transient failure
RETRIES = 3

# Seconds to wait between retries
RETRY_INTERVAL = 30

# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════


def positive_int(value: str) -> int:
    """Validate integer arguments that must be greater than zero."""
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, got '{value}'") from exc

    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0")

    return parsed_value


def non_negative_int(value: str) -> int:
    """Validate integer arguments that may be zero but not negative."""
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, got '{value}'") from exc

    if parsed_value < 0:
        raise argparse.ArgumentTypeError("Value must be greater than or equal to 0")

    return parsed_value


def validate_target_file(value: str) -> str:
    """Accept only a simple XML filename for the staged target file."""
    target_file = value.strip()
    if not target_file:
        raise argparse.ArgumentTypeError("Target file cannot be empty")
    if os.path.isabs(target_file):
        raise argparse.ArgumentTypeError("Target file must be a filename, not an absolute path")
    if os.path.basename(target_file) != target_file:
        raise argparse.ArgumentTypeError("Target file must not include directory components")
    if not target_file.lower().endswith(".xml"):
        raise argparse.ArgumentTypeError("Target file must end with .xml")
    return target_file


def _decode_argument_value(value: str) -> tuple[str, bool]:
    """Strip stray quotes and URL-decode an argument value."""
    decoded_value = unquote(value.strip("'\""))
    return decoded_value, decoded_value != value


def _decode_cli_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """URL-decode supported CLI arguments and return the number of changed values."""
    replaced_tokens = 0

    if isinstance(args.message, str):
        restored_message, changed = _decode_argument_value(args.message)
        if changed:
            replaced_tokens += 1
        args.message = restored_message

    if isinstance(args.target_file, str):
        restored_target_file, changed = _decode_argument_value(args.target_file)
        try:
            validated_target_file = validate_target_file(restored_target_file)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
        if changed:
            replaced_tokens += 1
        args.target_file = validated_target_file

    return replaced_tokens


def summarize_response(response):
    """Print SDK response messages and return the final status and message."""
    if not response:
        print("[FAIL] SDK returned no response.")
        return "", ""

    for item in response:
        message = getattr(item, "Message", "")
        if message:
            print(f"  {message}")

    final_item = response[-1]
    return getattr(final_item, "Status", ""), getattr(final_item, "Message", "")


def prepare_staging_directory(staging_dir: str) -> None:
    """Remove any existing staging clone so each run starts from a clean baseline."""
    if os.path.isdir(staging_dir):
        shutil.rmtree(staging_dir)
        print(f"[OK] Removed existing staging directory: {staging_dir}")
    elif os.path.exists(staging_dir):
        os.remove(staging_dir)
        print(f"[OK] Removed existing staging file: {staging_dir}")


def clone_study(pxc, study_id, output_directory):
    """Clone the study to the specified output directory."""
    print(f"[OK] Cloning study '{study_id}' to '{output_directory}'...")
    response = pxc.study.clone_study(
        study_id=study_id,
        output_directory_path=output_directory,
        print_message=False,
    )
    status, message = summarize_response(response)
    if status == "Success":
        print("[OK] Study cloned successfully.")
        return True
    print(f"[FAIL] Clone failed: {message or 'No response details available'}")
    return False


def sync_model_files(source_dir, staging_dir, target_file) -> tuple[int, str]:
    """Sync the local project.xml into staging and report whether it changed."""
    print("[OK] Syncing model files into staging directory...")
    source_path = Path(source_dir) / MODEL_XML_SOURCE_FILE
    staged_path = Path(staging_dir) / target_file

    if not source_path.is_file():
        if staged_path.is_file():
            print(f"[WARN] {MODEL_XML_SOURCE_FILE} missing locally; keeping existing staged {target_file}")
            print("[OK] Files changed for tracking: 0")
            return 0, "staged_only"
        print(f"[WARN] {MODEL_XML_SOURCE_FILE} not found in {source_dir}; nothing to stage")
        print("[OK] Files changed for tracking: 0")
        return 0, "missing_source"

    target_exists = staged_path.is_file()
    if target_exists and filecmp.cmp(source_path, staged_path, shallow=False):
        print(f"[OK] {MODEL_XML_SOURCE_FILE} is unchanged relative to staged {target_file}")
        print("[OK] Files changed for tracking: 0")
        return 0, "unchanged"

    shutil.copy2(source_path, staged_path)
    status = "updated" if target_exists else "copied"
    print(f"[OK] {status.capitalize()} {MODEL_XML_SOURCE_FILE} -> {target_file}")
    print("[OK] Files changed for tracking: 1")
    return 1, status


def push_study_changeset(pxc, study_id, message, retries=3, retry_interval=30):
    """Push local changes as a new changeset to PLEXOS Cloud, with retries."""
    for attempt in range(1, retries + 1):
        print(f"[OK] Pushing changeset for study '{study_id}' (attempt {attempt}/{retries})...")
        response = pxc.study.push_changeset(
            study_id=study_id,
            commit_message=message,
            print_message=False,
        )
        status, message_text = summarize_response(response)
        if status == "Success":
            print(f"[OK] Successfully pushed changeset for study '{study_id}'.")
            return True

        last_message = (message_text or "").lower()
        if "no changes to push" in last_message or "no change is present" in last_message:
            print("[OK] No changes detected. Skipping push retries.")
            return True

        print(f"[WARN] Attempt {attempt} failed: {message_text or 'No response details available'}")
        if attempt < retries:
            print(f"[WARN] Retrying in {retry_interval}s...")
            time.sleep(retry_interval)

    print(f"[FAIL] Failed to push changeset for study '{study_id}' after {retries} attempts.")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
                "Clone the target study into a staging directory, stage the local model XML "
                "into the clone, and push a new PLEXOS Cloud changeset when differences exist."
        )
    )
    parser.add_argument(
        "--message",
        required=True,
        help="Commit message describing the study changes.",
    )
    parser.add_argument(
        "--retries",
        type=positive_int,
        default=RETRIES,
        help=f"Number of retry attempts on transient failure (default: {RETRIES}).",
    )
    parser.add_argument(
        "--retry-interval",
        dest="retry_interval",
        type=non_negative_int,
        default=RETRY_INTERVAL,
        help=f"Seconds to wait between retries (default: {RETRY_INTERVAL}).",
    )
    parser.add_argument(
        "--target-file",
        type=validate_target_file,
        default=MODEL_XML_SOURCE_FILE,
        help=f"Target XML filename to write inside the staging clone (default: {MODEL_XML_SOURCE_FILE}).",
    )
    args = parser.parse_args()
    decoded_count = _decode_cli_args(args, parser)
    if decoded_count:
        print(f"[OK] Decoded {decoded_count} URL-encoded argument(s).")
    print(f"[OK] Parsed arguments: {args}")

    try:
        pxc = CloudSDK(cli_path=CLOUD_CLI_PATH)
        staging_dir = os.path.join(OUTPUT_PATH, STAGING_DIRECTORY_NAME)

        prepare_staging_directory(staging_dir)
        if not clone_study(pxc, STUDY_ID, staging_dir):
            return 1

        changed_files, sync_status = sync_model_files(SIMULATION_PATH, staging_dir, args.target_file)
        if changed_files == 0:
            if sync_status in {"missing_source", "staged_only"}:
                print(f"[WARN] No local {MODEL_XML_SOURCE_FILE} was staged. Nothing to push.")
            else:
                print(f"[OK] {MODEL_XML_SOURCE_FILE} unchanged. Nothing to push.")
            return 0

        if not push_study_changeset(pxc, STUDY_ID, args.message, args.retries, args.retry_interval):
            return 1

        return 0
    except Exception as exc:
        print(f"[FAIL] Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())