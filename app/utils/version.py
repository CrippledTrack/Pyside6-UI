"""
Version information utilities.

This module provides functions for building and formatting version
information for display in the application.
"""

from __future__ import annotations

from typing import Dict


def build_version_details(version_info: Dict[str, str], platform_name: str) -> Dict[str, str]:
    """Build version details dictionary for display."""
    return {
        "version": version_info["version"],
        "name": version_info["name"],
        "platform": platform_name.capitalize(),
        "supported_platforms": ", ".join(version_info["supported_platforms"]) if isinstance(version_info.get("supported_platforms"), (list, tuple)) else version_info.get("supported_platforms", ""),
        "description": version_info.get("description", ""),
    }


__all__ = ['build_version_details']


