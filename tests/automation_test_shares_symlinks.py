"""
Unit tests for Automation/PLEXOS/DatahubSharesAndSymlinks/datahub_shares_symlinks.py.

Covers subcommand routing, SDK kwarg correctness, and error handling
for share and symlink create, list, and delete operations.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from .conftest import get_module

MOD = get_module("auto_shares_symlinks")
DatahubShareManager = MOD.DatahubShareManager
DatahubSymlinkManager = MOD.DatahubSymlinkManager


# ── Helper: mock SDK that passes authentication ──────────────────────────────

def _make_sdk_mock():
    """Create a CloudSDK mock that passes authentication."""
    sdk = MagicMock()
    login_data = SimpleNamespace(IsLoggedIn=True, UserName="test", TenantName="tenant")
    sdk.auth.login.return_value = [SimpleNamespace(Status="Success", Data=login_data)]
    return sdk


# ═══════════════════════════════════════════════════════════════════════════════
# DatahubShareManager tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestShareManagerInit:
    """Test constructor."""

    @patch("auto_shares_symlinks.CloudSDK")
    def test_init_creates_sdk(self, mock_sdk_cls):
        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        mock_sdk_cls.assert_called_once_with(cli_path="/cli")
        assert mgr.environment == "env"
        assert mgr._authenticated is False


class TestShareManagerAuthentication:
    """Tests for the authentication flow."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_auth_failure_raises(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        mock_get_data.return_value = SimpleNamespace(IsLoggedIn=False, UserName=None, TenantName=None)

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        with pytest.raises(RuntimeError, match="Authentication failed"):
            mgr._authenticate()

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_auth_only_called_once(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_shares.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Shares=[]),
            SimpleNamespace(Success=True, Shares=[]),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        mgr.list_shares()
        mgr.list_shares()

        sdk.auth.login.assert_called_once()


class TestShareManagerCreate:
    """Tests for the share-create subcommand."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.create_share(
            display_name="Test Share",
            remote_path="datasets/test",
            permissions=["cloud.api,tenant-abc-123,"],
            permissions_file_path=None,
        )

        assert result is True
        sdk.datahub.create_share.assert_called_once_with(
            display_name="Test Share",
            remote_path="datasets/test",
            permissions=["cloud.api,tenant-abc-123,"],
            permissions_file_path=None,
            print_message=False,
        )

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_with_permissions_file(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.create_share(
            display_name="File Share",
            remote_path="data/path",
            permissions=None,
            permissions_file_path="/path/to/perms.txt",
        )

        assert result is True
        _, kwargs = sdk.datahub.create_share.call_args
        assert kwargs["permissions_file_path"] == "/path/to/perms.txt"
        assert kwargs["permissions"] is None

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.create_share(display_name="x", remote_path="y")

        assert result is False

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_returns_false_when_data_is_none(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            None,
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.create_share(display_name="x", remote_path="y")

        assert result is False


class TestShareManagerList:
    """Tests for the share-list subcommand."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_list_returns_true_with_shares(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_shares.return_value = [SimpleNamespace(Status="Success")]

        perm = SimpleNamespace(PermissionId="p1", AllowedScope="Read", TenantId="t1", UserId="u1")
        share = SimpleNamespace(
            ShareId="share-abc", Name="My Share",
            RelativePath="datasets/shared", Permissions=[perm],
        )
        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Shares=[share]),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.list_shares()

        assert result is True

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_list_returns_true_when_empty(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_shares.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Shares=[]),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.list_shares()

        assert result is True

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_list_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_shares.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False, Shares=None),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.list_shares()

        assert result is False


