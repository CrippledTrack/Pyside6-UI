"""
Mock modules for Linux-specific dependencies when running on Windows in dev mode.

This module provides stub implementations of Linux-only modules
to allow Linux plugins to be loaded (for UI testing) on Windows systems.

Note: The actual functionality won't work, but the imports will succeed
and the UI can be tested.
"""

from __future__ import annotations

import sys
import logging
from types import ModuleType
from typing import Any, Iterator, NamedTuple

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
    
    def __iter__(self) -> Iterator:
        return iter([])
    
    def __len__(self) -> int:
        return 0


# Mock passwd entry (struct_passwd)
class MockPasswd(NamedTuple):
    """Mock passwd structure returned by pwd module functions."""
    pw_name: str = "mockuser"
    pw_passwd: str = "x"
    pw_uid: int = 1000
    pw_gid: int = 1000
    pw_gecos: str = "Mock User"
    pw_dir: str = "/home/mockuser"
    pw_shell: str = "/bin/bash"


# Mock group entry (struct_group)
class MockGroup(NamedTuple):
    """Mock group structure returned by grp module functions."""
    gr_name: str = "mockgroup"
    gr_passwd: str = "x"
    gr_gid: int = 1000
    gr_mem: list = []


# Mock shadow password entry (struct_spwd)
class MockSpwd(NamedTuple):
    """Mock shadow password structure returned by spwd module functions."""
    sp_namp: str = "mockuser"
    sp_pwdp: str = "!"
    sp_lstchg: int = 19000
    sp_min: int = 0
    sp_max: int = 99999
    sp_warn: int = 7
    sp_inact: int = -1
    sp_expire: int = -1
    sp_flag: int = -1


class MockPwdModule(ModuleType):
    """Mock pwd module with realistic function signatures."""
    
    def __init__(self):
        super().__init__('pwd')
        self.__name__ = 'pwd'
        self.__file__ = '<mock pwd>'
        self.__loader__ = None
        self.__package__ = ''
        self.struct_passwd = MockPasswd
    
    def getpwnam(self, name: str) -> MockPasswd:
        """Look up a user by name."""
        return MockPasswd(pw_name=name)
    
    def getpwuid(self, uid: int) -> MockPasswd:
        """Look up a user by UID."""
        return MockPasswd(pw_uid=uid)
    
    def getpwall(self) -> list:
        """Return all password database entries."""
        return []
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        return MockCallable(f"pwd.{name}")


class MockGrpModule(ModuleType):
    """Mock grp module with realistic function signatures."""
    
    def __init__(self):
        super().__init__('grp')
        self.__name__ = 'grp'
        self.__file__ = '<mock grp>'
        self.__loader__ = None
        self.__package__ = ''
        self.struct_group = MockGroup
    
    def getgrnam(self, name: str) -> MockGroup:
        """Look up a group by name."""
        return MockGroup(gr_name=name)
    
    def getgrgid(self, gid: int) -> MockGroup:
        """Look up a group by GID."""
        return MockGroup(gr_gid=gid)
    
    def getgrall(self) -> list:
        """Return all group database entries."""
        return []
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        return MockCallable(f"grp.{name}")


class MockSpwdModule(ModuleType):
    """Mock spwd (shadow password) module with realistic function signatures."""
    
    def __init__(self):
        super().__init__('spwd')
        self.__name__ = 'spwd'
        self.__file__ = '<mock spwd>'
        self.__loader__ = None
        self.__package__ = ''
        self.struct_spwd = MockSpwd
    
    def getspnam(self, name: str) -> MockSpwd:
        """Look up shadow password entry by name."""
        return MockSpwd(sp_namp=name)
    
    def getspall(self) -> list:
        """Return all shadow password entries."""
        return []
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        return MockCallable(f"spwd.{name}")


