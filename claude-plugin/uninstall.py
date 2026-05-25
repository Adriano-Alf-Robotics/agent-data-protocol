#!/usr/bin/env python3
"""Cross-platform uninstaller for the ADP Claude Code plugin.

Removes the symlink/copy at ~/.claude/plugins/cache/local/adp and
cleans the entry from installed_plugins.json.
"""

import json
import shutil
import sys
from pathlib import Path

PLUGIN_NAME = "adp"

CLAUDE_PLUGINS = Path.home() / ".claude" / "plugins"
TARGET = CLAUDE_PLUGINS / "cache" / "local" / PLUGIN_NAME
INSTALLED_JSON = CLAUDE_PLUGINS / "installed_plugins.json"


def remove_installation() -> bool:
    if TARGET.is_symlink() or TARGET.exists():
        if TARGET.is_symlink() or TARGET.is_file():
            TARGET.unlink()
        else:
            shutil.rmtree(TARGET)
        print(f"Removed {TARGET}")
        return True
    print(f"No installation found at {TARGET}")
    return False


def clean_registry() -> bool:
    if not INSTALLED_JSON.exists():
        print(f"No {INSTALLED_JSON} found.")
        return False

    data = json.loads(INSTALLED_JSON.read_text())
    changed = False

    plugins = data.get("plugins", {})
    key = f"{PLUGIN_NAME}@local"
    if key in plugins:
        del plugins[key]
        changed = True
        print(f"Removed {key} from registry")

    legacy_key = f"local/{PLUGIN_NAME}"
    if legacy_key in data:
        del data[legacy_key]
        changed = True
        print(f"Removed legacy {legacy_key} entry")

    if changed:
        INSTALLED_JSON.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Updated {INSTALLED_JSON}")

    return changed


def main() -> int:
    removed = remove_installation()
    cleaned = clean_registry()

    if removed or cleaned:
        print("\nADP plugin uninstalled. Restart Claude Code to deactivate.")
    else:
        print("\nNothing to uninstall.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
