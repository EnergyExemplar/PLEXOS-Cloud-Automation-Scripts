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
    
    def process_diagnostics(
        self, 
        model_name: str, 
        remote_base_path: str,
        execution_id: str,
        simulation_id: str,
        pattern: str = "**/*Diagnostics.xml",
        keep_files: bool = False
    ) -> bool:
        """
        Download diagnostics XMLs, compress them into a ZIP, and re-upload.
        
        This method performs three steps:
        1. Downloads XML files from Datahub matching the glob pattern
        2. Creates a ZIP archive containing all downloaded files
        3. Uploads the ZIP archive back to Datahub
        4. Optionally removes downloaded XMLs so they are not uploaded as separate artifacts
        
        Args:
            model_name: Name of the PLEXOS model
            remote_base_path: Base path in Datahub (e.g., "Project/Study")
            execution_id: Execution identifier for remote path construction
            simulation_id: Simulation identifier for remote path construction
            pattern: Glob pattern for diagnostics files (default: **/*Diagnostics.xml)
            keep_files: If False (default), remove downloaded XMLs after successful upload
            
        Returns:
            True if all steps completed successfully, False otherwise
            
        Raises:
            ValueError: If execution_id or simulation_id is empty or None
            RuntimeError: If download fails or no files matched the pattern
        """
        if not execution_id:
            raise ValueError("execution_id is required for remote path construction")
        if not simulation_id:
            raise ValueError("simulation_id is required for remote path construction")
        
        # Step 1: Define the remote glob pattern for diagnostics
        # Match the same path structure as extract_diag_xml.py
        remote_glob_pattern = (
            f"{remote_base_path}/{model_name}/{execution_id}/diagnostics/{simulation_id}/{pattern}"
        )
        
        print(f"\n--- Step 1: Downloading Diagnostics ---")
        print(f"Remote pattern: {remote_glob_pattern}")
        print(f"Output directory: {self.output_path}")
        
        # Download diagnostics XML files from Datahub
        download_response = self.sdk.datahub.download(
            remote_glob_patterns=[remote_glob_pattern],
            output_directory=str(self.output_path),
            print_message=False
        )
        download_final = SDKBase.get_response_data(download_response)
        
        if not download_final:
            raise RuntimeError(
                "Failed to download diagnostics XML files: no response data returned."
            )
        
        if not hasattr(download_final, "DatahubResourceResults"):
            raise RuntimeError(
                "Failed to download diagnostics XML files: unexpected response structure (missing DatahubResourceResults)."
            )
        
        if not download_final.DatahubResourceResults:
            raise RuntimeError(
                "Failed to download diagnostics XML files or no files matched the glob pattern."
            )
        
        # Extract downloaded file paths and log any failures
        downloaded_files: List[str] = []
        failed_downloads = []
        
        for result in download_final.DatahubResourceResults:
            if result.Success:
                downloaded_files.append(result.LocalFilePath)
            else:
                failed_downloads.append((result.RelativeFilePath, result.FailureReason or "Unknown error"))
        
        if failed_downloads:
            print(f"[WARN] {len(failed_downloads)} file(s) failed to download:")
            for path, reason in failed_downloads:
                print(f"        {path}: {reason}")
        
        if not downloaded_files:
            raise RuntimeError("No diagnostics XML files were successfully downloaded.")
        
        print(f"[OK] Downloaded {len(downloaded_files)} file(s)")
        
        # Step 2: Create a ZIP file containing all downloaded diagnostics
        zip_filename = f"{model_name}_diagnostics.zip"
        zip_file_path = self.output_path / zip_filename
        
        print(f"\n--- Step 2: Creating ZIP Archive ---")
        print(f"Archive: {zip_file_path}")
        
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
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
        
        # Step 3: Upload the ZIP file back to Datahub
        # Match the same path structure as extract_diag_xml.py
        remote_zip_folder = (
            f"{remote_base_path}/{model_name}/{execution_id}/diagnostics/{simulation_id}"
        )
        
        print(f"\n--- Step 3: Uploading ZIP to Datahub ---")
        print(f"Remote folder: {remote_zip_folder}")
        print(f"File: {zip_filename}")
        
        upload_response = self.sdk.datahub.upload(
            local_folder=str(self.output_path),
            remote_folder=remote_zip_folder,
            glob_patterns=[zip_filename],
            is_versioned=False,
            print_message=False
        )
        upload_final = SDKBase.get_response_data(upload_response)
        
        if not upload_final:
            print("[FAIL] Upload failed: no response data returned")
            return False
        
        if not hasattr(upload_final, "DatahubResourceResults"):
            print("[FAIL] Upload failed: unexpected response structure (missing DatahubResourceResults)")
            return False
        
        if not upload_final.DatahubResourceResults:
            print("[FAIL] Upload failed: no resources returned in response")
            return False
        
        # Check upload results
        successful = []
        skipped = []
        failed = []
        
        for result in upload_final.DatahubResourceResults:
            if result.Success:
                successful.append(result.RelativeFilePath)
            elif result.FailureReason and "identical to the remote file" in result.FailureReason:
                skipped.append(result.RelativeFilePath)
            else:
                failed.append((result.RelativeFilePath, result.FailureReason or "Unknown error"))
        
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
        
        # Remove downloaded XMLs unless --keep-files; they would otherwise be uploaded as separate artifacts
        if not keep_files:
            for file_path in downloaded_files:
                Path(file_path).unlink(missing_ok=True)
            print("[OK] Removed downloaded XML files (use --keep-files to retain them)")
        
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
        default="Project/Study",
        help="Base path in Datahub (default: Project/Study). The script appends /{model_name}/{execution_id}/diagnostics/{simulation_id} automatically."
    )
    parser.add_argument(
        "-pt", "--pattern",
        default="**/*Diagnostics.xml",
        help="Glob pattern for diagnostics files (default: **/*Diagnostics.xml)"
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep downloaded XML files after creating ZIP (default: remove them to avoid duplicate artifacts)"
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
