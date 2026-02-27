"""
Upload files from local directory to DataHub.

This script can be run standalone OR imported by other automation scripts.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
from eecloud.cloudsdk import CloudSDK, SDKBase


class DataHubUploader:
    """Reusable DataHub uploader for automation scripts."""
    
    def __init__(self, cli_path: str, environment: str):
        """
        Initialize DataHub uploader.
        
        Args:
            cli_path: Full path to PLEXOS Cloud CLI executable
            environment: Cloud environment name
        """
        self.cli_path = cli_path
        self.environment = environment
        self.sdk = CloudSDK(cli_path=self.cli_path)
        self._authenticated = False
    
    def authenticate(self) -> None:
        """Authenticate with the specified environment."""
        if self._authenticated:
            return
        
        try:
            print(f"[ENV] Setting cloud environment: {self.environment}")
            env_response = self.sdk.environment.set_user_environment(self.environment)
            env_data = SDKBase.get_response_data(env_response)
            print(f"[OK] Selected Environment: {env_data.Environment}")
            
            print(f"[AUTH] Logging in...")
            login_response = self.sdk.auth.login()
            login_data = SDKBase.get_response_data(login_response)
            print(f"[OK] Tenant: {login_data.TenantName}, User: {login_data.UserName}")
            
            self._authenticated = True
            
        except Exception as ex:
            print(f"[FAIL] Failed to authenticate: {ex}")
            raise
    
    def upload_file(self, local_path: Path, datahub_path: str, overwrite: bool = True) -> None:
        """
        Upload file from local path to DataHub.
        
        Args:
            local_path: Path to local file
            datahub_path: Target path in DataHub (e.g. 'Project/Study/Results/')
            overwrite: Whether to overwrite existing files
        """
        self.authenticate()
        
        try:
            local_path = Path(local_path)
            if not local_path.exists():
                raise FileNotFoundError(f"Local file not found: {local_path}")
            
            print(f"[UPLOAD] {local_path} → {datahub_path}")
            
            responses = self.sdk.datahub.upload(
                local_folder=str(local_path.parent),
                remote_folder=datahub_path,
                glob_patterns=[local_path.name]
            )
            
            if not isinstance(responses, list):
                responses = [responses]
            SDKBase.get_response_data(responses)
            print(f"[OK] Uploaded: {datahub_path}/{local_path.name}")
            
        except Exception as ex:
            print(f"[FAIL] Failed to upload {local_path}: {ex}")
            raise
    
    def upload_directory(self, local_dir: Path, datahub_path: str, 
                        pattern: str = "*", overwrite: bool = True) -> int:
        """
        Upload all files matching pattern from local directory to DataHub.
        
        Args:
            local_dir: Path to local directory
            datahub_path: Target directory in DataHub
            pattern: Glob pattern for files to upload
            overwrite: Whether to overwrite existing files
            
        Returns:
            Number of files uploaded
        """
        self.authenticate()
        
        try:
            local_dir = Path(local_dir)
            if not local_dir.is_dir():
                raise NotADirectoryError(f"Not a directory: {local_dir}")

            print(f"[UPLOAD] {local_dir} → {datahub_path} (pattern: {pattern})")

            responses = self.sdk.datahub.upload(
                local_folder=str(local_dir),
                remote_folder=datahub_path,
                glob_patterns=[pattern]
            )

            if not isinstance(responses, list):
                responses = [responses]
            results = SDKBase.get_response_data(responses)
            count = len(results) if isinstance(results, list) else 1
            print(f"[OK] Uploaded {count} file(s) to {datahub_path}")
            return count

        except Exception as ex:
            print(f"[FAIL] Failed to upload directory {local_dir}: {ex}")
            raise


def main() -> int:
    """
    Main entry point for command-line usage.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Upload files from local directory to DataHub',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Upload single file
  python upload_to_datahub.py -c /usr/local/bin/plexos-cloud -e prod \\
    -f ./results/output.csv -d Project/Study/Results

  # Upload multiple files
  python upload_to_datahub.py -c /usr/local/bin/plexos-cloud -e prod \\
    -f ./output1.csv -f ./output2.parquet \\
    -d Project/Study/Results

  # Upload entire directory
  python upload_to_datahub.py -c /usr/local/bin/plexos-cloud -e prod \\
    --directory ./results \\
    -d Project/Study/Results \\
    --pattern "*.csv"
        '''
    )
    
    parser.add_argument(
        '-c', '--cli-path',
        required=True,
        help='Full path to PLEXOS Cloud CLI executable'
    )
    
    parser.add_argument(
        '-e', '--environment',
        required=True,
        help='Cloud environment name (contact your Energy Exemplar administrator)'
    )
    
    parser.add_argument(
        '-f', '--file',
        action='append',
        dest='files',
        help='Local file path to upload (can be specified multiple times)'
    )
    
    parser.add_argument(
        '--directory',
        help='Upload all files from this directory (use with --pattern)'
    )
    
    parser.add_argument(
        '--pattern',
        default='**/*',
        help='Glob pattern for files to upload from directory (default: "**/*")'
    )
    
    parser.add_argument(
        '-d', '--datahub-path',
        required=True,
        help='Target DataHub directory path (e.g., Project/Study/Results)'
    )
    
    parser.add_argument(
        '--no-overwrite',
        action='store_true',
        help='Do not overwrite existing files in DataHub'
    )
    
    args = parser.parse_args()
    
    if not args.files and not args.directory:
        print("[ERROR] Must specify either --file or --directory")
        return 1
    
    try:
        print(f"[START] Uploading files to DataHub")
        print(f"[TARGET] DataHub path: {args.datahub_path}")
        
        uploader = DataHubUploader(cli_path=args.cli_path, environment=args.environment)
        
        uploaded = []
        failed = []
        
        if args.files:
            print(f"\n[FILES] Uploading {len(args.files)} specified file(s)")
            for file_path in args.files:
                try:
                    local_path = Path(file_path)
                    if not local_path.exists():
                        print(f"[SKIP] File not found: {file_path}")
                        failed.append(file_path)
                        continue
                    
                    uploader.upload_file(
                        local_path=local_path,
                        datahub_path=args.datahub_path,
                        overwrite=not args.no_overwrite
                    )
                    uploaded.append(str(local_path))
                    
                except Exception as ex:
                    print(f"[ERROR] Failed to upload {file_path}: {ex}")
                    failed.append(file_path)
        
        if args.directory:
            print(f"\n[DIRECTORY] Uploading from: {args.directory}")
            print(f"[PATTERN] Matching files: {args.pattern}")
            
            try:
                count = uploader.upload_directory(
                    local_dir=Path(args.directory),
                    datahub_path=args.datahub_path,
                    pattern=args.pattern,
                    overwrite=not args.no_overwrite
                )
                print(f"[OK] Uploaded {count} file(s) from directory")
                
            except Exception as ex:
                print(f"[ERROR] Failed to upload directory: {ex}")
                return 1
        
        print(f"\n{'='*60}")
        if args.files:
            print(f"[SUMMARY] Uploaded: {len(uploaded)}/{len(args.files)} file(s)")
            
            if uploaded:
                print(f"\n[SUCCESS] Uploaded files:")
                for path in uploaded:
                    print(f"  - {path}")
            
            if failed:
                print(f"\n[FAILED] Failed to upload:")
                for path in failed:
                    print(f"  - {path}")
                return 1
        
        print(f"{'='*60}\n")
        return 0
        
    except Exception as ex:
        print(f"\n[FATAL] {ex}")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
