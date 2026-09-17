"""
Qt style map for shared UI definitions.

Implements create/apply helpers used by ``GUI.app.ui.definitions``. Plugins
should not import this module directly — use the definitions facade instead.
"""

from __future__ import annotations

from typing import Any, Callable

from .bindings import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFontDatabase,
    QFrame,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPalette,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextCharFormat,
    QTextCursor,
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
CAPABILITIES = frozenset(
    {"split", "stretch", "expand", "pixel_sizing", "context_menu"}
)


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


def create_label(
    text: str,
    role: str = "body",
    parent: Any = None,
    *,
    wrap: bool = True,
    align: str = "start",
) -> QLabel:
    """Create a QLabel with the given role."""
    label = QLabel(text, parent)
    label.setWordWrap(bool(wrap))
    alignment = str(align or "start").strip().lower()
    if alignment == "center":
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        # Expand horizontally so text centers within the parent column/row.
        label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
    elif alignment == "end":
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    else:
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
    wrap: bool = True,
    monospace: bool = False,
) -> QTextEdit:
    """Create a multiline text area (e.g. event log)."""
    edit = QTextEdit(parent)
    edit.setReadOnly(read_only)
    edit.document().setMaximumBlockCount(10000)
    edit.setLineWrapMode(
        QTextEdit.LineWrapMode.WidgetWidth
        if wrap
        else QTextEdit.LineWrapMode.NoWrap
    )
    if monospace:
        edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    apply_input_role(edit, role)
    if expand:
        set_expand(edit, True)
    return edit


def create_combo(items: list[tuple[str, Any]], parent: Any = None) -> QComboBox:
    """Create a QComboBox populated with labels and opaque values."""
    combo = QComboBox(parent)
    for label, value in items:
        combo.addItem(label, value)
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


def create_checkbox(
    text: str = "",
    checked: bool = False,
    parent: Any = None,
) -> QCheckBox:
    """Create a QCheckBox with an initial state."""
    checkbox = QCheckBox(text, parent)
    checkbox.setChecked(bool(checked))
    return checkbox


def create_table(
    columns: list[str],
    parent: Any = None,
    *,
    check_column: int | None = None,
    selectable: bool = True,
    sortable: bool = False,
    stretch_column: int | None = None,
) -> QTableWidget:
    """Create a read-only QTableWidget with neutral row semantics."""
    table = QTableWidget(parent)
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
        if selectable
        else QAbstractItemView.SelectionMode.NoSelection
    )
    table.setSortingEnabled(bool(sortable))
    table.setProperty("_cp_check_column", -1 if check_column is None else check_column)

    header = table.horizontalHeader()
    if stretch_column is None:
        header.setStretchLastSection(True)
    else:
        for index in range(len(columns)):
            mode = (
                QHeaderView.ResizeMode.Stretch
                if index == stretch_column
                else QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(index, mode)
    return table


def set_table_rows(table: QTableWidget, rows: list[dict[str, Any]]) -> None:
    """Replace rows while preserving stable keys and semantic metadata."""
    sorting = table.isSortingEnabled()
    signals_blocked = table.blockSignals(True)
    if sorting:
        table.setSortingEnabled(False)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        cells = row["cells"]
        key = row["key"]
        role = row.get("role")
        tooltip = row.get("tooltip")
        for column_index in range(table.columnCount()):
            value = cells[column_index] if column_index < len(cells) else ""
            item = QTableWidgetItem(value)
            item.setData(Qt.ItemDataRole.UserRole, key)
            if tooltip:
                item.setToolTip(str(tooltip))
            if role in {"warning", "error", "muted"}:
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            check_column = table.property("_cp_check_column")
            if column_index == int(check_column if check_column is not None else -1):
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if row.get("checked")
                    else Qt.CheckState.Unchecked
                )
            table.setItem(row_index, column_index, item)
    if sorting:
        table.setSortingEnabled(True)
    table.blockSignals(signals_blocked)


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


def create_card(parent: Any = None) -> QFrame:
    """Create an untitled themed card with vertical child layout."""
    card = QFrame(parent)
    card.setObjectName("card")
    card.setProperty("card", True)
    layout = QVBoxLayout(card)
    gap = spacing("medium")
    # Match CardContainer padding without importing the Qt widget helper.
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(gap)
    card.setProperty("_cp_layout_kind", "card")
    return card


