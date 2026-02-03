#!/usr/bin/env python3
"""
File Finder - Recursively search for files and folders by name.
"""

import argparse
import os
import fnmatch
from pathlib import Path


def find_files(
    root: Path,
    filename: str,
    case_sensitive: bool = False,
    pattern_match: bool = False,
    find_type: str = "both",  # "files", "dirs", or "both"
) -> list[Path]:
    """
    Recursively search for files and/or folders matching a name.

    Args:
        root: Directory to search from
        filename: Name to search for (or pattern if pattern_match=True)
        case_sensitive: Whether to match case exactly
        pattern_match: Whether to use glob/fnmatch patterns (e.g., *.txt)
        find_type: What to find - "files", "dirs", or "both"

    Returns:
        List of matching paths
    """
    matches = []
    search_name = filename if case_sensitive else filename.lower()

    # Skip directories that slow things down
    skip_dirs = {".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv"}

    for dirpath, dirnames, filenames in os.walk(root):
        # Check directory names before filtering them out
        if find_type in ("dirs", "both"):
            for name in dirnames:
                if name in skip_dirs:
                    continue
                compare_name = name if case_sensitive else name.lower()

                if pattern_match:
                    if fnmatch.fnmatch(compare_name, search_name):
                        matches.append(Path(dirpath) / name)
                else:
                    if compare_name == search_name:
                        matches.append(Path(dirpath) / name)

        # Filter out skip directories for recursion
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        # Check file names
        if find_type in ("files", "both"):
            for name in filenames:
                compare_name = name if case_sensitive else name.lower()

                if pattern_match:
                    if fnmatch.fnmatch(compare_name, search_name):
                        matches.append(Path(dirpath) / name)
                else:
                    if compare_name == search_name:
                        matches.append(Path(dirpath) / name)

    return sorted(matches)


def main():
    parser = argparse.ArgumentParser(
        description="Recursively search for files and folders by name",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s config.yaml                      # Find all config.yaml files/folders
  %(prog)s cli --root /path/to/repo         # Find files or folders named "cli"
  %(prog)s "*.json" --pattern               # Find all JSON files
  %(prog)s src --dirs-only                  # Find only folders named "src"
  %(prog)s README.md --files-only           # Find only files named README.md
  %(prog)s Makefile --case-sensitive        # Case-sensitive search
        """,
    )

    parser.add_argument("filename", help="Filename or folder name to search for (or pattern with --pattern)")

    parser.add_argument(
        "--root", "-r",
        type=Path,
        default=Path.cwd(),
        help="Directory to search (default: current directory)",
    )

    parser.add_argument(
        "--pattern", "-p",
        action="store_true",
        help="Treat filename as a glob pattern (e.g., *.txt, test_*.py)",
    )

    parser.add_argument(
        "--case-sensitive", "-c",
        action="store_true",
        help="Match case exactly (default: case-insensitive)",
    )

    parser.add_argument(
        "--absolute", "-a",
        action="store_true",
        help="Show absolute paths (default: relative to root)",
    )

    parser.add_argument(
        "--files-only", "-f",
        action="store_true",
        help="Search for files only (ignore folders)",
    )

    parser.add_argument(
        "--dirs-only", "-d",
        action="store_true",
        help="Search for folders/directories only (ignore files)",
    )

    args = parser.parse_args()

    if not args.root.exists():
        print(f"Error: Path does not exist: {args.root}")
        return 1

    if not args.root.is_dir():
        print(f"Error: Not a directory: {args.root}")
        return 1

    # Determine find type
    if args.files_only and args.dirs_only:
        print("Error: Cannot use both --files-only and --dirs-only")
        return 1
    elif args.files_only:
        find_type = "files"
    elif args.dirs_only:
        find_type = "dirs"
    else:
        find_type = "both"

    matches = find_files(
        root=args.root.resolve(),
        filename=args.filename,
        case_sensitive=args.case_sensitive,
        pattern_match=args.pattern,
        find_type=find_type,
    )

    if not matches:
        print(f"No files or folders found matching: {args.filename}")
        return 1

    print(f"Found {len(matches)} match(es):\n")
    for path in matches:
        # Add indicator for directories
        suffix = "/" if path.is_dir() else ""
        if args.absolute:
            print(f"{path}{suffix}")
        else:
            try:
                print(f"{path.relative_to(args.root.resolve())}{suffix}")
            except ValueError:
                print(f"{path}{suffix}")

    return 0


if __name__ == "__main__":
    exit(main())
