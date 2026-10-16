"""Tests for Automation/PLEXOS/DatahubDeepLink/deep_link_http_download.py"""
from unittest.mock import patch, MagicMock

import pytest
import requests

from .conftest import get_module

mod = get_module("auto_deeplink_download")
DeepLinkBatchDownloader = mod.DeepLinkBatchDownloader
DeepLinkBrowser = mod.DeepLinkBrowser
_file_name_from_download_url = mod._file_name_from_download_url
_expected_total_bytes = mod._expected_total_bytes


def _make_response(ok=True, status_code=200, headers=None, chunks=(b"data",), text="error"):
    """Build a MagicMock that behaves like a requests.Response used as a context manager."""
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.iter_content = MagicMock(return_value=list(chunks))
    resp.text = text
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


# ── DeepLinkBrowser tests ────────────────────────────────────────────────────


class TestDeepLinkBrowser:
    """Test browse via urllib."""

    @patch("auto_deeplink_download.urlopen")
    def test_browse_success_with_resources(self, mock_urlopen, capsys):
        response = MagicMock()
        response.read.return_value = (
            b'{"resources":[{"relativePath":"folder/file.parquet","lastModifiedAtUtc":"2025-06-01T10:00:00","versions":[{"fileSize":1234}]}]}'
        )
        mock_urlopen.return_value.__enter__.return_value = response

        browser = DeepLinkBrowser(
            "https://example.com/1.0/deeplink/abc12345678901234567890123456789/download/",
            "sig",
        )
        result = browser.browse()

        assert result is True
        out = capsys.readouterr().out
        assert "folder/file.parquet" in out
        assert "[OK] 1 resource(s) listed." in out

    @patch("auto_deeplink_download.urlopen")
    def test_browse_with_file_path_encodes_internal_path(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = b'{"Resources":[]}'
        mock_urlopen.return_value.__enter__.return_value = response

        browser = DeepLinkBrowser(
            "https://example.com/1.0/deeplink/abc12345678901234567890123456789/download/",
            "sig",
        )
        browser.browse("SOLUTION DATA")

        request_arg = mock_urlopen.call_args[0][0]
        assert "InternalFilePath=SOLUTION%20DATA" in request_arg.full_url

    def test_browse_rejects_path_traversal(self, capsys):
        """file_path containing '..' is rejected before making an HTTP request."""
        browser = DeepLinkBrowser(
            "https://example.com/1.0/deeplink/abc12345678901234567890123456789/download/",
            "sig",
        )
        result = browser.browse("../etc/passwd")

        assert result is False
        assert "[FAIL]" in capsys.readouterr().out

    def test_browse_rejects_absolute_path(self, capsys):
        """file_path starting with '/' is rejected before making an HTTP request."""
        browser = DeepLinkBrowser(
            "https://example.com/1.0/deeplink/abc12345678901234567890123456789/download/",
            "sig",
        )
        result = browser.browse("/etc/passwd")

        assert result is False
        assert "[FAIL]" in capsys.readouterr().out

    def test_browse_rejects_windows_absolute_path(self, capsys):
        """file_path starting with backslash is rejected before making an HTTP request."""
        browser = DeepLinkBrowser(
            "https://example.com/1.0/deeplink/abc12345678901234567890123456789/download/",
            "sig",
        )
        result = browser.browse("\\windows\\system32")

        assert result is False
        assert "[FAIL]" in capsys.readouterr().out

    def test_browse_rejects_windows_drive_letter_path(self, capsys):
        """file_path with a Windows drive letter (C:\\...) is rejected."""
        browser = DeepLinkBrowser(
            "https://example.com/1.0/deeplink/abc12345678901234567890123456789/download/",
            "sig",
        )
        result = browser.browse("C:\\Windows\\System32")

        assert result is False
        assert "[FAIL]" in capsys.readouterr().out


# ── Helper function tests ─────────────────────────────────────────────────────


class TestFileNameFromDownloadUrl:
    """_file_name_from_download_url derives the file name for File-type deep links."""

    def test_extracts_name_after_download_marker(self):
        url = "https://example.com/1.0/deeplink/abc/download/Common%20Data.xlsx?kst=1"
        assert _file_name_from_download_url(url) == "Common Data.xlsx"

    def test_extracts_nested_path_last_segment(self):
        url = "https://example.com/1.0/deeplink/abc/download/folder/nested/file.csv?x=1"
        assert _file_name_from_download_url(url) == "file.csv"

    def test_falls_back_to_last_path_segment_when_no_marker(self):
        url = "https://example.com/some/other/path/report.pdf?x=1"
        assert _file_name_from_download_url(url) == "report.pdf"


class TestExpectedTotalBytes:
    """_expected_total_bytes prefers headers that survive gzip compression."""

    def test_prefers_ee_full_content_length(self):
        response = MagicMock()
        response.headers = {"EE-FullContentLength": "1000", "Content-Length": "10"}
        assert _expected_total_bytes(response, resume_from=0) == 1000

    def test_falls_back_to_content_range_total(self):
        response = MagicMock()
        response.headers = {"Content-Range": "bytes 500-999/2000"}
        assert _expected_total_bytes(response, resume_from=500) == 2000

    def test_falls_back_to_content_length_plus_resume(self):
        response = MagicMock()
        response.headers = {"Content-Length": "500"}
        assert _expected_total_bytes(response, resume_from=300) == 800

    def test_returns_none_when_no_usable_header(self):
        response = MagicMock()
        response.headers = {}
        assert _expected_total_bytes(response, resume_from=0) is None

    def test_ignores_malformed_headers(self):
        response = MagicMock()
        response.headers = {"EE-FullContentLength": "not-a-number", "Content-Length": "not-a-number"}
        assert _expected_total_bytes(response, resume_from=0) is None


# ── DeepLinkBatchDownloader tests ─────────────────────────────────────────────


class TestBatchDownloaderInit:
    """Test constructor and URL normalisation."""

    def test_strips_trailing_ampersand(self):
        dl = DeepLinkBatchDownloader("https://example.com/deeplink/abc?x=1&", "sig", "/out")
        assert dl.download_url == "https://example.com/deeplink/abc?x=1"

    def test_strips_trailing_question_mark(self):
        dl = DeepLinkBatchDownloader("https://example.com/deeplink/abc?", "sig", "/out")
        assert dl.download_url == "https://example.com/deeplink/abc"

    def test_preserves_clean_url(self):
        url = "https://example.com/deeplink/abc?x=1"
        dl = DeepLinkBatchDownloader(url, "sig", "/out")
        assert dl.download_url == url


class TestBatchDownloaderFolderStyle:
    """When file_paths is given, InternalFilePath is appended (Folder deep link)."""

    @patch("auto_deeplink_download.requests.get")
    def test_single_file_success(self, mock_get, tmp_path):
        content = b"parquet-data-here"
        mock_get.return_value = _make_response(headers={"Content-Length": str(len(content))}, chunks=(content,))

        dl = DeepLinkBatchDownloader(
            "https://example.com/deeplink/abc?x=1",
            "my-signature",
            str(tmp_path),
        )
        result = dl.download(["SOLUTION_DATA/result.parquet"])

        assert result is True
        assert (tmp_path / "SOLUTION_DATA" / "result.parquet").read_bytes() == content
        mock_get.assert_called_once()

        call_url = mock_get.call_args[0][0]
        assert "&InternalFilePath=" in call_url
        assert "SOLUTION_DATA" in call_url

        call_headers = mock_get.call_args[1]["headers"]
        assert call_headers["X-DeepLink-Signature"] == "my-signature"

    @patch("auto_deeplink_download.requests.get")
    def test_multiple_files_all_succeed(self, mock_get, tmp_path):
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        files = ["folder/file1.parquet", "folder/file2.parquet", "folder/file3.csv"]
        result = dl.download(files)

        assert result is True
        assert mock_get.call_count == 3
        assert (tmp_path / "folder" / "file1.parquet").exists()
        assert (tmp_path / "folder" / "file2.parquet").exists()
        assert (tmp_path / "folder" / "file3.csv").exists()

    @patch("auto_deeplink_download.requests.get")
    def test_partial_failure_returns_false(self, mock_get, tmp_path):
        success_resp = _make_response(headers={"Content-Length": "2"}, chunks=(b"ok",))
        fail_resp = _make_response(ok=False, status_code=404, text="Not Found")

        mock_get.side_effect = [success_resp, fail_resp]

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["good.parquet", "missing.parquet"])

        assert result is False
        assert (tmp_path / "good.parquet").exists()
        assert not (tmp_path / "missing.parquet").exists()

    @patch("auto_deeplink_download.requests.get")
    def test_non_ok_response_fails_immediately_without_retry(self, mock_get, tmp_path):
        """A 4xx/5xx response is a hard failure, not retried."""
        mock_get.return_value = _make_response(ok=False, status_code=403, text="Forbidden")

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file1.parquet"])

        assert result is False
        mock_get.assert_called_once()

    @patch("auto_deeplink_download.requests.get")
    def test_request_exception_retries_then_fails(self, mock_get, tmp_path):
        mock_get.side_effect = requests.RequestException("Connection timed out")

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.parquet"])

        assert result is False
        assert mock_get.call_count == DeepLinkBatchDownloader._MAX_ATTEMPTS

    @patch("auto_deeplink_download.requests.get")
    def test_url_separator_when_no_query_string(self, mock_get, tmp_path):
        """If the URL has no '?', the separator should be '?' not '&'."""
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        dl = DeepLinkBatchDownloader("https://example.com/deeplink/abc", "sig", str(tmp_path))
        dl.download(["file.parquet"])

        call_url = mock_get.call_args[0][0]
        assert "?InternalFilePath=" in call_url

    @patch("auto_deeplink_download.requests.get")
    def test_url_separator_when_query_string_exists(self, mock_get, tmp_path):
        """If the URL already has '?', the separator should be '&'."""
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        dl = DeepLinkBatchDownloader("https://example.com/deeplink/abc?token=xyz", "sig", str(tmp_path))
        dl.download(["file.parquet"])

        call_url = mock_get.call_args[0][0]
        assert "&InternalFilePath=" in call_url

    @patch("auto_deeplink_download.requests.get")
    def test_file_path_is_url_encoded(self, mock_get, tmp_path):
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        dl.download(["folder with spaces/file name.parquet"])

        call_url = mock_get.call_args[0][0]
        assert "folder%20with%20spaces" in call_url
        assert "file%20name.parquet" in call_url

    @patch("auto_deeplink_download.requests.get")
    def test_creates_output_dir(self, mock_get, tmp_path):
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        out = tmp_path / "new_sub" / "dir"
        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(out))
        dl.download(["file.parquet"])

        assert out.exists()
        assert (out / "file.parquet").exists()

    @patch("auto_deeplink_download.requests.get")
    def test_rejects_path_traversal(self, mock_get, tmp_path):
        """Paths containing '..' are rejected."""
        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["../etc/passwd"])

        assert result is False
        mock_get.assert_not_called()

    @patch("auto_deeplink_download.requests.get")
    def test_rejects_absolute_path(self, mock_get, tmp_path):
        """Absolute paths are rejected."""
        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["/etc/passwd"])

        assert result is False
        mock_get.assert_not_called()

    @patch("auto_deeplink_download.requests.get")
    def test_rejects_windows_drive_letter_path(self, mock_get, tmp_path):
        """Windows drive-letter absolute paths are rejected."""
        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["C:\\Windows\\System32\\file.txt"])

        assert result is False
        mock_get.assert_not_called()

    @patch("auto_deeplink_download.requests.get")
    def test_preserves_subfolder_structure(self, mock_get, tmp_path):
        """Files with subfolders create matching directory structure."""
        content = b"nested-data"
        mock_get.return_value = _make_response(headers={"Content-Length": str(len(content))}, chunks=(content,))

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["a/b/c/result.parquet"])

        assert result is True
        assert (tmp_path / "a" / "b" / "c" / "result.parquet").read_bytes() == content


