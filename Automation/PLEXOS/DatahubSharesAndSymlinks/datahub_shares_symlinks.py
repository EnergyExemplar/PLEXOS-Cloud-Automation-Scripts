"""
Create, list, and delete Datahub shares and symlinks.

Standalone script — all configuration is passed as CLI arguments.
All operations require interactive login via the CloudSDK.

Subcommands:
    share-create     Create a new file share for a dataset/folder path
    share-list       List existing shares and their recipients
    share-delete     Delete a file share
    symlink-create   Create a symbolic link pointing to a shared dataset
    symlink-list     List all symlinks
    symlink-delete   Delete a symbolic link
"""
import argparse
from eecloud.cloudsdk import CloudSDK, SDKBase


class DatahubShareManager:
    """Manages Datahub file shares — create, list, and delete (authenticated).

    Shares grant external parties access to datasets in your Datahub.
    Authentication is performed via interactive login (sdk.auth.login()).
    """

    def __init__(self, cli_path: str, environment: str):
        """
        Args:
            cli_path: Full path to the PLEXOS Cloud CLI executable.
            environment: Cloud environment name (e.g. 'preprod', 'production').
        """
        self.sdk = CloudSDK(cli_path=cli_path)
        self.environment = environment
        self._authenticated = False

    def _authenticate(self) -> None:
        """Authenticate with the specified environment via interactive login."""
        if self._authenticated:
            return

        self.sdk.environment.set_user_environment(self.environment)
        login_response = self.sdk.auth.login()
        login_data = SDKBase.get_response_data(login_response)

        if login_data is None or not login_data.IsLoggedIn:
            raise RuntimeError("Authentication failed.")

        print(f"[OK] Authenticated: {login_data.UserName} @ {login_data.TenantName}")
        self._authenticated = True

    def create_share(
        self,
        display_name: str,
        remote_path: str,
        permissions: list[str] | None = None,
        permissions_file_path: str | None = None,
    ) -> bool:
        """
        Create a new file share for a dataset/folder path.

        Args:
            display_name: Human-readable name for the share.
            remote_path: Datahub relative path to share.
            permissions: Optional list of CSV permission strings
                (e.g. ['cloud.api,<TenantId>,<UserId>']).
            permissions_file_path: Optional path to a file containing permissions.

        Returns:
            True if the share was created successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.create_share(
            display_name=display_name,
            remote_path=remote_path,
            permissions=permissions,
            permissions_file_path=permissions_file_path,
            print_message=False,
        )

        data = SDKBase.get_response_data(response)

        if data is None:
            msg = getattr(response[0], "Message", "Unknown error") if response else "No response"
            print(f"[FAIL] Failed to create share '{display_name}': {msg}")
            return False

        if not data.Success:
            print(f"[FAIL] Failed to create share '{display_name}'.")
            return False

        print(f"[OK] Share created: '{display_name}' -> {remote_path}")
        return True

    def list_shares(self) -> bool:
        """
        List all file shares.

        Returns:
            True if the list was retrieved successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.list_shares(print_message=False)
        data = SDKBase.get_response_data(response)

        if data is None or not data.Success:
            print("[FAIL] Failed to retrieve shares.")
            return False

        if not data.Shares:
            print("[OK] No shares found.")
            return True

        print(f"\n{'ShareId':<38} {'Name':<30} {'Path':<40} {'Permissions'}")
        print("-" * 140)
        for share in data.Shares:
            perm_count = len(share.Permissions) if share.Permissions else 0
            print(
                f"{share.ShareId or '':<38} "
                f"{(share.Name or '')[:30]:<30} "
                f"{(share.RelativePath or '')[:40]:<40} "
                f"{perm_count} permission(s)"
            )
            if share.Permissions:
                for perm in share.Permissions:
                    scope = perm.AllowedScope or "N/A"
                    tenant = perm.TenantId or ""
                    user = perm.UserId or ""
                    print(f"  \u2514\u2500 Scope: {scope}  Tenant: {tenant}  User: {user}")

        print(f"\n[OK] {len(data.Shares)} share(s) found.")
        return True

    def delete_share(self, share_id: str) -> bool:
        """
        Delete a file share.

        Args:
            share_id: The share ID (GUID) to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.delete_share(
            share_id=share_id,
            print_message=False,
        )

        data = SDKBase.get_response_data(response)

        if data is None:
            msg = getattr(response[0], "Message", "Unknown error") if response else "No response"
            print(f"[FAIL] Failed to delete share '{share_id}': {msg}")
            return False

        if not data.Success:
            print(f"[FAIL] Failed to delete share '{share_id}'.")
            return False

        print(f"[OK] Share deleted: {share_id}")
        return True


class DatahubSymlinkManager:
    """Manages Datahub symbolic links — create, list, and delete (authenticated).

    Symlinks reference shared datasets within a study or workflow.
    Supports both local symlinks (same tenant) and cross-tenant symlinks.
    Authentication is performed via interactive login (sdk.auth.login()).
    """

    def __init__(self, cli_path: str, environment: str):
        """
        Args:
            cli_path: Full path to the PLEXOS Cloud CLI executable.
            environment: Cloud environment name (e.g. 'preprod', 'production').
        """
        self.sdk = CloudSDK(cli_path=cli_path)
        self.environment = environment
        self._authenticated = False

    def _authenticate(self) -> None:
        """Authenticate with the specified environment via interactive login."""
        if self._authenticated:
            return

        self.sdk.environment.set_user_environment(self.environment)
        login_response = self.sdk.auth.login()
        login_data = SDKBase.get_response_data(login_response)

        if login_data is None or not login_data.IsLoggedIn:
            raise RuntimeError("Authentication failed.")

        print(f"[OK] Authenticated: {login_data.UserName} @ {login_data.TenantName}")
        self._authenticated = True

    def create_local_symlink(
        self,
        display_name: str,
        target_remote_path: str,
        symlink_path: str,
        symlink_type: str,
    ) -> bool:
        """
        Create a local symbolic link (same tenant).

        Args:
            display_name: Human-readable name for the symlink.
            target_remote_path: Datahub path the symlink points to.
            symlink_path: Path where the symlink will be created.
            symlink_type: Symlink type ('File' or 'Directory').

        Returns:
            True if the symlink was created successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.create_local_symlink(
            display_name=display_name,
            target_remote_path=target_remote_path,
            symlink_path=symlink_path,
            symlink_type=symlink_type,
            print_message=False,
        )

        data = SDKBase.get_response_data(response)

        if data is None:
            msg = getattr(response[0], "Message", "Unknown error") if response else "No response"
            print(f"[FAIL] Failed to create local symlink '{display_name}': {msg}")
            return False

        if not data.Success:
            print(f"[FAIL] Failed to create local symlink '{display_name}'.")
            return False

        print(f"[OK] Local symlink created: '{display_name}' @ {symlink_path} -> {target_remote_path}")
        return True

    def create_symlink(
        self,
        display_name: str,
        target_tenant_id: str,
        target_remote_path: str,
        symlink_path: str,
        symlink_type: str,
    ) -> bool:
        """
        Create a cross-tenant symbolic link.

        Args:
            display_name: Human-readable name for the symlink.
            target_tenant_id: Tenant ID of the share owner.
            target_remote_path: Datahub path in the target tenant.
            symlink_path: Path where the symlink will be created.
            symlink_type: Symlink type ('File' or 'Directory').

        Returns:
            True if the symlink was created successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.create_symlink(
            display_name=display_name,
            target_tenant_id=target_tenant_id,
            target_remote_path=target_remote_path,
            symlink_path=symlink_path,
            symlink_type=symlink_type,
            print_message=False,
        )

        data = SDKBase.get_response_data(response)

        if data is None:
            msg = getattr(response[0], "Message", "Unknown error") if response else "No response"
            print(f"[FAIL] Failed to create cross-tenant symlink '{display_name}': {msg}")
            return False

        if not data.Success:
            print(f"[FAIL] Failed to create cross-tenant symlink '{display_name}'.")
            return False

        print(f"[OK] Cross-tenant symlink created: '{display_name}' @ {symlink_path} -> {target_tenant_id}:{target_remote_path}")
        return True

    def list_symlinks(self, path_filter: str = None) -> bool:
        """
        List symbolic links, optionally filtered by symlink path prefix.

        Args:
            path_filter: Only show symlinks whose SymlinkPath starts with this value.

        Returns:
            True if the list was retrieved successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.list_symlinks(print_message=False)
        data = SDKBase.get_response_data(response)

        if data is None or not data.Success:
            print("[FAIL] Failed to retrieve symlinks.")
            return False

        symlinks = data.Symlinks or []

        if path_filter:
            symlinks = [
                lnk for lnk in symlinks
                if (lnk.SymlinkPath or "").startswith(path_filter)
            ]

        if not symlinks:
            msg = f"No symlinks found under path '{path_filter}'." if path_filter else "No symlinks found."
            print(f"[OK] {msg}")
            return True

        print(f"\n{'DisplayName':<25} {'SymlinkId':<38} {'Type':<10} {'TargetTenantId':<38} {'RemotePath':<30} {'SymlinkPath'}")
        print("-" * 180)
        for link in symlinks:
            print(
                f"{(link.DisplayName or '')[:25]:<25} "
                f"{link.SymlinkId or '':<38} "
                f"{link.Type or ''!s:<10} "
                f"{link.TargetTenantId or '':<38} "
                f"{(link.RemotePath or '')[:30]:<30} "
                f"{link.SymlinkPath or ''}"
            )

        print(f"\n[OK] {len(symlinks)} symlink(s) found.")
        return True

    def delete_symlink(self, symlink_path: str) -> bool:
        """
        Delete a symbolic link.

        Args:
            symlink_path: The path of the symlink to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.delete_symlink(
            symlink_path=symlink_path,
            print_message=False,
        )

        data = SDKBase.get_response_data(response)

        if data is None:
            msg = getattr(response[0], "Message", "Unknown error") if response else "No response"
            print(f"[FAIL] Failed to delete symlink '{symlink_path}': {msg}")
            return False

        if not data.Success:
            print(f"[FAIL] Failed to delete symlink '{symlink_path}'.")
            return False

        print(f"[OK] Symlink deleted: {symlink_path}")
        return True


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with share and symlink subcommands."""
    parser = argparse.ArgumentParser(
        description="Create, list, and delete Datahub shares and symlinks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── share-create ────────────────────────────────────────────────────────
    sc = subparsers.add_parser(
        "share-create",
        help="Create a new file share for a dataset/folder path",
    )
    sc.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    sc.add_argument("--environment", required=True, help="Cloud environment name")
    sc.add_argument("--display-name", required=True, help="Human-readable name for the share")
    sc.add_argument("--remote-path", required=True, help="Datahub relative path to share")
    sc.add_argument("--permissions", nargs="+", default=None, help="One or more permission strings in CSV format 'AllowedScope,TenantId,UserId'. UserId is optional (use trailing comma for tenant-wide access, e.g. 'Read,<TenantId>,')")
    sc.add_argument("--permissions-file", default=None, help="Path to a file containing permissions")

    # ── share-list ──────────────────────────────────────────────────────────
    sl = subparsers.add_parser(
        "share-list",
        help="List existing shares and their recipients",
    )
    sl.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    sl.add_argument("--environment", required=True, help="Cloud environment name")

    # ── share-delete ────────────────────────────────────────────────────────
    sd = subparsers.add_parser(
        "share-delete",
        help="Delete a file share",
    )
    sd.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    sd.add_argument("--environment", required=True, help="Cloud environment name")
    sd.add_argument("--share-id", required=True, help="Share ID (GUID) to delete")

    # ── symlink-create ──────────────────────────────────────────────────────
    lc = subparsers.add_parser(
        "symlink-create",
        help="Create a symbolic link pointing to a shared dataset",
    )
    lc.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    lc.add_argument("--environment", required=True, help="Cloud environment name")
    lc.add_argument("--display-name", required=True, help="Human-readable name for the symlink")
    lc.add_argument("--target-remote-path", required=True, help="Datahub path the symlink points to")
    lc.add_argument("--symlink-path", required=True, help="Path where the symlink will be created")
    lc.add_argument("--symlink-type", required=True, choices=["File", "Directory"], help="Symlink type: 'File' or 'Directory'. Note: SDK docs show 'Local' but the CLI only accepts 'File' or 'Directory'")
    lc.add_argument("--local", action="store_true", help="Create a local symlink (same tenant)")
    lc.add_argument("--target-tenant-id", default=None, help="Target tenant ID (required for cross-tenant symlinks)")

    # ── symlink-list ────────────────────────────────────────────────────────
    ll = subparsers.add_parser(
        "symlink-list",
        help="List all symlinks",
    )
    ll.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    ll.add_argument("--environment", required=True, help="Cloud environment name")
    ll.add_argument("--path-filter", default=None, help="Only show symlinks whose SymlinkPath starts with this value")

    # ── symlink-delete ──────────────────────────────────────────────────────
    ld = subparsers.add_parser(
        "symlink-delete",
        help="Delete a symbolic link",
    )
    ld.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    ld.add_argument("--environment", required=True, help="Cloud environment name")
    ld.add_argument("--symlink-path", required=True, help="Path of the symlink to delete")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "share-create":
            mgr = DatahubShareManager(cli_path=args.cli_path, environment=args.environment)
            success = mgr.create_share(
                display_name=args.display_name,
                remote_path=args.remote_path,
                permissions=args.permissions,
                permissions_file_path=args.permissions_file,
            )

        elif args.command == "share-list":
            mgr = DatahubShareManager(cli_path=args.cli_path, environment=args.environment)
            success = mgr.list_shares()

        elif args.command == "share-delete":
            mgr = DatahubShareManager(cli_path=args.cli_path, environment=args.environment)
            success = mgr.delete_share(share_id=args.share_id)

        elif args.command == "symlink-create":
            sym = DatahubSymlinkManager(cli_path=args.cli_path, environment=args.environment)
            if args.local:
                success = sym.create_local_symlink(
                    display_name=args.display_name,
                    target_remote_path=args.target_remote_path,
                    symlink_path=args.symlink_path,
                    symlink_type=args.symlink_type,
                )
            else:
                if not args.target_tenant_id:
                    print("[FAIL] --target-tenant-id is required for cross-tenant symlinks. Use --local for same-tenant.")
                    return 1
                success = sym.create_symlink(
                    display_name=args.display_name,
                    target_tenant_id=args.target_tenant_id,
                    target_remote_path=args.target_remote_path,
                    symlink_path=args.symlink_path,
                    symlink_type=args.symlink_type,
                )

        elif args.command == "symlink-list":
            sym = DatahubSymlinkManager(cli_path=args.cli_path, environment=args.environment)
            success = sym.list_symlinks(path_filter=args.path_filter)

        elif args.command == "symlink-delete":
            sym = DatahubSymlinkManager(cli_path=args.cli_path, environment=args.environment)
            success = sym.delete_symlink(symlink_path=args.symlink_path)

        else:
            parser.print_help()
            return 1

        return 0 if success else 1

    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
