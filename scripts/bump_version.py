#!/usr/bin/env python3
"""
Bump the GREAT SDD Kit version.

Usage:
    python3 scripts/bump_version.py patch   # 1.0.0 → 1.0.1
    python3 scripts/bump_version.py minor   # 1.0.0 → 1.1.0
    python3 scripts/bump_version.py major   # 1.0.0 → 2.0.0

Updates:
    - great_sdd/__init__.__version__
    - pyproject.toml version
    - package.json version
    - commits (incl. CHANGELOG.md if present) + git tag vX.Y.Z
"""
import re
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

INIT_FILE = REPO_ROOT / "great_sdd" / "__init__.py"
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
PACKAGE_FILE = REPO_ROOT / "package.json"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"


def current_version() -> str:
    content = INIT_FILE.read_text()
    m = re.search(r'__version__ = "(\d+\.\d+\.\d+)"', content)
    if not m:
        raise RuntimeError("Cannot find __version__ in __init__.py")
    return m.group(1)


def bump(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown part: {part}. Use major, minor, or patch.")


def update_file(path: str, pattern: str, replacement: str):
    content = Path(path).read_text()
    new = re.sub(pattern, replacement, content)
    assert new != content, f"Pattern not found in {path}"
    Path(path).write_text(new)
    print(f"  updated {path}")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("major", "minor", "patch"):
        print(f"Usage: {sys.argv[0]} <major|minor|patch>")
        sys.exit(1)

    part = sys.argv[1]
    old = current_version()
    new = bump(old, part)

    print(f"Bumping {part}: {old} → {new}")

    update_file(INIT_FILE, f'__version__ = "{old}"', f'__version__ = "{new}"')
    update_file(PYPROJECT_FILE, f'version = "{old}"', f'version = "{new}"')

    # Keep package.json in sync (JSON-safe edit).
    import json
    pkg = json.loads(PACKAGE_FILE.read_text())
    pkg["version"] = new
    PACKAGE_FILE.write_text(json.dumps(pkg, indent=2) + "\n")
    print(f"  updated {PACKAGE_FILE}")

    # Stage + commit + tag (include package.json + CHANGELOG so the version
    # commit carries the changelog entry the developer prepared).
    files = [str(INIT_FILE), str(PYPROJECT_FILE), str(PACKAGE_FILE)]
    if CHANGELOG_FILE.exists():
        files.append(str(CHANGELOG_FILE))
    subprocess.run(["git", "add", *files], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "commit", "-m", f"chore: bump version {old} → {new}"], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "tag", f"v{new}"], cwd=REPO_ROOT, check=True)

    print(f"\nDone. Tag v{new} created.")
    print(f"Push with: git push && git push --tags")


if __name__ == "__main__":
    main()