class TestBatchDownloaderFileStyle:
    """When file_paths is omitted/empty, the URL already targets a single File deep link.

    No InternalFilePath is appended (doing so would invalidate the signed query
    string for a File-type deep link), and the destination file name is derived
    from the URL itself.
    """

    @patch("auto_deeplink_download.requests.get")
    def test_no_files_arg_downloads_single_file_without_internal_file_path(self, mock_get, tmp_path):
        content = b"xlsx-bytes"
        mock_get.return_value = _make_response(headers={"Content-Length": str(len(content))}, chunks=(content,))

        url = "https://example.com/1.0/deeplink/abc/download/Common%20Data.xlsx?kst=1&ut=file"
        dl = DeepLinkBatchDownloader(url, "sig", str(tmp_path))
        result = dl.download(None)

        assert result is True
        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        assert called_url == url
        assert "InternalFilePath" not in called_url
        assert (tmp_path / "Common Data.xlsx").read_bytes() == content

    @patch("auto_deeplink_download.requests.get")
    def test_empty_files_list_also_uses_file_level_behaviour(self, mock_get, tmp_path):
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        url = "https://example.com/1.0/deeplink/abc/download/report.csv?kst=1"
        dl = DeepLinkBatchDownloader(url, "sig", str(tmp_path))
        result = dl.download([])

        assert result is True
        called_url = mock_get.call_args[0][0]
        assert "InternalFilePath" not in called_url