class MockFcntlModule(ModuleType):
    """Mock fcntl module with file control constants and functions."""
    
    # Common fcntl constants
    LOCK_EX = 2
    LOCK_NB = 4
    LOCK_SH = 1
    LOCK_UN = 8
    F_DUPFD = 0
    F_GETFD = 1
    F_SETFD = 2
    F_GETFL = 3
    F_SETFL = 4
    F_GETLK = 5
    F_SETLK = 6
    F_SETLKW = 7
    FD_CLOEXEC = 1
    
    def __init__(self):
        super().__init__('fcntl')
        self.__name__ = 'fcntl'
        self.__file__ = '<mock fcntl>'
        self.__loader__ = None
        self.__package__ = ''
    
    def fcntl(self, fd: Any, cmd: int, arg: Any = 0) -> int:
        """Perform file control operation."""
        return 0
    
    def ioctl(self, fd: Any, request: int, arg: Any = 0, mutate_flag: bool = True) -> Any:
        """Perform I/O control operation."""
        return 0
    
    def flock(self, fd: Any, operation: int) -> None:
        """Lock/unlock a file."""
        pass
    
    def lockf(self, fd: Any, cmd: int, len: int = 0, start: int = 0, whence: int = 0) -> None:
        """Lock a section of a file."""
        pass
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        return MockCallable(f"fcntl.{name}")


class MockCryptModule(ModuleType):
    """Mock crypt module for password hashing."""
    
    # Method constants
    METHOD_SHA512 = "$6$"
    METHOD_SHA256 = "$5$"
    METHOD_MD5 = "$1$"
    METHOD_BLOWFISH = "$2b$"
    METHOD_CRYPT = ""
    
    def __init__(self):
        super().__init__('crypt')
        self.__name__ = 'crypt'
        self.__file__ = '<mock crypt>'
        self.__loader__ = None
        self.__package__ = ''
    
    def crypt(self, word: str, salt: str = None) -> str:
        """Hash a password."""
        return "$6$mocksalt$mockhash"
    
    def mksalt(self, method: str = None, rounds: int = None) -> str:
        """Generate a salt for crypt()."""
        return "$6$mocksalt$"
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        return MockCallable(f"crypt.{name}")


# List of Linux-specific modules to mock
LINUX_MODULES = [
    # User/group database modules
    'pwd',
    'grp',
    'spwd',
    # File control
    'fcntl',
    # Password hashing
    'crypt',
    # POSIX-specific
    'posix',
    'termios',
    'tty',
    'pty',
    'resource',
    'syslog',
    # D-Bus and GObject (for system service interaction)
    'dbus',
    'dbus.mainloop',
    'dbus.mainloop.glib',
    'gi',
    'gi.repository',
    'gi.repository.GLib',
    'gi.repository.Gio',
]

# Specialized mock modules with realistic APIs
SPECIALIZED_MOCKS = {
    'pwd': MockPwdModule,
    'grp': MockGrpModule,
    'spwd': MockSpwdModule,
    'fcntl': MockFcntlModule,
    'crypt': MockCryptModule,
}


_mocks_installed = False


def install_linux_mocks() -> None:
    """Install mock modules for Linux-specific dependencies.
    
    This should only be called in dev mode when cross-platform tabs are enabled.
    """
    global _mocks_installed
    
    if _mocks_installed:
        logger.debug("Linux mocks already installed")
        return
    
    logger.warning("Installing mock modules for Linux dependencies (dev mode)")
    
    for module_name in LINUX_MODULES:
        if module_name not in sys.modules:
            # Use specialized mock if available, otherwise generic
            if module_name in SPECIALIZED_MOCKS:
                sys.modules[module_name] = SPECIALIZED_MOCKS[module_name]()
            else:
                sys.modules[module_name] = MockModule(module_name)
            logger.debug(f"Installed mock for: {module_name}")
    
    _mocks_installed = True
    logger.info(f"Installed {len(LINUX_MODULES)} Linux module mocks for cross-platform testing")


def uninstall_linux_mocks() -> None:
    """Remove mock modules from sys.modules.
    
    This is primarily for testing purposes.
    """
    global _mocks_installed
    
    for module_name in LINUX_MODULES:
        if module_name in sys.modules:
            mock = sys.modules[module_name]
            if isinstance(mock, (MockModule, MockPwdModule, MockGrpModule, 
                                 MockSpwdModule, MockFcntlModule, MockCryptModule)):
                del sys.modules[module_name]
                logger.debug(f"Removed mock for: {module_name}")
    
    _mocks_installed = False
    logger.info("Removed Linux module mocks")


def are_linux_mocks_installed() -> bool:
    """Check if Linux mocks are currently installed."""
    return _mocks_installed


__all__ = ['install_linux_mocks', 'uninstall_linux_mocks', 'are_linux_mocks_installed', 'LINUX_MODULES']