def create_tabs(parent: Any = None) -> QTabWidget:
    """Create a QTabWidget whose tab bar scrolls at full label width.

    The macOS style would otherwise drop the scroll arrows, which makes the bar's
    minimum width cover every tab and widen the window, and elide every label to
    an ellipsis once the bar overflows.
    """
    tabs = QTabWidget(parent)
    set_expand(tabs, True)
    tabs.tabBar().setUsesScrollButtons(True)
    tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
    return tabs


def add_tab(tabs: QTabWidget, content: Any, title: str) -> None:
    """Add content to a QTabWidget."""
    tabs.addTab(content, title)


def create_form(parent: Any = None) -> QWidget:
    """Create a QWidget backed by QFormLayout."""
    form = QWidget(parent)
    layout = QFormLayout(form)
    gap = spacing("medium")
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(gap)
    form.setProperty("_cp_layout_kind", "form")
    return form


def add_form_row(form: QWidget, label: str, widget: Any) -> None:
    """Add a labeled row to a definitions form."""
    layout = form.layout()
    if not isinstance(layout, QFormLayout):
        raise ValueError("Form has no supported definitions form layout")
    layout.addRow(label, widget)


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


def set_split_proportions(
    split: QSplitter,
    proportions: list[float],
) -> None:
    """Apply relative stretch factors and initial QSplitter pane sizes."""
    weights = [max(0, round(proportion * 1000)) for proportion in proportions]
    for index, weight in enumerate(weights):
        split.setStretchFactor(index, weight)
    # QSplitter otherwise combines stretch factors with each child's size hint,
    # which can let a detail pane start larger despite a higher table ratio.
    split.setSizes(weights)


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


def on_change(widget: Any, callback: Callable[[Any], None]) -> None:
    """Connect a supported control's semantic value-change signal."""
    if isinstance(widget, QLineEdit):
        widget.textChanged.connect(callback)
    elif isinstance(widget, QComboBox):
        widget.currentTextChanged.connect(callback)
    elif isinstance(widget, QSpinBox):
        widget.valueChanged.connect(callback)
    elif isinstance(widget, QCheckBox):
        widget.toggled.connect(callback)
    else:
        raise TypeError(f"Cannot connect value changes on {type(widget)!r}")


def get_selected_key(table: QTableWidget) -> Any:
    """Return the stable key of the current table row."""
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    return item.data(Qt.ItemDataRole.UserRole) if item is not None else None


def select_row(table: QTableWidget, key: Any) -> bool:
    """Select a table row by stable key."""
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == key:
            table.selectRow(row)
            return True
    return False


def on_select(table: QTableWidget, callback: Callable[[Any], None]) -> None:
    """Connect table selection changes to a stable-key callback."""
    table.itemSelectionChanged.connect(lambda: callback(get_selected_key(table)))


def on_row_toggled(
    table: QTableWidget,
    callback: Callable[[Any, bool], None],
) -> None:
    """Connect check-column changes to a stable-key callback."""
    def changed(item: QTableWidgetItem) -> None:
        value = table.property("_cp_check_column")
        check_column = int(value if value is not None else -1)
        if item.column() != check_column:
            return
        callback(
            item.data(Qt.ItemDataRole.UserRole),
            item.checkState() == Qt.CheckState.Checked,
        )

    table.itemChanged.connect(changed)


def on_context_menu(
    widget: Any,
    builder: Callable[[], list[dict[str, Any]]],
) -> None:
    """Attach a QMenu built on demand without exposing QPoint."""
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def show_menu(position: Any) -> None:
        if isinstance(widget, QTableWidget):
            index = widget.indexAt(position)
            if not index.isValid():
                return
            widget.selectRow(index.row())

        actions = builder()
        if not actions:
            return
        menu = QMenu(widget)
        for spec in actions:
            if spec.get("separator_before"):
                menu.addSeparator()
            action = menu.addAction(str(spec["label"]))
            action.setEnabled(bool(spec.get("enabled", True)))
            callback = spec["on_select"]
            action.triggered.connect(lambda _checked=False, cb=callback: cb())
        target = widget.viewport() if hasattr(widget, "viewport") else widget
        menu.exec(target.mapToGlobal(position))

    widget.customContextMenuRequested.connect(show_menu)


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


