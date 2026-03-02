"""
Download files from DataHub to local directory.

This script can be run standalone OR imported by other automation scripts.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
from eecloud.cloudsdk import CloudSDK, SDKBase


class DataHubDownloader:
    """Reusable DataHub downloader for automation scripts."""
    
    def __init__(self, cli_path: str, environment: str):
        """
        Initialize DataHub downloader.
        
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
            print(f"❌ Failed to authenticate: {ex}")
            raise
    
    def download_file(self, datahub_path: str, local_dir: Path) -> Path:
        """
        Download file from DataHub to local directory.
        
        Args:
            datahub_path: Path in DataHub (e.g. 'Project/Study/file.csv')
            local_dir: Local directory to download to
            
        Returns:
            Path to downloaded file
        """
        self.authenticate()
        
        try:
            local_dir = Path(local_dir)
            local_dir.mkdir(parents=True, exist_ok=True)

            print(f"[DOWNLOAD] {datahub_path} → {local_dir}")

            response = self.sdk.datahub.download(
                remote_glob_patterns=[datahub_path],
                output_directory=str(local_dir),
                print_message=False
            )

            data = SDKBase.get_response_data(response)

            if data is None or not hasattr(data, "DatahubResourceResults"):
                raise RuntimeError(
                    f"SDK returned no DatahubResourceResults for: {datahub_path}. "
                    f"Verify the path exists in DataHub."
                )

            downloaded = []
            failed = []
            for result in data.DatahubResourceResults:
                if result.Success:
                    downloaded.append((result.RelativeFilePath, Path(result.LocalFilePath)))
                else:
                    reason = result.FailureReason or "unknown"
                    failed.append((result.RelativeFilePath, reason))

            if failed:
                for path, reason in failed:
                    print(f"[FAIL] {path}: {reason}")

            if not downloaded:
                raise FileNotFoundError(f"No files downloaded for: {datahub_path}")

            for rel_path, local_file in downloaded:
                print(f"[OK] Downloaded: {rel_path} → {local_file} ({local_file.stat().st_size:,} bytes)")

            local_paths = [local for _, local in downloaded]
            return local_paths[0] if len(local_paths) == 1 else local_dir

        except Exception as ex:
            print(f"[FAIL] Failed to download {datahub_path}: {ex}")
            raise


def main() -> int:
    """
    Main entry point for command-line usage.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Download files from DataHub to local directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Download single file
  python download_from_datahub.py -c /usr/local/bin/plexos-cloud -e prod \\
    -f Project/Study/input.csv -o ./downloads

  # Download multiple files
  python download_from_datahub.py -c /usr/local/bin/plexos-cloud -e prod \\
    -f Project/Study/forecast.csv -f Project/Study/actual.csv \\
    -o ./downloads
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
        required=True,
        help='DataHub file path to download (can be specified multiple times)'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        required=True,
        help='Local output directory for downloaded files'
    )
    
    args = parser.parse_args()
    
    try:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[START] Downloading {len(args.files)} file(s) from DataHub")
        print(f"[OUTPUT] Local directory: {output_dir.absolute()}")
        
        downloader = DataHubDownloader(cli_path=args.cli_path, environment=args.environment)
        
        downloaded = []
        failed = []
        
        for datahub_path in args.files:
            try:
                local_path = downloader.download_file(datahub_path, output_dir)
                downloaded.append(str(local_path))
            except Exception as ex:
                print(f"[ERROR] Failed to download {datahub_path}: {ex}")
                failed.append(datahub_path)
        
        print(f"\n{'='*60}")
        print(f"[SUMMARY] Downloaded: {len(downloaded)}/{len(args.files)} file(s)")
        
        if downloaded:
            print(f"\n[SUCCESS] Downloaded files:")
            for path in downloaded:
                print(f"  - {path}")
        
        if failed:
            print(f"\n[FAILED] Failed to download:")
            for path in failed:
                print(f"  - {path}")
            return 1
        
        print(f"{'='*60}\n")
        return 0
        
    except Exception as ex:
        print(f"\n❌ FATAL ERROR: {ex}")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
