"""
Runtime import aliases for backward compatibility.

Some first-party plugin modules (and potentially third-party ones) historically
imported GUI modules via top-level names like:

- `plugins.*`  (intended to be `GUI.plugins.*`)
- `themes.*`   (intended to be `GUI.themes.*`)
- `app.*`      (intended to be `GUI.app.*`)

Those imports used to work only when the GUI directory was temporarily added to
sys.path. We avoid sys.path mutation and instead install explicit aliases in
sys.modules before importing plugin modules.
"""

from __future__ import annotations

import importlib
import sys
from typing import Dict


def install_import_aliases() -> Dict[str, str]:
    """Install `plugins`, `themes`, and `app` aliases into sys.modules.

    Returns:
        Mapping of alias name -> target module name that was installed.
    """
    aliases = {
        "plugins": "GUI.plugins",
        "themes": "GUI.themes",
        "app": "GUI.app",
    }

    installed: Dict[str, str] = {}
    for alias, target in aliases.items():
        if alias in sys.modules:
            continue
        try:
            sys.modules[alias] = importlib.import_module(target)
            installed[alias] = target
        except Exception:
            # Best-effort: if target isn't importable, don't install alias.
            continue

    return installed


__all__ = ["install_import_aliases"]

