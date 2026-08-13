"""UI backend registry (lazy imports)."""

from __future__ import annotations

import os
from typing import Any, Callable, List, Optional, Type


def list_ui_backends() -> List[str]:
    """Return UI backend ids registered for this release."""
    return ["qt", "tui"]


def resolve_ui_backend_name(argv: Optional[List[str]] = None) -> str:
    """Resolve the UI backend id for this process.

    Precedence:
    1. ``UI_BACKEND`` environment variable
    2. ``--ui-backend=`` argv flag
    3. ``DEFAULT_UI_BACKEND`` from merged platform constants
    4. ``"qt"``
    """
    env_backend = os.environ.get("UI_BACKEND", "").strip()
    if env_backend:
        return env_backend.lower()

    if argv:
        for i, arg in enumerate(argv):
            if arg.startswith("--ui-backend="):
                return arg.split("=", 1)[1].strip().lower()
            if arg == "--ui-backend" and i + 1 < len(argv):
                return argv[i + 1].strip().lower()

    try:
        from ..utils.imports import get_platforms_constants

        constants = get_platforms_constants()
        default = getattr(constants, "DEFAULT_UI_BACKEND", None)
        if default:
            return str(default).strip().lower()
    except Exception:
        pass

    return "qt"


def get_ui_backend(name: str) -> Type[Any]:
    """Return a UI backend class by name.

    Backends are imported lazily.
    """
    key = (name or "qt").strip().lower()
    loaders: dict[str, Callable[[], Type[Any]]] = {
        "qt": _load_qt,
        "tui": _load_tui,
    }
    if key not in loaders:
        raise ValueError(
            f"Unknown UI backend: {name!r}. Available: {sorted(loaders)}"
        )
    return loaders[key]()


def _load_qt() -> Type[Any]:
    from .qt.application import QtApplicationBackend
    return QtApplicationBackend


def _load_tui() -> Type[Any]:
    try:
        from .tui.application import TextualApplicationBackend
    except ImportError as exc:
        raise RuntimeError(
            "The TUI backend is registered but could not be imported. "
            "Ensure the Textual package is installed (textual>=0.80) and "
            "that GUI.app.ui.tui is available. Use the Qt backend (default) "
            "via UI_BACKEND=qt or --ui-backend=qt."
        ) from exc
    return TextualApplicationBackend


__all__ = ["get_ui_backend", "resolve_ui_backend_name", "list_ui_backends"]