class TestShareManagerDelete:
    """Tests for the share-delete subcommand."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_delete_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.delete_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.delete_share(share_id="share-abc-123")

        assert result is True
        sdk.datahub.delete_share.assert_called_once_with(
            share_id="share-abc-123",
            print_message=False,
        )

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_delete_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.delete_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False),
        ]

        mgr = DatahubShareManager(cli_path="/cli", environment="env")
        result = mgr.delete_share(share_id="bad-id")

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# DatahubSymlinkManager tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSymlinkManagerInit:
    """Test constructor."""

    @patch("auto_shares_symlinks.CloudSDK")
    def test_init_creates_sdk(self, mock_sdk_cls):
        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        mock_sdk_cls.assert_called_once_with(cli_path="/cli")
        assert mgr.environment == "env"
        assert mgr._authenticated is False


class TestSymlinkManagerAuthentication:
    """Tests for the authentication flow."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_auth_failure_raises(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        mock_get_data.return_value = SimpleNamespace(IsLoggedIn=False, UserName=None, TenantName=None)

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        with pytest.raises(RuntimeError, match="Authentication failed"):
            mgr._authenticate()

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_auth_only_called_once(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_symlinks.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Symlinks=[]),
            SimpleNamespace(Success=True, Symlinks=[]),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        mgr.list_symlinks()
        mgr.list_symlinks()

        sdk.auth.login.assert_called_once()


class TestSymlinkManagerCreateLocal:
    """Tests for local symlink creation."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_local_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_local_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.create_local_symlink(
            display_name="Local Link",
            target_remote_path="datasets/shared",
            symlink_path="my-project/data",
            symlink_type="Directory",
        )

        assert result is True
        sdk.datahub.create_local_symlink.assert_called_once_with(
            display_name="Local Link",
            target_remote_path="datasets/shared",
            symlink_path="my-project/data",
            symlink_type="Directory",
            print_message=False,
        )

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_local_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_local_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.create_local_symlink(
            display_name="x", target_remote_path="y",
            symlink_path="z", symlink_type="Directory",
        )

        assert result is False

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_local_returns_false_when_data_is_none(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_local_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            None,
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.create_local_symlink(
            display_name="x", target_remote_path="y",
            symlink_path="z", symlink_type="Directory",
        )

        assert result is False


class TestSymlinkManagerCreateCrossTenant:
    """Tests for cross-tenant symlink creation."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_cross_tenant_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.create_symlink(
            display_name="Cross Link",
            target_tenant_id="tenant-abc-123",
            target_remote_path="shared/data",
            symlink_path="my-project/partner",
            symlink_type="Directory",
        )

        assert result is True
        sdk.datahub.create_symlink.assert_called_once_with(
            display_name="Cross Link",
            target_tenant_id="tenant-abc-123",
            target_remote_path="shared/data",
            symlink_path="my-project/partner",
            symlink_type="Directory",
            print_message=False,
        )

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_create_cross_tenant_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.create_symlink(
            display_name="x", target_tenant_id="tid",
            target_remote_path="y", symlink_path="z", symlink_type="Directory",
        )

        assert result is False


