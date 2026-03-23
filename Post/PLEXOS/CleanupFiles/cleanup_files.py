"""
Delete files or folders matching a pattern from a specified path.

Use this script to clean up temporary data after upload or between processing steps.
Supports wildcards, recursive deletion, and dry-run mode.

Environment variables used:
    output_path  – resolved when -p output_path is passed (optional)
"""
import os
import sys
import argparse
from pathlib import Path
import shutil


def cleanup_files(
    target_path: str,
    pattern: str,
    recursive: bool = False,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Delete files or folders matching a pattern.

    Args:
        target_path: Root directory to search.
        pattern:     Glob pattern (e.g., "*.csv", "temp_*", "Analysis_*").
        recursive:   Search subdirectories.
        dry_run:     Preview deletions without executing.

    Returns:
        (files_deleted, folders_deleted)
    """
    root = Path(target_path)
    if not root.exists():
        print(f"[ERROR] Path does not exist: {target_path}")
        return 0, 0

    glob_method = root.rglob if recursive else root.glob
    matches = list(glob_method(pattern))

    if not matches:
        print(f"[INFO] No matches found for pattern: {pattern}")
        return 0, 0

    files_deleted = 0
    folders_deleted = 0

    print(f"[{'DRY-RUN' if dry_run else 'DELETE'}] Found {len(matches)} match(es) for '{pattern}'")

    for item in matches:
        if item.is_file():
            size_kb = item.stat().st_size / 1024
            print(f"  [FILE] {item.relative_to(root)} ({size_kb:.1f} KB)")
            if not dry_run:
                item.unlink()
                files_deleted += 1
        elif item.is_dir():
            num_items = sum(1 for _ in item.rglob("*"))
            print(f"  [DIR]  {item.relative_to(root)}/ ({num_items} items)")
            if not dry_run:
                shutil.rmtree(item)
                folders_deleted += 1

    if dry_run:
        print("[DRY-RUN] No files were deleted. Remove --dry-run to execute.")
    else:
        print(f"[OK] Deleted {files_deleted} file(s), {folders_deleted} folder(s)")

    return files_deleted, folders_deleted


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Delete files or folders matching a pattern from a specified path.\n"
            "Use after upload or between processing steps to clean up temporary data."
        ),
        epilog=(
            "Examples:\n\n"
            "  Delete all CSV files in output_path (non-recursive):\n"
            "    python3 cleanup_files.py -p output_path -pt '*.csv'\n\n"
            "  Delete all Analysis_* folders recursively (dry-run first):\n"
            "    python3 cleanup_files.py -p output_path -pt 'Analysis_*' -r --dry-run\n"
            "    python3 cleanup_files.py -p output_path -pt 'Analysis_*' -r\n\n"
            "  Chain — convert, upload, cleanup:\n"
            "    python3 convert_csv_to_parquet.py -r output_path\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Study/Results -p '*.parquet'\n"
            "    python3 cleanup_files.py -p output_path -pt '*.csv' -r\n\n"
            "  Chain — analyse, upload, cleanup temp data:\n"
            "    python3 timeseries_comparison.py -f baseline.csv -f result.csv\n"
            "    python3 upload_to_datahub.py -l output_path -r Project/Analysis/Results\n"
            "    python3 cleanup_files.py -p output_path -pt 'Analysis_*' -r"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-p", "--path",
        required=True,
        help=(
            "Root directory to search. Pass 'output_path' to use the environment variable. "
            "Can also be an absolute or relative path."
        ),
    )
    parser.add_argument(
        "-pt", "--pattern",
        default="**/*",
        help=(
            "Glob pattern to match files/folders (e.g., '*.csv', 'temp_*', 'Analysis_*'). "
            "Use quotes to prevent shell expansion. Defaults to '**/*' (all files including subdirectories)."
        ),
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Search subdirectories recursively.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without actually deleting.",
    )
    args = parser.parse_args()

    # Resolve output_path if specified
    if args.path == "output_path":
        try:
            resolved_path = os.environ["output_path"]
        except KeyError:
            print("[ERROR] 'output_path' environment variable not found.")
            print("        Either provide an absolute/relative path or ensure output_path is set.")
            return 1
    else:
        resolved_path = args.path

    print(f"Target   : {resolved_path}")
    print(f"Pattern  : {args.pattern}")
    print(f"Recursive: {args.recursive}")
    print(f"Dry-run  : {args.dry_run}")
    print()

    if not Path(resolved_path).exists():
        print(f"[ERROR] Target path does not exist: {resolved_path}")
        return 1

    try:
        files_deleted, folders_deleted = cleanup_files(
            resolved_path,
            args.pattern,
            recursive=args.recursive,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[ERROR] Cleanup failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
