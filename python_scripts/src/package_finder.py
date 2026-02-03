#!/usr/bin/env python3
"""
Package Finder - Search massive repositories for packages by name.

This script efficiently searches large repositories for packages/namespaces
in Python, C#, or Perl, finding both source definitions and usage locations.
"""

import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class PackageMatch:
    """Represents a found package or usage location."""

    path: Path
    match_type: str  # 'definition', 'import', 'usage'
    line_number: int | None = None
    line_content: str | None = None


@dataclass
class SearchResult:
    """Aggregated search results for a package."""

    package_name: str
    language: str
    definitions: list[PackageMatch] = field(default_factory=list)
    imports: list[PackageMatch] = field(default_factory=list)
    usages: list[PackageMatch] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.definitions or self.imports or self.usages)


# Directories to skip for performance
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    "build",
    "dist",
    "*.egg-info",
    ".eggs",
    "bin",
    "obj",
    "packages",
    ".vs",
    ".idea",
}

# Language configurations
LANGUAGE_CONFIG = {
    "python": {
        "extensions": {".py", ".pyi", ".pyx"},
        "config_files": {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"},
    },
    "csharp": {
        "extensions": {".cs", ".csx"},
        "config_files": {"*.csproj", "*.sln", "packages.config", "*.nuspec"},
    },
    "perl": {
        "extensions": {".pl", ".pm", ".t", ".pod"},
        "config_files": {"Makefile.PL", "Build.PL", "cpanfile", "META.json", "META.yml"},
    },
    "rust": {
        "extensions": {".rs"},
        "config_files": {"Cargo.toml", "Cargo.lock"},
    },
    "packageset": {
        "extensions": {".packageset"},
        "config_files": set(),
    },
}

# For auto-detection
ALL_EXTENSIONS = set()
for cfg in LANGUAGE_CONFIG.values():
    ALL_EXTENSIONS.update(cfg["extensions"])


def should_skip_dir(dir_name: str) -> bool:
    """Check if a directory should be skipped."""
    return dir_name in SKIP_DIRS or dir_name.endswith(".egg-info")


def iter_source_files(
    root: Path, language: str | None = None, include_configs: bool = True, verbose: bool = False
) -> Iterator[Path]:
    """
    Iterate over source files in a directory tree.

    Uses os.walk for speed on massive repositories.
    """
    if language and language in LANGUAGE_CONFIG:
        extensions = LANGUAGE_CONFIG[language]["extensions"]
        config_files = LANGUAGE_CONFIG[language]["config_files"]
    else:
        # Search all supported languages
        extensions = ALL_EXTENSIONS
        config_files = set()
        for cfg in LANGUAGE_CONFIG.values():
            config_files.update(cfg["config_files"])

    if verbose:
        print(f"  Looking for extensions: {extensions}")

    dirs_scanned = 0
    files_found = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Modify dirnames in-place to skip unwanted directories
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        dirs_scanned += 1
        if verbose and dirs_scanned % 500 == 0:
            print(f"  Scanned {dirs_scanned} directories, found {files_found} matching files...")

        for filename in filenames:
            filepath = Path(dirpath) / filename
            suffix = filepath.suffix

            if suffix in extensions:
                files_found += 1
                if verbose and files_found <= 5:
                    print(f"  Sample file: {filepath}")
                yield filepath
            elif include_configs and filename in config_files:
                files_found += 1
                yield filepath

    if verbose:
        print(f"  Total: scanned {dirs_scanned} directories, found {files_found} matching files")


def get_definition_patterns(package_name: str, language: str) -> list[re.Pattern]:
    """Get regex patterns to find package/namespace definitions."""
    escaped = re.escape(package_name)

    if language == "python":
        return []  # Python uses directory structure, handled separately

    elif language == "csharp":
        return [
            # namespace MyPackage { ... }
            re.compile(rf"^\s*namespace\s+{escaped}\s*[{{;]", re.IGNORECASE),
            # namespace MyPackage.Something { ... }
            re.compile(rf"^\s*namespace\s+{escaped}\.", re.IGNORECASE),
        ]

    elif language == "perl":
        return [
            # package MyPackage;
            re.compile(rf"^\s*package\s+{escaped}\s*;"),
            # package MyPackage::Something;
            re.compile(rf"^\s*package\s+{escaped}::"),
        ]

    elif language == "rust":
        return [
            # mod mypackage { ... }
            re.compile(rf"^\s*(?:pub\s+)?mod\s+{escaped}\s*\{{"),
            # mod mypackage;
            re.compile(rf"^\s*(?:pub\s+)?mod\s+{escaped}\s*;"),
            # crate name in Cargo.toml: name = "mypackage"
            re.compile(rf'^\s*name\s*=\s*"{escaped}"'),
        ]

    return []


def get_import_patterns(package_name: str, language: str) -> list[re.Pattern]:
    """Get regex patterns to find import/using statements."""
    escaped = re.escape(package_name)

    if language == "python":
        return [
            # import package
            re.compile(rf"^\s*import\s+{escaped}(?:\s|$|,)"),
            # from package import ...
            re.compile(rf"^\s*from\s+{escaped}(?:\.|$|\s)"),
            # import ... as ... (where package is imported)
            re.compile(rf"^\s*import\s+.*\b{escaped}\b"),
        ]

    elif language == "csharp":
        return [
            # using MyPackage;
            re.compile(rf"^\s*using\s+{escaped}\s*;", re.IGNORECASE),
            # using MyPackage.Something;
            re.compile(rf"^\s*using\s+{escaped}\.", re.IGNORECASE),
            # using static MyPackage.Something;
            re.compile(rf"^\s*using\s+static\s+{escaped}\.", re.IGNORECASE),
            # using Alias = MyPackage.Something;
            re.compile(rf"^\s*using\s+\w+\s*=\s*{escaped}", re.IGNORECASE),
        ]

    elif language == "perl":
        return [
            # use MyPackage;
            re.compile(rf"^\s*use\s+{escaped}\s*[;(]"),
            # use MyPackage::Something;
            re.compile(rf"^\s*use\s+{escaped}::"),
            # require MyPackage;
            re.compile(rf"^\s*require\s+{escaped}\s*;"),
            # require MyPackage::Something;
            re.compile(rf"^\s*require\s+{escaped}::"),
        ]

    elif language == "rust":
        return [
            # use mypackage;
            re.compile(rf"^\s*use\s+{escaped}\s*;"),
            # use mypackage::something;
            re.compile(rf"^\s*use\s+{escaped}::"),
            # use crate::mypackage;
            re.compile(rf"^\s*use\s+crate::{escaped}"),
            # use super::mypackage;
            re.compile(rf"^\s*use\s+super::{escaped}"),
            # extern crate mypackage;
            re.compile(rf"^\s*extern\s+crate\s+{escaped}\s*;"),
            # mypackage = "version" in Cargo.toml dependencies
            re.compile(rf'^\s*{escaped}\s*='),
        ]

    return []


def get_usage_pattern(package_name: str, language: str) -> re.Pattern | None:
    """Get regex pattern to find package usage in code."""
    escaped = re.escape(package_name)

    if language == "python":
        # package.something
        return re.compile(rf"\b{escaped}\.")

    elif language == "csharp":
        # MyPackage.Something or new MyPackage.Class()
        return re.compile(rf"\b{escaped}\.", re.IGNORECASE)

    elif language == "perl":
        # MyPackage::something or MyPackage->method
        return re.compile(rf"\b{escaped}(?:::|->)")

    elif language == "rust":
        # mypackage::something
        return re.compile(rf"\b{escaped}::")

    return None


def find_packageset_definition(
    root: Path, package_name: str, verbose: bool = False
) -> list[PackageMatch]:
    """
    Find .packageset files that define or reference a package.

    Office monorepo (OMR) uses .packageset files under src/otools/deps/pkgsets/.
    Searches for:
    - Files named <package_name>.packageset (case-insensitive)
    - Files containing "id": "<package_name>" in their content
    - Files containing the package name in their content
    """
    matches = []
    package_lower = package_name.lower()

    # Try the canonical pkgsets directory first for speed
    pkgset_roots = []
    canonical_pkgset = root / "src" / "otools" / "deps" / "pkgsets"
    if canonical_pkgset.is_dir():
        pkgset_roots.append(canonical_pkgset)
        if verbose:
            print(f"  Found canonical pkgsets directory: {canonical_pkgset}")
    else:
        # Fall back to searching from root
        pkgset_roots.append(root)
        if verbose:
            print(f"  No canonical pkgsets dir found, searching from root: {root}")

    files_checked = 0
    for pkgset_root in pkgset_roots:
        for dirpath, dirnames, filenames in os.walk(pkgset_root):
            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

            for filename in filenames:
                if not filename.endswith(".packageset"):
                    continue

                filepath = Path(dirpath) / filename
                files_checked += 1

                if verbose and files_checked % 100 == 0:
                    print(f"  Checked {files_checked} packageset files...")

                # Check 1: Filename matches package name
                # e.g., office.engineering.opmlite.packageset matches "opmlite" or "office.engineering.opmlite"
                filename_base = filename.rsplit(".packageset", 1)[0].lower()
                if filename_base == package_lower or filename_base.endswith(f".{package_lower}"):
                    if verbose:
                        print(f"  FOUND (filename match): {filepath}")
                    matches.append(
                        PackageMatch(
                            path=filepath,
                            match_type="definition",
                            line_content=f"Filename match: {filename}",
                        )
                    )
                    continue

                # Check 2: Search inside file for package reference
                try:
                    with open(filepath, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # Look for "id": "package_name" pattern
                        id_pattern = rf'"id"\s*:\s*"[^"]*{re.escape(package_name)}[^"]*"'
                        id_match = re.search(id_pattern, content, re.IGNORECASE)
                        if id_match:
                            # Find line number
                            line_num = content[:id_match.start()].count('\n') + 1
                            line_content = content.split('\n')[line_num - 1].strip()
                            if verbose:
                                print(f"  FOUND (id field): {filepath}:{line_num}")
                            matches.append(
                                PackageMatch(
                                    path=filepath,
                                    match_type="definition",
                                    line_number=line_num,
                                    line_content=line_content,
                                )
                            )
                            continue

                        # Look for package name mentioned anywhere (looser match)
                        if package_lower in content.lower():
                            if verbose:
                                print(f"  FOUND (content reference): {filepath}")
                            matches.append(
                                PackageMatch(
                                    path=filepath,
                                    match_type="import",  # Mark as import/reference, not definition
                                    line_content=f"References '{package_name}' in content",
                                )
                            )
                except (OSError, PermissionError):
                    pass

    if verbose:
        print(f"  Packageset search complete: checked {files_checked} files, found {len(matches)} match(es)")

    return matches


def find_package_definition(
    root: Path, package_name: str, language: str, verbose: bool = False
) -> list[PackageMatch]:
    """
    Find where a package is defined (its source location).

    Language-specific:
    - Python: Directory with __init__.py or single .py file
    - C#: Files with namespace declarations
    - Perl: Files with package declarations
    - Rust: mod declarations or Cargo.toml
    - Packageset: .packageset files (handled separately)
    """
    matches = []
    config = LANGUAGE_CONFIG.get(language, {})
    extensions = config.get("extensions", ALL_EXTENSIONS)

    if verbose:
        print(f"  Searching for '{package_name}' definitions in {language} files...")
        print(f"  Extensions: {extensions}")

    files_checked = 0

    if language == "python":
        # Python uses directory structure
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
            current_dir = Path(dirpath)

            # Check if this directory is the package (has __init__.py)
            if current_dir.name == package_name and "__init__.py" in filenames:
                if verbose:
                    print(f"  FOUND definition: {current_dir / '__init__.py'}")
                matches.append(
                    PackageMatch(
                        path=current_dir / "__init__.py",
                        match_type="definition",
                    )
                )

            # Check for single-file module
            module_file = f"{package_name}.py"
            if module_file in filenames:
                if verbose:
                    print(f"  FOUND definition: {current_dir / module_file}")
                matches.append(
                    PackageMatch(
                        path=current_dir / module_file,
                        match_type="definition",
                    )
                )
    else:
        # C# and Perl use in-file declarations
        definition_patterns = get_definition_patterns(package_name, language)
        if verbose:
            print(f"  Definition patterns: {[p.pattern for p in definition_patterns]}")

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

            for filename in filenames:
                filepath = Path(dirpath) / filename
                if filepath.suffix not in extensions:
                    continue

                files_checked += 1
                if verbose and files_checked % 1000 == 0:
                    print(f"  Checked {files_checked} files for definitions...")

                try:
                    with open(filepath, encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            for pattern in definition_patterns:
                                if pattern.search(line):
                                    if verbose:
                                        print(f"  FOUND definition: {filepath}:{line_num}")
                                        print(f"    {line.strip()}")
                                    matches.append(
                                        PackageMatch(
                                            path=filepath,
                                            match_type="definition",
                                            line_number=line_num,
                                            line_content=line.strip(),
                                        )
                                    )
                                    break
                except (OSError, PermissionError):
                    pass

    if verbose:
        print(f"  Definition search complete. Found {len(matches)} definition(s)")

    return matches


def search_file_for_imports(
    filepath: Path, package_name: str, language: str
) -> tuple[list[PackageMatch], list[PackageMatch]]:
    """
    Search a single file for imports and usages of a package.

    Returns (imports, usages) tuples.
    """
    imports = []
    usages = []

    import_patterns = get_import_patterns(package_name, language)
    usage_pattern = get_usage_pattern(package_name, language)

    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                # Check for imports
                is_import = False
                for pattern in import_patterns:
                    if pattern.search(line):
                        imports.append(
                            PackageMatch(
                                path=filepath,
                                match_type="import",
                                line_number=line_num,
                                line_content=line.strip(),
                            )
                        )
                        is_import = True
                        break

                # Check for usage (only if not an import line)
                if not is_import and usage_pattern and usage_pattern.search(line):
                    usages.append(
                        PackageMatch(
                            path=filepath,
                            match_type="usage",
                            line_number=line_num,
                            line_content=line.strip(),
                        )
                    )
    except (OSError, PermissionError):
        pass  # Skip files we can't read

    return imports, usages


def search_files_batch(
    filepaths: list[Path], package_name: str, language: str
) -> tuple[list[PackageMatch], list[PackageMatch]]:
    """Process a batch of files (for parallel processing)."""
    all_imports = []
    all_usages = []

    for filepath in filepaths:
        imports, usages = search_file_for_imports(filepath, package_name, language)
        all_imports.extend(imports)
        all_usages.extend(usages)

    return all_imports, all_usages


def find_package(
    root: Path,
    package_name: str,
    language: str = "auto",
    max_workers: int | None = None,
    batch_size: int = 100,
    verbose: bool = False,
    search_packagesets: bool = True,
) -> SearchResult:
    """
    Search a repository for a package.

    Args:
        root: Repository root path
        package_name: Name of the package to find
        language: Language to search ('python', 'csharp', 'perl', 'rust', or 'auto')
        max_workers: Number of parallel workers (None = auto)
        batch_size: Files per batch for parallel processing
        verbose: Print progress information
        search_packagesets: Also search .packageset files (OMR specific)

    Returns:
        SearchResult with all findings
    """
    # Step 0: Try packageset search first (fastest success path in OMR)
    packageset_matches: list[PackageMatch] = []
    if search_packagesets:
        if verbose:
            print("=" * 60)
            print("STEP 0: Searching for .packageset files (OMR)...")
            print("=" * 60)

        packageset_matches = find_packageset_definition(root, package_name, verbose)

        if packageset_matches and verbose:
            print(f"\n  Found {len(packageset_matches)} packageset match(es)")
            print()

    # Auto-detect language if needed
    if language == "auto":
        language = detect_language(root, verbose)
        if verbose:
            print()

    result = SearchResult(package_name=package_name, language=language)

    # Add any packageset matches to definitions
    if packageset_matches:
        # Separate definitions from references
        for match in packageset_matches:
            if match.match_type == "definition":
                result.definitions.append(match)
            else:
                result.imports.append(match)

    if verbose:
        print("=" * 60)
        print(f"SEARCH CONFIGURATION")
        print("=" * 60)
        print(f"  Package name: {package_name}")
        print(f"  Language: {language}")
        print(f"  Repository root: {root}")
        print(f"  Root exists: {root.exists()}")
        print(f"  Root is dir: {root.is_dir()}")
        print()

    # Step 1: Find package definitions in source code
    if verbose:
        print("=" * 60)
        print("STEP 1: Finding package definitions in source code...")
        print("=" * 60)

    source_definitions = find_package_definition(root, package_name, language, verbose)
    result.definitions.extend(source_definitions)

    if verbose:
        print(f"\n  Found {len(source_definitions)} source definition(s)")
        print(f"  Total definitions (including packagesets): {len(result.definitions)}")

    # Step 2: Collect all source files
    if verbose:
        print()
        print("=" * 60)
        print("STEP 2: Collecting source files...")
        print("=" * 60)

    all_files = list(iter_source_files(root, language, verbose=verbose))

    if verbose:
        print(f"\n  Found {len(all_files)} files to search")

    # Step 3: Search for imports and usages in parallel
    if verbose:
        print()
        print("=" * 60)
        print("STEP 3: Searching for imports and usages...")
        print("=" * 60)

    # Split files into batches
    batches = [all_files[i : i + batch_size] for i in range(0, len(all_files), batch_size)]

    if len(batches) > 1 and max_workers != 1:
        # Use parallel processing for large repos
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(search_files_batch, batch, package_name, language): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                imports, usages = future.result()
                result.imports.extend(imports)
                result.usages.extend(usages)

                if verbose:
                    batch_idx = futures[future]
                    print(f"  Processed batch {batch_idx + 1}/{len(batches)}")
    else:
        # Single-threaded for small repos
        for batch in batches:
            imports, usages = search_files_batch(batch, package_name, language)
            result.imports.extend(imports)
            result.usages.extend(usages)

    # Sort results by path for consistent output
    result.imports.sort(key=lambda m: (m.path, m.line_number or 0))
    result.usages.sort(key=lambda m: (m.path, m.line_number or 0))

    return result


def detect_language(root: Path, verbose: bool = False) -> str:
    """
    Auto-detect the primary language of a repository.

    Returns the language with the most source files.
    """
    counts = {lang: 0 for lang in LANGUAGE_CONFIG}

    if verbose:
        print("Auto-detecting language...")
        print(f"  Scanning: {root}")

    dirs_scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        dirs_scanned += 1

        for filename in filenames:
            suffix = Path(filename).suffix
            for lang, config in LANGUAGE_CONFIG.items():
                if suffix in config["extensions"]:
                    counts[lang] += 1
                    break

        # Early exit if we've scanned enough files
        if sum(counts.values()) > 1000:
            if verbose:
                print(f"  Early exit after {dirs_scanned} directories (found 1000+ files)")
            break

    if verbose:
        print(f"  File counts by language: {counts}")

    # Return the language with most files, default to csharp
    if max(counts.values()) == 0:
        if verbose:
            print("  No matching files found, defaulting to csharp")
        return "csharp"  # Default for when no files found yet

    detected = max(counts.keys(), key=lambda lang: counts[lang])
    if verbose:
        print(f"  Detected language: {detected}")
    return detected


def format_results(result: SearchResult, root: Path, max_items: int = 50) -> str:
    """Format search results for display."""
    lines = []
    lines.append(f"Search Results for: {result.package_name} ({result.language})")
    lines.append("=" * 60)

    if not result.found:
        lines.append("No matches found.")
        return "\n".join(lines)

    # Definitions
    if result.definitions:
        lines.append(f"\n📦 Package Definitions ({len(result.definitions)}):")
        lines.append("-" * 40)
        for match in result.definitions[:max_items]:
            rel_path = match.path.relative_to(root)
            lines.append(f"  {rel_path}")

    # Imports
    if result.imports:
        lines.append(f"\n📥 Imports ({len(result.imports)}):")
        lines.append("-" * 40)
        shown = result.imports[:max_items]
        for match in shown:
            rel_path = match.path.relative_to(root)
            lines.append(f"  {rel_path}:{match.line_number}")
            if match.line_content:
                lines.append(f"    {match.line_content}")
        if len(result.imports) > max_items:
            lines.append(f"  ... and {len(result.imports) - max_items} more")

    # Usages
    if result.usages:
        lines.append(f"\n🔗 Usages ({len(result.usages)}):")
        lines.append("-" * 40)
        shown = result.usages[:max_items]
        for match in shown:
            rel_path = match.path.relative_to(root)
            lines.append(f"  {rel_path}:{match.line_number}")
            if match.line_content:
                lines.append(f"    {match.line_content}")
        if len(result.usages) > max_items:
            lines.append(f"  ... and {len(result.usages) - max_items} more")

    # Summary
    lines.append("\n" + "=" * 60)
    lines.append("Summary:")
    lines.append(f"  Definitions: {len(result.definitions)}")
    lines.append(f"  Import statements: {len(result.imports)}")
    lines.append(f"  Usage locations: {len(result.usages)}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Search a repository for a package/namespace (Python, C#, Perl, Rust, or OMR packagesets)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s MyNamespace                           # Auto-detect language
  %(prog)s MyNamespace --lang csharp             # Search C# namespaces
  %(prog)s MyPackage --lang perl                 # Search Perl packages
  %(prog)s mypackage --lang python               # Search Python packages
  %(prog)s mycrate --lang rust                   # Search Rust crates/modules
  %(prog)s MyNamespace --root /path/to/repo -v   # Verbose with custom root

Office Monorepo (OMR) examples:
  %(prog)s opmlite --root ~/Office/src -v        # Find opmlite packageset
  %(prog)s office.engineering.opmlite -r ~/Office/src  # Full packageset name
  %(prog)s buildxl.win-x64 -r ~/Office/src       # Find buildxl packageset
  %(prog)s Office.BuildSystem -r ~/Office/src    # Find Office.BuildSystem
  %(prog)s opm --lang csharp -r ~/Office/src     # Find OPM C# code
        """,
    )

    parser.add_argument("package_name", help="Name of the package/namespace to search for")

    parser.add_argument(
        "--root",
        "-r",
        type=Path,
        default=Path.cwd(),
        help="Repository root directory (default: current directory)",
    )

    parser.add_argument(
        "--lang",
        "-l",
        choices=["auto", "python", "csharp", "perl", "rust"],
        default="auto",
        help="Language to search (default: auto-detect)",
    )

    parser.add_argument(
        "--max-results",
        "-m",
        type=int,
        default=50,
        help="Maximum results to display per category (default: 50)",
    )

    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="Number of parallel workers (default: auto)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show progress information",
    )

    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output results as JSON",
    )

    parser.add_argument(
        "--no-packagesets",
        action="store_true",
        help="Skip searching .packageset files (OMR specific)",
    )

    args = parser.parse_args()

    # Validate root path
    if not args.root.exists():
        print(f"Error: Path does not exist: {args.root}", file=sys.stderr)
        sys.exit(1)

    if not args.root.is_dir():
        print(f"Error: Path is not a directory: {args.root}", file=sys.stderr)
        sys.exit(1)

    # Run the search
    result = find_package(
        root=args.root.resolve(),
        package_name=args.package_name,
        language=args.lang,
        max_workers=args.workers,
        verbose=args.verbose,
        search_packagesets=not args.no_packagesets,
    )

    # Output results
    if args.json:
        import json

        output = {
            "package_name": result.package_name,
            "language": result.language,
            "found": result.found,
            "definitions": [
                {"path": str(m.path), "line": m.line_number, "content": m.line_content}
                for m in result.definitions
            ],
            "imports": [
                {"path": str(m.path), "line": m.line_number, "content": m.line_content}
                for m in result.imports
            ],
            "usages": [
                {"path": str(m.path), "line": m.line_number, "content": m.line_content}
                for m in result.usages
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_results(result, args.root.resolve(), args.max_results))

    # Exit code based on whether package was found
    sys.exit(0 if result.found else 1)


if __name__ == "__main__":
    main()
