from __future__ import annotations

from typing import Optional


def build_title(version_name: str, version: str, platform_name: str,
                tab_name: Optional[str] = None, plugin_version: Optional[str] = None) -> str:
    base_title = f"{version_name} v{version} ({platform_name.capitalize()})"
    if not tab_name:
        return base_title
    if plugin_version:
        return f"{base_title} - {tab_name} v{plugin_version}"
    return f"{base_title} - {tab_name}"


__all__ = ['build_title']


