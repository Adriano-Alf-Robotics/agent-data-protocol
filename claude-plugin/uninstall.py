#!/usr/bin/env python3
"""Cross-platform uninstaller for the ADP Claude Code plugin.

Removes the symlink/copy at ~/.claude/plugins/cache/adp/agent-data-protocol/<version>/
and cleans the entry from installed_plugins.json.  Also cleans up legacy
cache/local/adp paths if present.
"""

import json
import shutil
import sys
from pathlib import Path

PLUGIN_NAME = "adp"
PLUGIN_SLUG = "agent-data-protocol"
PLUGIN_VERSION = "0.3.5"
REGISTRY_KEY = f"{PLUGIN_NAME}@{PLUGIN_NAME}"

CLAUDE_PLUGINS = Path.home() / ".claude" / "plugins"
CACHE_NS = CLAUDE_PLUGINS / "cache" / PLUGIN_NAME / PLUGIN_SLUG / PLUGIN_VERSION
INSTALLED_JSON = CLAUDE_PLUGINS / "installed_plugins.json"

LEGACY_TARGET = CLAUDE_PLUGINS / "cache" / "local" / PLUGIN_NAME
LEGACY_KEY = f"{PLUGIN_NAME}@local"


def _remove_path(p: Path, label: str) -> bool:
    if p.is_symlink() or p.exists():
        if p.is_symlink() or p.is_file():
            p.unlink()
        else:
            shutil.rmtree(p)
        print(f"Removed {label}: {p}")
        return True
    return False


def remove_installation() -> bool:
    removed = _remove_path(CACHE_NS, "install")
    # clean empty parent dirs
    for parent in (CACHE_NS.parent, CACHE_NS.parent.parent):
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    removed |= _remove_path(LEGACY_TARGET, "legacy install")
    return removed


def clean_registry() -> bool:
    if not INSTALLED_JSON.exists():
        print(f"No {INSTALLED_JSON} found.")
        return False

    data = json.loads(INSTALLED_JSON.read_text())
    changed = False
    plugins = data.get("plugins", {})

    for key in (REGISTRY_KEY, LEGACY_KEY, f"local/{PLUGIN_NAME}"):
        if key in plugins:
            del plugins[key]
            changed = True
            print(f"Removed {key} from registry")

    if changed:
        INSTALLED_JSON.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Updated {INSTALLED_JSON}")

    return changed


def remove_markers() -> None:
    """Remove marker files from the source plugin directory."""
    plugin_dir = Path(__file__).resolve().parent
    for name in (".cli-installed", ".install-version"):
        p = plugin_dir / name
        if p.exists():
            p.unlink()
    in_use = plugin_dir / ".in_use"
    if in_use.exists():
        shutil.rmtree(in_use)


def main() -> int:
    removed = remove_installation()
    cleaned = clean_registry()
    remove_markers()

    if removed or cleaned:
        print("\nADP plugin uninstalled. Restart Claude Code to deactivate.")
    else:
        print("\nNothing to uninstall.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
