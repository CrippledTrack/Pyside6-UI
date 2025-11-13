"""
Display utility functions for formatting version information and window titles.

This module provides functions for building and formatting version information
and window titles for display in the application.
"""

from __future__ import annotations

from typing import Dict, Optional


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
    base_title = f"{version_name} v{version} ({platform_name.capitalize()})"
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
    return {
        "version": version_info["version"],
        "name": version_info["name"],
        "platform": platform_name.capitalize(),
        "supported_platforms": ", ".join(version_info["supported_platforms"]) if isinstance(version_info.get("supported_platforms"), (list, tuple)) else version_info.get("supported_platforms", ""),
        "description": version_info.get("description", ""),
    }


__all__ = ['build_title', 'build_version_details']