class TestSymlinkManagerList:
    """Tests for the symlink-list subcommand."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_list_returns_true_with_symlinks(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_symlinks.return_value = [SimpleNamespace(Status="Success")]

        link = SimpleNamespace(
            DisplayName="My Link", SymlinkId="sym-123",
            Type="Local", TargetTenantId=None,
            RemotePath="datasets/shared", SymlinkPath="project/data",
        )
        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Symlinks=[link]),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.list_symlinks()

        assert result is True

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_list_returns_true_when_empty(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_symlinks.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Symlinks=[]),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.list_symlinks()

        assert result is True

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_list_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_symlinks.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False, Symlinks=None),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.list_symlinks()

        assert result is False

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_list_filters_by_path_prefix(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_symlinks.return_value = [SimpleNamespace(Status="Success")]

        match_link = SimpleNamespace(
            DisplayName="Match", SymlinkId="sym-1",
            Type="Directory", TargetTenantId=None,
            RemotePath="src", SymlinkPath="project/data/link",
        )
        no_match_link = SimpleNamespace(
            DisplayName="NoMatch", SymlinkId="sym-2",
            Type="Directory", TargetTenantId=None,
            RemotePath="src", SymlinkPath="other/data/link",
        )
        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Symlinks=[match_link, no_match_link]),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.list_symlinks(path_filter="project/")

        assert result is True


class TestSymlinkManagerDelete:
    """Tests for the symlink-delete subcommand."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_delete_calls_sdk_with_correct_kwargs(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.delete_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.delete_symlink(symlink_path="project/data")

        assert result is True
        sdk.datahub.delete_symlink.assert_called_once_with(
            symlink_path="project/data",
            print_message=False,
        )

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_delete_returns_false_on_failure(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.delete_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=False),
        ]

        mgr = DatahubSymlinkManager(cli_path="/cli", environment="env")
        result = mgr.delete_symlink(symlink_path="bad/path")

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# main() routing tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMain:
    """Tests for main() subcommand routing."""

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_share_create_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "share-create",
            "--cli-path", "/cli",
            "--environment", "env",
            "--display-name", "Test",
            "--remote-path", "data/path",
            "--permissions", "cloud.api,tenant-abc-123,",
        ]):
            result = MOD.main()

        assert result == 0
        sdk.datahub.create_share.assert_called_once()

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_share_list_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_shares.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Shares=[]),
        ]

        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "share-list",
            "--cli-path", "/cli",
            "--environment", "env",
        ]):
            result = MOD.main()

        assert result == 0

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_share_delete_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.delete_share.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "share-delete",
            "--cli-path", "/cli",
            "--environment", "env",
            "--share-id", "share-abc",
        ]):
            result = MOD.main()

        assert result == 0

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_symlink_create_local_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_local_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "symlink-create",
            "--cli-path", "/cli",
            "--environment", "env",
            "--local",
            "--display-name", "Link",
            "--target-remote-path", "datasets/x",
            "--symlink-path", "proj/data",
            "--symlink-type", "Directory",
        ]):
            result = MOD.main()

        assert result == 0
        sdk.datahub.create_local_symlink.assert_called_once_with(
            display_name="Link",
            target_remote_path="datasets/x",
            symlink_path="proj/data",
            symlink_type="Directory",
            print_message=False,
        )

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_symlink_create_cross_tenant_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.create_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "symlink-create",
            "--cli-path", "/cli",
            "--environment", "env",
            "--display-name", "Cross Link",
            "--target-tenant-id", "tenant-123",
            "--target-remote-path", "shared/data",
            "--symlink-path", "proj/partner",
            "--symlink-type", "Directory",
        ]):
            result = MOD.main()

        assert result == 0
        sdk.datahub.create_symlink.assert_called_once()

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_symlink_create_cross_tenant_requires_tenant_id(self, mock_sdk_cls, mock_get_data):
        """Cross-tenant symlink without --local and without --target-tenant-id should fail."""
        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "symlink-create",
            "--cli-path", "/cli",
            "--environment", "env",
            "--display-name", "Link",
            "--target-remote-path", "datasets/x",
            "--symlink-path", "proj/data",
            "--symlink-type", "Directory",
        ]):
            result = MOD.main()

        assert result == 1

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_symlink_list_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.list_symlinks.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True, Symlinks=[]),
        ]

        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "symlink-list",
            "--cli-path", "/cli",
            "--environment", "env",
        ]):
            result = MOD.main()

        assert result == 0

    @patch("auto_shares_symlinks.SDKBase.get_response_data")
    @patch("auto_shares_symlinks.CloudSDK")
    def test_main_symlink_delete_routes_correctly(self, mock_sdk_cls, mock_get_data):
        sdk = _make_sdk_mock()
        mock_sdk_cls.return_value = sdk
        sdk.datahub.delete_symlink.return_value = [SimpleNamespace(Status="Success")]

        mock_get_data.side_effect = [
            SimpleNamespace(IsLoggedIn=True, UserName="u", TenantName="t"),
            SimpleNamespace(Success=True),
        ]

        with patch("sys.argv", [
            "datahub_shares_symlinks.py", "symlink-delete",
            "--cli-path", "/cli",
            "--environment", "env",
            "--symlink-path", "proj/data",
        ]):
            result = MOD.main()

        assert result == 0

    def test_main_no_subcommand_exits(self):
        with patch("sys.argv", ["datahub_shares_symlinks.py"]):
            with pytest.raises(SystemExit) as exc_info:
                MOD.main()
            assert exc_info.value.code != 0
