"""
Update the simulation horizon (date range and step configuration) in a PLEXOS model.

Focused script — horizon update only. No other model modifications.
After updating the .db file, converts it back to XML so the engine picks up
the change. The existing project.xml must be deleted first because the
converter will not overwrite it.

Environment variables used:
    cloud_cli_path  - required; path to the Cloud CLI executable
    simulation_path - root path for study files (read/write in pre tasks)
    study_id        - required; identifies the current study
"""
import argparse
import os
import sys
from datetime import datetime
from urllib.parse import unquote

from eecloud.cloudsdk import CloudSDK, SDKBase
from plexos_sdk import PLEXOSSDK

# Platform-provided — injected automatically. Do not set these manually.
try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("Error: Missing required environment variable: cloud_cli_path")
    sys.exit(1)

try:
    STUDY_ID = os.environ["study_id"]
except KeyError:
    print("Error: Missing required environment variable: study_id")
    sys.exit(1)

SIMULATION_PATH = os.environ.get("simulation_path", "/simulation")

# Step type constants for readability
STEP_TYPES = {"day": 1, "week": 2, "month": 3, "year": 4}


def _decode_value(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


class HorizonUpdater:
    """Updates the horizon in a PLEXOS .db model and regenerates the XML."""

    def __init__(self, cli_path: str, simulation_path: str, study_id: str):
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

    def update(
        self,
        horizon_name: str,
        date_from: datetime | None = None,
        step_count: int | None = None,
        step_type: int | None = None,
    ) -> bool:
        """
        Update the named horizon and regenerate the XML file.

        Args:
            horizon_name: Name of the horizon to update.
            date_from:    New simulation start date (optional).
            step_count:   New number of steps (optional).
            step_type:    New step type: 1=Day, 2=Week, 3=Month, 4=Year (optional).

        Returns:
            True if horizon was updated and XML regenerated.
            False if reference.db is missing or db-to-xml conversion fails.

        Raises:
            Exception: If the horizon name is not found or the SDK
                       encounters an unexpected error.
        """
        if not os.path.exists(self.db_path):
            print(f"[FAIL] PLEXOS database not found: {self.db_path}")
            return False

        if not self._update_horizon_in_db(horizon_name, date_from, step_count, step_type):
            return False

        if not self._regenerate_xml():
            return False

        print(f"[OK] Horizon '{horizon_name}' updated and XML regenerated")
        return True

    def _update_horizon_in_db(
        self,
        horizon_name: str,
        date_from: datetime | None,
        step_count: int | None,
        step_type: int | None,
    ) -> bool:
        """
        Open the PLEXOS .db with the SDK and update the horizon.

        Returns:
            True on success, False otherwise.
        """
        with PLEXOSSDK(self.db_path) as sdk:
            horizon = sdk.get_horizon_by_name(horizon_name)
            print(f"[OK] Found horizon: {horizon.name}")

            with sdk.transaction():
                updated = sdk.update_horizon(
                    horizon,
                    date_from=date_from,
                    step_count=step_count,
                    step_type=step_type,
                    chrono_date_from=date_from,
                )

            if not updated:
                print("[FAIL] update_horizon returned None")
                return False

            print("[OK] Horizon updated in database")
            return True

    def _regenerate_xml(self) -> bool:
        """
        Delete the existing project.xml and convert the .db back to XML.

        The Cloud CLI converter will not overwrite an existing XML file, so
        the old one must be removed first.

        Returns:
            True on success, False otherwise.
        """
        if os.path.exists(self.xml_path):
            os.remove(self.xml_path)
            print(f"[OK] Removed existing XML: {self.xml_path}")

        pxc = CloudSDK(cli_path=self.cli_path)
        response = pxc.inputdata.convert_database_to_xml(
            db_file_path=self.db_path,
            xml_file_path=self.xml_path,
            study_id=self.study_id,
            print_message=False,
        )

        result = SDKBase.get_response_data(response)
        if result is None:
            print(f"[FAIL] db-to-xml conversion failed: {response.Message}")
            return False

        print(f"[OK] Regenerated XML: {self.xml_path}")
        return True


def _parse_date(value: str) -> datetime:
    """Parse an ISO-format date string to datetime."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: '{value}'. Use ISO format, e.g. 2025-01-01"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update the simulation horizon in a PLEXOS model."
    )
    parser.add_argument(
        "--horizon-name",
        required=True,
        help="Name of the horizon to update.",
    )
    parser.add_argument(
        "--date-from",
        type=_parse_date,
        default=None,
        help="New simulation start date (ISO format, e.g. 2025-01-01).",
    )
    parser.add_argument(
        "--step-count",
        type=int,
        default=None,
        help="New number of steps.",
    )
    parser.add_argument(
        "--step-type",
        type=str,
        choices=list(STEP_TYPES.keys()) + ["1", "2", "3", "4"],
        default=None,
        help="Step type: day (1), week (2), month (3), year (4).",
    )
    print(f"\n[OK] Received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    args.horizon_name = _decode_value(args.horizon_name)
    print(f"[OK] Interpreted: {args}")

    step_type = None
    if args.step_type is not None:
        step_type = STEP_TYPES.get(args.step_type) or int(args.step_type)

    if args.date_from is None and args.step_count is None and step_type is None:
        print("Error: At least one of --date-from, --step-count, or --step-type must be provided")
        return 1

    try:
        updater = HorizonUpdater(
            cli_path=CLOUD_CLI_PATH,
            simulation_path=SIMULATION_PATH,
            study_id=STUDY_ID,
        )
        success = updater.update(
            horizon_name=args.horizon_name,
            date_from=args.date_from,
            step_count=args.step_count,
            step_type=step_type,
        )
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
