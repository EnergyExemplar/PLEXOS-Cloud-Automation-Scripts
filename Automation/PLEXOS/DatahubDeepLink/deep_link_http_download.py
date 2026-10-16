"""
Browse and download Datahub deep links using raw HTTP (no authentication needed).

Subcommands:
    browse    List files inside a folder deep link via raw HTTP/urllib
    download  Download from a File or Folder deep link via raw HTTP:
              - File deep link (`ut=file`): omit --files; the destination file name
                is derived from the deep link URL itself.
              - Folder deep link (`ut=folder`): pass one or more --files paths to
                select which file(s) within the folder to download; each value is
                also used as the local destination path.

Note: To create deep links, use datahub_deep_link.py which handles authenticated creation via SDK.
"""
import argparse
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlsplit
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





def _file_name_from_download_url(url: str) -> str:
    path = urlsplit(url).path
    marker = "/download/"
    index = path.find(marker)
    if index == -1:
        return unquote(path.rsplit("/", 1)[-1])
    return unquote(path[index + len(marker):]).split("/")[-1]


def _expected_total_bytes(response, resume_from: int) -> int | None:
    """Full resource size, preferring the header that survives compression."""
    full_length = response.headers.get("EE-FullContentLength")
    if full_length:
        try:
            return int(full_length)
        except ValueError:
            pass

    content_range = response.headers.get("Content-Range")
    if content_range and "/" in content_range:
        try:
            return int(content_range.rsplit("/", 1)[-1].strip())
        except ValueError:
            pass

    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            return int(content_length) + resume_from
        except ValueError:
            pass

    return None


