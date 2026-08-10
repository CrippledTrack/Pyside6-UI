"""
Qt style map for shared UI definitions.

Implements create/apply helpers used by ``GUI.app.ui.definitions``. Plugins
should not import this module directly — use the definitions facade instead.
"""

from __future__ import annotations

from typing import Any, Callable

from .bindings import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)

# Keep in sync with theme _base spacing constants / definitions token names.
SPACING_PX = {
    "small": 4,
    "medium": 8,
    "large": 16,
}

ROLE_PROPERTY = "cp_role"

# Capabilities advertised to ``GUI.app.ui.definitions.supports``.
CAPABILITIES = frozenset({"split", "stretch", "expand", "pixel_sizing"})


def supports(capability: str) -> bool:
    """Return whether this Qt style map implements ``capability``."""
    return str(capability).strip().lower() in CAPABILITIES


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
    expand: bool = False,
) -> QTextEdit:
    """Create a multiline text area (e.g. event log)."""
    edit = QTextEdit(parent)
    edit.setReadOnly(read_only)
    apply_input_role(edit, role)
    if expand:
        set_expand(edit, True)
    return edit


def create_combo(items: list[str], parent: Any = None) -> QComboBox:
    """Create a QComboBox populated with string items."""
    combo = QComboBox(parent)
    combo.addItems(items)
    apply_input_role(combo, "default")
    return combo


def create_spin(
    minimum: int,
    maximum: int,
    value: int = 0,
    parent: Any = None,
) -> QSpinBox:
    """Create a bounded QSpinBox."""
    spin = QSpinBox(parent)
    spin.setRange(int(minimum), int(maximum))
    spin.setValue(int(value))
    apply_input_role(spin, "default")
    return spin


def create_table(columns: list[str], parent: Any = None) -> QTableWidget:
    """Create a read-only table with stretchable final column."""
    table = QTableWidget(parent)
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def set_table_rows(table: QTableWidget, rows: list[list[str]]) -> None:
    """Replace all rows in a QTableWidget."""
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column_index in range(table.columnCount()):
            value = row[column_index] if column_index < len(row) else ""
            table.setItem(row_index, column_index, QTableWidgetItem(value))


def spacing(name: str = "medium") -> int:
    """Return spacing in pixels for the given token name."""
    key = (name or "medium").strip().lower()
    if key not in SPACING_PX:
        raise ValueError(f"Unknown spacing token '{name}'. Expected one of {tuple(SPACING_PX)}")
    return SPACING_PX[key]


def set_expand(widget: Any, expand: bool = True) -> None:
    """Mark a widget to fill leftover space in its parent layout."""
    widget.setProperty("_cp_expand", bool(expand))
    # Stretch weight stays backend-internal (definitions no longer exposes it).
    widget.setProperty("_cp_expand_stretch", 1 if expand else 0)
    if expand:
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
    else:
        widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )


def create_column(parent: Any = None, *, expand: bool = False) -> QWidget:
    """Create a vertical box container widget."""
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    gap = spacing("medium")
    layout.setContentsMargins(gap, gap, gap, gap)
    layout.setSpacing(gap)
    container.setProperty("_cp_layout_kind", "column")
    if expand:
        set_expand(container, True)
    return container


def create_row(parent: Any = None, *, expand: bool = False) -> QWidget:
    """Create a horizontal box container widget."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    gap = spacing("medium")
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(gap)
    container.setProperty("_cp_layout_kind", "row")
    if expand:
        set_expand(container, True)
    return container


def create_group(title: str, parent: Any = None) -> QGroupBox:
    """Create a titled group with vertical child layout."""
    group = QGroupBox(title, parent)
    layout = QVBoxLayout(group)
    gap = spacing("medium")
    layout.setContentsMargins(gap, gap, gap, gap)
    layout.setSpacing(gap)
    group.setProperty("_cp_layout_kind", "group")
    return group


def create_split(orientation: str = "horizontal", parent: Any = None) -> QSplitter:
    """Create a horizontal or vertical QSplitter."""
    qt_orientation = (
        Qt.Orientation.Horizontal
        if orientation == "horizontal"
        else Qt.Orientation.Vertical
    )
    split = QSplitter(qt_orientation, parent)
    split.setProperty("_cp_layout_kind", "split")
    set_expand(split, True)
    return split


def add(container: Any, child: Any) -> None:
    """Add a child widget to a definitions container."""
    if container.property("_cp_layout_kind") == "split":
        container.addWidget(child)
        return

    layout = container.layout()
    if layout is None:
        raise ValueError("Container has no supported definitions layout")
    stretch = 0
    try:
        if bool(child.property("_cp_expand")):
            stretch = int(child.property("_cp_expand_stretch") or 1)
    except Exception:
        stretch = 1 if getattr(child, "_cp_expand", False) else 0
    layout.addWidget(child, stretch)


def add_stretch(container: Any) -> None:
    """Add a stretch spacer to a column/row container."""
    if container.property("_cp_layout_kind") == "split":
        raise ValueError("Split containers do not support stretch spacers")
    layout = container.layout()
    if layout is None:
        raise ValueError("Container has no layout; use create_column/create_row")
    layout.addStretch(1)


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


def get_text(widget: Any) -> str:
    """Read text from a supported Qt control."""
    if hasattr(widget, "currentText"):
        return str(widget.currentText())
    if hasattr(widget, "toPlainText"):
        return str(widget.toPlainText())
    if hasattr(widget, "text"):
        return str(widget.text())
    raise TypeError(f"Cannot get text from {type(widget)!r}")


def get_value(widget: Any) -> Any:
    """Read the semantic value of a supported Qt control."""
    if isinstance(widget, QSpinBox):
        return widget.value()
    if isinstance(widget, QComboBox):
        return widget.currentText()
    return get_text(widget)


def set_value(widget: Any, value: Any) -> None:
    """Set the semantic value of a supported Qt control."""
    if isinstance(widget, QSpinBox):
        widget.setValue(int(value))
    elif isinstance(widget, QComboBox):
        index = widget.findText(str(value))
        if index >= 0:
            widget.setCurrentIndex(index)
        else:
            raise ValueError(f"Unknown combo value {value!r}")
    elif hasattr(widget, "setText"):
        widget.setText(str(value))
    else:
        raise TypeError(f"Cannot set value on {type(widget)!r}")


def set_items(widget: Any, items: list[str]) -> None:
    """Replace the choices in a QComboBox."""
    if not isinstance(widget, QComboBox):
        raise TypeError(f"Cannot set items on {type(widget)!r}")
    widget.clear()
    widget.addItems(items)


def set_enabled(widget: Any, enabled: bool = True) -> None:
    """Set the enabled state of a Qt widget."""
    widget.setEnabled(bool(enabled))


__all__ = [
    "SPACING_PX",
    "ROLE_PROPERTY",
    "CAPABILITIES",
    "supports",
    "apply_button_role",
    "apply_label_role",
    "apply_input_role",
    "create_button",
    "create_label",
    "create_input",
    "create_text_area",
    "create_combo",
    "create_spin",
    "create_table",
    "set_table_rows",
    "spacing",
    "set_expand",
    "create_column",
    "create_row",
    "create_group",
    "create_split",
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
