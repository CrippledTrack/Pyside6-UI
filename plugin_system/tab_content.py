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


__all__ = ["resolve_tab_content"]
