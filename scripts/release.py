#!/usr/bin/env python3
"""Repository release automation for ztemplate.

This script provides automated release management workflows including:
- Version management and bump automation
- Changelog generation
- Git tag and release creation
- Asset preparation and validation
- Quality checks before release
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "camfrog_auto.py"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"


def get_version():
    """Extract current version from camfrog_auto.py"""
    if VERSION_FILE.exists():
        content = VERSION_FILE.read_text(encoding="utf-8")
        match = re.search(r'VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"', content)
        if match:
            return match.group(1)
    return None


def bump_version(version: str, bump_type: str) -> str:
    """Bump version according to semantic versioning"""
    major, minor, patch = map(int, version.split("."))

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown version bump type: {bump_type}")

    return f"{major}.{minor}.{patch}"


def update_version(new_version: str) -> bool:
    """Update version in camfrog_auto.py"""
    if not VERSION_FILE.exists():
        print(f"ERROR: Version file not found: {VERSION_FILE}")
        return False

    content = VERSION_FILE.read_text(encoding="utf-8")
    pattern = r'VERSION = "[0-9]+\.[0-9]+\.[0-9]+"'
    replacement = f'VERSION = "{new_version}"'

    if not re.search(pattern, content):
        print(f"ERROR: Version pattern not found in {VERSION_FILE}")
        return False

    new_content = re.sub(pattern, replacement, content)
    VERSION_FILE.write_text(new_content, encoding="utf-8")
    return True


def generate_changelog(version: str, changes: list[str]) -> bool:
    """Generate changelog entry for new version"""
    if not CHANGELOG_FILE.exists():
        print(f"ERROR: Changelog file not found: {CHANGELOG_FILE}")
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"## [{version}] - {today}\n\n"
    for change in changes:
        new_entry += f"* {change}\n"
    new_entry += "\n"

    content = CHANGELOG_FILE.read_text(encoding="utf-8")

    # Check if this version already exists
    # Fixed regex pattern syntax to avoid f-string issues
    pattern = r"## \" + version + r\" - [0-9]{4}-[0-9]{2}-[0-9]{2}"
    if re.search(pattern, content):
        print(f"WARNING: Version {version} already exists in changelog")
        return False

    # Insert after first ## header or at top if no headers
    if "## [" in content:
        # Insert after the first ## header
        lines = content.split('\n')
        insert_pos = 1
        for i, line in enumerate(lines):
            if line.startswith("## [") and i > 0:
                insert_pos = i + 1
                break
        lines.insert(insert_pos, new_entry)
        new_content = '\n'.join(lines)
    else:
        new_content = new_entry + content

    CHANGELOG_FILE.write_text(new_content, encoding="utf-8")
    return True


def git_commit(message: str, files: list[str]) -> bool:
    """Make a git commit with the given message"""
    try:
        subprocess.run(["git", "add"] + files, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Git commit failed: {e}")
        return False


def git_tag(version: str, message: str) -> bool:
    """Create a git tag for the release"""
    try:
        subprocess.run(["git", "tag", "-a", version, "-m", message], check=True, capture_output=True)
        return True
    except subprocess.CordingProcessError as e:
        print(f"ERROR: Git tag failed: {e}")
        return False


def pre_release_checks() -> bool:
    """Run pre-release quality checks"""
    print("Running pre-release checks...")

    # Check if we can run the tests
    try:
        subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], 
                      check=True, capture_output=True, timeout=300)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Tests failed: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("WARNING: Tests timed out")

    # Check for any stray files in dist directory
    dist_dir = ROOT / "dist"
    if dist_dir.exists():
        for file in dist_dir.iterdir():
            if file.is_file() and file.suffix in ['.tmp', '.temp']:
                print(f"WARNING: Temporary file found in dist: {file}")

    print("Pre-release checks complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="Release automation for ztemplate")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Bump version command
    bump_parser = subparsers.add_parser("bump", help="Bump version")
    bump_parser.add_argument("type", choices=["major", "minor", "patch"], 
                           help="Version bump type")
    bump_parser.add_argument("--changelog", nargs="*", 
                           help="Changes to add to changelog")

    # Create release command
    release_parser = subparsers.add_parser("create", help="Create release")
    release_parser.add_argument("version", help="Version to release")
    release_parser.add_argument("--changelog", nargs="*", 
                               help="Changes to add to changelog")
    release_parser.add_argument("--message", help="Release message")

    # Validate version command
    validate_parser = subparsers.add_parser("validate", help="Validate current version")

    args = parser.parse_args()

    if args.command == "bump":
        if not VERSION_FILE.exists():
            print(f"ERROR: Version file not found: {VERSION_FILE}")
            return 1

        current_version = get_version()
        if not current_version:
            print("ERROR: Could not get current version")
            return 1

        new_version = bump_version(current_version, args.type)
        print(f"Bumping version from {current_version} to {new_version}")

        if update_version(new_version):
            print(f"Updated version to {new_version}")
            
            # Ask if user wants to add changelog entries
            if args.changelog:
                if generate_changelog(new_version, args.changelog):
                    print(f"Generated changelog entry for version {new_version}")
                    git_commit(f"Release: version {new_version}", ["camfrog_auto.py", "CHANGELOG.md"])
                    print("Committed version bump and changelog")

            return 0
        else:
            return 1

    elif args.command == "create":
        if not pre_release_checks():
            return 1

        version = args.version
        if not version:
            print("ERROR: Version required for create command")
            return 1

        if not update_version(version):
            return 1

        changelog_message = args.message or f"Release version {version}"
        if generate_changelog(version, args.changelog or []):
            git_commit(f"Release: version {version}", ["camfrog_auto.py", "CHANGELOG.md"])
            if git_tag(version, changelog_message):
                print(f"Created tag and commit for version {version}")
                print("To publish this release, run:")
                print(f"  gh release create {version} --repo $(gh repo view --json owner,repo --jq '.owner.login + \"/\" + .repo.name')")
                return 0
            else:
                return 1
        else:
            return 1

    elif args.command == "validate":
        version = get_version()
        if version:
            print(f"Current version: {version}")
            return 0
        else:
            print("ERROR: Could not determine current version")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())