_role_color_cache: dict[tuple[int, str], Any] = {}


def invalidate_text_role_colors() -> None:
    """Drop cached semantic text colors after a theme or palette change."""
    _role_color_cache.clear()


def _color_for_role(widget: Any, role: str) -> Any:
    key = (id(widget), role)
    cached = _role_color_cache.get(key)
    if cached is not None:
        return cached
    probe = QLabel("", widget)
    apply_label_role(probe, role)
    probe.ensurePolished()
    color = probe.palette().color(QPalette.ColorRole.WindowText)
    probe.deleteLater()
    _role_color_cache[key] = color
    return color


def append_text(
    widget: Any,
    text: str,
    *,
    role: str | None = None,
) -> None:
    """Append a line to QTextEdit using a theme-derived semantic color."""
    if not isinstance(widget, QTextEdit):
        raise TypeError(f"Cannot append text to {type(widget)!r}")

    color = _color_for_role(widget, role or "body")

    text_format = QTextCharFormat()
    text_format.setForeground(color)
    cursor = widget.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(f"{text}\n", text_format)


def clear_text(widget: Any) -> None:
    """Clear a supported Qt text control."""
    if not hasattr(widget, "clear"):
        raise TypeError(f"Cannot clear text on {type(widget)!r}")
    widget.clear()


def scroll_to_end(widget: Any) -> None:
    """Scroll a supported Qt text control to its end."""
    if not hasattr(widget, "verticalScrollBar"):
        raise TypeError(f"Cannot scroll text on {type(widget)!r}")
    scrollbar = widget.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())


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
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QComboBox):
        data = widget.currentData()
        return widget.currentText() if data is None else data
    return get_text(widget)


def set_value(widget: Any, value: Any) -> None:
    """Set the semantic value of a supported Qt control."""
    if isinstance(widget, QSpinBox):
        widget.setValue(int(value))
    elif isinstance(widget, QCheckBox):
        widget.setChecked(bool(value))
    elif isinstance(widget, QComboBox):
        index = widget.findData(value)
        if index < 0:
            index = widget.findText(str(value))
        if index >= 0:
            widget.setCurrentIndex(index)
        else:
            raise ValueError(f"Unknown combo value {value!r}")
    elif hasattr(widget, "setText"):
        widget.setText(str(value))
    else:
        raise TypeError(f"Cannot set value on {type(widget)!r}")


def set_items(widget: Any, items: list[tuple[str, Any]]) -> None:
    """Replace the choices in a QComboBox."""
    if not isinstance(widget, QComboBox):
        raise TypeError(f"Cannot set items on {type(widget)!r}")
    widget.clear()
    for label, value in items:
        widget.addItem(label, value)


def set_enabled(widget: Any, enabled: bool = True) -> None:
    """Set the enabled state of a Qt widget."""
    widget.setEnabled(bool(enabled))


def is_checked(widget: Any) -> bool:
    """Return a QCheckBox state."""
    if not isinstance(widget, QCheckBox):
        raise TypeError(f"Cannot read checked state from {type(widget)!r}")
    return widget.isChecked()


def set_checked(
    widget: Any,
    checked: bool,
    *,
    notify: bool = True,
) -> None:
    """Set a QCheckBox state with optional signal suppression."""
    if not isinstance(widget, QCheckBox):
        raise TypeError(f"Cannot set checked state on {type(widget)!r}")
    if notify:
        widget.setChecked(bool(checked))
        return
    was_blocked = widget.blockSignals(True)
    widget.setChecked(bool(checked))
    widget.blockSignals(was_blocked)


def set_visible(widget: Any, visible: bool = True) -> None:
    """Set a Qt widget's visibility."""
    widget.setVisible(bool(visible))


def set_tooltip(widget: Any, text: str) -> None:
    """Set a Qt widget tooltip."""
    widget.setToolTip(str(text))


def copy_to_clipboard(text: str) -> None:
    """Copy text through the active QApplication clipboard."""
    QApplication.clipboard().setText(str(text))


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
    "create_checkbox",
    "create_table",
    "set_table_rows",
    "spacing",
    "set_expand",
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
