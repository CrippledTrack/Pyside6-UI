"""
Qt binding abstraction layer.

Import Qt classes from here instead of directly from a concrete binding
so swapping bindings later is localized to this module.

Supported bindings: pyside6 (default), pyqt6.
"""

from __future__ import annotations

import os

def _resolve_binding() -> str:
    """Determine which Qt binding to use."""
    explicit = os.getenv("QT_BINDING", "").strip().lower()
    if explicit:
        return explicit

    for binding in ("pyside6", "pyqt6"):
        try:
            __import__("PySide6" if binding == "pyside6" else "PyQt6")
            return binding
        except ImportError:
            continue

    return "pyside6"

_binding = _resolve_binding()

def get_binding_name() -> str:
    """Return the active Qt binding name."""
    return _binding

if _binding in {"pyqt6", "pyqt"}:
    from PyQt6 import QtCore, QtGui, QtWidgets
    Signal = QtCore.pyqtSignal
    Slot = QtCore.pyqtSlot
    Property = QtCore.pyqtProperty

    # Provide PySide6-style Signal/Slot/Property on QtCore module.
    if not hasattr(QtCore, "Signal"):
        QtCore.Signal = Signal
    if not hasattr(QtCore, "Slot"):
        QtCore.Slot = Slot
    if not hasattr(QtCore, "Property"):
        QtCore.Property = Property

    # Back-compat aliases for PySide6-style enum access.
    if not hasattr(QtCore.Qt, "Horizontal"):
        QtCore.Qt.Horizontal = QtCore.Qt.Orientation.Horizontal
    if not hasattr(QtCore.Qt, "Vertical"):
        QtCore.Qt.Vertical = QtCore.Qt.Orientation.Vertical
    if not hasattr(QtWidgets.QFrame, "StyledPanel"):
        QtWidgets.QFrame.StyledPanel = QtWidgets.QFrame.Shape.StyledPanel
    if not hasattr(QtGui.QFont, "Bold"):
        QtGui.QFont.Bold = QtGui.QFont.Weight.Bold
    if not hasattr(QtWidgets.QHeaderView, "ResizeToContents"):
        QtWidgets.QHeaderView.ResizeToContents = QtWidgets.QHeaderView.ResizeMode.ResizeToContents
    if not hasattr(QtWidgets.QTreeWidget, "ExtendedSelection"):
        QtWidgets.QTreeWidget.ExtendedSelection = QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
    if not hasattr(QtCore.Qt, "CustomContextMenu"):
        QtCore.Qt.CustomContextMenu = QtCore.Qt.ContextMenuPolicy.CustomContextMenu
    
    # GlobalColor aliases
    for _color_name in (
        "white", "black", "red", "darkRed", "green", "darkGreen",
        "blue", "darkBlue", "cyan", "darkCyan", "magenta", "darkMagenta",
        "yellow", "darkYellow", "gray", "darkGray", "lightGray",
        "transparent", "color0", "color1",
    ):
        if not hasattr(QtCore.Qt, _color_name) and hasattr(QtCore.Qt.GlobalColor, _color_name):
            setattr(QtCore.Qt, _color_name, getattr(QtCore.Qt.GlobalColor, _color_name))
            
    # About dialog enum aliases
    if not hasattr(QtCore.Qt, "RichText"):
        QtCore.Qt.RichText = QtCore.Qt.TextFormat.RichText
    if not hasattr(QtCore.Qt, "NonModal"):
        QtCore.Qt.NonModal = QtCore.Qt.WindowModality.NonModal
    if not hasattr(QtCore.Qt, "WA_DeleteOnClose"):
        QtCore.Qt.WA_DeleteOnClose = QtCore.Qt.WidgetAttribute.WA_DeleteOnClose
    if not hasattr(QtWidgets.QMessageBox, "Close"):
        QtWidgets.QMessageBox.Close = QtWidgets.QMessageBox.StandardButton.Close
        
elif _binding in {"pyside6", "pyside"}:
    from PySide6 import QtCore, QtGui, QtWidgets
    Signal = QtCore.Signal
    Slot = QtCore.Slot
    Property = QtCore.Property
else:
    raise ImportError(f"Unsupported QT_BINDING: {_binding}")

def is_valid(obj: object) -> bool:
    """Check if a Qt object's underlying C++ object is still valid (not deleted)."""
    if _binding in {"pyqt6", "pyqt"}:
        try:
            from PyQt6 import sip
            return not sip.isdeleted(obj)
        except (ImportError, TypeError):
            return obj is not None
    else:
        try:
            import shiboken6
            return shiboken6.isValid(obj)
        except (ImportError, TypeError):
            return obj is not None

def __getattr__(name: str):
    """Resolve Qt symbols from QtCore/QtGui/QtWidgets."""
    for module in (QtCore, QtGui, QtWidgets):
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"qt_bindings has no attribute {name!r}")

__all__ = ["QtCore", "QtGui", "QtWidgets", "Signal", "Slot", "Property", "is_valid"]
