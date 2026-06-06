"""
Download one or more files from a Datahub folder deep link using raw HTTP.

No CloudSDK or CLI required — uses the requests library directly.
Accepts a deep link URL, signature, and a list of internal file paths.
Each file is downloaded individually via GET with the X-DeepLink-Signature header.
"""
import argparse
import os
import sys
from urllib.parse import quote

import requests


class DeepLinkBatchDownloader:
    """Downloads files from a Datahub deep link via raw HTTP requests.

    Useful for downloading multiple files from a folder-type deep link
    without requiring the CloudSDK or CLI executable.
    """

    def __init__(self, download_url: str, signature: str, output_dir: str):
        """
        Args:
            download_url: The full deep link download URL.
            signature: The X-DeepLink-Signature value from deep link creation.
            output_dir: Local directory to save downloaded files.
        """
        self.download_url = download_url.rstrip("&").rstrip("?")
        self.signature = signature
        self.output_dir = output_dir

    def download(self, file_paths: list[str]) -> bool:
        """
        Download a list of files from the deep link.

        Args:
            file_paths: List of internal file paths relative to the shared folder.

        Returns:
            True if all files downloaded successfully, False if any failed.
        """
        os.makedirs(self.output_dir, exist_ok=True)

        headers = {"X-DeepLink-Signature": self.signature}
        separator = "&" if "?" in self.download_url else "?"

        succeeded = 0
        failed = 0

        for file_path in file_paths:
            # Reject path traversal attempts
            if ".." in file_path or file_path.startswith("/") or file_path.startswith("\\"):
                print(f"[FAIL] {file_path} — rejected: path must be relative without '..'")
                failed += 1
                continue

            encoded_path = quote(file_path, safe="")
            url = f"{self.download_url}{separator}InternalFilePath={encoded_path}"

            try:
                response = requests.get(url, headers=headers, timeout=300, stream=True)
            except requests.RequestException as e:
                print(f"[FAIL] {file_path} — request error: {e}")
                failed += 1
                continue

            if response.ok:
                # Preserve folder structure under output_dir
                dest = os.path.join(self.output_dir, file_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                size = 0
                with open(dest, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        size += len(chunk)
                print(f"[OK] Downloaded: {file_path} ({size:,} bytes)")
                succeeded += 1
            else:
                print(f"[FAIL] {file_path} — HTTP {response.status_code}: {response.text}")
                failed += 1

        print(f"\n[OK] {succeeded} succeeded, {failed} failed out of {len(file_paths)} file(s).")
        return failed == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download files from a Datahub folder deep link via raw HTTP.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Download a single file\n"
            "  python deep_link_http_download.py \\\n"
            '    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/..." \\\n'
            '    --signature "PQDxyzI+XVy..." \\\n'
            '    --output-dir ./downloads \\\n'
            '    --files "SOLUTION_DATA/result.parquet"\n'
            "\n"
            "  # Download multiple files\n"
            "  python deep_link_http_download.py \\\n"
            '    --url "https://datahub-api-eeprod-na.energyexemplar.com/1.0/deeplink/..." \\\n'
            '    --signature "PQDxyzI+XVy..." \\\n'
            '    --output-dir ./downloads \\\n'
            '    --files "SOLUTION_DATA/file1.parquet" "SOLUTION_DATA/file2.parquet"\n'
        ),
    )
    parser.add_argument("--url", required=True, help="The full deep link download URL")
    parser.add_argument("--signature", required=True, help="The X-DeepLink-Signature value")
    parser.add_argument("--output-dir", required=True, help="Local directory to save downloaded files")
    parser.add_argument(
        "--files",
        required=True,
        nargs="+",
        help="One or more internal file paths to download from the deep link folder",
    )

    args = parser.parse_args()

    try:
        downloader = DeepLinkBatchDownloader(
            download_url=args.url,
            signature=args.signature,
            output_dir=args.output_dir,
        )
        success = downloader.download(args.files)
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())





