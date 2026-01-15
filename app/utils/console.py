"""Console utility functions for controlling console window visibility.

This module provides functions to show, hide, and configure console window
visibility on Windows systems.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def hide_console_window() -> bool:
    """
    Hide the console window on Windows.
    
    Returns:
        bool: True if successfully hidden or not needed, False if hiding failed
    """
    if platform.system().lower() != "windows":
        return True  # Not needed on non-Windows platforms
    
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        # Get console window handle
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            # Hide the console window (SW_HIDE = 0)
            user32.ShowWindow(console_window, 0)
            return True
        return True  # No console window found, which is fine
    except Exception:
        # If hiding fails, return False but don't crash
        return False


def show_console_window() -> bool:
    """
    Show the console window on Windows.
    
    Returns:
        bool: True if successfully shown or not needed, False if showing failed
    """
    if platform.system().lower() != "windows":
        return True  # Not needed on non-Windows platforms
    
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        # Get console window handle
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            # Show the console window (SW_SHOW = 1)
            user32.ShowWindow(console_window, 1)
            return True
        return True  # No console window found, which is fine
    except Exception:
        # If showing fails, return False but don't crash
        return False


def set_console_visibility(show: bool) -> bool:
    """
    Set console window visibility based on SHOW_CONSOLE constant.
    
    Args:
        show (bool): True to show console, False to hide
        
    Returns:
        bool: True if operation succeeded or not needed, False if failed
    """
    if show:
        return show_console_window()
    else:
        return hide_console_window()


def apply_console_setting() -> bool:
    """
    Apply console visibility setting based on SHOW_CONSOLE and LOGGING_ENABLED constants.
    
    If LOGGING_ENABLED is False, the console will be hidden regardless of SHOW_CONSOLE,
    since there's no point displaying an empty console window.
    
    Constants are loaded with priority: app_plugins > platforms > GUI defaults.
    
    Returns:
        bool: True if operation succeeded or not needed, False if failed
    """
    try:
        # Import merged constants using the priority-based import utility
        from .imports import get_platforms_constants
        constants = get_platforms_constants()
        
        show_console = getattr(constants, 'SHOW_CONSOLE', True)
        logging_enabled = getattr(constants, 'LOGGING_ENABLED', True)
        
        # If logging is disabled, hide the console regardless of SHOW_CONSOLE setting
        # (no point showing an empty console window)
        if not logging_enabled:
            return set_console_visibility(False)
        
        return set_console_visibility(show_console)
    except Exception:
        # If import fails, default to hiding console (production behavior)
        return set_console_visibility(False)


__all__ = [
    'hide_console_window',
    'show_console_window',
    'set_console_visibility',
    'apply_console_setting',
]

