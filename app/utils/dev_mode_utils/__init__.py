"""
Dev mode utilities for cross-platform testing and development.

This package contains utilities that are only used when running in dev mode,
such as cross-platform plugin loading and Windows/Linux API mocks.
"""

from .cross_platform_plugins import load_cross_platform_plugins, clear_cross_platform_cache
from .win32_mocks import install_win32_mocks, uninstall_win32_mocks, are_mocks_installed
from .linux_mocks import install_linux_mocks, uninstall_linux_mocks, are_linux_mocks_installed

__all__ = [
    'load_cross_platform_plugins',
    'clear_cross_platform_cache',
    'install_win32_mocks',
    'uninstall_win32_mocks',
    'are_mocks_installed',
    'install_linux_mocks',
    'uninstall_linux_mocks',
    'are_linux_mocks_installed',
]

