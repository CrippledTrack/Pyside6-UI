"""UI backend registry (lazy imports)."""

from __future__ import annotations

from typing import Any, Callable, Type


def get_ui_backend(name: str) -> Type[Any]:
    """Return a UI backend class by name.

    Backends are imported lazily. Currently only ``qt`` is registered;
    """
    key = (name or "qt").strip().lower()
    loaders: dict[str, Callable[[], Type[Any]]] = {
        "qt": _load_qt,
    }
    if key not in loaders:
        raise ValueError(
            f"Unknown UI backend: {name!r}. Available: {sorted(loaders)}"
        )
    return loaders[key]()


def _load_qt() -> Type[Any]:
    from .qt.application import QtApplicationBackend
    return QtApplicationBackend


__all__ = ["get_ui_backend"]
