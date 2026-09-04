"""Classic / new UI path smoke (no display required for classic stylesheet)."""

from __future__ import annotations

from GUI.app.ui.qt.themes.classic_theme_manager import get_classic_stylesheet
from GUI.app.ui.qt.themes.theme_manager import ThemeManager
from GUI.app.ui.qt.themes.ui_mode import classic_stylesheet_for, is_classic_ui
from GUI.app.services.settings_service import SettingsService


def test_classic_stylesheet_reachable() -> None:
    theme_data = {
        "name": "dark",
        "palette": {
            "background": "#1e1e1e",
            "foreground": "#ffffff",
            "highlight": "#0078d4",
            "button": "#333333",
            "button_text": "#ffffff",
            "border": "#555555",
        },
    }
    css = get_classic_stylesheet(theme_data)
    assert isinstance(css, str)
    assert len(css) > 0
    via_helper = classic_stylesheet_for(None, theme_data)
    assert via_helper == css


def test_new_ui_settings_roundtrip() -> None:
    settings = SettingsService()
    settings.save_new_ui_enabled(False)
    assert settings.get_new_ui_enabled() is False
    settings.save_new_ui_enabled(True)
    assert settings.get_new_ui_enabled() is True
    assert hasattr(ThemeManager, "is_legacy_ui")
    assert hasattr(ThemeManager, "apply_theme")
    assert is_classic_ui(None) is False


def test_about_info_builds_html() -> None:
    from GUI.app.utils import about_info

    html = about_info.build_about_info(
        app_name="Test",
        gui_api_version="5.3.0",
        platform_name="linux",
    )
    assert "Test" in html
    assert "5.3.0" in html
