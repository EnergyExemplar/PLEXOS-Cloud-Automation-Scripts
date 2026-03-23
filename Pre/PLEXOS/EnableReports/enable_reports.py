"""
Extend a PLEXOS model report with additional reporting properties.

Focused script — report configuration only. No other model modifications.
Adds reporting properties (by name) to an existing Report object in the
PLEXOS model database, enabling outputs such as emissions by generator,
fuel offtake by generator, and similar per-property reports.

After updating the database, converts it back to XML so the engine picks up
the change. The existing project.xml is backed up before conversion and
restored if conversion fails, so the study is never left without a valid XML.

The Report class lang id and reporting property lang ids are resolved
automatically from reference.db — no numeric ids need to be provided.

Environment variables used:
    cloud_cli_path  - required; path to the Cloud CLI executable
    study_id        - required; identifies the current study
    simulation_path - root path for study files (read/write in pre tasks)
"""

import argparse
import os
import sqlite3
import sys
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


PHASE_MAP: dict[str, int] = {
    "ST": 1,    # ST Schedule
    "MT": 2,    # MT Schedule
    "PASA": 3,  # PASA
    "LT": 4,    # LT Plan
}


def _decode_value(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip("'\""))


def parse_name_list(value: str) -> list[str]:
    """Parse a comma-separated string of names into a deduplicated list preserving order."""
    raw_items = [item.strip() for item in value.split(",") if item.strip()]
    if not raw_items:
        raise argparse.ArgumentTypeError("Provide at least one reporting property name")
    seen: set[str] = set()
    result: list[str] = []
    for item in raw_items:
        lower = item.lower()
        if lower not in seen:
            result.append(item)
            seen.add(lower)
    return result