class DeepLinkBatchDownloader:
    """Downloads files from a Datahub deep link via raw HTTP requests.

    Supports both link types, distinguished by the `ut=` query parameter already
    present in the URL:
    - File deep links (`ut=file`) already identify a single file; `--files` must
      be omitted, and the destination name is derived from the URL.
    - Folder deep links (`ut=folder`) require one or more `--files` paths to
      select which file(s) to download; each is appended as `InternalFilePath`.

    Passing `--files` for a File-type link (or omitting it for a Folder-type
    link) is rejected up front rather than silently sent to the server, since
    the former reproduces a signature-invalidating 401 and the latter requests
    the folder URL without a file selector.
    """

    _CHUNK_SIZE = 1024 * 1024
    _MAX_ATTEMPTS = 20
    _PROGRESS_EVERY = 256 * 1024 * 1024

    def __init__(self, download_url: str, signature: str, output_dir: str):
        self.download_url = download_url.rstrip("&").rstrip("?")
        self.signature = signature
        self.output_dir = output_dir
        self.link_type = (parse_qs(urlsplit(self.download_url).query).get("ut", [""])[0] or "").lower()

    def download(self, file_paths: list[str] | None) -> bool:
        os.makedirs(self.output_dir, exist_ok=True)

        if file_paths and self.link_type == "file":
            print("[FAIL] This is a File-type deep link (ut=file); it already targets a single file "
                  "and does not accept --files. Omit --files, or create a Folder-type deep link instead.")
            return False
        if not file_paths and self.link_type == "folder":
            print("[FAIL] This is a Folder-type deep link (ut=folder); pass one or more --files paths "
                  "to select which file(s) to download.")
            return False

        separator = "&" if "?" in self.download_url else "?"

        succeeded = 0
        failed = 0

        if not file_paths:
            # File-level deep link: the route already targets one file, so no InternalFilePath.
            file_paths = [_file_name_from_download_url(self.download_url)]
            urls = [self.download_url]
        else:
            urls = None

        for index, file_path in enumerate(file_paths):
            if (_PATH_TRAVERSAL.search(file_path)
                    or file_path.startswith("/")
                    or file_path.startswith("\\")
                    or _WINDOWS_DRIVE_PATH.match(file_path)):
                print(f"[FAIL] {file_path} - rejected: path must be relative without '..'")
                failed += 1
                continue

            if urls:
                url = urls[index]
            else:
                encoded_path = quote(file_path, safe="")
                url = f"{self.download_url}{separator}InternalFilePath={encoded_path}"

            if self._download_one(url, file_path):
                succeeded += 1
            else:
                failed += 1

        print(f"\n[OK] {succeeded} succeeded, {failed} failed out of {len(file_paths)} file(s).")
        return failed == 0

    def _download_one(self, url: str, file_path: str) -> bool:
        dest = os.path.join(self.output_dir, file_path.replace("/", os.sep))
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        part = f"{dest}.part"
        meta_path = f"{dest}.part.meta"

        expected = None

        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            resume_from = 0
            validator = None
            if os.path.exists(part):
                resume_from = os.path.getsize(part)
                if resume_from > 0:
                    validator = self._load_validator(meta_path)
                    if validator is None:
                        # No trusted ETag/Last-Modified for this partial file (e.g. left
                        # over from an earlier invocation) -- discard rather than risk
                        # resuming into a differently-versioned object.
                        os.remove(part)
                        resume_from = 0

            headers = {
                "X-DeepLink-Signature": self.signature,
                # Without this the API gzips the payload, which drops Content-Length and
                # switches to chunked, leaving no way to tell a short body from a complete one.
                "Accept-Encoding": "identity",
            }
            if resume_from > 0:
                headers["Range"] = f"bytes={resume_from}-"
                if validator:
                    headers["If-Range"] = validator

            try:
                response = requests.get(url, headers=headers, timeout=(30, 300), stream=True)
            except requests.RequestException as e:
                print(f"[WARN] {file_path} - attempt {attempt}: request error: {e}")
                continue

            with response:
                if not response.ok:
                    print(f"[FAIL] {file_path} - HTTP {response.status_code}: {response.text[:500]}")
                    return False

                if resume_from > 0 and response.status_code != 206:
                    # Range/If-Range not honoured -- either the server doesn't support partial
                    # content or the object changed since the .part file was started. Discard
                    # and restart from zero rather than appending onto a mismatched prefix.
                    # `expected` must also be reset: it may hold the previous (now stale) object's
                    # size, and checking the replacement content against that size could accept a
                    # truncated larger replacement or exhaust retries on a smaller one.
                    print(f"[WARN] {file_path} - attempt {attempt}: Range ignored or object changed, restarting from zero")
                    if os.path.exists(part):
                        os.remove(part)
                    self._remove_validator(meta_path)
                    expected = None
                    continue

                if resume_from == 0:
                    self._save_validator(meta_path, response.headers)

                if expected is None:
                    expected = _expected_total_bytes(response, resume_from)

                written = resume_from
                next_report = written + self._PROGRESS_EVERY
                try:
                    with open(part, "ab") as f:
                        for chunk in response.iter_content(chunk_size=self._CHUNK_SIZE):
                            f.write(chunk)
                            written += len(chunk)
                            if written >= next_report:
                                self._report(file_path, written, expected)
                                next_report = written + self._PROGRESS_EVERY
                except (requests.RequestException, OSError) as e:
                    print(f"[WARN] {file_path} - attempt {attempt}: interrupted at {written:,} bytes: {e}")
                    continue

            if expected is not None and written < expected:
                print(f"[WARN] {file_path} - attempt {attempt}: short read {written:,}/{expected:,}, resuming")
                continue

            os.replace(part, dest)
            self._remove_validator(meta_path)
            print(f"[OK] Downloaded: {file_path} ({written:,} bytes)")
            return True

        print(f"[FAIL] {file_path} - still incomplete after {self._MAX_ATTEMPTS} attempts; partial kept at {part}")
        return False

    @staticmethod
    def _save_validator(meta_path: str, headers) -> None:
        """Persist the ETag/Last-Modified of a freshly-started download for later If-Range use."""
        validator = headers.get("ETag") or headers.get("Last-Modified")
        if not validator:
            DeepLinkBatchDownloader._remove_validator(meta_path)
            return
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"validator": validator}, f)
        except OSError:
            pass

    @staticmethod
    def _load_validator(meta_path: str) -> str | None:
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f).get("validator")
        except (OSError, ValueError):
            return None

    @staticmethod
    def _remove_validator(meta_path: str) -> None:
        try:
            os.remove(meta_path)
        except OSError:
            pass

    @staticmethod
    def _report(file_path: str, written: int, expected: int | None) -> None:
        if expected:
            print(f"  {file_path}: {written:,}/{expected:,} bytes ({written * 100.0 / expected:.1f}%)")
        else:
            print(f"  {file_path}: {written:,} bytes")


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
        help="Download from a File or Folder deep link (see module docstring for the difference)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    download_parser.add_argument("--url", required=True, help="The full deep link download URL")
    download_parser.add_argument("--signature", required=True, help="The X-DeepLink-Signature value")
    download_parser.add_argument("--output-dir", required=True, help="Local directory to save downloaded files")
    download_parser.add_argument(
        "--files",
        nargs="+",
        default=None,
        help="Internal file paths to download from a Folder deep link (each also used as the local "
             "destination path). Required for a Folder deep link (ut=folder) and must be omitted for a "
             "File deep link (ut=file), whose URL already targets a single file and whose destination "
             "name is derived from the URL.",
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
