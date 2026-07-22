"""
Shared UI definitions and backend-auto-dispatch helpers.

Plugins should import from this module only for styled basics (buttons, labels,
inputs, simple column/row layouts). The active UI backend — set at launch via
``get_active_ui_backend_id()`` — selects the correct toolkit implementation.

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
from typing import Any, Callable, Optional, Union

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


class InputRole(str, Enum):
    """Semantic input roles."""

    DEFAULT = "default"


RoleValue = Union[str, Enum]


def _role_str(role: RoleValue) -> str:
    return role.value if isinstance(role, Enum) else str(role)


def _load_style_map() -> Any:
    """Lazily import the style_map for the active UI backend."""
    backend_id = get_active_ui_backend_id()
    if backend_id == "qt":
        from .qt import style_map

        return style_map
    if backend_id == "tui":
        from .tui import style_map

        return style_map
    raise RuntimeError(f"No UI definitions style map for backend '{backend_id}'")


def create_button(
    text: str,
    role: RoleValue = ButtonRole.DEFAULT,
    parent: Any = None,
) -> Any:
    """Create a button with the given semantic role for the active backend."""
    return _load_style_map().create_button(text, _role_str(role), parent)


def create_label(
    text: str,
    role: RoleValue = LabelRole.BODY,
    parent: Any = None,
) -> Any:
    """Create a label with the given semantic role for the active backend."""
    return _load_style_map().create_label(text, _role_str(role), parent)


def create_input(
    role: RoleValue = InputRole.DEFAULT,
    parent: Any = None,
    placeholder: str = "",
) -> Any:
    """Create a text input with the given semantic role for the active backend."""
    return _load_style_map().create_input(_role_str(role), parent, placeholder)


def create_text_area(
    role: RoleValue = InputRole.DEFAULT,
    parent: Any = None,
    *,
    read_only: bool = True,
    min_height: Optional[int] = None,
    expand: bool = False,
) -> Any:
    """Create a multiline text area (e.g. logs) for the active backend.

    When ``expand`` is True, the widget grows to fill leftover space in its
    parent column (TUI ``1fr`` / Qt expanding size policy).
    """
    return _load_style_map().create_text_area(
        _role_str(role),
        parent,
        read_only=read_only,
        min_height=min_height,
        expand=expand,
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


def spacing(name: str = SPACING_MEDIUM) -> int:
    """Return the spacing value for ``name`` (``small`` / ``medium`` / ``large``)."""
    return int(_load_style_map().spacing(name))


def create_column(parent: Any = None, *, expand: bool = False) -> Any:
    """Create a vertical container for the active backend.

    Use ``expand=True`` for tab roots so the column fills the host pane.
    """
    return _load_style_map().create_column(parent, expand=expand)


def create_row(parent: Any = None, *, expand: bool = False) -> Any:
    """Create a horizontal container for the active backend."""
    return _load_style_map().create_row(parent, expand=expand)


def set_expand(widget: Any, expand: bool = True, stretch: int = 1) -> Any:
    """Mark ``widget`` to fill leftover space in its parent layout."""
    _load_style_map().set_expand(widget, expand, stretch)
    return widget


def add(container: Any, child: Any) -> None:
    """Add ``child`` to a column/row created by this module."""
    _load_style_map().add(container, child)


def add_stretch(container: Any, stretch: int = 1) -> None:
    """Add a flexible spacer to a column/row (no-op on backends without stretch)."""
    _load_style_map().add_stretch(container, stretch)


def on_click(widget: Any, callback: Callable[[], None]) -> None:
    """Connect a no-arg click/press callback on a button widget."""
    _load_style_map().on_click(widget, callback)


def on_interval(
    callback: Callable[[], None],
    interval_ms: int,
    parent: Any = None,
) -> Any:
    """Start a repeating timer; returns a backend-specific handle."""
    return _load_style_map().on_interval(callback, interval_ms, parent)


def stop_interval(handle: Any) -> None:
    """Stop a timer returned by ``on_interval``."""
    _load_style_map().stop_interval(handle)


def set_text(widget: Any, text: str) -> None:
    """Set display text on a label, text area, or compatible widget."""
    _load_style_map().set_text(widget, text)


__all__ = [
    "ROLE_PROPERTY",
    "SPACING_SMALL",
    "SPACING_MEDIUM",
    "SPACING_LARGE",
    "SPACING_NAMES",
    "ButtonRole",
    "LabelRole",
    "InputRole",
    "create_button",
    "create_label",
    "create_input",
    "create_text_area",
    "apply_button_role",
    "apply_label_role",
    "apply_input_role",
    "spacing",
    "create_column",
    "create_row",
    "set_expand",
    "add",
    "add_stretch",
    "on_click",
    "on_interval",
    "stop_interval",
    "set_text",
]
