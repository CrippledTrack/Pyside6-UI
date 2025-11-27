"""
Mock modules for Windows-specific dependencies when running on Linux in dev mode.

This module provides stub implementations of pywin32 and related modules
to allow Windows plugins to be loaded (for UI testing) on Linux systems.

Note: The actual functionality won't work, but the imports will succeed
and the UI can be tested.
"""

from __future__ import annotations

import sys
import logging
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)


class MockModule(ModuleType):
    """A mock module that returns mock objects for any attribute access."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.__name__ = name
        self.__file__ = f"<mock {name}>"
        self.__loader__ = None
        self.__package__ = name.rsplit('.', 1)[0] if '.' in name else ''
    
    def __getattr__(self, name: str) -> Any:
        """Return a mock for any attribute access."""
        if name.startswith('_'):
            raise AttributeError(name)
        # Return a callable mock that can be used as both a class and function
        return MockCallable(f"{self.__name__}.{name}")
    
    def __repr__(self) -> str:
        return f"<MockModule '{self.__name__}'>"


class MockCallable:
    """A mock callable that can be used as a function, class, or constant."""
    
    def __init__(self, name: str):
        self._name = name
    
    def __call__(self, *args: Any, **kwargs: Any) -> "MockCallable":
        """Allow calling as a function or class constructor."""
        return MockCallable(f"{self._name}()")
    
    def __getattr__(self, name: str) -> "MockCallable":
        """Allow chained attribute access."""
        if name.startswith('_'):
            raise AttributeError(name)
        return MockCallable(f"{self._name}.{name}")
    
    def __repr__(self) -> str:
        return f"<Mock {self._name}>"
    
    def __str__(self) -> str:
        return f"<Mock {self._name}>"
    
    def __bool__(self) -> bool:
        return False
    
    def __int__(self) -> int:
        return 0
    
    def __iter__(self):
        return iter([])
    
    def __len__(self) -> int:
        return 0


# List of Windows-specific modules to mock
WIN32_MODULES = [
    # pywin32 core modules
    'win32api',
    'win32con',
    'win32gui',
    'win32security',
    'win32service',
    'win32serviceutil',
    'win32event',
    'win32file',
    'win32process',
    'win32net',
    'win32netcon',
    'win32ts',
    'win32profile',
    'win32cred',
    'win32timezone',
    'win32pipe',
    'pywintypes',
    'ntsecuritycon',
    'servicemanager',
    'winerror',
    # win32com modules
    'win32com',
    'win32com.client',
    'win32com.server',
    'win32com.shell',
    'win32com.shell.shell',
    'win32com.shell.shellcon',
    # pythoncom
    'pythoncom',
    # Windows-specific ctypes modules (these exist but behave differently)
    'winreg',
    '_winreg',
]


_mocks_installed = False


def install_win32_mocks() -> None:
    """Install mock modules for Windows-specific dependencies.
    
    This should only be called in dev mode when cross-platform tabs are enabled.
    """
    global _mocks_installed
    
    if _mocks_installed:
        logger.debug("Win32 mocks already installed")
        return
    
    logger.warning("Installing mock modules for Windows dependencies (dev mode)")
    
    for module_name in WIN32_MODULES:
        if module_name not in sys.modules:
            sys.modules[module_name] = MockModule(module_name)
            logger.debug(f"Installed mock for: {module_name}")
    
    _mocks_installed = True
    logger.info(f"Installed {len(WIN32_MODULES)} Windows module mocks for cross-platform testing")


def uninstall_win32_mocks() -> None:
    """Remove mock modules from sys.modules.
    
    This is primarily for testing purposes.
    """
    global _mocks_installed
    
    for module_name in WIN32_MODULES:
        if module_name in sys.modules and isinstance(sys.modules[module_name], MockModule):
            del sys.modules[module_name]
            logger.debug(f"Removed mock for: {module_name}")
    
    _mocks_installed = False
    logger.info("Removed Windows module mocks")


def are_mocks_installed() -> bool:
    """Check if Windows mocks are currently installed."""
    return _mocks_installed


__all__ = ['install_win32_mocks', 'uninstall_win32_mocks', 'are_mocks_installed', 'WIN32_MODULES']

