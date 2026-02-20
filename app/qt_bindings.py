"""
Qt binding shim.

Import Qt classes from here instead of directly from a concrete binding
so swapping bindings later is localized to this module.

Supported bindings (via QT_BINDING env var): pyside6 (default), pyqt6.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import sys
import types

def _resolve_binding() -> str:
    """Determine which Qt binding to use.

    Priority:
      1. Explicit ``QT_BINDING`` env var (``pyside6`` or ``pyqt6``).
      2. Auto-detect: try importing PySide6 first, fall back to PyQt6.

    Uses real imports (not ``find_spec``) so missing native libraries
    (e.g. ``libxkbcommon.so``) are caught and the fallback kicks in.

    This ensures PyInstaller bundles built with only one binding work
    without requiring the env var to be baked in.
    """
    explicit = os.getenv("QT_BINDING", "").strip().lower()
    if explicit:
        return explicit

    # Auto-detect: prefer PySide6, fall back to PyQt6.
    # We must actually import to surface missing shared-library errors
    # that find_spec would not catch.
    for binding in ("pyside6", "pyqt6"):
        try:
            __import__("PySide6" if binding == "pyside6" else "PyQt6")
            return binding
        except Exception:
            continue

    # Default if neither can be imported (let the later import fail with
    # a clear message).
    return "pyside6"


_binding = _resolve_binding()


def get_binding_name() -> str:
    """Return the active Qt binding name."""
    return _binding


# ---------------------------------------------------------------------------
# PyQt6 mode: neutralize shiboken and provide PySide6 -> PyQt6 shims
# ---------------------------------------------------------------------------

def _setup_pyqt6_shim() -> tuple[types.ModuleType, types.ModuleType, types.ModuleType, type, type, type]:
    """Block real PySide6/shiboken imports and install PyQt6-backed shims.

    PySide6 installs a shiboken bootstrap (via a .pth file) that registers
    a deferred import hook.  When *anything* later causes the hook to fire
    it expects the real PySide6 C extensions which our shim cannot provide.

    Strategy:
      1. Install a meta-path blocker at the *front* of ``sys.meta_path``
         that intercepts any real PySide6 / shiboken import and returns our
         shim modules (or raises ``ImportError`` for unknown sub-modules).
      2. Evict any partially-loaded PySide6 / shiboken entries from
         ``sys.modules`` so the blocker takes precedence.
      3. Remove any shiboken meta-path finders that were installed at
         interpreter startup.
      4. Populate ``sys.modules`` with the shim entries.
    """
    from PyQt6 import QtCore, QtGui, QtWidgets

    _Signal = QtCore.pyqtSignal
    _Slot = QtCore.pyqtSlot
    _Property = QtCore.pyqtProperty

    # -- Build shim modules ------------------------------------------------

    def _make_module(name: str, *, is_package: bool = False) -> types.ModuleType:
        mod = types.ModuleType(name)
        mod.__spec__ = importlib.machinery.ModuleSpec(
            name, None, is_package=is_package,
        )
        mod.__package__ = name if is_package else name.rpartition(".")[0]
        if is_package:
            mod.__path__ = []
        return mod

    pyside6 = _make_module("PySide6", is_package=True)
    pyside6.__dict__.update(
        QtCore=QtCore,
        QtGui=QtGui,
        QtWidgets=QtWidgets,
        Signal=_Signal,
        Slot=_Slot,
        Property=_Property,
    )

    # Stub sub-packages that shiboken's bootstrap probes.
    _support = _make_module("PySide6.support", is_package=True)
    _support_sig = _make_module("PySide6.support.signature", is_package=True)
    _support_sig_lib = _make_module("PySide6.support.signature.lib", is_package=True)
    _support.signature = _support_sig
    _support_sig.lib = _support_sig_lib
    pyside6.support = _support

    # Map of shim names we own.
    _shim_modules: dict[str, types.ModuleType] = {
        "PySide6": pyside6,
        "PySide6.QtCore": QtCore,
        "PySide6.QtGui": QtGui,
        "PySide6.QtWidgets": QtWidgets,
        "PySide6.support": _support,
        "PySide6.support.signature": _support_sig,
        "PySide6.support.signature.lib": _support_sig_lib,
    }

    # -- Meta-path blocker -------------------------------------------------

    _BLOCKED_ROOTS = frozenset(("PySide6", "shiboken6", "shibokensupport"))

    class _PySide6Blocker(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        """Intercept PySide6 / shiboken imports.

        Uses find_spec / create_module / exec_module (PEP 451) for Python 3.12+.
        * Known shim names  -> return our shim from ``_shim_modules``.
        * Other PySide6.*   -> raise ``ImportError`` (prevents shiboken
          from finding the real C extensions).
        * shiboken*         -> raise ``ImportError``.
        """

        def find_spec(
            self,
            fullname: str,
            path: object = None,
            target: object = None,
        ) -> importlib.machinery.ModuleSpec | None:
            top = fullname.split(".", 1)[0]
            if top not in _BLOCKED_ROOTS:
                return None
            if fullname in _shim_modules:
                mod = _shim_modules[fullname]
                return importlib.machinery.ModuleSpec(
                    fullname,
                    self,
                    is_package=hasattr(mod, "__path__"),
                )
            raise ImportError(
                f"{fullname} is not available (using PyQt6 binding)"
            )

        def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType | None:
            if spec.name in _shim_modules:
                return _shim_modules[spec.name]
            return None

        def exec_module(self, module: types.ModuleType) -> None:
            # Modules are pre-populated; nothing to execute
            pass

    # -- Apply -------------------------------------------------------------

    # 1. Remove existing shiboken finders.
    sys.meta_path[:] = [
        f for f in sys.meta_path
        if not (
            "shiboken" in getattr(type(f), "__module__", "")
            or "shiboken" in type(f).__name__.lower()
        )
    ]

    # 2. Evict partially-loaded entries.
    for key in list(sys.modules):
        if key.split(".", 1)[0] in _BLOCKED_ROOTS:
            del sys.modules[key]

    # 3. Install our blocker at the *front* so it wins over any remaining
    #    finders (including the default file-system finder).
    sys.meta_path.insert(0, _PySide6Blocker())

    # 4. Populate sys.modules with shim entries.
    sys.modules.update(_shim_modules)

    return QtCore, QtGui, QtWidgets, _Signal, _Slot, _Property


if _binding in {"pyqt6", "pyqt"}:
    QtCore, QtGui, QtWidgets, Signal, Slot, Property = _setup_pyqt6_shim()
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
    # GlobalColor aliases (PySide6-style, e.g. Qt.red -> Qt.GlobalColor.red).
    for _color_name in (
        "white", "black", "red", "darkRed", "green", "darkGreen",
        "blue", "darkBlue", "cyan", "darkCyan", "magenta", "darkMagenta",
        "yellow", "darkYellow", "gray", "darkGray", "lightGray",
        "transparent", "color0", "color1",
    ):
        if not hasattr(QtCore.Qt, _color_name) and hasattr(QtCore.Qt.GlobalColor, _color_name):
            setattr(QtCore.Qt, _color_name, getattr(QtCore.Qt.GlobalColor, _color_name))
    # About dialog enum aliases (PySide6-style).
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


def __getattr__(name: str):
    """Resolve Qt symbols from QtCore/QtGui/QtWidgets."""
    for module in (QtCore, QtGui, QtWidgets):
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"qt_bindings has no attribute {name!r}")


__all__ = ["QtCore", "QtGui", "QtWidgets", "Signal", "Slot", "Property"]
