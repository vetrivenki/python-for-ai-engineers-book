"""Lesson 1.1 / Task 1 - Set Up a Secure Python Client.

Verifies local setup only: interpreter, SDK import, credential presence.
Makes no API call, so it cannot incur charges and cannot prove account access.

Run:  python setup_check.py
"""

from __future__ import annotations

import importlib.metadata as metadata
import os
import pathlib
import sys

from config import API_KEY_VAR, DEFAULT_MODEL, api_key_present


def sdk_version() -> str | None:
    """Return the installed anthropic version, or None when it is absent."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return None
    try:
        return metadata.version("anthropic")
    except metadata.PackageNotFoundError:
        return "unknown"


def git_ignores_secrets(root: pathlib.Path | None = None) -> bool | None:
    """True when .gitignore excludes .env. None when there is no .gitignore."""
    root = root or pathlib.Path(__file__).resolve().parent
    ignore = root / ".gitignore"
    if not ignore.exists():
        return None
    patterns = {line.strip() for line in ignore.read_text().splitlines()}
    return bool(patterns & {".env", "*.env", ".env*"})


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    checks.append(("interpreter", True, sys.executable))
    checks.append(("python version", sys.version_info >= (3, 10),
                   f"{sys.version_info.major}.{sys.version_info.minor} (SDK requires 3.10+)"))

    version = sdk_version()
    checks.append(("anthropic SDK", version is not None, version or "not installed"))

    # Report presence only. The value itself is never printed.
    checks.append((f"{API_KEY_VAR}", api_key_present(),
                   "present" if api_key_present() else "missing"))

    checks.append(("model configured", True, DEFAULT_MODEL))

    ignored = git_ignores_secrets()
    checks.append((".env excluded from git", ignored is not False,
                   {True: "yes", False: "NO - .env is tracked", None: "no .gitignore found"}[ignored]))

    width = max(len(name) for name, _, _ in checks)
    print("Local setup check (no API call is made)")
    print("-" * (width + 34))
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
    print("-" * (width + 34))

    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        print(f"RESULT: not ready - fix {', '.join(failed)}")
        return 1
    print("RESULT: local setup OK. This does not verify account access or billing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
