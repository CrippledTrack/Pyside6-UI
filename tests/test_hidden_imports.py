"""Hidden-import list for dynamically loaded UI maps and builtin themes."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_build_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
    spec = importlib.util.spec_from_file_location("gui_build_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_hidden_imports_includes_dynamic_ui_modules() -> None:
    build_mod = _load_build_module()
    imports = set(build_mod._collect_hidden_imports())
    # Standalone and parent-project entry points both import the app as a
    # subpackage of the GUI directory, so the prefix is not layout-dependent.
    prefix = f"{build_mod.GUI_ROOT.name}."
    assert f"{prefix}app.ui.qt.style_map" in imports
    assert f"{prefix}app.ui.qt.dialog_map" in imports
    assert f"{prefix}app._build_info_generated" in imports
    themes = build_mod.GUI_ROOT / "app" / "ui" / "qt" / "themes" / "builtin_themes"
    missing = []
    for path in themes.glob("*.py"):
        if path.stem.startswith("_"):
            continue
        name = f"{prefix}app.ui.qt.themes.builtin_themes.{path.stem}"
        if name not in imports:
            missing.append(name)
    assert missing == [], f"Frozen hidden imports omit theme modules: {missing}"


def test_hidden_imports_match_runtime_module_names() -> None:
    """Collected names must match what importlib asks for at runtime."""
    from GUI.app.ui import definitions
    from GUI.app.ui.qt.themes import theme_manager

    build_mod = _load_build_module()
    imports = set(build_mod._collect_hidden_imports())

    for component in ("style_map", "dialog_map"):
        name = f"{definitions.__package__}.qt.{component}"
        assert name in imports, f"definitions loads {name} but it is not collected"

    themes_package = f"{theme_manager.__name__.rsplit('.', 1)[0]}.builtin_themes"
    missing = [
        f"{themes_package}.{module}"
        for module in sorted(set(theme_manager._BUILTIN_THEME_MODULES.values()))
        if f"{themes_package}.{module}" not in imports
    ]
    assert missing == [], f"Builtin theme factories are not collected: {missing}"
