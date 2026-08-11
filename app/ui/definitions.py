"""
Shared UI definitions and backend-auto-dispatch helpers.

Plugins should import from this module for styled controls, forms, tables,
layouts, and content-bearing dialog windows. The active UI backend — set via
``get_active_ui_backend_id()`` — selects the correct toolkit implementation.

Desktop-only layout ideas (resizable splits, pixel heights, stretch weights,
widget parent ownership) are **optional backend capabilities**, not required
paradigms. Query them with :func:`supports` / :class:`UICapability`. Backends
that lack a capability no-op or fall back (for example, ``create_split`` stacks
panes in a column).

Example::

    from GUI.app.ui.definitions import (
        LabelRole, add, create_button, create_label, tab_root,
    )

    root = tab_root(context)
    add(root, create_label("Title", role=LabelRole.HEADING))
    add(root, create_button("Save", on_click=self.save))

Raw toolkit widgets remain allowed as an escape hatch; use ``apply_*_role``
to attach semantic roles to them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from importlib import import_module
from typing import Any, Callable, Optional, Sequence, Union

from .active_backend import get_active_ui_backend_id

# Property name applied by backend maps (Qt dynamic property / Textual class).
ROLE_PROPERTY = "cp_role"

# Spacing token names (values live in each backend style_map).
SPACING_SMALL = "small"
SPACING_MEDIUM = "medium"
SPACING_LARGE = "large"
SPACING_NAMES = (SPACING_SMALL, SPACING_MEDIUM, SPACING_LARGE)


class ButtonRole(str, Enum):
    """Semantic button roles."""

    DEFAULT = "default"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FLAT = "flat"
    DANGER = "danger"


class LabelRole(str, Enum):
    """Semantic label roles."""

    HEADING = "heading"
    BODY = "body"
    FIELD = "field_label"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    MUTED = "muted"


class InputRole(str, Enum):
    """Semantic input roles."""

    DEFAULT = "default"


class UICapability(str, Enum):
    """Optional layout/chrome capabilities a backend may implement.

    Plugins should treat missing capabilities as soft: use
    :func:`supports` and accept no-ops / fallbacks rather than assuming
    desktop layout semantics.
    """

    SPLIT = "split"
    """Resizable multi-pane split containers."""

    STRETCH = "stretch"
    """Flexible spacers that consume leftover space."""

    EXPAND = "expand"
    """Children that grow to fill leftover space in a container."""

    PIXEL_SIZING = "pixel_sizing"
    """Pixel-oriented sizes (spacing ints, fixed heights, etc.)."""

    CONTEXT_MENU = "context_menu"
    """Pointer-oriented context menus attached to content."""


RoleValue = Union[str, Enum]
ComboItem = Union[str, tuple[str, Any]]
_BACKEND_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_BACKEND_COMPONENTS = frozenset({"style_map", "dialog_map"})


@dataclass(frozen=True)
class TableRow:
    """Toolkit-neutral row data for tables with stable selection keys."""

    key: Any
    cells: Sequence[str]
    checked: bool = False
    role: Optional[RoleValue] = None
    tooltip: Optional[str] = None


@dataclass(frozen=True)
class MenuAction:
    """An action shown in a content-level context menu."""

    label: str
    on_select: Callable[[], None]
    enabled: bool = True
    separator_before: bool = False


def _role_str(role: RoleValue) -> str:
    return role.value if isinstance(role, Enum) else str(role)


def _capability_str(capability: RoleValue) -> str:
    return capability.value if isinstance(capability, Enum) else str(capability)


@lru_cache(maxsize=None)
def _load_backend_component(backend_id: str, component: str) -> Any:
    """Import a definitions component from a backend package by convention."""
    if not _BACKEND_ID_PATTERN.fullmatch(backend_id):
        raise RuntimeError(f"Invalid UI backend id {backend_id!r}")
    if component not in _BACKEND_COMPONENTS:
        raise RuntimeError(f"Unknown UI backend component {component!r}")

    module_name = f"{__package__}.{backend_id}.{component}"
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        # Only translate a missing component module. Missing toolkit
        # dependencies inside a real component should retain their traceback.
        missing_name = exc.name or ""
        if not (
            missing_name == module_name
            or module_name.startswith(f"{missing_name}.")
        ):
            raise
        raise RuntimeError(
            f"UI backend '{backend_id}' does not provide {component!r}"
        ) from exc


def _load_style_map() -> Any:
    """Lazily import the style map for the active UI backend."""
    backend_id = get_active_ui_backend_id()
    return _load_backend_component(backend_id, "style_map")


def _load_dialog_map() -> Any:
    """Lazily import the dialog map for the active UI backend."""
    backend_id = get_active_ui_backend_id()
    return _load_backend_component(backend_id, "dialog_map")


def supports(capability: RoleValue) -> bool:
    """Return whether the active backend implements ``capability``."""
    style_map = _load_style_map()
    checker = getattr(style_map, "supports", None)
    if checker is None:
        return False
    return bool(checker(_capability_str(capability)))


def tab_root(context: Any = None, *, parent: Any = None, expand: bool = True) -> Any:
    """Create a standard expanding column for ``create_tab_content``.

    Pass the ``TabCreateContext`` from ``create_tab_content`` to pick up
    ``context.parent``, or pass ``parent=`` directly. Prefer this over
    manually wiring ``create_column(parent=..., expand=True)``.
    """
    if context is not None and parent is None:
        parent = getattr(context, "parent", None)
    return create_column(parent=parent, expand=expand)


def create_dialog(
    title: str,
    *,
    parent: Any = None,
    modal: bool = True,
    default_size: Optional[tuple[int, int]] = None,
) -> Any:
    """Create a toolkit-neutral content dialog handle.

    ``parent`` is an optional attachment hint. Dialog completion is delivered
    through :func:`open_dialog`; this API does not expose a blocking result.
    ``default_size`` is a best-effort pixel-oriented initial window hint that
    backends without window sizing semantics may ignore.
    """
    if default_size is not None:
        width, height = (int(default_size[0]), int(default_size[1]))
        if width <= 0 or height <= 0:
            raise ValueError("default_size dimensions must be positive")
        default_size = (width, height)
    return _load_dialog_map().create_dialog(
        title,
        parent=parent,
        modal=modal,
        default_size=default_size,
    )


def set_dialog_content(dialog: Any, content: Any) -> None:
    """Attach definitions-built ``content`` to a dialog handle."""
    _load_dialog_map().set_dialog_content(dialog, content)


def open_dialog(
    dialog: Any,
    *,
    on_closed: Optional[Callable[[bool], None]] = None,
) -> None:
    """Open a dialog and report acceptance through ``on_closed``.

    Modal dialogs remain callback-driven; callers never receive a blocking
    return value from this facade.
    """
    _load_dialog_map().open_dialog(dialog, on_closed=on_closed)


def close_dialog(dialog: Any, *, accepted: bool = False) -> None:
    """Close a dialog with an accepted or rejected result."""
    _load_dialog_map().close_dialog(dialog, accepted=accepted)


def accept_dialog(dialog: Any) -> None:
    """Accept and close a content dialog."""
    _load_dialog_map().accept_dialog(dialog)


def reject_dialog(dialog: Any) -> None:
    """Reject and close a content dialog."""
    _load_dialog_map().reject_dialog(dialog)


def dialog_button_row(dialog: Any, *, save_cancel: bool = True) -> Any:
    """Create a standard Save/Cancel or Close row for ``dialog``."""
    row = create_row()
    add_stretch(row)
    if save_cancel:
        add(
            row,
            create_button(
                "Cancel",
                on_click=lambda: reject_dialog(dialog),
            ),
        )
        add(
            row,
            create_button(
                "Save",
                on_click=lambda: accept_dialog(dialog),
            ),
        )
    else:
        add(
            row,
            create_button(
                "Close",
                on_click=lambda: accept_dialog(dialog),
            ),
        )
    return row


def pick_save_file(
    title: str,
    *,
    parent: Any = None,
    name_filter: str = "",
    default_name: str = "",
) -> Optional[str]:
    """Ask for a destination path using the active backend.

    Returns ``None`` when the picker is cancelled or unavailable.
    """
    picker = getattr(_load_dialog_map(), "pick_save_file", None)
    if picker is None:
        return None
    return picker(
        title,
        parent=parent,
        name_filter=name_filter,
        default_name=default_name,
    )


def create_button(
    text: str,
    role: RoleValue = ButtonRole.DEFAULT,
    parent: Any = None,
    *,
    on_click: Optional[Callable[[], None]] = None,
) -> Any:
    """Create a button with the given semantic role for the active backend.

    ``parent`` is an optional attachment hint for backends that use ownership
    trees; other backends may ignore it.

    Pass ``on_click=callback`` to wire the press handler in one step (same as
    calling :func:`on_click` afterward).
    """
    button = _load_style_map().create_button(text, _role_str(role), parent)
    if on_click is not None:
        _load_style_map().on_click(button, on_click)
    return button


def create_label(
    text: str,
    role: RoleValue = LabelRole.BODY,
    parent: Any = None,
    *,
    wrap: bool = True,
    align: str = "start",
) -> Any:
    """Create a label with the given semantic role for the active backend.

    ``parent`` is an optional attachment hint; backends may ignore it.
    Set ``wrap=False`` for compact single-line status text.
    ``align`` is one of ``start``, ``center``, or ``end``.
    """
    return _load_style_map().create_label(
        text,
        _role_str(role),
        parent,
        wrap=wrap,
        align=align,
    )


def create_input(
    role: RoleValue = InputRole.DEFAULT,
    parent: Any = None,
    placeholder: str = "",
) -> Any:
    """Create a text input with the given semantic role for the active backend.

    ``parent`` is an optional attachment hint; backends may ignore it.
    """
    return _load_style_map().create_input(_role_str(role), parent, placeholder)


def create_text_area(
    role: RoleValue = InputRole.DEFAULT,
    parent: Any = None,
    *,
    read_only: bool = True,
    expand: bool = False,
    wrap: bool = True,
    monospace: bool = False,
) -> Any:
    """Create a multiline text area (e.g. logs) for the active backend.

    Prefer ``expand=True`` (when :attr:`UICapability.EXPAND` is available) over
    pixel heights. ``parent`` is an optional attachment hint.
    """
    return _load_style_map().create_text_area(
        _role_str(role),
        parent,
        read_only=read_only,
        expand=expand,
        wrap=wrap,
        monospace=monospace,
    )


def create_combo(items: Sequence[ComboItem] = (), parent: Any = None) -> Any:
    """Create a single-selection control.

    Items may be display strings or ``(label, opaque_value)`` tuples.
    """
    return _load_style_map().create_combo(_normalize_combo_items(items), parent)


def create_spin(
    minimum: int,
    maximum: int,
    value: int = 0,
    parent: Any = None,
) -> Any:
    """Create an integer input constrained to the inclusive range."""
    return _load_style_map().create_spin(minimum, maximum, value, parent)


def create_checkbox(
    text: str = "",
    checked: bool = False,
    parent: Any = None,
) -> Any:
    """Create a boolean checkbox, optionally with a text label."""
    return _load_style_map().create_checkbox(text, checked, parent)


def create_table(
    columns: Sequence[str],
    parent: Any = None,
    *,
    check_column: Optional[int] = None,
    selectable: bool = True,
    sortable: bool = False,
    stretch_column: Optional[int] = None,
) -> Any:
    """Create a read-only table with optional selection and check controls.

    ``sortable`` is a preference rather than a capability requirement;
    backends without interactive sorting may ignore it.
    """
    return _load_style_map().create_table(
        list(columns),
        parent,
        check_column=check_column,
        selectable=selectable,
        sortable=sortable,
        stretch_column=stretch_column,
    )


def set_table_rows(
    table: Any,
    rows: Sequence[Union[TableRow, Sequence[str]]],
) -> None:
    """Replace table rows while preserving plain-sequence compatibility."""
    normalized = []
    for row in rows:
        if isinstance(row, TableRow):
            normalized.append(
                {
                    "key": row.key,
                    "cells": [str(cell) for cell in row.cells],
                    "checked": bool(row.checked),
                    "role": _role_str(row.role) if row.role is not None else None,
                    "tooltip": row.tooltip,
                }
            )
            continue
        cells = [str(cell) for cell in row]
        normalized.append(
            {
                "key": cells[0] if cells else None,
                "cells": cells,
                "checked": False,
                "role": None,
                "tooltip": None,
            }
        )
    _load_style_map().set_table_rows(table, normalized)


def apply_button_role(widget: Any, role: RoleValue) -> None:
    """Apply a button role to an existing (possibly raw) widget."""
    _load_style_map().apply_button_role(widget, _role_str(role))


def apply_label_role(widget: Any, role: RoleValue) -> None:
    """Apply a label role to an existing (possibly raw) widget."""
    _load_style_map().apply_label_role(widget, _role_str(role))


def apply_input_role(widget: Any, role: RoleValue) -> None:
    """Apply an input role to an existing (possibly raw) widget."""
    _load_style_map().apply_input_role(widget, _role_str(role))


def spacing(name: str = SPACING_MEDIUM) -> Any:
    """Return a backend-specific spacing value for the named token.

    The return type is opaque (often an ``int`` on pixel backends). Prefer
    named tokens via container helpers rather than hard-coding sizes in
    plugins. Meaningful when :attr:`UICapability.PIXEL_SIZING` is supported.
    """
    return _load_style_map().spacing(name)


def create_column(parent: Any = None, *, expand: bool = False) -> Any:
    """Create a vertical container for the active backend.

    Use ``expand=True`` for tab roots when the backend supports
    :attr:`UICapability.EXPAND`. ``parent`` is an optional attachment hint.
    """
    return _load_style_map().create_column(parent, expand=expand)


def create_row(parent: Any = None, *, expand: bool = False) -> Any:
    """Create a horizontal container for the active backend.

    ``parent`` is an optional attachment hint; backends may ignore it.
    """
    return _load_style_map().create_row(parent, expand=expand)


def create_group(title: str, parent: Any = None) -> Any:
    """Create a titled vertical content group."""
    return _load_style_map().create_group(title, parent)


def create_card(parent: Any = None) -> Any:
    """Create an untitled themed card container for grouped content."""
    return _load_style_map().create_card(parent)


def create_tabs(parent: Any = None) -> Any:
    """Create a required multi-section tab container."""
    return _load_style_map().create_tabs(parent)


def add_tab(tabs: Any, content: Any, title: str) -> None:
    """Add titled ``content`` to a container created by :func:`create_tabs`."""
    _load_style_map().add_tab(tabs, content, title)


def create_form(parent: Any = None) -> Any:
    """Create a required label-and-control form container."""
    return _load_style_map().create_form(parent)


def add_form_row(form: Any, label: str, widget: Any) -> None:
    """Add a labeled control or value to a form."""
    _load_style_map().add_form_row(form, label, widget)


def create_split(orientation: str = "horizontal", parent: Any = None) -> Any:
    """Create a multi-pane container; falls back to a column when unsupported.

    When :attr:`UICapability.SPLIT` is unavailable, panes added with
    :func:`add` stack vertically instead of becoming a resizable split.
    """
    key = orientation.strip().lower()
    if key not in {"horizontal", "vertical"}:
        raise ValueError("orientation must be 'horizontal' or 'vertical'")
    if not supports(UICapability.SPLIT):
        return create_column(parent, expand=True)
    return _load_style_map().create_split(key, parent)


def set_split_proportions(
    split: Any,
    proportions: Sequence[Union[int, float]],
) -> None:
    """Set relative pane proportions on a supported split container.

    Ratios such as ``(3, 2)`` are backend-neutral and avoid pixel sizing.
    This is a no-op when split containers are unavailable.
    """
    if not supports(UICapability.SPLIT):
        return
    values = [float(value) for value in proportions]
    if not values or any(value < 0 for value in values) or not any(values):
        raise ValueError("proportions must contain at least one positive ratio")
    _load_style_map().set_split_proportions(split, values)


def set_expand(widget: Any, expand: bool = True) -> Any:
    """Ask ``widget`` to fill leftover space when the backend supports it.

    No-op when :attr:`UICapability.EXPAND` is unavailable. Stretch weights are
    a backend-internal detail and are not part of this facade.
    """
    if not supports(UICapability.EXPAND):
        return widget
    _load_style_map().set_expand(widget, expand)
    return widget


def add(container: Any, child: Any) -> None:
    """Add ``child`` to a column/row/group/split created by this module."""
    _load_style_map().add(container, child)


def add_stretch(container: Any) -> None:
    """Add a flexible spacer when the backend supports stretch; otherwise no-op."""
    if not supports(UICapability.STRETCH):
        return
    _load_style_map().add_stretch(container)


def on_click(widget: Any, callback: Callable[[], None]) -> None:
    """Connect a no-arg click/press callback on a button widget."""
    _load_style_map().on_click(widget, callback)


def on_change(widget: Any, callback: Callable[[Any], None]) -> None:
    """Connect a value-change callback to an input, combo, spin, or checkbox."""
    _load_style_map().on_change(widget, callback)


def on_select(table: Any, callback: Callable[[Any], None]) -> None:
    """Connect a callback receiving the selected table row key."""
    _load_style_map().on_select(table, callback)


def on_row_toggled(
    table: Any,
    callback: Callable[[Any, bool], None],
) -> None:
    """Connect a callback receiving a table row key and checked state."""
    _load_style_map().on_row_toggled(table, callback)


def get_selected_key(table: Any) -> Any:
    """Return the stable key for the selected table row, or ``None``."""
    return _load_style_map().get_selected_key(table)


def select_row(table: Any, key: Any) -> bool:
    """Select the row with ``key``; return whether it was found."""
    return bool(_load_style_map().select_row(table, key))


def on_context_menu(
    widget: Any,
    builder: Callable[[], Sequence[MenuAction]],
) -> None:
    """Attach an optional content context menu.

    This is a no-op on backends without :attr:`UICapability.CONTEXT_MENU`.
    """
    if not supports(UICapability.CONTEXT_MENU):
        return

    def normalized_builder() -> list[dict[str, Any]]:
        return [
            {
                "label": action.label,
                "on_select": action.on_select,
                "enabled": bool(action.enabled),
                "separator_before": bool(action.separator_before),
            }
            for action in builder()
        ]

    _load_style_map().on_context_menu(widget, normalized_builder)


def on_interval(
    callback: Callable[[], None],
    interval_ms: int,
    parent: Any = None,
) -> Any:
    """Start a repeating timer; returns a backend-specific handle.

    ``parent`` is an optional lifetime hint for backends that tie timers to
    a content tree; other backends may ignore it.
    """
    return _load_style_map().on_interval(callback, interval_ms, parent)


def stop_interval(handle: Any) -> None:
    """Stop a timer returned by ``on_interval``."""
    _load_style_map().stop_interval(handle)


def append_text(
    widget: Any,
    text: str,
    *,
    role: Optional[RoleValue] = None,
) -> None:
    """Append one themed line to a text-area-like control."""
    _load_style_map().append_text(
        widget,
        str(text),
        role=_role_str(role) if role is not None else None,
    )


def append_log_text(widget: Any, text: str, *, level: int) -> None:
    """Append one log line using the same level colors as console logging."""
    from ..services.logging_service import log_display_role

    append_text(widget, str(text), role=log_display_role(level))


def clear_text(widget: Any) -> None:
    """Clear a text-area-like control."""
    _load_style_map().clear_text(widget)


def scroll_to_end(widget: Any) -> None:
    """Scroll a text-area-like control to its final line."""
    _load_style_map().scroll_to_end(widget)


def set_text(widget: Any, text: str) -> None:
    """Set display text on a label, text area, or compatible widget."""
    _load_style_map().set_text(widget, text)


def get_text(widget: Any) -> str:
    """Return text from an input, label, combo, or compatible control."""
    return str(_load_style_map().get_text(widget))


def get_value(widget: Any) -> Any:
    """Return the current value of an input, combo, or spin control."""
    return _load_style_map().get_value(widget)


def set_value(widget: Any, value: Any) -> None:
    """Set the current value of an input, combo, or spin control."""
    _load_style_map().set_value(widget, value)


def _normalize_combo_items(
    items: Sequence[ComboItem],
) -> list[tuple[str, Any]]:
    """Normalize combo labels and opaque values for backend maps."""
    normalized: list[tuple[str, Any]] = []
    for item in items:
        if isinstance(item, tuple):
            if len(item) != 2:
                raise ValueError("combo item tuples must contain (label, value)")
            normalized.append((str(item[0]), item[1]))
        else:
            normalized.append((str(item), None))
    return normalized


def set_items(widget: Any, items: Sequence[ComboItem]) -> None:
    """Replace the choices in a combo-like control."""
    _load_style_map().set_items(widget, _normalize_combo_items(items))


def set_enabled(widget: Any, enabled: bool = True) -> None:
    """Enable or disable an interactive control."""
    _load_style_map().set_enabled(widget, enabled)


def is_checked(widget: Any) -> bool:
    """Return the boolean state of a checkbox-like control."""
    return bool(_load_style_map().is_checked(widget))


def set_checked(widget: Any, checked: bool, *, notify: bool = True) -> None:
    """Set a checkbox state, optionally suppressing its change callback."""
    _load_style_map().set_checked(widget, checked, notify=notify)


def set_visible(widget: Any, visible: bool = True) -> None:
    """Show or hide a content element."""
    _load_style_map().set_visible(widget, visible)


def set_tooltip(widget: Any, text: str) -> None:
    """Set best-effort explanatory text for pointer-capable backends."""
    setter = getattr(_load_style_map(), "set_tooltip", None)
    if setter is not None:
        setter(widget, text)


def copy_to_clipboard(text: str) -> None:
    """Copy text when the active backend provides a clipboard."""
    copier = getattr(_load_style_map(), "copy_to_clipboard", None)
    if copier is not None:
        copier(text)


__all__ = [
    "ROLE_PROPERTY",
    "SPACING_SMALL",
    "SPACING_MEDIUM",
    "SPACING_LARGE",
    "SPACING_NAMES",
    "ButtonRole",
    "LabelRole",
    "InputRole",
    "UICapability",
    "TableRow",
    "MenuAction",
    "ComboItem",
    "supports",
    "tab_root",
    "create_dialog",
    "set_dialog_content",
    "open_dialog",
    "close_dialog",
    "accept_dialog",
    "reject_dialog",
    "dialog_button_row",
    "pick_save_file",
    "create_button",
    "create_label",
    "create_input",
    "create_text_area",
    "create_combo",
    "create_spin",
    "create_checkbox",
    "create_table",
    "set_table_rows",
    "apply_button_role",
    "apply_label_role",
    "apply_input_role",
    "spacing",
    "create_column",
    "create_row",
    "create_group",
    "create_card",
    "create_tabs",
    "add_tab",
    "create_form",
    "add_form_row",
    "create_split",
    "set_split_proportions",
    "set_expand",
    "add",
    "add_stretch",
    "on_click",
    "on_change",
    "on_select",
    "on_row_toggled",
    "get_selected_key",
    "select_row",
    "on_context_menu",
    "on_interval",
    "stop_interval",
    "append_text",
    "append_log_text",
    "clear_text",
    "scroll_to_end",
    "set_text",
    "get_text",
    "get_value",
    "set_value",
    "set_items",
    "set_enabled",
    "is_checked",
    "set_checked",
    "set_visible",
    "set_tooltip",
    "copy_to_clipboard",
]
