"""
Display utility functions for formatting version information and window titles.

This module provides functions for building and formatting version information
and window titles for display in the application.
"""

from __future__ import annotations

from typing import Dict, Optional


def _format_platform_name(platform_name: str) -> str:
    """Return a human-friendly platform label for titles/metadata."""
    normalized = str(platform_name).lower()
    mapping = {
        "windows": "Windows",
        "linux": "Linux",
        "darwin": "macOS",
    }
    return mapping.get(normalized, platform_name.capitalize())


def build_title(version_name: str, version: str, platform_name: str,
                tab_name: Optional[str] = None, plugin_version: Optional[str] = None) -> str:
    """
    Build a window title string with version and platform information.
    
    Args:
        version_name: Name of the application version
        version: Version string (e.g., "3.0.0")
        platform_name: Platform name (e.g., "windows", "linux")
        tab_name: Optional name of the current tab
        plugin_version: Optional version string for the current plugin
        
    Returns:
        Formatted title string
    """
    pretty_platform = _format_platform_name(platform_name)
    base_title = f"{version_name} v{version} ({pretty_platform})"
    if not tab_name:
        return base_title
    if plugin_version:
        return f"{base_title} - {tab_name} v{plugin_version}"
    return f"{base_title} - {tab_name}"


def build_version_details(version_info: Dict[str, str], platform_name: str) -> Dict[str, str]:
    """
    Build version details dictionary for display.
    
    Args:
        version_info: Dictionary containing version information
        platform_name: Platform name (e.g., "windows", "linux")
        
    Returns:
        Dictionary with formatted version details for display
    """
    pretty_platform = _format_platform_name(platform_name)
    return {
        "version": version_info["version"],
        "name": version_info["name"],
        "platform": pretty_platform,
        "supported_platforms": ", ".join(version_info["supported_platforms"]) if isinstance(version_info.get("supported_platforms"), (list, tuple)) else version_info.get("supported_platforms", ""),
        "description": version_info.get("description", ""),
    }


def get_other_platforms_text() -> str:
    """
    Return a human-readable list of other platforms (excluding the current one) for display/tooltips.
    
    Returns:
        Comma-separated string of other platform names (e.g. "Windows, macOS")
    """
    from ..constants import CURRENT_PLATFORM
    platform_labels = {
        "windows": "Windows",
        "linux": "Linux",
        "darwin": "macOS",
    }
    all_platform_keys = ["windows", "linux", "darwin"]
    other_platforms = [
        platform_labels[p]
        for p in all_platform_keys
        if p != CURRENT_PLATFORM and p in platform_labels
    ]
    return ", ".join(other_platforms) if other_platforms else "other platforms"


__all__ = ['build_title', 'build_version_details', 'get_other_platforms_text']

