#!/usr/bin/env python3
"""
Release helper for cerebrus-pulse-mcp.

Usage:
    python scripts/release.py check          # verify version consistency
    python scripts/release.py bump 0.4.1     # bump all version sources + tag
    python scripts/release.py publish        # build + publish to PyPI (after bump)

Ensures pyproject.toml, __init__.py, CHANGELOG.md, and git tag all agree.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "cerebrus_pulse_mcp" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"


def get_pyproject_version() -> str:
    text = PYPROJECT.read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "MISSING"


def get_init_version() -> str:
    text = INIT.read_text()
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "MISSING"


def get_changelog_version() -> str:
    text = CHANGELOG.read_text()
    m = re.search(r'## \[(\d+\.\d+\.\d+)\]', text)
    return m.group(1) if m else "MISSING"


def get_git_tags() -> list[str]:
    result = subprocess.run(
        ["git", "tag", "-l", "v*"], capture_output=True, text=True, cwd=ROOT
    )
    return sorted(result.stdout.strip().split("\n")) if result.stdout.strip() else []


def check():
    pyp = get_pyproject_version()
    ini = get_init_version()
    chg = get_changelog_version()
    tags = get_git_tags()

    print(f"  pyproject.toml:  {pyp}")
    print(f"  __init__.py:     {ini}")
    print(f"  CHANGELOG.md:    {chg}")
    print(f"  git tags:        {', '.join(tags) or '(none)'}")

    issues = []
    if pyp != ini:
        issues.append(f"pyproject.toml ({pyp}) != __init__.py ({ini})")
    if pyp != chg:
        issues.append(f"pyproject.toml ({pyp}) != CHANGELOG.md ({chg})")
    if f"v{pyp}" not in tags:
        issues.append(f"git tag v{pyp} missing")

    if issues:
        print(f"\n  PROBLEMS:")
        for i in issues:
            print(f"    - {i}")
        return False
    else:
        print(f"\n  All sources agree on v{pyp}")
        return True


def bump(version: str):
    print(f"Bumping to {version}...")

    # pyproject.toml
    text = PYPROJECT.read_text()
    text = re.sub(r'^(version\s*=\s*)"[^"]+"', f'\\1"{version}"', text, flags=re.MULTILINE)
    PYPROJECT.write_text(text)
    print(f"  pyproject.toml -> {version}")

    # __init__.py
    text = INIT.read_text()
    text = re.sub(r'^(__version__\s*=\s*)"[^"]+"', f'\\1"{version}"', text, flags=re.MULTILINE)
    INIT.write_text(text)
    print(f"  __init__.py    -> {version}")

    # Check CHANGELOG has an entry
    chg = get_changelog_version()
    if chg != version:
        print(f"  WARNING: CHANGELOG.md top entry is {chg}, not {version}")
        print(f"           Add a ## [{version}] entry before committing.")

    print(f"\nNext steps:")
    print(f"  1. git add -A && git commit -m 'v{version}: <description>'")
    print(f"  2. git tag v{version}")
    print(f"  3. git push origin main --tags")
    print(f"  4. python scripts/release.py publish")


def publish():
    v = get_pyproject_version()
    ok = check()
    if not ok:
        print("\nFix version inconsistencies before publishing.")
        sys.exit(1)

    print(f"\nBuilding v{v}...")
    subprocess.run([sys.executable, "-m", "build"], cwd=ROOT, check=True)

    print(f"\nPublishing v{v} to PyPI...")
    subprocess.run(
        [sys.executable, "-m", "twine", "upload", "dist/*"],
        cwd=ROOT,
        check=True,
    )
    print(f"\n  Published cerebrus-pulse-mcp {v} to PyPI")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "check":
        ok = check()
        sys.exit(0 if ok else 1)
    elif cmd == "bump":
        if len(sys.argv) < 3:
            print("Usage: release.py bump <version>")
            sys.exit(1)
        bump(sys.argv[2])
    elif cmd == "publish":
        publish()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
