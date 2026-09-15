"""Explicit host/application configuration for writable paths.

Portable mode (the default) keeps settings and logs next to the inferred
install/source root from :func:`GUI.app.utils.paths.get_base_path`. Hosts that
need a user-data directory or extra plugin roots inject a :class:`HostConfig`
at bootstrap via :func:`set_host_config`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .utils.paths import get_base_path, get_plugins_dir as _legacy_plugins_dir

_lock = threading.Lock()
_current: Optional["HostConfig"] = None


@dataclass
class HostConfig:
    """Process-wide host layout: branding, data paths, and plugin roots."""

    app_id: str = "gui"
    display_name: str = ""
    portable: bool = True
    user_data_dir: Optional[Path] = None
    plugin_roots: List[Path] = field(default_factory=list)

    def data_dir(self) -> Path:
        """Directory for settings, logs, and other writable host files."""
        if self.user_data_dir is not None:
            return Path(self.user_data_dir)
        return get_base_path()

    def settings_file(self) -> Path:
        return self.data_dir() / "settings.json"

    def logs_dir(self) -> Path:
        return self.data_dir() / "logs"

    def plugins_dir(self) -> Path:
        if self.plugin_roots:
            return Path(self.plugin_roots[0])
        return _legacy_plugins_dir()


def get_host_config() -> HostConfig:
    """Return the process host config, creating a portable adapter if unset."""
    global _current
    with _lock:
        if _current is None:
            _current = HostConfig()
        return _current


def set_host_config(config: Optional[HostConfig]) -> None:
    """Replace the process host config (``None`` restores the portable adapter)."""
    global _current
    with _lock:
        _current = config


__all__ = [
    "HostConfig",
    "get_host_config",
    "set_host_config",
]
