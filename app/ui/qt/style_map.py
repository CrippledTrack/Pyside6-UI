"""
Qt style map for shared UI definitions.

Implements create/apply helpers used by ``GUI.app.ui.definitions``. Plugins
should not import this module directly — use the definitions facade instead.
"""

from __future__ import annotations

from typing import Any, Callable

from .bindings import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
)

# Keep in sync with theme _base spacing constants / definitions token names.
SPACING_PX = {
    "small": 4,
    "medium": 8,
    "large": 16,
}

ROLE_PROPERTY = "cp_role"


def _refresh_style(widget: Any) -> None:
    """Force Qt to re-evaluate dynamic property selectors."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def apply_button_role(widget: Any, role: str) -> None:
    """Apply a semantic button role via ``cp_role`` / ``flat`` properties."""
    role = (role or "default").strip().lower()
    widget.setProperty(ROLE_PROPERTY, role)
    if role == "flat":
        widget.setFlat(True)
        widget.setProperty("flat", True)
    else:
        # Clear flat so QSS [flat="true"] does not stick after role changes.
        if hasattr(widget, "setFlat"):
            widget.setFlat(False)
        widget.setProperty("flat", False)
    _refresh_style(widget)


def apply_label_role(widget: Any, role: str) -> None:
    """Apply a semantic label role."""
    role = (role or "body").strip().lower()
    widget.setProperty(ROLE_PROPERTY, role)
    if role == "heading":
        widget.setObjectName("heading")
    elif role == "field_label":
        # Preserve existing theme quirk selector.
        widget.setProperty("variant", "field_label")
    _refresh_style(widget)


def apply_input_role(widget: Any, role: str) -> None:
    """Apply a semantic input role."""
    role = (role or "default").strip().lower()
    widget.setProperty(ROLE_PROPERTY, role)
    _refresh_style(widget)


def create_button(text: str, role: str = "default", parent: Any = None) -> QPushButton:
    """Create a QPushButton with the given role."""
    btn = QPushButton(text, parent)
    apply_button_role(btn, role)
    return btn


def create_label(text: str, role: str = "body", parent: Any = None) -> QLabel:
    """Create a QLabel with the given role."""
    label = QLabel(text, parent)
    label.setWordWrap(True)
    apply_label_role(label, role)
    return label


def create_input(
    role: str = "default",
    parent: Any = None,
    placeholder: str = "",
) -> QLineEdit:
    """Create a QLineEdit with the given role."""
    edit = QLineEdit(parent)
    if placeholder:
        edit.setPlaceholderText(placeholder)
    apply_input_role(edit, role)
    return edit


def create_text_area(
    role: str = "default",
    parent: Any = None,
    *,
    read_only: bool = True,
    min_height: int | None = None,
) -> QTextEdit:
    """Create a multiline text area (e.g. event log)."""
    edit = QTextEdit(parent)
    edit.setReadOnly(read_only)
    if min_height is not None:
        edit.setMinimumHeight(int(min_height))
    apply_input_role(edit, role)
    return edit


def spacing(name: str = "medium") -> int:
    """Return spacing in pixels for the given token name."""
    key = (name or "medium").strip().lower()
    if key not in SPACING_PX:
        raise ValueError(f"Unknown spacing token '{name}'. Expected one of {tuple(SPACING_PX)}")
    return SPACING_PX[key]


def create_column(parent: Any = None) -> QWidget:
    """Create a vertical box container widget."""
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    gap = spacing("medium")
    layout.setContentsMargins(gap, gap, gap, gap)
    layout.setSpacing(gap)
    container.setProperty("_cp_layout_kind", "column")
    return container


def create_row(parent: Any = None) -> QWidget:
    """Create a horizontal box container widget."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    gap = spacing("medium")
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(gap)
    container.setProperty("_cp_layout_kind", "row")
    return container


def add(container: Any, child: Any) -> None:
    """Add a child widget to a column/row container."""
    layout = container.layout()
    if layout is None:
        raise ValueError("Container has no layout; use create_column/create_row")
    layout.addWidget(child)


def add_stretch(container: Any, stretch: int = 1) -> None:
    """Add a stretch spacer to a column/row container."""
    layout = container.layout()
    if layout is None:
        raise ValueError("Container has no layout; use create_column/create_row")
    layout.addStretch(stretch)


def on_click(widget: Any, callback: Callable[[], None]) -> None:
    """Connect a button click to a no-arg callback."""
    widget.clicked.connect(callback)


def on_interval(
    callback: Callable[[], None],
    interval_ms: int,
    parent: Any = None,
) -> QTimer:
    """Start a repeating timer; returns the QTimer handle."""
    timer = QTimer(parent)
    timer.timeout.connect(callback)
    timer.start(int(interval_ms))
    return timer


def stop_interval(handle: Any) -> None:
    """Stop a timer returned by ``on_interval``."""
    if handle is not None and hasattr(handle, "stop"):
        handle.stop()


def set_text(widget: Any, text: str) -> None:
    """Set text on a label or similar widget."""
    if hasattr(widget, "setPlainText"):
        widget.setPlainText(text)
    elif hasattr(widget, "setText"):
        widget.setText(text)
    else:
        raise TypeError(f"Cannot set text on {type(widget)!r}")


__all__ = [
    "SPACING_PX",
    "ROLE_PROPERTY",
    "apply_button_role",
    "apply_label_role",
    "apply_input_role",
    "create_button",
    "create_label",
    "create_input",
    "create_text_area",
    "spacing",
    "create_column",
    "create_row",
    "add",
    "add_stretch",
    "on_click",
    "on_interval",
    "stop_interval",
    "set_text",
]
