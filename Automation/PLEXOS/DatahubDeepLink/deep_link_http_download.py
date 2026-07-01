"""
Browse and download Datahub deep links using raw HTTP (no authentication needed).

Subcommands:
    browse    List files inside a folder deep link via raw HTTP/urllib
    download  Download one or more files from a folder deep link via raw HTTP

Note: To create deep links, use datahub_deep_link.py which handles authenticated creation via SDK.
"""
import argparse
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import requests

_WINDOWS_DRIVE_PATH = re.compile(r'^[a-zA-Z]:[/\\]')
_PATH_TRAVERSAL = re.compile(r'(^|[/\\])\.\.([$\/\\]|$)')


class DeepLinkBrowser:
    """Lists files inside a Datahub folder deep link via raw HTTP/urllib requests."""

    # Replaces /download/ segment with /browse/ so users can pass either URL
    _DOWNLOAD_TO_BROWSE = re.compile(
        r"(/deeplink/[0-9a-fA-F\-]{32,36}/)download(/|\?|$)"
    )

    def __init__(self, url: str, signature: str):
        """
        Args:
            url:       The full deep link URL (download or browse URL from creation).
            signature: The X-DeepLink-Signature value from deep link creation.
        """
        # Normalise to the /browse/ endpoint
        self.browse_url = self._DOWNLOAD_TO_BROWSE.sub(r"\1browse\2", url.rstrip("&").rstrip("?"))
        self.signature = signature

    def browse(self, file_path: str | None = None) -> bool:
        """
        List files at the root of the shared folder, or inside a subfolder.

        Args:
            file_path: Optional subfolder path within the shared folder to list.

        Returns:
            True if the listing was retrieved successfully, False otherwise.
        """
        url = self.browse_url
        if file_path:
            # Reject path traversal and absolute paths (Unix, Windows UNC, and drive-letter)
            if (_PATH_TRAVERSAL.search(file_path)
                    or file_path.startswith("/")
                    or file_path.startswith("\\")
                    or _WINDOWS_DRIVE_PATH.match(file_path)):
                print("[FAIL] Rejected file-path: path must be relative without '..'")
                return False
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}InternalFilePath={quote(file_path, safe='')}"

        headers = {"X-DeepLink-Signature": self.signature}
        try:
            request = Request(url, headers=headers, method="GET")
            with urlopen(request, timeout=60) as response:
                response_body = response.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
            print(f"[FAIL] HTTP {e.code}: {body}")
            return False
        except URLError as e:
            print(f"[FAIL] Request error: {e}")
            return False

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as e:
            print(f"[FAIL] Could not parse response JSON: {e}")
            return False

        resources = data.get("Resources") or data.get("resources") or []
        if not resources:
            print("No files found.")
            return True

        # Sort by lastModifiedAtUtc descending (latest files first)
        resources = sorted(resources, key=lambda r: r.get("lastModifiedAtUtc") or "", reverse=True)

        # Print formatted table
        print(f"{'Size':>15}  {'Last Modified':<24}  Path")
        print(f"{'-'*15}  {'-'*24}  {'-'*40}")
        for r in resources:
            # File size is nested in versions[0] if it exists, otherwise None
            versions = r.get("versions") or []
            file_size = versions[0].get("fileSize") if versions else None
            size_str = f"{file_size:,} B" if file_size is not None else "-"
            modified = (r.get("lastModifiedAtUtc") or "")[:19].replace("T", " ")
            path = r.get("relativePath") or ""
            print(f"{size_str:>15}  {modified:<24}  {path}")

        print(f"\n[OK] {len(resources)} resource(s) listed.")
        return True





class DeepLinkBatchDownloader:
    """Downloads files from a Datahub deep link via raw HTTP requests."""

    def __init__(self, download_url: str, signature: str, output_dir: str):
        self.download_url = download_url.rstrip("&").rstrip("?")
        self.signature = signature
        self.output_dir = output_dir

    def download(self, file_paths: list[str]) -> bool:
        os.makedirs(self.output_dir, exist_ok=True)

        headers = {"X-DeepLink-Signature": self.signature}
        separator = "&" if "?" in self.download_url else "?"

        succeeded = 0
        failed = 0

        for file_path in file_paths:
            if (_PATH_TRAVERSAL.search(file_path)
                    or file_path.startswith("/")
                    or file_path.startswith("\\")
                    or _WINDOWS_DRIVE_PATH.match(file_path)):
                print(f"[FAIL] {file_path} - rejected: path must be relative without '..'")
                failed += 1
                continue

            encoded_path = quote(file_path, safe="")
            url = f"{self.download_url}{separator}InternalFilePath={encoded_path}"

            try:
                response = requests.get(url, headers=headers, timeout=300, stream=True)
            except requests.RequestException as e:
                print(f"[FAIL] {file_path} - request error: {e}")
                failed += 1
                continue

            if response.ok:
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
                print(f"[FAIL] {file_path} - HTTP {response.status_code}: {response.text}")
                failed += 1

        print(f"\n[OK] {succeeded} succeeded, {failed} failed out of {len(file_paths)} file(s).")
        return failed == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Browse and download Datahub deep links using raw HTTP (no authentication needed).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    browse_parser = subparsers.add_parser(
        "browse",
        help="List files inside a folder deep link (no authentication needed)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    browse_parser.add_argument("--url", required=True, help="The full deep link URL (download or browse URL from creation)")
    browse_parser.add_argument("--signature", required=True, help="The X-DeepLink-Signature value")
    browse_parser.add_argument("--file-path", default=None, help="Subfolder path within the shared folder to browse (optional)")

    download_parser = subparsers.add_parser(
        "download",
        help="Download one or more files from a folder deep link",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    download_parser.add_argument("--url", required=True, help="The full deep link download URL")
    download_parser.add_argument("--signature", required=True, help="The X-DeepLink-Signature value")
    download_parser.add_argument("--output-dir", required=True, help="Local directory to save downloaded files")
    download_parser.add_argument(
        "--files",
        required=True,
        nargs="+",
        help="One or more internal file paths to download from the deep link folder",
    )

    args = parser.parse_args()

    try:
        if args.subcommand == "browse":
            browser = DeepLinkBrowser(url=args.url, signature=args.signature)
            success = browser.browse(file_path=args.file_path)
            return 0 if success else 1

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
