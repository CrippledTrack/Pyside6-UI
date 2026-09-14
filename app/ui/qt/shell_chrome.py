"""Qt chrome helpers for IMainWindowShell implementations.

Keeps menu / toolbar / status wiring out of MainWindow while remaining
toolkit-specific (QAction, QMenu, QToolBar).
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple, TYPE_CHECKING

from .bindings import QAction, QIcon, QMenu, QToolBar, Qt

if TYPE_CHECKING:
    from .bindings import QMainWindow, QWidget


def add_menu_action(
    window: "QMainWindow",
    menu_title: str,
    label: str,
    callback: Callable[[], None],
    shortcut: Optional[str] = None,
    icon: Optional[str] = None,
    enabled: bool = True,
    separator_before: bool = False,
    separator_after: bool = False,
) -> Tuple[QAction, QMenu, bool, Optional[QAction], Optional[QAction]]:
    """Add a menu action to a top-level menu on ``window``."""
    from .bindings import is_valid as _qt_is_valid

    menu_bar = window.menuBar()
    target_menu = None
    was_created = False

    for action in menu_bar.actions():
        try:
            menu = action.menu()
        except Exception:
            continue
        if not _qt_is_valid(menu):
            continue
        if action.text().replace("&", "") == menu_title:
            target_menu = menu
            break

    if target_menu is None:
        target_menu = menu_bar.addMenu(menu_title)
        was_created = True

    sep_before_action = None
    if separator_before:
        sep_before_action = target_menu.addSeparator()

    action = QAction(label, window)
    # Qt's macOS heuristics map labels such as "About …" to AboutRole and
    # would otherwise replace the host About item in the application menu.
    action.setMenuRole(QAction.MenuRole.NoRole)
    action.triggered.connect(callback)
    if shortcut:
        action.setShortcut(shortcut)
    if icon:
        action.setIcon(QIcon(icon))
    action.setEnabled(enabled)
    target_menu.addAction(action)

    sep_after_action = None
    if separator_after:
        sep_after_action = target_menu.addSeparator()

    return action, target_menu, was_created, sep_before_action, sep_after_action


def remove_menu_action(action: QAction, target_menu: QMenu) -> None:
    """Remove a menu action from a target menu."""
    from .bindings import is_valid as _qt_is_valid

    if target_menu and _qt_is_valid(target_menu) and _qt_is_valid(action):
        target_menu.removeAction(action)
        action.deleteLater()


def remove_qmenu_if_empty(window: "QMainWindow", menu: QMenu) -> None:
    """Remove a top-level menu if it contains no actions."""
    from .bindings import is_valid as _qt_is_valid

    if not _qt_is_valid(menu):
        return
    if len(menu.actions()) == 0:
        menu_bar = window.menuBar()
        for action in menu_bar.actions():
            try:
                action_menu = action.menu()
            except Exception:
                continue
            if action_menu == menu:
                menu_bar.removeAction(action)
                if _qt_is_valid(action):
                    action.deleteLater()
                if _qt_is_valid(menu):
                    menu.deleteLater()
                break


def get_or_create_plugin_toolbar(
    window: "QMainWindow",
    existing: Optional[QToolBar],
) -> QToolBar:
    """Return ``existing`` or create and attach a plugin toolbar on ``window``."""
    if existing is not None:
        return existing

    toolbar = QToolBar("Plugin Toolbar", window)
    toolbar.setObjectName("PluginToolbar")
    toolbar.setMovable(True)
    toolbar.setFloatable(True)

    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
    toolbar.hide()
    return toolbar


def add_toolbar_action(
    window: "QMainWindow",
    toolbar: QToolBar,
    label: str,
    callback: Callable[[], None],
    icon: Optional[str] = None,
    tooltip: Optional[str] = None,
    checkable: bool = False,
    checked: bool = False,
) -> QAction:
    """Add an action to ``toolbar`` and show the toolbar if needed."""
    action = QAction(label, window)
    action.triggered.connect(callback)
    if icon:
        action.setIcon(QIcon(icon))
    if tooltip:
        action.setToolTip(tooltip)
    if checkable:
        action.setCheckable(True)
        action.setChecked(checked)
    toolbar.addAction(action)
    if toolbar.actions():
        toolbar.show()
    return action


def remove_toolbar_action(toolbar: Optional[QToolBar], action: QAction) -> None:
    """Remove a toolbar action and hide the toolbar if empty."""
    from .bindings import is_valid as _qt_is_valid

    if toolbar and _qt_is_valid(action):
        toolbar.removeAction(action)
        action.deleteLater()
        if not toolbar.actions():
            toolbar.hide()


def remove_status_widget(window: "QMainWindow", widget: "QWidget") -> None:
    """Remove a permanent status-bar widget."""
    from .bindings import is_valid as _qt_is_valid

    if widget and _qt_is_valid(widget):
        window.statusBar().removeWidget(widget)
        widget.hide()
        widget.deleteLater()


__all__ = [
    "add_menu_action",
    "remove_menu_action",
    "remove_qmenu_if_empty",
    "get_or_create_plugin_toolbar",
    "add_toolbar_action",
    "remove_toolbar_action",
    "remove_status_widget",
]