def str_to_bool(value: str) -> bool:
    """Parse user-friendly boolean values for CLI flags."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y"}:
        return True
    if normalized in {"0", "false", "f", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(
        f"Invalid boolean value '{value}'. Use true/false, yes/no, or 1/0"
    )


def non_empty_text(value: str) -> str:
    """Validate that a CLI argument is a non-empty string."""
    cleaned = value.strip()
    if not cleaned:
        raise argparse.ArgumentTypeError("Value cannot be empty")
    return cleaned


def phase_name(value: str) -> str:
    """Normalize and validate a simulation phase name CLI argument."""
    upper = value.strip().upper()
    if upper not in PHASE_MAP:
        raise argparse.ArgumentTypeError(
            f"Invalid phase '{value}'. Choose from: {', '.join(PHASE_MAP)}"
        )
    return upper


class ReportExtender:
    """Extends an existing PLEXOS Report object with reporting properties and regenerates the XML."""

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

    def extend(
        self,
        report_object_name: str,
        reporting_property_names: list[str],
        phase_id: int = 4,
        report_period: bool = True,
        report_samples: bool = False,
        report_statistics: bool = False,
        report_summary: bool = True,
        write_flat_files: bool = False,
    ) -> bool:
        """
        Add reporting properties to the named Report object and regenerate XML.

        Args:
            report_object_name:       Name of the Report object in the model.
            reporting_property_names: Property names to enable (e.g. 'Emissions by Generator').
            phase_id:                 Phase id for report configuration (default: 4 = LT).
            report_period:            Enable period output (default: True).
            report_samples:           Enable sample output (default: False).
            report_statistics:        Enable statistics output (default: False).
            report_summary:           Enable summary output (default: True).
            write_flat_files:         Enable flat-file output (default: False).

        Returns:
            True if all reporting properties were configured and XML regenerated successfully.
            False on any failure (missing database, unknown report object or property, SDK error).
        """
        if not os.path.exists(self.db_path):
            print(f"[FAIL] PLEXOS database not found: {self.db_path}")
            return False

        if not self._configure_report(
            report_object_name,
            reporting_property_names,
            phase_id,
            report_period,
            report_samples,
            report_statistics,
            report_summary,
            write_flat_files,
        ):
            return False

        if not self._regenerate_xml():
            return False

        print(f"[OK] Report '{report_object_name}' updated and XML regenerated")
        return True

    def _configure_report(
        self,
        report_object_name: str,
        reporting_property_names: list[str],
        phase_id: int,
        report_period: bool,
        report_samples: bool,
        report_statistics: bool,
        report_summary: bool,
        write_flat_files: bool,
    ) -> bool:
        """
        Resolve lang ids from the database, open the SDK, and configure reporting properties.

        Returns:
            True on success, False otherwise.
        """
        try:
            report_class_lang_id = self._discover_report_class_lang_id()
            reporting_lang_ids = self._discover_reporting_lang_ids_by_name(reporting_property_names)

            with PLEXOSSDK(self.db_path) as sdk:
                report_object = sdk.get_object_by_name(report_class_lang_id, report_object_name)
                print(f"[OK] Report object found: {report_object.name!r}")

                with sdk.transaction():
                    reports = sdk.configure_report_properties(
                        object_obj=report_object,
                        reporting_lang_ids=reporting_lang_ids,
                        phase_id=phase_id,
                        report_period=report_period,
                        report_samples=report_samples,
                        report_statistics=report_statistics,
                        report_summary=report_summary,
                        write_flat_files=write_flat_files,
                    )

            print(f"[OK] Configured {len(reports)} reporting propert{'y' if len(reports) == 1 else 'ies'} on {report_object.name!r}")
            return True
        except Exception as exc:
            print(f"[FAIL] {exc}")
            return False

    def _regenerate_xml(self) -> bool:
        """
        Convert the .db back to XML, replacing the existing project.xml only on success.

        Renames the existing project.xml to a .bak file before conversion and
        restores it if conversion fails, so the study is never left without a
        valid XML file.

        Returns:
            True on success, False otherwise.
        """
        backup_path = self.xml_path + ".bak"
        try:
            if os.path.exists(self.xml_path):
                os.rename(self.xml_path, backup_path)
                print(f"[OK] Backed up existing XML: {backup_path}")

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
                if os.path.exists(backup_path):
                    os.rename(backup_path, self.xml_path)
                    print(f"[OK] Restored original XML: {self.xml_path}")
                return False

            if os.path.exists(backup_path):
                os.remove(backup_path)

            print(f"[OK] Regenerated XML: {self.xml_path}")
            return True
        except Exception as exc:
            print(f"[FAIL] {exc}")
            if os.path.exists(backup_path) and not os.path.exists(self.xml_path):
                os.rename(backup_path, self.xml_path)
                print(f"[OK] Restored original XML: {self.xml_path}")
            return False

    def _discover_report_class_lang_id(self) -> int:
        """Resolve the lang id for the Report class from t_class."""
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT lang_id, name FROM t_class "
                "WHERE lower(name) = 'report' ORDER BY class_id LIMIT 1"
            ).fetchone()
        if not row:
            raise ValueError(
                "Could not auto-detect Report class lang id from model. "
                "Ensure the model contains a 'Report' class in t_class."
            )
        lang_id, class_name = row
        print(f"[OK] Report class: '{class_name}' (lang_id={lang_id})")
        return int(lang_id)

    def _discover_reporting_lang_ids_by_name(self, property_names: list[str]) -> list[int]:
        """
        Resolve reporting property lang ids from t_property_report by name (case-insensitive).

        Raises ValueError if any name produces no match.
        """
        result: list[int] = []
        with sqlite3.connect(self.db_path) as con:
            for name in property_names:
                row = con.execute(
                    "SELECT lang_id, name FROM t_property_report "
                    "WHERE lower(name) = lower(?) ORDER BY property_id LIMIT 1",
                    (name,),
                ).fetchone()
                if not row:
                    raise ValueError(
                        f"Reporting property '{name}' not found in t_property_report. "
                        "Check the property name against the model."
                    )
                lang_id, matched_name = row
                print(f"[OK] Reporting property: '{matched_name}' (lang_id={lang_id})")
                result.append(int(lang_id))
        return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extend a PLEXOS model report with additional reporting properties.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n\n"
            "  Extend a report with multiple properties:\n"
            "    python3 enable_reports.py"
            " --report-object-name Generators"
            " --reporting-property-names 'Emissions by Generator,Fuel Offtake by Generator'\n\n"
            "  Include sample and statistics output:\n"
            "    python3 enable_reports.py"
            " --report-object-name Generators"
            " --reporting-property-names 'Emissions by Generator'"
            " --phase LT --report-samples true --report-statistics true"
        ),
    )
    parser.add_argument(
        "--report-object-name",
        required=True,
        type=non_empty_text,
        help="Name of the existing Report object in the model. Supports URL-encoding (e.g. My%%20Report).",
    )
    parser.add_argument(
        "--reporting-property-names",
        required=True,
        type=parse_name_list,
        help="Comma-separated reporting property names to enable (e.g. 'Emissions by Generator,Fuel Offtake by Generator'). Names are looked up case-insensitively in t_property_report.",
    )
    parser.add_argument(
        "--phase",
        type=phase_name,
        default="LT",
        help="Simulation phase for report configuration: ST (1), MT (2), PASA (3), LT (4) (default: LT).",
    )
    parser.add_argument(
        "--report-period",
        type=str_to_bool,
        default=True,
        help="Enable period output (default: true).",
    )
    parser.add_argument(
        "--report-samples",
        type=str_to_bool,
        default=False,
        help="Enable sample output (default: false).",
    )
    parser.add_argument(
        "--report-statistics",
        type=str_to_bool,
        default=False,
        help="Enable statistics output (default: false).",
    )
    parser.add_argument(
        "--report-summary",
        type=str_to_bool,
        default=True,
        help="Enable summary output (default: true).",
    )
    parser.add_argument(
        "--write-flat-files",
        type=str_to_bool,
        default=False,
        help="Enable flat-file output (default: false).",
    )

    print(f"\n[OK] Received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    args.report_object_name = _decode_value(args.report_object_name)
    phase_id = PHASE_MAP[args.phase]
    print(f"[OK] Interpreted: {args} -> phase_id={phase_id}\n")

    extender = ReportExtender(
        cli_path=CLOUD_CLI_PATH,
        simulation_path=SIMULATION_PATH,
        study_id=STUDY_ID,
    )
    success = extender.extend(
        report_object_name=args.report_object_name,
        reporting_property_names=args.reporting_property_names,
        phase_id=phase_id,
        report_period=args.report_period,
        report_samples=args.report_samples,
        report_statistics=args.report_statistics,
        report_summary=args.report_summary,
        write_flat_files=args.write_flat_files,
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
