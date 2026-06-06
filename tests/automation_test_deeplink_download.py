"""Tests for Automation/PLEXOS/DatahubDeepLink/deep_link_http_download.py"""
import os
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from .conftest import get_module

mod = get_module("auto_deeplink_download")
DeepLinkBatchDownloader = mod.DeepLinkBatchDownloader


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


class TestBatchDownloaderDownload:
    """Test the download method."""

    @patch("auto_deeplink_download.requests.get")
    def test_single_file_success(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"parquet-data-here"])
        mock_get.return_value = mock_resp

        dl = DeepLinkBatchDownloader(
            "https://example.com/deeplink/abc?x=1",
            "my-signature",
            str(tmp_path),
        )
        result = dl.download(["SOLUTION_DATA/result.parquet"])

        assert result is True
        assert (tmp_path / "SOLUTION_DATA" / "result.parquet").read_bytes() == b"parquet-data-here"
        mock_get.assert_called_once()

        # Verify correct URL construction
        call_url = mock_get.call_args[0][0]
        assert "&InternalFilePath=" in call_url
        assert "SOLUTION_DATA" in call_url

        # Verify signature header
        call_headers = mock_get.call_args[1]["headers"]
        assert call_headers["X-DeepLink-Signature"] == "my-signature"

    @patch("auto_deeplink_download.requests.get")
    def test_multiple_files_all_succeed(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_resp

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
        success_resp = MagicMock()
        success_resp.ok = True
        success_resp.iter_content = MagicMock(return_value=[b"ok"])

        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 404
        fail_resp.text = "Not Found"

        mock_get.side_effect = [success_resp, fail_resp]

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["good.parquet", "missing.parquet"])

        assert result is False
        assert (tmp_path / "good.parquet").exists()
        assert not (tmp_path / "missing.parquet").exists()

    @patch("auto_deeplink_download.requests.get")
    def test_all_fail_returns_false(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_get.return_value = mock_resp

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file1.parquet", "file2.parquet"])

        assert result is False

    @patch("auto_deeplink_download.requests.get")
    def test_request_exception_counts_as_failure(self, mock_get, tmp_path):
        import requests
        mock_get.side_effect = requests.RequestException("Connection timed out")

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["file.parquet"])

        assert result is False

    @patch("auto_deeplink_download.requests.get")
    def test_url_separator_when_no_query_string(self, mock_get, tmp_path):
        """If the URL has no '?', the separator should be '?' not '&'."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_resp

        dl = DeepLinkBatchDownloader("https://example.com/deeplink/abc", "sig", str(tmp_path))
        dl.download(["file.parquet"])

        call_url = mock_get.call_args[0][0]
        assert "?InternalFilePath=" in call_url

    @patch("auto_deeplink_download.requests.get")
    def test_url_separator_when_query_string_exists(self, mock_get, tmp_path):
        """If the URL already has '?', the separator should be '&'."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_resp

        dl = DeepLinkBatchDownloader("https://example.com/deeplink/abc?token=xyz", "sig", str(tmp_path))
        dl.download(["file.parquet"])

        call_url = mock_get.call_args[0][0]
        assert "&InternalFilePath=" in call_url

    @patch("auto_deeplink_download.requests.get")
    def test_file_path_is_url_encoded(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_resp

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        dl.download(["folder with spaces/file name.parquet"])

        call_url = mock_get.call_args[0][0]
        assert "folder%20with%20spaces" in call_url
        assert "file%20name.parquet" in call_url

    @patch("auto_deeplink_download.requests.get")
    def test_creates_output_dir(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_resp

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
    def test_preserves_subfolder_structure(self, mock_get, tmp_path):
        """Files with subfolders create matching directory structure."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"nested-data"])
        mock_get.return_value = mock_resp

        dl = DeepLinkBatchDownloader("https://example.com/dl?x=1", "sig", str(tmp_path))
        result = dl.download(["a/b/c/result.parquet"])

        assert result is True
        assert (tmp_path / "a" / "b" / "c" / "result.parquet").read_bytes() == b"nested-data"


# ── main() tests ──────────────────────────────────────────────────────────────


class TestMain:
    """Test the main() entrypoint."""

    @patch("auto_deeplink_download.requests.get")
    def test_main_success(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_resp

        with patch("sys.argv", [
            "deep_link_http_download.py",
            "--url", "https://example.com/dl?x=1",
            "--signature", "my-sig",
            "--output-dir", str(tmp_path),
            "--files", "file1.parquet", "file2.parquet",
        ]):
            result = mod.main()

        assert result == 0
        assert mock_get.call_count == 2

    @patch("auto_deeplink_download.requests.get")
    def test_main_failure(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp

        with patch("sys.argv", [
            "deep_link_http_download.py",
            "--url", "https://example.com/dl?x=1",
            "--signature", "my-sig",
            "--output-dir", str(tmp_path),
            "--files", "file.parquet",
        ]):
            result = mod.main()

        assert result == 1

    def test_main_missing_required_args(self):
        with patch("sys.argv", ["deep_link_http_download.py"]):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code != 0
