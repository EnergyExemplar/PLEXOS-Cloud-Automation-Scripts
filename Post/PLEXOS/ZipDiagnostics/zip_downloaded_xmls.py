"""
Download, compress, and re-upload PLEXOS diagnostics XML files.

Focused script — archive only. Downloads diagnostics XML files from Datahub,
compresses them into a single ZIP archive, and uploads the archive back.

Model name for path construction is read from directory mapping JSON.
Chain with extract_diag_xml.py to first upload XMLs, then archive them.

Environment variables used:
    cloud_cli_path     – Path to the Cloud CLI binary
    execution_id       – Execution identifier for remote path construction
    simulation_id      – Simulation identifier for remote path construction
    directory_map_path – Path to directory mapping JSON (optional; falls back to 
                         /simulation/splits/directorymapping.json for distributed runs)
    output_path        – Working directory (default: /output)
"""
import argparse
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import List
from urllib.parse import unquote

from eecloud.cloudsdk import CloudSDK, SDKBase


# Required env vars — fail fast with a clear message
try:
    CLOUD_CLI_PATH = os.environ["cloud_cli_path"]
except KeyError:
    print("[FAIL] Missing required environment variable: cloud_cli_path")
    sys.exit(1)

try:
    EXECUTION_ID = os.environ["execution_id"]
except KeyError:
    print("[FAIL] Missing required environment variable: execution_id")
    sys.exit(1)

try:
    SIMULATION_ID = os.environ["simulation_id"]
except KeyError:
    print("[FAIL] Missing required environment variable: simulation_id")
    sys.exit(1)

# Optional env vars — use sensible defaults
OUTPUT_PATH = os.environ.get("output_path", "/output")
DIRECTORY_MAP_PATH = os.environ.get("directory_map_path", "")


# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION \u2014 These defaults are used when no command-line arguments are provided.
# ═══════════════════════════════════════════════════════════════════════════════

# Base path in DataHub (model/execution/diagnostics/simulation appended)
# Example: "Project/Study"
REMOTE_BASE_PATH = "Project/Study"

# Glob pattern for diagnostics files
# Example: "**/*ST*Diagnostics.xml" for ST phase only
DIAGNOSTICS_PATTERN = "**/*Diagnostics.xml"

# Keep downloaded XML files after creating ZIP
KEEP_FILES = False

# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════


def _decode_path(value: str) -> str:
    """Strip surrounding quotes left by a non-shell task runner, then URL-decode."""
    return unquote(value.strip('\'"'))


def _resolve_mapping_file(env_path: str) -> Path:
    """
    Resolve the directory mapping JSON file path.
    
    Uses env_path if set and file exists, then falls back to 
    /simulation/splits/directorymapping.json for distributed runs.
    
    Args:
        env_path: Value of directory_map_path env var (may be empty).
        
    Returns:
        Resolved Path to an existing mapping file.
        
    Raises:
        FileNotFoundError: If neither path exists.
    """
    # Check env var path first
    if env_path:
        env_mapping_path = Path(env_path)
        if env_mapping_path.exists():
            return env_mapping_path
    
    # Fall back to distributed run location
    split_mapping_path = Path("/simulation/splits/directorymapping.json")
    if split_mapping_path.exists():
        return split_mapping_path
    
    raise FileNotFoundError(
        f"Mapping file not found. Checked: "
        f"{env_path or '[directory_map_path not set]'} and {split_mapping_path}"
    )


def _get_model_name_from_mapping(env_path: str) -> str:
    """
    Read model name (Name) from directory mapping JSON.
    
    Resolves the mapping file, then returns the Name of the first entry 
    that has a ParquetPath field. This is the human-readable model name 
    used in remote paths.
    
    Args:
        env_path: Value of directory_map_path env var (may be empty).
        
    Returns:
        Model name (Name) for path construction.
        
    Raises:
        FileNotFoundError: If mapping file not found at either path.
        ValueError: If JSON is empty, malformed, or no entry with ParquetPath and Name.
    """
    mapping_path = _resolve_mapping_file(env_path)
    
    with mapping_path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in mapping file: {exc}") from exc
    
    if not isinstance(data, list) or not data:
        raise ValueError("Mapping JSON must be a non-empty list")
    
    # Find first entry with ParquetPath (identifies the model/split entry)
    for item in data:
        if not isinstance(item, dict):
            continue
        if "ParquetPath" not in item:
            continue
        
        model_name = str(item.get("Name", "")).strip()
        if not model_name:
            raise ValueError(
                "Mapping entry with 'ParquetPath' is missing a non-empty 'Name' field. "
                "'Name' is required for path construction."
            )
        return model_name
    
    raise ValueError("No entry with 'ParquetPath' found in the directory mapping file.")


# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
DEFAULT_DIAGNOSTICS_PATTERN = "**/*Diagnostics.xml"
ZIP_COMPRESSION = zipfile.ZIP_DEFLATED