class TestLinkTypeValidation:
    """The `ut=` query parameter is cross-checked against --files usage and mismatches rejected."""

    @patch("auto_deeplink_download.requests.get")
    def test_files_rejected_for_file_type_link(self, mock_get, tmp_path):
        """Passing --files for a ut=file link would reproduce the signature-invalidating 401."""
        url = "https://example.com/1.0/deeplink/abc/download/Common%20Data.xlsx?kst=1&ut=file"
        dl = DeepLinkBatchDownloader(url, "sig", str(tmp_path))
        result = dl.download(["Common Data.xlsx"])

        assert result is False
        mock_get.assert_not_called()

    @patch("auto_deeplink_download.requests.get")
    def test_missing_files_rejected_for_folder_type_link(self, mock_get, tmp_path):
        """Omitting --files for a ut=folder link would request the folder URL without a file selector."""
        url = "https://example.com/1.0/deeplink/abc/download?kst=1&ut=folder"
        dl = DeepLinkBatchDownloader(url, "sig", str(tmp_path))
        result = dl.download(None)

        assert result is False
        mock_get.assert_not_called()

    @patch("auto_deeplink_download.requests.get")
    def test_unqualified_link_permits_either_usage(self, mock_get, tmp_path):
        """URLs without a ut= parameter (e.g. older links) fall back to file_paths-based detection."""
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        url = "https://example.com/1.0/deeplink/abc/download?kst=1"
        dl = DeepLinkBatchDownloader(url, "sig", str(tmp_path))
        result = dl.download(["some/file.csv"])

        assert result is True
        mock_get.assert_called_once()


