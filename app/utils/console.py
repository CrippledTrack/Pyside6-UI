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
    
    Returns:
        bool: True if operation succeeded or not needed, False if failed
    """
    try:
        show_console = True  # Default to showing
        logging_enabled = True  # Default to enabled
        
        # Import constants - try app_plugins first, then legacy platforms, then GUI app constants
        try:
            # Try new name first
            from app_plugins.constants import SHOW_CONSOLE, LOGGING_ENABLED
            show_console = SHOW_CONSOLE
            logging_enabled = LOGGING_ENABLED
        except ImportError:
            try:
                # If running from GUI directory, try parent directory with new name
                import os
                parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                from app_plugins.constants import SHOW_CONSOLE, LOGGING_ENABLED
                show_console = SHOW_CONSOLE
                logging_enabled = LOGGING_ENABLED
            except ImportError:
                # LEGACY: Support for old 'platforms/' folder name (deprecated, 3.0.0 compatibility)
                try:
                    from platforms.constants import SHOW_CONSOLE
                    show_console = SHOW_CONSOLE
                    # LOGGING_ENABLED may not exist in legacy, default to True
                    try:
                        from platforms.constants import LOGGING_ENABLED
                        logging_enabled = LOGGING_ENABLED
                    except ImportError:
                        pass
                except ImportError:
                    # LEGACY: Support for old 'platforms/' folder name with path manipulation (deprecated, 3.0.0 compatibility)
                    try:
                        parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                        if parent_dir not in sys.path:
                            sys.path.insert(0, parent_dir)
                        from platforms.constants import SHOW_CONSOLE
                        show_console = SHOW_CONSOLE
                    except ImportError:
                        from ..constants import SHOW_CONSOLE
                        show_console = SHOW_CONSOLE
        
        # If logging is disabled, hide the console regardless of SHOW_CONSOLE setting
        # (no point showing an empty console window)
        if not logging_enabled:
            return set_console_visibility(False)
        
        return set_console_visibility(show_console)
    except ImportError:
        # If import fails, default to hiding console (production behavior)
        return set_console_visibility(False)


__all__ = [
    'hide_console_window',
    'show_console_window',
    'set_console_visibility',
    'apply_console_setting',
]