def _validate_datahub_response(response_data, operation: str):
    """Validate a Datahub SDK response and return the resource results.

    Both download and upload responses share the same structure. This helper
    removes the duplicated three-check validation pattern.

    Raises:
        RuntimeError: If the response is missing, malformed, or empty.
    """
    if not response_data:
        raise RuntimeError(f"Failed to {operation}: no response data returned.")
    if not hasattr(response_data, "DatahubResourceResults"):
        raise RuntimeError(
            f"Failed to {operation}: unexpected response structure "
            "(missing DatahubResourceResults)."
        )
    if not response_data.DatahubResourceResults:
        raise RuntimeError(
            f"Failed to {operation} or no files matched the pattern."
        )
    return response_data.DatahubResourceResults


class DiagnosticsZipper:
    """Handles downloading, compressing, and re-uploading diagnostics XML files."""
    
    def __init__(self, cli_path: str, output_path: str):
        """
        Initialize the DiagnosticsZipper.
        
        Args:
            cli_path: Path to the Cloud CLI binary
            output_path: Working directory for temporary files
        """
        self.sdk = CloudSDK(cli_path=cli_path)
        self.output_path = Path(output_path)
    
    def _download_diagnostics(self, remote_glob_pattern: str) -> List[str]:
        """Download diagnostics XML files from Datahub matching the glob pattern.

        Returns:
            List of local file paths for successfully downloaded files.

        Raises:
            RuntimeError: If download fails or no files were successfully downloaded.
        """
        print(f"\n--- Step 1: Downloading Diagnostics ---")
        print(f"Remote pattern: {remote_glob_pattern}")
        print(f"Output directory: {self.output_path}")

        download_response = self.sdk.datahub.download(
            remote_glob_patterns=[remote_glob_pattern],
            output_directory=str(self.output_path),
            print_message=False
        )
        download_final = SDKBase.get_response_data(download_response)
        results = _validate_datahub_response(download_final, "download diagnostics XML files")

        downloaded_files: List[str] = []
        failed_downloads = []

        for result in results:
            if result.Success:
                downloaded_files.append(result.LocalFilePath)
            else:
                failed_downloads.append(
                    (result.RelativeFilePath, result.FailureReason or "Unknown error")
                )

        if failed_downloads:
            print(f"[WARN] {len(failed_downloads)} file(s) failed to download:")
            for path, reason in failed_downloads:
                print(f"        {path}: {reason}")

        if not downloaded_files:
            raise RuntimeError("No diagnostics XML files were successfully downloaded.")

        print(f"[OK] Downloaded {len(downloaded_files)} file(s)")
        return downloaded_files

    def _create_zip_archive(self, downloaded_files: List[str], model_name: str) -> Path:
        """Create a ZIP archive containing all downloaded diagnostics files.

        Returns:
            Path to the created ZIP file.
        """
        zip_filename = f"{model_name}_diagnostics.zip"
        zip_file_path = self.output_path / zip_filename

        print(f"\n--- Step 2: Creating ZIP Archive ---")
        print(f"Archive: {zip_file_path}")

        with zipfile.ZipFile(zip_file_path, 'w', ZIP_COMPRESSION) as zipf:
            for file_path in downloaded_files:
                file_path_obj = Path(file_path)
                try:
                    rel = file_path_obj.relative_to(self.output_path)
                except ValueError:
                    raise RuntimeError(
                        f"Downloaded file is outside output path: {file_path}"
                    ) from None
                # Use forward slashes in ZIP for portability
                arcname = rel.as_posix()
                zipf.write(file_path, arcname=arcname)
                print(f"  Added: {arcname}")

        print(f"[OK] Created ZIP archive: {zip_filename}")
        return zip_file_path

    def _upload_zip_archive(self, zip_file_path: Path, remote_zip_folder: str) -> bool:
        """Upload the ZIP archive back to Datahub.

        Returns:
            True if upload succeeded, False otherwise.
        """
        zip_filename = zip_file_path.name

        print(f"\n--- Step 3: Uploading ZIP to Datahub ---")
        print(f"Remote folder: {remote_zip_folder}")
        print(f"File: {zip_filename}")

        upload_response = self.sdk.datahub.upload(
            local_folder=str(self.output_path),
            remote_folder=remote_zip_folder,
            glob_patterns=[zip_filename],
            # Non-versioned: diagnostics archives are overwritten each run
            is_versioned=False,
            print_message=False
        )
        upload_final = SDKBase.get_response_data(upload_response)

        try:
            results = _validate_datahub_response(upload_final, "upload ZIP archive")
        except RuntimeError as e:
            print(f"[FAIL] {e}")
            return False

        successful = []
        skipped = []
        failed = []

        for result in results:
            if result.Success:
                successful.append(result.RelativeFilePath)
            elif result.FailureReason and "identical to the remote file" in result.FailureReason:
                skipped.append(result.RelativeFilePath)
            else:
                failed.append(
                    (result.RelativeFilePath, result.FailureReason or "Unknown error")
                )

        if failed:
            print(f"[FAIL] Upload failed for {len(failed)} file(s):")
            for path, reason in failed:
                print(f"        {path}: {reason}")
            return False

        print(f"[OK] Uploaded: {len(successful)} file(s)")
        if skipped:
            print(f"[OK] Skipped (identical to remote): {len(skipped)} file(s)")

        remote_path = f"{remote_zip_folder}/{zip_filename}"
        print(f"[OK] Successfully uploaded ZIP to: {remote_path}")
        return True

    @staticmethod
    def _cleanup_xml_files(downloaded_files: List[str], keep_files: bool) -> None:
        """Remove downloaded XML files unless *keep_files* is set.

        XMLs are removed so they are not uploaded as separate artifacts
        by any subsequent upload step.
        """
        if not keep_files:
            for file_path in downloaded_files:
                Path(file_path).unlink(missing_ok=True)
            print("[OK] Removed downloaded XML files (use --keep-files to retain them)")

    def process_diagnostics(
        self, 
        model_name: str, 
        remote_base_path: str,
        execution_id: str,
        simulation_id: str,
        pattern: str = DEFAULT_DIAGNOSTICS_PATTERN,
        keep_files: bool = False
    ) -> bool:
        """Download diagnostics XMLs, compress them into a ZIP, and re-upload.
        
        Orchestrates four steps:
        1. Download XML files from Datahub matching the glob pattern
        2. Create a ZIP archive containing all downloaded files
        3. Upload the ZIP archive back to Datahub
        4. Remove downloaded XMLs (unless *keep_files* is True)
        
        Args:
            model_name: Name of the PLEXOS model
            remote_base_path: Base path in Datahub (e.g., "Project/Study")
            execution_id: Execution identifier for remote path construction
            simulation_id: Simulation identifier for remote path construction
            pattern: Glob pattern for diagnostics files
            keep_files: If False (default), remove downloaded XMLs after upload
            
        Returns:
            True if all steps completed successfully, False otherwise
        """
        if not execution_id:
            raise ValueError("execution_id is required for remote path construction")
        if not simulation_id:
            raise ValueError("simulation_id is required for remote path construction")

        remote_base = f"{remote_base_path}/{model_name}/{execution_id}/diagnostics/{simulation_id}"
        remote_glob_pattern = f"{remote_base}/{pattern}"

        # Step 1: Download XML files
        downloaded_files = self._download_diagnostics(remote_glob_pattern)

        # Step 2: Compress into ZIP
        zip_file_path = self._create_zip_archive(downloaded_files, model_name)

        # Step 3: Upload ZIP back to Datahub
        if not self._upload_zip_archive(zip_file_path, remote_base):
            return False

        # Step 4: Cleanup (remove XMLs unless --keep-files)
        self._cleanup_xml_files(downloaded_files, keep_files)

        return True


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Download, compress, and re-upload PLEXOS diagnostics XML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download, ZIP, and upload diagnostics (model name from directory mapping)
  python3 zip_downloaded_xmls.py -r Project/Study

  # Use custom pattern to get only ST diagnostics
  python3 zip_downloaded_xmls.py -r Project/Study -pt "**/*ST*Diagnostics.xml"
  
  # Full workflow in task configuration:
  # 1. Run simulation
  # 2. Extract diagnostics (extract_diag_xml.py)
  # 3. Archive diagnostics (this script)
        """
    )
    parser.add_argument(
        "-r", "--remote-base-path",
        default=REMOTE_BASE_PATH,
        help=f"Base path in Datahub (default: {REMOTE_BASE_PATH}). The script appends /{{model_name}}/{{execution_id}}/diagnostics/{{simulation_id}} automatically."
    )
    parser.add_argument(
        "-pt", "--pattern",
        default=DIAGNOSTICS_PATTERN,
        help=f"Glob pattern for diagnostics files (default: {DIAGNOSTICS_PATTERN})"
    )
    parser.add_argument(
        "--keep-files",
        action=argparse.BooleanOptionalAction,
        default=KEEP_FILES,
        help=f"Keep downloaded XML files after creating ZIP (default: {KEEP_FILES})"
    )
    
    print(f"\n[OK] Args received: python3 {' '.join(sys.argv)}")
    args = parser.parse_args()
    remote_base_path = _decode_path(args.remote_base_path)
    
    # Read model name from directory mapping
    try:
        model_name = _get_model_name_from_mapping(DIRECTORY_MAP_PATH)
    except (FileNotFoundError, ValueError) as e:
        print(f"[FAIL] {e}")
        return 1
    
    print(f"[OK] Args interpreted: remote_base_path={remote_base_path!r}, pattern={args.pattern!r}, keep_files={args.keep_files}, model_name(from mapping)={model_name!r}\n")
    
    try:
        zipper = DiagnosticsZipper(CLOUD_CLI_PATH, OUTPUT_PATH)
        success = zipper.process_diagnostics(
            model_name, 
            remote_base_path,
            EXECUTION_ID,
            SIMULATION_ID,
            args.pattern,
            keep_files=args.keep_files
        )
        
        if success:
            print(f"\n{'='*60}")
            print("[OK] All steps completed successfully")
            print(f"{'='*60}\n")
            return 0
        else:
            print(f"\n{'='*60}")
            print("[FAIL] Process failed")
            print(f"{'='*60}\n")
            return 1
            
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"[FAIL] {e}")
        print(f"{'='*60}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
