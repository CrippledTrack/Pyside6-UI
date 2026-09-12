"""Settings writer/schema and HostConfig path isolation."""

from __future__ import annotations

import json
from pathlib import Path

from GUI.app.host_config import HostConfig, get_host_config
from GUI.app.services.settings_service import SETTINGS_SCHEMA_VERSION, SettingsService


def test_plugin_settings_lost_update_is_merged(_isolate_host_paths: Path) -> None:
    path = _isolate_host_paths / "merge.json"
    a = SettingsService(settings_file=path)
    b = SettingsService(settings_file=path)
    a.save_plugin_settings("pluginA", {"x": 1})
    b.save_plugin_settings("pluginB", {"y": 2})
    reloaded = SettingsService(settings_file=path)
    ps = reloaded.get_settings().plugin_settings
    assert ps["pluginA"]["x"] == 1
    assert ps["pluginB"]["y"] == 2


def test_future_schema_preserves_unknown_fields_and_refuses_save(
    _isolate_host_paths: Path,
) -> None:
    path = _isolate_host_paths / "future.json"
    original = {
        "settings_schema_version": 99,
        "theme": "dark",
        "future_only_field": "keep-me",
        "plugin_settings": {},
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    svc = SettingsService(settings_file=path)
    assert svc.get_settings().settings_schema_version == 99
    svc.save_theme_preference("light")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["future_only_field"] == "keep-me"
    assert on_disk["settings_schema_version"] == 99
    assert on_disk["theme"] == "dark"


def test_unknown_fields_preserved_on_known_schema(_isolate_host_paths: Path) -> None:
    path = _isolate_host_paths / "unknown.json"
    path.write_text(
        json.dumps(
            {
                "settings_schema_version": SETTINGS_SCHEMA_VERSION,
                "theme": "dark",
                "custom_host_flag": True,
            }
        ),
        encoding="utf-8",
    )
    svc = SettingsService(settings_file=path)
    svc.save_theme_preference("light")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["custom_host_flag"] is True
    assert on_disk["theme"] == "light"


def test_host_config_data_dir_is_used(_isolate_host_paths: Path) -> None:
    cfg = get_host_config()
    assert cfg.user_data_dir == _isolate_host_paths
    svc = SettingsService()
    svc.save_theme_preference("dark")
    assert (_isolate_host_paths / "settings.json").exists()


def test_host_config_explicit_user_data_dir(_isolate_host_paths: Path) -> None:
    nested = _isolate_host_paths / "profile"
    cfg = HostConfig(app_id="host", user_data_dir=nested, portable=False)
    svc = SettingsService(host_config=cfg)
    svc.save_dev_mode(True)
    assert (nested / "settings.json").exists()


def test_skip_unchanged_theme_and_plugin_override_writes(_isolate_host_paths: Path) -> None:
    path = _isolate_host_paths / "skip.json"
    svc = SettingsService(settings_file=path)
    svc.save_theme_preference("dark")
    first_mtime = path.stat().st_mtime_ns
    svc.save_theme_preference("dark")
    assert path.stat().st_mtime_ns == first_mtime

    assert svc.has_plugin_override_keys() is False
    svc.save_plugin_overrides([], [])
    assert svc.has_plugin_override_keys() is True
    after_first = path.read_text(encoding="utf-8")
    mtime = path.stat().st_mtime_ns
    svc.save_plugin_overrides([], [])
    assert path.stat().st_mtime_ns == mtime
    assert path.read_text(encoding="utf-8") == after_first


def test_missing_override_keys_are_not_treated_as_empty_lists(
    _isolate_host_paths: Path,
) -> None:
    path = _isolate_host_paths / "no-overrides.json"
    path.write_text(
        json.dumps(
            {
                "settings_schema_version": SETTINGS_SCHEMA_VERSION,
                "theme": "dark",
            }
        ),
        encoding="utf-8",
    )
    svc = SettingsService(settings_file=path)
    assert svc.has_plugin_override_keys() is False
    assert svc.get_disabled_plugins() == []
    assert svc.get_enabled_plugins() == []
