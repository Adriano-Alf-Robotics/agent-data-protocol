#!/usr/bin/env python3
"""Cross-platform installer for the ADP Claude Code plugin.

Creates a symlink (preferred) or directory copy (fallback on Windows
without developer mode) at ~/.claude/plugins/cache/adp/agent-data-protocol/<version>/
and registers the plugin in installed_plugins.json.

Uses the same namespace/version/marker-file convention as official
plugins (claude-mem, superpowers, etc.) so that Claude Code's cache
management does not prune the entry.
"""

import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_NAME = "adp"
PLUGIN_SLUG = "agent-data-protocol"
PLUGIN_VERSION = "0.3.5"
REGISTRY_KEY = f"{PLUGIN_NAME}@{PLUGIN_NAME}"

PLUGIN_DIR = Path(__file__).resolve().parent
CLAUDE_PLUGINS = Path.home() / ".claude" / "plugins"
CACHE_NS = CLAUDE_PLUGINS / "cache" / PLUGIN_NAME / PLUGIN_SLUG / PLUGIN_VERSION
INSTALLED_JSON = CLAUDE_PLUGINS / "installed_plugins.json"

LEGACY_TARGET = CLAUDE_PLUGINS / "cache" / "local" / PLUGIN_NAME
LEGACY_KEY = f"{PLUGIN_NAME}@local"


def _remove_legacy() -> None:
    """Remove old cache/local/adp symlink and registry key if present."""
    if LEGACY_TARGET.is_symlink() or LEGACY_TARGET.exists():
        if LEGACY_TARGET.is_symlink() or LEGACY_TARGET.is_file():
            LEGACY_TARGET.unlink()
        else:
            shutil.rmtree(LEGACY_TARGET)
        print(f"Removed legacy install: {LEGACY_TARGET}")

    if INSTALLED_JSON.exists():
        data = json.loads(INSTALLED_JSON.read_text())
        if LEGACY_KEY in data.get("plugins", {}):
            del data["plugins"][LEGACY_KEY]
            INSTALLED_JSON.write_text(json.dumps(data, indent=2) + "\n")
            print(f"Removed legacy registry key: {LEGACY_KEY}")


def create_link(source: Path, dest: Path) -> str:
    """Symlink source→dest, fall back to copy on Windows if no privilege."""
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
        print(f"Removed existing: {dest}")

    try:
        dest.symlink_to(source, target_is_directory=True)
        return "symlink"
    except OSError:
        if platform.system() == "Windows":
            shutil.copytree(source, dest)
            return "copy"
        raise


def write_markers(dest: Path) -> None:
    """Write .cli-installed and .install-version marker files."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    cli_installed = dest / ".cli-installed"
    cli_installed.write_text(now_iso)

    install_version = dest / ".install-version"
    install_version.write_text(json.dumps({
        "version": PLUGIN_VERSION,
        "installedAt": now_iso,
    }))

    in_use = dest / ".in_use"
    in_use.mkdir(exist_ok=True)


def update_registry() -> None:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    entry = {
        "scope": "user",
        "installPath": str(CACHE_NS),
        "version": PLUGIN_VERSION,
        "installedAt": now_iso,
        "lastUpdated": now_iso,
    }

    if INSTALLED_JSON.exists():
        data = json.loads(INSTALLED_JSON.read_text())
        data.setdefault("version", 2)
        data.setdefault("plugins", {})
    else:
        data = {"version": 2, "plugins": {}}

    data["plugins"][REGISTRY_KEY] = [entry]
    INSTALLED_JSON.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {INSTALLED_JSON}")


def main() -> int:
    if not CLAUDE_PLUGINS.is_dir():
        print(f"Error: {CLAUDE_PLUGINS} not found. Is Claude Code installed?", file=sys.stderr)
        return 1

    plugin_json = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        print(f"Error: {plugin_json} not found.", file=sys.stderr)
        return 1

    _remove_legacy()

    CACHE_NS.mkdir(parents=True, exist_ok=True)

    method = create_link(PLUGIN_DIR, CACHE_NS)
    print(f"Installed ({method}): {CACHE_NS} -> {PLUGIN_DIR}")

    write_markers(PLUGIN_DIR)
    update_registry()

    print(f"\nADP plugin v{PLUGIN_VERSION} installed. Restart Claude Code to activate.")
    if method == "copy":
        print("NOTE: using directory copy (symlink not available).")
        print("Re-run this script after updating the plugin to refresh the copy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
