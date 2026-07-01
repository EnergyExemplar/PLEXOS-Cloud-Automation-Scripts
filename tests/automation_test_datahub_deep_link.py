"""
Unit tests for Automation/PLEXOS/DatahubDeepLink/datahub_deep_link.py.

Covers subcommand routing, SDK kwarg correctness, and error handling
for create, list, browse, download, and delete operations.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module

MOD = get_module("auto_deep_link")
DatahubDeepLinkManager = MOD.DatahubDeepLinkManager
DeepLinkBrowser = MOD.DeepLinkBrowser
DeepLinkDownloader = MOD.DeepLinkDownloader


# ── Helper: mock SDK that passes authentication ──────────────────────────────

def _make_sdk_mock():
    """Create a CloudSDK mock that passes authentication."""
    sdk = MagicMock()
    login_data = SimpleNamespace(IsLoggedIn=True, UserName="test", TenantName="tenant")
    sdk.auth.login.return_value = [SimpleNamespace(Status="Success", Data=login_data)]
    return sdk


# ── DatahubDeepLinkManager.create ────────────────────────────────────────────

class TestManagerCreate:
    """Tests for the create subcommand."""

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_create_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, UrlId="abc", RelativePath="p",
                           DownloadUrl="http://x", DeepLinkEndTimeUtc="2099",
                           MaximumDownloads=5, Signature="sig", CurlCommand="curl x"),
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.create(path="folder/file.csv", link_type="File", days=7, hours=None, expiry=None, limit=5)

        assert result is True
        sdk.datahub.create_deep_link.assert_called_once_with(
            path="folder/file.csv",
            type="File",
            days=7,
            hours=None,
            expiry=None,
            limit=5,
            print_message=False,
        )

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_create_returns_false_on_api_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_deep_link.return_value = [
            SimpleNamespace(Status="Failed", Message="Path not found")
        ]

        mock_get_data.return_value = SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t")

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.create(path="bad/path", link_type="File", days=1, hours=None, expiry=None, limit=None)

        assert result is False

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_create_returns_false_when_data_is_none(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            None,
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.create(path="x", link_type="File", days=1, hours=None, expiry=None, limit=None)

        assert result is False


# ── DatahubDeepLinkManager.list_deep_links ───────────────────────────────────

class TestManagerList:
    """Tests for the list subcommand."""

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_list_returns_true_with_links(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_deep_links.return_value = [SimpleNamespace(Status="Success")]

        link = SimpleNamespace(
            UrlId="abc-123", RelativePath="folder/file.csv",
            UrlType="File", IsActive=True, IsExpired=False,
            CompletedDownloads=2, DeepLinkEndTimeUtc="2099-01-01"
        )
        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, DeepLinks=[link]),
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.list_deep_links()

        assert result is True

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_list_returns_true_when_empty(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_deep_links.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, DeepLinks=[]),
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.list_deep_links()

        assert result is True

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_list_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_deep_links.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False, DeepLinks=None),
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.list_deep_links()

        assert result is False


# ── DatahubDeepLinkManager.delete ────────────────────────────────────────────

class TestManagerDelete:
    """Tests for the delete subcommand."""

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_delete_calls_revoke_with_correct_id(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.revoke_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, UrlId="abc-123"),
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.delete(url_id="abc-123")

        assert result is True
        sdk.datahub.revoke_deep_link.assert_called_once_with(id="abc-123", print_message=False)

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_delete_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.revoke_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False, UrlId=None),
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        result = mgr.delete(url_id="bad-id")

        assert result is False


# ── DatahubDeepLinkManager authentication ────────────────────────────────────

class TestManagerAuthentication:
    """Tests for the authentication flow."""

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_auth_failure_raises(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk

        mock_get_data.return_value = SimpleNamespace(IsLoggedIn=False, UserName=None, TenantName=None)

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        with pytest.raises(RuntimeError, match="Authentication failed"):
            mgr._authenticate()

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_auth_only_called_once(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_deep_links.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, DeepLinks=[]),
            SimpleNamespace(Success=True, DeepLinks=[]),
        ]

        mgr = DatahubDeepLinkManager(cli_path="/cli", environment="env")
        mgr.list_deep_links()
        mgr.list_deep_links()

        # login called only once
        sdk.auth.login.assert_called_once()


# ── DeepLinkDownloader ───────────────────────────────────────────────────────

class TestDownloader:
    """Tests for the download subcommand."""

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_download_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data, tmp_path):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.download_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.return_value = SimpleNamespace(
            Success=True, FileName="file.csv", FilePath=str(tmp_path / "file.csv"), FileSize=100
        )

        dl = DeepLinkDownloader(cli_path="/cli")
        result = dl.download(
            download_url="http://dl",
            signature="sig123",
            output_dir=str(tmp_path),
            internal_file_path="sub/file.csv",
        )

        assert result is True
        sdk.datahub.download_deep_link.assert_called_once_with(
            url="http://dl",
            signature="sig123",
            output=str(tmp_path),
            file_path="sub/file.csv",
            print_message=False,
        )

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_download_returns_false_on_api_failure(self, mock_sdk_cls, mock_get_data, tmp_path):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.download_deep_link.return_value = [
            SimpleNamespace(Status="Failed", Message="Invalid signature")
        ]

        mock_get_data.return_value = None

        dl = DeepLinkDownloader(cli_path="/cli")
        result = dl.download(
            download_url="http://dl",
            signature="bad",
            output_dir=str(tmp_path),
        )

        assert result is False

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_download_returns_false_when_not_successful(self, mock_sdk_cls, mock_get_data, tmp_path):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.download_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.return_value = SimpleNamespace(Success=False, FileName=None, FilePath=None, FileSize=0)

        dl = DeepLinkDownloader(cli_path="/cli")
        result = dl.download(
            download_url="http://dl",
            signature="sig",
            output_dir=str(tmp_path),
        )

        assert result is False


# ── DeepLinkBrowser ──────────────────────────────────────────────────────────

class TestBrowser:
    """Tests for the browse subcommand (SDK-based)."""

    _URL = "https://api.example.com/1.0/deeplink/abc-123/download/MyFolder?x=1"
    _SIGNATURE = "sig=="

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_browse_returns_true_on_success(self, mock_sdk_cls, mock_get_data):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.browse_deep_link.return_value = [SimpleNamespace(Status="Success")]
        mock_get_data.return_value = SimpleNamespace(Success=True, DatahubSearchResults=[
            SimpleNamespace(RelativePath="file.py", FileSize=100, LastModifiedAtUtc="2026-01-01T00:00:00Z", CreatedAtUtc="")
        ])
        result = DeepLinkBrowser(cli_path="/cli").browse(url=self._URL, signature=self._SIGNATURE)
        assert result is True

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_browse_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.browse_deep_link.return_value = [SimpleNamespace(Status="Success")]
        mock_get_data.return_value = SimpleNamespace(Success=True, DatahubSearchResults=[])
        DeepLinkBrowser(cli_path="/cli").browse(url=self._URL, signature=self._SIGNATURE, file_path="sub/dir")
        sdk.datahub.browse_deep_link.assert_called_once_with(
            url=self._URL,
            signature=self._SIGNATURE,
            file_path="sub/dir",
            print_message=False,
        )

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_browse_returns_true_when_no_items(self, mock_sdk_cls, mock_get_data):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.browse_deep_link.return_value = [SimpleNamespace(Status="Success")]
        mock_get_data.return_value = SimpleNamespace(Success=True, DatahubSearchResults=[])
        result = DeepLinkBrowser(cli_path="/cli").browse(url=self._URL, signature=self._SIGNATURE)
        assert result is True

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_browse_returns_false_on_api_failure(self, mock_sdk_cls, mock_get_data):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.browse_deep_link.return_value = [
            SimpleNamespace(Status="Failed", Message="Invalid signature")
        ]
        mock_get_data.return_value = None
        result = DeepLinkBrowser(cli_path="/cli").browse(url=self._URL, signature="bad")
        assert result is False

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_browse_returns_false_when_data_none(self, mock_sdk_cls, mock_get_data):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.browse_deep_link.return_value = [SimpleNamespace(Status="Success")]
        mock_get_data.return_value = None
        result = DeepLinkBrowser(cli_path="/cli").browse(url=self._URL, signature=self._SIGNATURE)
        assert result is False

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_browse_returns_false_when_success_false(self, mock_sdk_cls, mock_get_data):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.browse_deep_link.return_value = [SimpleNamespace(Status="Success")]
        mock_get_data.return_value = SimpleNamespace(Success=False, DatahubSearchResults=None)
        result = DeepLinkBrowser(cli_path="/cli").browse(url=self._URL, signature=self._SIGNATURE)
        assert result is False


# ── main() routing tests ─────────────────────────────────────────────────────

class TestMain:
    """Tests for main() subcommand routing."""

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_main_create_requires_expiry(self, mock_sdk_cls, mock_get_data):
        with patch("sys.argv", [
            "datahub_deep_link.py", "create",
            "--cli-path", "/cli",
            "--environment", "env",
            "--path", "folder/file",
            "--type", "File",
        ]):
            result = MOD.main()
        assert result == 1

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_main_list_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_deep_links.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, DeepLinks=[]),
        ]

        with patch("sys.argv", [
            "datahub_deep_link.py", "list",
            "--cli-path", "/cli",
            "--environment", "env",
        ]):
            result = MOD.main()

        assert result == 0

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_main_download_routes_correctly(self, mock_sdk_cls, mock_get_data, tmp_path):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.download_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.return_value = SimpleNamespace(
            Success=True, FileName="f.csv", FilePath=str(tmp_path / "f.csv"), FileSize=50
        )

        with patch("sys.argv", [
            "datahub_deep_link.py", "download",
            "--cli-path", "/cli",
            "--download-url", "http://dl",
            "--signature", "sig",
            "--output-dir", str(tmp_path),
        ]):
            result = MOD.main()

        assert result == 0

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_main_delete_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.revoke_deep_link.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, UrlId="test-id"),
        ]

        with patch("sys.argv", [
            "datahub_deep_link.py", "delete",
            "--cli-path", "/cli",
            "--environment", "env",
            "--id", "test-id",
        ]):
            result = MOD.main()

        assert result == 0

    def test_main_no_subcommand_exits(self):
        with patch("sys.argv", ["datahub_deep_link.py"]):
            with pytest.raises(SystemExit) as exc_info:
                MOD.main()
            assert exc_info.value.code != 0

    @patch("auto_deep_link.SDKBase.get_response_data")
    @patch("auto_deep_link.CloudSDK")
    def test_main_browse_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = MagicMock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.browse_deep_link.return_value = [SimpleNamespace(Status="Success")]
        mock_get_data.return_value = SimpleNamespace(
            Success=True,
            DatahubSearchResults=[
                SimpleNamespace(RelativePath="MyFolder/file.py", FileSize=999,
                                LastModifiedAtUtc="2026-04-30T10:58:01Z", CreatedAtUtc="")
            ]
        )

        with patch("sys.argv", [
            "datahub_deep_link.py", "browse",
            "--cli-path", "/cli",
            "--url", "https://api.example.com/1.0/deeplink/abc/download/Folder?x=1",
            "--signature", "sig==",
        ]):
            result = MOD.main()

        assert result == 0
