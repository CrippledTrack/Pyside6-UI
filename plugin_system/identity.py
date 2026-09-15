"""Stable plugin identity vs display names."""

from __future__ import annotations

from typing import Any, Type

UNNAMED_PLUGIN = "Unnamed Plugin"


def plugin_display_name(plugin_class: Type[Any]) -> str:
    """Author ``plugin_name`` (unique-name convenience, not the registry key).

    Falls back to the class name when ``plugin_name`` is missing or the
    default placeholder. Show All does not rewrite this value.
    """
    name = getattr(plugin_class, "plugin_name", None)
    if not name or name == UNNAMED_PLUGIN:
        return plugin_class.__name__
    return str(name)


def plugin_ui_label(plugin_class: Type[Any]) -> str:
    """User-facing list label, including a Show All platform prefix if set."""
    name = plugin_display_name(plugin_class)
    prefix = getattr(plugin_class, "_show_all_prefix", None)
    if prefix:
        return f"{prefix} {name}"
    return name


def plugin_tab_label(plugin_class: Type[Any]) -> str:
    """Label shown on a plugin tab (not the registry ``plugin_id``).

    Uses ``tab_title`` when it is set to something other than the
    ``Unnamed Tab`` placeholder; otherwise the display name.
    Show All prefixes ``tab_title`` on the wrap so the bar shows
    ``[Linux] Updates`` without changing ``plugin_name``.
    """
    title = getattr(plugin_class, "tab_title", None)
    if title and title != "Unnamed Tab":
        return str(title)
    return plugin_ui_label(plugin_class)


def plugin_identity(plugin_class: Type[Any]) -> str:
    """Immutable registry key for a plugin class.

    Uses ``plugin_id`` when set; otherwise defaults to the display name so
    existing unique ``plugin_name`` values keep working.
    """
    plugin_id = getattr(plugin_class, "plugin_id", None)
    if plugin_id and str(plugin_id).strip():
        return str(plugin_id).strip()
    return plugin_display_name(plugin_class)


__all__ = [
    "UNNAMED_PLUGIN",
    "plugin_display_name",
    "plugin_identity",
    "plugin_tab_label",
    "plugin_ui_label",
]