class TestBatchDownloaderResumeAndRetry:
    """Resumable, retrying download behaviour via the .part file and Range header."""

    @patch("auto_deeplink_download.requests.get")
    def test_resumes_after_interrupted_write(self, mock_get, tmp_path):
        """First attempt writes half the bytes then dies; second attempt resumes with Range."""

        class InterruptingResponse:
            """A response whose iter_content raises partway through."""

            def __init__(self):
                self.ok = True
                self.status_code = 200
                self.headers = {"Content-Length": "10", "ETag": '"abc123"'}
                self.text = ""

            def iter_content(self, chunk_size):
                yield b"12345"
                raise requests.RequestException("connection reset")

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        resume_response = _make_response(
            status_code=206,
            headers={"Content-Range": "bytes 5-9/10", "ETag": '"abc123"'},
            chunks=(b"67890",),
        )

        mock_get.side_effect = [InterruptingResponse(), resume_response]

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.bin"])

        assert result is True
        assert (tmp_path / "file.bin").read_bytes() == b"1234567890"
        assert mock_get.call_count == 2

        second_call_headers = mock_get.call_args_list[1][1]["headers"]
        assert second_call_headers["Range"] == "bytes=5-"
        assert second_call_headers["If-Range"] == '"abc123"'
        assert not (tmp_path / "file.bin.part").exists()
        assert not (tmp_path / "file.bin.part.meta").exists()

    @patch("auto_deeplink_download.requests.get")
    def test_stale_part_without_validator_is_discarded(self, mock_get, tmp_path):
        """A .part file left by an earlier invocation (no persisted ETag/Last-Modified)
        is discarded rather than trusted, since the underlying object may have changed.
        """
        fresh_response = _make_response(
            status_code=200,
            headers={"Content-Length": "5"},
            chunks=(b"1234", b"5"),
        )

        (tmp_path / "file.bin.part").write_bytes(b"stale-partial-data")

        mock_get.return_value = fresh_response

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.bin"])

        assert result is True
        assert (tmp_path / "file.bin").read_bytes() == b"12345"
        # No Range/If-Range should have been sent -- the stale part was discarded first.
        call_headers = mock_get.call_args[1]["headers"]
        assert "Range" not in call_headers
        assert "If-Range" not in call_headers

    @patch("auto_deeplink_download.requests.get")
    def test_range_ignored_by_server_restarts_from_zero(self, mock_get, tmp_path):
        """If the object changed since the .part was started, If-Range fails and the server
        returns 200 (not 206); the stale partial is discarded and re-fetched from zero."""
        (tmp_path / "file.bin.part").write_bytes(b"AAAAA")
        (tmp_path / "file.bin.part.meta").write_text('{"validator": "\\"v1\\""}', encoding="utf-8")

        object_changed_response = _make_response(status_code=200, ok=True)
        fresh_full_response = _make_response(status_code=200, headers={"Content-Length": "5"}, chunks=(b"12345",))

        mock_get.side_effect = [object_changed_response, fresh_full_response]

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.bin"])

        assert result is True
        assert (tmp_path / "file.bin").read_bytes() == b"12345"
        assert mock_get.call_count == 2

        first_call_headers = mock_get.call_args_list[0][1]["headers"]
        assert first_call_headers["Range"] == "bytes=5-"
        assert first_call_headers["If-Range"] == '"v1"'
        second_call_headers = mock_get.call_args_list[1][1]["headers"]
        assert "Range" not in second_call_headers

    @patch("auto_deeplink_download.requests.get")
    def test_expected_size_is_reset_when_object_changes(self, mock_get, tmp_path):
        """After a short read on the old object, then a change detected via If-Range, the
        replacement object's (smaller) expected size must not be checked against the stale one.
        """
        short_read_of_old_object = _make_response(
            headers={"Content-Length": "10", "ETag": '"v1"'}, chunks=(b"12345",)
        )
        # If-Range fails (object changed): server returns 200, not 206.
        object_changed_response = _make_response(status_code=200, ok=True)
        # The replacement object is smaller than the original 10 bytes.
        new_object_full_response = _make_response(
            status_code=200, headers={"Content-Length": "3", "ETag": '"v2"'}, chunks=(b"abc",)
        )

        mock_get.side_effect = [short_read_of_old_object, object_changed_response, new_object_full_response]

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.bin"])

        assert result is True
        assert (tmp_path / "file.bin").read_bytes() == b"abc"
        assert mock_get.call_count == 3

    @patch("auto_deeplink_download.requests.get")
    def test_short_read_triggers_retry(self, mock_get, tmp_path):
        """If fewer bytes arrive than Content-Length promised, the download retries."""
        short_response = _make_response(headers={"Content-Length": "10", "ETag": '"v1"'}, chunks=(b"12345",))
        full_response = _make_response(
            status_code=206, headers={"Content-Range": "bytes 5-9/10", "ETag": '"v1"'}, chunks=(b"67890",)
        )

        mock_get.side_effect = [short_response, full_response]

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.bin"])

        assert result is True
        assert (tmp_path / "file.bin").read_bytes() == b"1234567890"
        assert mock_get.call_count == 2

    @patch("auto_deeplink_download.requests.get")
    def test_gives_up_after_max_attempts(self, mock_get, tmp_path):
        """Persistent connection errors exhaust retries and report failure."""
        mock_get.side_effect = requests.RequestException("always fails")

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.bin"])

        assert result is False
        assert mock_get.call_count == DeepLinkBatchDownloader._MAX_ATTEMPTS

    @patch("auto_deeplink_download.requests.get")
    def test_accept_encoding_identity_header_always_sent(self, mock_get, tmp_path):
        """Accept-Encoding: identity avoids gzip, which would drop Content-Length."""
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        dl.download(["file.bin"])

        call_headers = mock_get.call_args[1]["headers"]
        assert call_headers["Accept-Encoding"] == "identity"


