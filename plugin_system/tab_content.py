"""Helpers for resolving toolkit-neutral tab content from plugins."""

from __future__ import annotations

from typing import Any

from .types import TabContent, TabCreateContext


def _is_overridden(plugin: Any, method_name: str) -> bool:
    """Return True if *plugin*'s class defines *method_name* beyond BaseTabPlugin."""
    from .base import BaseTabPlugin

    cls = type(plugin)
    method = getattr(cls, method_name, None)
    if method is None or not callable(getattr(plugin, method_name, None)):
        return False
    if not isinstance(plugin, BaseTabPlugin):
        return True
    base_method = getattr(BaseTabPlugin, method_name, None)
    return method is not base_method


def supports_tab_on_backend(plugin_class: type, backend_id: str) -> bool:
    """Return whether *plugin_class* can provide a tab on *backend_id*.

    Rules:
    - Honors ``BaseTabPlugin.ui_backends`` / ``is_supported_ui_backend``.
    - Non-``qt`` backends require an overridden ``create_tab_content`` (definitions
      path). Legacy ``create_widget``-only plugins are treated as Qt-shaped and
      are not hosted on TUI or other non-Qt backends.
    """
    from .base import BaseTabPlugin

    key = (backend_id or "qt").strip().lower()

    if issubclass(plugin_class, BaseTabPlugin):
        if not plugin_class.is_supported_ui_backend(key):
            return False
        if key != "qt":
            has_tab_content = (
                getattr(plugin_class, "create_tab_content", None)
                is not BaseTabPlugin.create_tab_content
            )
            if not has_tab_content:
                return False
        return True

    # Non-BaseTabPlugin tabs: only Qt may attempt legacy widget construction.
    return key == "qt"


def resolve_tab_content(
    plugin_instance: Any,
    *,
    parent: Any = None,
    backend_id: str = "qt",
) -> TabContent:
    """Create tab content via ``create_tab_content`` or legacy ``create_widget``.

    Prefers an overridden ``create_tab_content``. Falls back to ``create_widget``
    for existing plugins. Uses BaseTabPlugin mutual delegates when neither is
    overridden on a BaseTabPlugin subclass (which raises NotImplementedError).
    """
    context = TabCreateContext(backend_id=backend_id, parent=parent)

    if _is_overridden(plugin_instance, "create_tab_content"):
        return plugin_instance.create_tab_content(context)

    if _is_overridden(plugin_instance, "create_widget"):
        return plugin_instance.create_widget(parent)

    if hasattr(plugin_instance, "create_tab_content") and callable(
        getattr(plugin_instance, "create_tab_content", None)
    ):
        return plugin_instance.create_tab_content(context)

    if hasattr(plugin_instance, "create_widget") and callable(
        getattr(plugin_instance, "create_widget", None)
    ):
        return plugin_instance.create_widget(parent)

    raise TypeError(
        f"{type(plugin_instance).__name__} must implement create_tab_content() "
        "or create_widget()"
    )


__all__ = ["resolve_tab_content", "supports_tab_on_backend"]
