"""
Create, list, download, and delete Datahub deep links.

Standalone script — all configuration is passed as CLI arguments.
Authenticated operations (create, list, delete) require interactive login.
Download uses a pre-signed URL and signature — no authentication needed.

Subcommands:
    create    Create a new deep link for a Datahub file or folder
    list      List deep links created by the current user
    download  Download a file via deep link (no authentication)
    delete    Revoke a deep link, making it immediately inactive
"""
import argparse
import sys
from pathlib import Path
from eecloud.cloudsdk import CloudSDK, SDKBase


class DatahubDeepLinkManager:
    """Manages Datahub deep links — create, list, and delete (authenticated).

    Authentication is performed via interactive login (sdk.auth.login()).
    The user must have access to the target environment and Datahub resources.
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

    def create(
        self,
        path: str,
        link_type: str,
        days: int | None = None,
        hours: int | None = None,
        expiry: str | None = None,
        limit: int | None = None,
    ) -> bool:
        """
        Create a new deep link for a Datahub resource.

        Args:
            path: Datahub relative path to the resource.
            link_type: Resource type — 'File' or 'Folder'.
            days: Link validity in days (from now).
            hours: Link validity in hours (from now).
            expiry: Exact expiry time (ISO 8601 UTC).
            limit: Maximum download count.

        Returns:
            True if the deep link was created successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.create_deep_link(
            path=path,
            type=link_type,
            days=days,
            hours=hours,
            expiry=expiry,
            limit=limit,
            print_message=False,
        )

        if response and hasattr(response[0], "Status") and response[0].Status == "Failed":
            msg = getattr(response[0], "Message", "Unknown error")
            print(f"[FAIL] {msg}")
            return False

        data = SDKBase.get_response_data(response)

        if data is None or not data.Success:
            print("[FAIL] Failed to create deep link.")
            return False

        print("\n" + "=" * 70)
        print("  DEEP LINK CREATED SUCCESSFULLY")
        print("=" * 70)
        print(f"  URL ID       : {data.UrlId}")
        print(f"  Path         : {data.RelativePath}")
        print(f"  Download URL : {data.DownloadUrl}")
        print(f"  Expires      : {data.DeepLinkEndTimeUtc}")
        if data.MaximumDownloads:
            print(f"  Max Downloads: {data.MaximumDownloads}")
        print()
        print("  *** SIGNATURE (shown ONCE — store it securely) ***")
        print(f"  {data.Signature}")
        print()
        print("  cURL Command:")
        print(f"  {data.CurlCommand}")
        print("=" * 70)
        return True

    def list_deep_links(self) -> bool:
        """
        List all deep links created by the current user.

        Returns:
            True if the list was retrieved successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.list_deep_links(print_message=False)
        data = SDKBase.get_response_data(response)

        if data is None or not data.Success:
            print("[FAIL] Failed to retrieve deep links.")
            return False

        if not data.DeepLinks:
            print("[OK] No deep links found.")
            return True

        print(f"\n{'UrlId':<38} {'Path':<40} {'Type':<8} {'Active':<8} {'Expired':<9} {'Downloads':<11} {'Expires'}")
        print("-" * 160)
        for link in data.DeepLinks:
            active = '' if link.IsActive is None else str(link.IsActive)
            expired = '' if link.IsExpired is None else str(link.IsExpired)
            print(
                f"{link.UrlId or '':<38} "
                f"{(link.RelativePath or '')[:40]:<40} "
                f"{link.UrlType or ''!s:<8} "
                f"{active:<8} "
                f"{expired:<9} "
                f"{link.CompletedDownloads or 0:<11} "
                f"{link.DeepLinkEndTimeUtc or ''}"
            )

        print(f"\n[OK] {len(data.DeepLinks)} deep link(s) found.")
        return True

    def delete(self, url_id: str) -> bool:
        """
        Revoke a deep link, making it immediately inactive.

        Args:
            url_id: The deep link URL ID (GUID) to revoke.

        Returns:
            True if revoked successfully, False otherwise.
        """
        self._authenticate()

        response = self.sdk.datahub.revoke_deep_link(id=url_id, print_message=False)
        data = SDKBase.get_response_data(response)

        if data is None or not data.Success:
            print(f"[FAIL] Failed to revoke deep link '{url_id}'.")
            return False

        print(f"[OK] Deep link revoked: {data.UrlId}")
        return True


class DeepLinkDownloader:
    """Downloads files via Datahub deep link — no authentication required.

    Uses the pre-signed download URL and signature provided when the deep link
    was created. No login or environment setup is needed.
    """

    def __init__(self, cli_path: str):
        """
        Args:
            cli_path: Full path to the PLEXOS Cloud CLI executable.
        """
        self.sdk = CloudSDK(cli_path=cli_path)

    def download(
        self,
        download_url: str,
        signature: str,
        output_dir: str,
        internal_file_path: str | None = None,
    ) -> bool:
        """
        Download a file using a deep link.

        Args:
            download_url: The full download URL from the deep link creation response.
            signature: The X-DeepLink-Signature value (shown once at creation).
            output_dir: Local directory to save the downloaded file.
            internal_file_path: For folder-type deep links, the relative path to
                                a specific file within the shared folder.

        Returns:
            True if download succeeded, False otherwise.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        response = self.sdk.datahub.download_deep_link(
            url=download_url,
            signature=signature,
            output=output_dir,
            file_path=internal_file_path,
            print_message=False,
        )

        if response and hasattr(response[0], "Status") and response[0].Status == "Failed":
            msg = getattr(response[0], "Message", "Unknown error")
            print(f"[FAIL] {msg}")
            return False

        data = SDKBase.get_response_data(response)

        if data is None:
            print("[FAIL] Download returned no response data.")
            return False

        if not data.Success:
            print("[FAIL] Download was not successful.")
            return False

        print(f"[OK] Downloaded: {data.FileName}")
        print(f"     Saved to : {data.FilePath}")
        print(f"     Size     : {data.FileSize:,} bytes")
        return True


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with create, list, download, and delete subcommands."""
    parser = argparse.ArgumentParser(
        description="Create, list, download, and delete Datahub deep links.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── create ──────────────────────────────────────────────────────────────
    create_parser = subparsers.add_parser(
        "create",
        help="Create a new deep link for a Datahub resource",
    )
    create_parser.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    create_parser.add_argument("--environment", required=True, help="Cloud environment name")
    create_parser.add_argument("--path", required=True, help="Datahub relative path to the resource")
    create_parser.add_argument("--type", required=True, choices=["File", "Folder"], help="Resource type")
    create_parser.add_argument("--days", type=int, default=None, help="Link validity in days")
    create_parser.add_argument("--hours", type=int, default=None, help="Link validity in hours")
    create_parser.add_argument("--expiry", default=None, help="Exact expiry time (ISO 8601 UTC)")
    create_parser.add_argument("--limit", type=int, default=None, help="Maximum download count")

    # ── list ────────────────────────────────────────────────────────────────
    list_parser = subparsers.add_parser(
        "list",
        help="List deep links created by the current user",
    )
    list_parser.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    list_parser.add_argument("--environment", required=True, help="Cloud environment name")

    # ── download ────────────────────────────────────────────────────────────
    download_parser = subparsers.add_parser(
        "download",
        help="Download a file via deep link (no authentication required)",
    )
    download_parser.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    download_parser.add_argument("--download-url", required=True, help="The full download URL from deep link creation")
    download_parser.add_argument("--signature", required=True, help="The X-DeepLink-Signature value")
    download_parser.add_argument("--output-dir", required=True, help="Local directory to save downloaded file(s)")
    download_parser.add_argument(
        "--internal-file-path",
        default=None,
        help="For folder deep links: relative path to a file within the shared folder",
    )

    # ── delete ──────────────────────────────────────────────────────────────
    delete_parser = subparsers.add_parser(
        "delete",
        help="Revoke a deep link, making it immediately inactive",
    )
    delete_parser.add_argument("--cli-path", required=True, help="Path to PLEXOS Cloud CLI executable")
    delete_parser.add_argument("--environment", required=True, help="Cloud environment name")
    delete_parser.add_argument("--id", required=True, help="Deep link URL ID (GUID) to revoke")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "create":
            if not args.days and not args.hours and not args.expiry:
                print("[FAIL] At least one of --days, --hours, or --expiry is required.")
                return 1
            manager = DatahubDeepLinkManager(cli_path=args.cli_path, environment=args.environment)
            success = manager.create(
                path=args.path,
                link_type=args.type,
                days=args.days,
                hours=args.hours,
                expiry=args.expiry,
                limit=args.limit,
            )

        elif args.command == "list":
            manager = DatahubDeepLinkManager(cli_path=args.cli_path, environment=args.environment)
            success = manager.list_deep_links()

        elif args.command == "download":
            downloader = DeepLinkDownloader(cli_path=args.cli_path)
            success = downloader.download(
                download_url=args.download_url,
                signature=args.signature,
                output_dir=args.output_dir,
                internal_file_path=args.internal_file_path,
            )

        elif args.command == "delete":
            manager = DatahubDeepLinkManager(cli_path=args.cli_path, environment=args.environment)
            success = manager.delete(url_id=args.id)

        else:
            parser.print_help()
            return 1

        return 0 if success else 1

    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
