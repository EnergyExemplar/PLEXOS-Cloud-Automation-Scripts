"""
Download all solutions for a given execution ID.

Standalone script — all configuration is passed as CLI arguments.
"""

import argparse
import sys
from pathlib import Path
from eecloud.cloudsdk import CloudSDK, SDKBase


# ═══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION — These defaults apply when the corresponding CLI flag is omitted.
# ═══════════════════════════════════════════════════════════════════════════════

# Solution type to download
# Example: "Raw" or "Standard"
SOLUTION_TYPE = "Raw"

# ═══════════════════════════════════════════════════════════════════════════════
# END OF USER CONFIGURATION — No changes needed below this line.
# ═══════════════════════════════════════════════════════════════════════════════


def authenticate(
    sdk: CloudSDK,
    environment: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Authenticate with the specified environment.

    If client_id, client_secret, and tenant_id are all provided, authenticates
    using client credentials. Otherwise falls back to interactive SSO login.
    """
    print(f"[ENV] Setting cloud environment: {environment}")
    env_response = sdk.environment.set_user_environment(environment)
    env_data = SDKBase.get_response_data(env_response)
    if env_data is None:
        message = (
            env_response[0].Message
            if isinstance(env_response, list) and env_response
            else getattr(env_response, "Message", None)
        ) or "Unknown error while setting user environment"
        raise RuntimeError(
            f"Failed to set user environment '{environment}': {message}"
        )
    print(f"[OK] Selected Environment: {env_data.Environment}")

    use_client_credentials = bool(client_id and client_secret and tenant_id)

    if use_client_credentials:
        print("[AUTH] Logging in with client credentials...")
        login_response = sdk.auth.login_client_credentials(
            use_client_credentials=True,
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
        )
    else:
        print("[AUTH] Logging in via SSO...")
        login_response = sdk.auth.login()

    login_data = SDKBase.get_response_data(login_response)
    if login_data is None:
        message = (
            login_response[0].Message
            if isinstance(login_response, list) and login_response
            else getattr(login_response, "Message", None)
        ) or "Unknown error during login"
        raise RuntimeError(f"Login failed: {message}")
    print(f"[OK] Tenant: {login_data.TenantName}, User: {login_data.UserName}")


def list_solution_ids(sdk: CloudSDK, execution_id: str) -> dict[str, str]:
    """
    List all solution IDs for the given execution ID.

    Queries simulations for the execution and extracts ModelIdentifiers
    (solution IDs) from simulation records that have them.

    Args:
        sdk: Authenticated CloudSDK instance
        execution_id: The execution ID to query simulations for

    Returns:
        Dict mapping solution ID → model name
    """
    print(f"[LIST] Fetching simulations for execution: {execution_id}")
    sim_resp = sdk.simulation.list_simulations(execution_id=execution_id)
    sim_data = SDKBase.get_response_data(sim_resp)

    if sim_data is None or not sim_data.SimulationRecords:
        raise RuntimeError(
            f"No simulations found for execution_id={execution_id}. "
            "Verify the execution ID and ensure simulations have run."
        )

    print(f"[OK] Found {len(sim_data.SimulationRecords)} simulation(s)")

    solution_ids: dict[str, str] = {}
    for sim in sim_data.SimulationRecords:
        sim_id = sim.Id.Value if hasattr(sim.Id, "Value") else str(sim.Id)
        print(f"  Simulation: {sim_id}  Status: {sim.Status}")
        if sim.ModelIdentifiers:
            for mi in sim.ModelIdentifiers:
                if mi.Name and mi.Id:
                    print(f"    [OK] Model: {mi.Name} -> SolutionId: {mi.Id}")
                    solution_ids[mi.Id] = mi.Name
        else:
            print("    [WARN] No ModelIdentifiers — simulation may not be complete")

    return solution_ids


def download_solution(
    sdk: CloudSDK,
    solution_id: str,
    output_directory: Path,
    solution_type: str = "Raw",
) -> bool:
    """
    Download a single solution to a local directory.

    Args:
        sdk: Authenticated CloudSDK instance
        solution_id: The solution ID to download
        output_directory: Local directory to save the solution files
        solution_type: Solution type (e.g. 'Raw', 'Standard')

    Returns:
        True if the download succeeded, False otherwise
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    print(f"[DOWNLOAD] solution_id={solution_id} -> {output_directory}")

    response = sdk.solution.download_solution(
        solution_id=solution_id,
        output_directory=str(output_directory),
        solution_type=solution_type,
    )

    data = SDKBase.get_response_data(response)
    if data is None:
        message = (
            response[0].Message
            if isinstance(response, list) and response
            else getattr(response, "Message", None)
        ) or f"Unknown error while downloading solution '{solution_id}'"
        print(f"[FAIL] Download failed for solution {solution_id}: {message}")
        return False

    if data.IsDownloadSuccessful:
        file_count = len(data.files) if data.files is not None else 0
        print(f"[OK] Downloaded {file_count} file(s) for solution {solution_id}")
        return True

    print(f"[FAIL] Download failed for solution {solution_id} (IsDownloadSuccessful=False)")
    return False


def download_all(
    sdk: CloudSDK,
    execution_id: str,
    output_dir: Path,
    solution_type: str = "Raw",
) -> bool:
    """
    List and download all solutions for an execution ID.

    Each solution is downloaded into a subdirectory named by its solution ID
    under output_dir.

    Args:
        sdk: Authenticated CloudSDK instance
        execution_id: The execution ID to download solutions for
        output_dir: Root local directory; each solution goes in a subfolder
        solution_type: Solution type passed to download_solution

    Returns:
        True if all solutions downloaded successfully, False if any failed
    """
    solution_ids = list_solution_ids(sdk, execution_id)

    if not solution_ids:
        print("[FAIL] No solution IDs found. Ensure simulations have completed successfully.")
        return False

    print(f"\n[START] Downloading {len(solution_ids)} solution(s) to: {output_dir}")
    all_ok = True
    for solution_id, model_name in solution_ids.items():
        sol_dir = output_dir / solution_id
        print(f"\n[DOWNLOAD] Model: {model_name} ({solution_id})")
        success = download_solution(
            sdk=sdk,
            solution_id=solution_id,
            output_directory=sol_dir,
            solution_type=solution_type,
        )
        if not success:
            all_ok = False

    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download all solutions for a given execution ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_solutions.py -c /usr/local/bin/plexos-cloud -e prod \\
    -x <execution-id> -o ./solutions

  python download_solutions.py -c /usr/local/bin/plexos-cloud -e prod \\
    -x <execution-id> -o ./solutions --solution-type Standard
        """,
    )

    parser.add_argument(
        "-c", "--cli-path",
        required=True,
        help="Full path to PLEXOS Cloud CLI executable",
    )
    parser.add_argument(
        "-e", "--environment",
        required=True,
        help="Cloud environment name (contact your Energy Exemplar administrator)",
    )
    parser.add_argument(
        "-x", "--execution-id",
        required=True,
        help="Execution ID to download solutions for",
    )
    parser.add_argument(
        "-o", "--output-dir",
        required=True,
        help="Local root directory; each solution is saved in a subfolder named by its solution ID",
    )
    parser.add_argument(
        "-t", "--solution-type",
        default=SOLUTION_TYPE,
        help="Solution type to download (default: Raw)",
    )
    parser.add_argument(
        "--client-id",
        help="Client ID for client-credentials login (optional; if omitted, SSO login is used)",
    )
    parser.add_argument(
        "--client-secret",
        help="Client secret for client-credentials login (optional; if omitted, SSO login is used)",
    )
    parser.add_argument(
        "--tenant-id",
        help="Tenant ID for client-credentials login (optional; if omitted, SSO login is used)",
    )

    args = parser.parse_args()

    try:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[START] Downloading solutions for execution: {args.execution_id}")
        print(f"[OUTPUT] Local directory: {output_dir.absolute()}")

        sdk = CloudSDK(cli_path=args.cli_path)
        authenticate(
            sdk,
            args.environment,
            client_id=args.client_id,
            client_secret=args.client_secret,
            tenant_id=args.tenant_id,
        )

        success = download_all(
            sdk=sdk,
            execution_id=args.execution_id,
            output_dir=output_dir,
            solution_type=args.solution_type,
        )

        if success:
            print("\n[OK] All solutions downloaded successfully.")
            return 0

        print("\n[FAIL] One or more solutions failed to download.")
        return 1

    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
