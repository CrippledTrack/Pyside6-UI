"""
Shared UI definitions and backend-auto-dispatch helpers.

Plugins should import from this module for styled controls, forms, tables, and
layouts. The active UI backend — set at launch via
``get_active_ui_backend_id()`` — selects the correct toolkit implementation.

Desktop-only layout ideas (resizable splits, pixel heights, stretch weights,
widget parent ownership) are **optional backend capabilities**, not required
paradigms. Query them with :func:`supports` / :class:`UICapability`. Backends
that lack a capability no-op or fall back (for example, ``create_split`` stacks
panes in a column).

Example::

    from GUI.app.ui.definitions import (
        ButtonRole, LabelRole, create_button, create_label, create_column, add,
    )

    root = create_column(parent=context.parent)
    add(root, create_label("Title", role=LabelRole.HEADING))
    add(root, create_button("Save", role=ButtonRole.PRIMARY))

Raw toolkit widgets remain allowed as an escape hatch; use ``apply_*_role``
to attach semantic roles to them.
"""

from __future__ import annotations

from enum import Enum
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


RoleValue = Union[str, Enum]


def _role_str(role: RoleValue) -> str:
    return role.value if isinstance(role, Enum) else str(role)


def _capability_str(capability: RoleValue) -> str:
    return capability.value if isinstance(capability, Enum) else str(capability)


def _load_style_map() -> Any:
    """Lazily import the style_map for the active UI backend."""
    backend_id = get_active_ui_backend_id()
    if backend_id == "qt":
        from .qt import style_map

        return style_map
    if backend_id == "tui":
        try:
            from .tui import style_map
        except ImportError as exc:
            raise RuntimeError(
                "The TUI backend style map is not available yet (WIP). "
                "Use the Qt backend (default)"
            ) from exc
        return style_map
    raise RuntimeError(f"No UI definitions style map for backend '{backend_id}'")


def supports(capability: RoleValue) -> bool:
    """Return whether the active backend implements ``capability``."""
    style_map = _load_style_map()
    checker = getattr(style_map, "supports", None)
    if checker is None:
        return False
    return bool(checker(_capability_str(capability)))


def create_button(
    text: str,
    role: RoleValue = ButtonRole.DEFAULT,
    parent: Any = None,
) -> Any:
    """Create a button with the given semantic role for the active backend.

    ``parent`` is an optional attachment hint for backends that use ownership
    trees; other backends may ignore it.
    """
    return _load_style_map().create_button(text, _role_str(role), parent)


def create_label(
    text: str,
    role: RoleValue = LabelRole.BODY,
    parent: Any = None,
) -> Any:
    """Create a label with the given semantic role for the active backend.

    ``parent`` is an optional attachment hint; backends may ignore it.
    """
    return _load_style_map().create_label(text, _role_str(role), parent)


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
    )


def create_combo(items: Sequence[str] = (), parent: Any = None) -> Any:
    """Create a single-selection control populated with ``items``."""
    return _load_style_map().create_combo(list(items), parent)


def create_spin(
    minimum: int,
    maximum: int,
    value: int = 0,
    parent: Any = None,
) -> Any:
    """Create an integer input constrained to the inclusive range."""
    return _load_style_map().create_spin(minimum, maximum, value, parent)


def create_table(columns: Sequence[str], parent: Any = None) -> Any:
    """Create a read-only table with the supplied column headings."""
    return _load_style_map().create_table(list(columns), parent)


def set_table_rows(table: Any, rows: Sequence[Sequence[str]]) -> None:
    """Replace all rows in a table created by :func:`create_table`."""
    _load_style_map().set_table_rows(
        table,
        [[str(cell) for cell in row] for row in rows],
    )


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


def set_items(widget: Any, items: Sequence[str]) -> None:
    """Replace the choices in a combo-like control."""
    _load_style_map().set_items(widget, [str(item) for item in items])


def set_enabled(widget: Any, enabled: bool = True) -> None:
    """Enable or disable an interactive control."""
    _load_style_map().set_enabled(widget, enabled)


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
    "supports",
    "create_button",
    "create_label",
    "create_input",
    "create_text_area",
    "create_combo",
    "create_spin",
    "create_table",
    "set_table_rows",
    "apply_button_role",
    "apply_label_role",
    "apply_input_role",
    "spacing",
    "create_column",
    "create_row",
    "create_group",
    "create_split",
    "set_expand",
    "add",
    "add_stretch",
    "on_click",
    "on_interval",
    "stop_interval",
    "set_text",
    "get_text",
    "get_value",
    "set_value",
    "set_items",
    "set_enabled",
]
