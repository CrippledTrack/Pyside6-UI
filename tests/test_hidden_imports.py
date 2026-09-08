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
    prefix = "" if build_mod.IS_STANDALONE else f"{build_mod.GUI_ROOT.name}."
    assert f"{prefix}app.ui.qt.style_map" in imports
    assert f"{prefix}app.ui.qt.dialog_map" in imports
    themes = build_mod.GUI_ROOT / "app" / "ui" / "qt" / "themes" / "builtin_themes"
    missing = []
    for path in themes.glob("*.py"):
        if path.stem.startswith("_"):
            continue
        name = f"{prefix}app.ui.qt.themes.builtin_themes.{path.stem}"
        if name not in imports:
            missing.append(name)
    assert missing == [], f"Frozen hidden imports omit theme modules: {missing}"