# ── main() tests ──────────────────────────────────────────────────────────────


class TestMain:
    """Test the main() entrypoint."""

    @patch("auto_deeplink_download.requests.get")
    def test_main_download_success_with_files(self, mock_get, tmp_path):
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        with patch("sys.argv", [
            "deep_link_http_download.py",
            "download",
            "--url", "https://example.com/dl?x=1",
            "--signature", "my-sig",
            "--output-dir", str(tmp_path),
            "--files", "file1.parquet", "file2.parquet",
        ]):
            result = mod.main()

        assert result == 0
        assert mock_get.call_count == 2

    @patch("auto_deeplink_download.requests.get")
    def test_main_download_success_without_files(self, mock_get, tmp_path):
        """--files is optional; omitting it downloads the single File-type deep link."""
        mock_get.return_value = _make_response(headers={"Content-Length": "4"}, chunks=(b"data",))

        with patch("sys.argv", [
            "deep_link_http_download.py",
            "download",
            "--url", "https://example.com/1.0/deeplink/abc/download/report.csv?kst=1",
            "--signature", "my-sig",
            "--output-dir", str(tmp_path),
        ]):
            result = mod.main()

        assert result == 0
        assert (tmp_path / "report.csv").exists()

    @patch("auto_deeplink_download.requests.get")
    def test_main_download_failure(self, mock_get, tmp_path):
        mock_get.return_value = _make_response(ok=False, status_code=500, text="Internal Server Error")

        with patch("sys.argv", [
            "deep_link_http_download.py",
            "download",
            "--url", "https://example.com/dl?x=1",
            "--signature", "my-sig",
            "--output-dir", str(tmp_path),
            "--files", "file.parquet",
        ]):
            result = mod.main()

        assert result == 1

    @patch("auto_deeplink_download.urlopen")
    def test_main_browse_success(self, mock_urlopen, capsys):
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"resources":[{"relativePath":"data/file.parquet","lastModifiedAtUtc":"2025-06-01T12:00:00","versions":[{"fileSize":2048}]}]}'
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with patch("sys.argv", [
            "deep_link_http_download.py",
            "browse",
            "--url", "https://example.com/1.0/deeplink/abc12345678901234567890123456789/download/",
            "--signature", "my-sig",
        ]):
            result = mod.main()

        assert result == 0
        assert "data/file.parquet" in capsys.readouterr().out

    def test_main_missing_subcommand(self):
        with patch("sys.argv", ["deep_link_http_download.py"]):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code != 0
