#!/usr/bin/env python3
"""Cross-platform installer for the ADP Claude Code plugin.

Creates a symlink (preferred) or directory copy (fallback on Windows
without developer mode) at ~/.claude/plugins/cache/local/adp and
registers the plugin in installed_plugins.json.
"""

import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_NAME = "adp"
PLUGIN_VERSION = "0.3.5"

PLUGIN_DIR = Path(__file__).resolve().parent
CLAUDE_PLUGINS = Path.home() / ".claude" / "plugins"
CACHE_LOCAL = CLAUDE_PLUGINS / "cache" / "local"
TARGET = CACHE_LOCAL / PLUGIN_NAME
INSTALLED_JSON = CLAUDE_PLUGINS / "installed_plugins.json"


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


def update_registry() -> None:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    entry = {
        "scope": "user",
        "installPath": str(TARGET),
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

    data["plugins"][f"{PLUGIN_NAME}@local"] = [entry]
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

    CACHE_LOCAL.mkdir(parents=True, exist_ok=True)

    method = create_link(PLUGIN_DIR, TARGET)
    print(f"Installed ({method}): {TARGET} -> {PLUGIN_DIR}")

    update_registry()

    print(f"\nADP plugin v{PLUGIN_VERSION} installed. Restart Claude Code to activate.")
    if method == "copy":
        print("NOTE: using directory copy (symlink not available).")
        print("Re-run this script after updating the plugin to refresh the copy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
