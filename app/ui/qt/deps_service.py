"""Qt dependency validation for Linux (Qt backend only).

Detects and installs Qt xcb platform dependencies by package manager
(``apt``, ``dnf``, or ``pacman``), not by distro ID. First matching
manager wins. Pass ``--skip-qt-deps`` on the command line to bypass.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

APT_PACKAGES = [
    "libxcb-cursor0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-shm0",
    "libxcb-sync1",
    "libxcb-util1",
    "libxcb-xfixes0",
    "libxcb-xinerama0",
    "libxcb-xkb1",
    "libx11-xcb1",
    "libxkbcommon0",
    "libxkbcommon-x11-0",
    "libegl1",
]

# Fedora / RHEL-family runtime names for the same Qt 6 xcb libs.
DNF_PACKAGES = [
    "xcb-util-cursor",
    "xcb-util-image",
    "xcb-util-keysyms",
    "xcb-util-renderutil",
    "xcb-util-wm",
    "xcb-util",
    "libxcb",
    "libX11-xcb",
    "libxkbcommon",
    "libxkbcommon-x11",
    "libglvnd-egl",
]

# Arch / pacman-family runtime names for the same Qt 6 xcb libs.
PACMAN_PACKAGES = [
    "xcb-util-cursor",
    "xcb-util-image",
    "xcb-util-keysyms",
    "xcb-util-renderutil",
    "xcb-util-wm",
    "xcb-util",
    "libxcb",
    "libx11",
    "libxkbcommon",
    "libxkbcommon-x11",
    "libglvnd",
]


@dataclass(frozen=True)
class PackageManager:
    """Install backend for one Linux package manager.

    Additional distros are another registry row, not extra distro-ID strings.
    """

    id: str
    packages: tuple[str, ...]
    detect: Callable[[], bool]
    is_installed: Callable[[str], bool]
    install: Callable[[list[str]], bool]
    manual_hint: str


def _apt_manual_hint(packages: Sequence[str] | None = None) -> str:
    pkgs = list(packages) if packages is not None else list(APT_PACKAGES)
    return (
        "Missing Qt dependencies. Please install with: "
        "sudo apt-get update && sudo apt-get install -y --no-install-recommends "
        + " ".join(pkgs)
    )


def _dnf_manual_hint(packages: Sequence[str] | None = None) -> str:
    pkgs = list(packages) if packages is not None else list(DNF_PACKAGES)
    return (
        "Missing Qt dependencies. Please install with: "
        "sudo dnf install -y "
        + " ".join(pkgs)
    )


def _pacman_manual_hint(packages: Sequence[str] | None = None) -> str:
    pkgs = list(packages) if packages is not None else list(PACMAN_PACKAGES)
    return (
        "Missing Qt dependencies. Please install with: "
        "sudo pacman -Sy --needed "
        + " ".join(pkgs)
    )


def _detect_apt() -> bool:
    return shutil.which("apt-get") is not None and shutil.which("dpkg-query") is not None


def _detect_dnf() -> bool:
    return shutil.which("dnf") is not None and shutil.which("rpm") is not None


def _detect_pacman() -> bool:
    return shutil.which("pacman") is not None


def _run(
    cmd: list[str],
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> tuple[str, str, int]:
    """Run a command and return stdout, stderr, and return code."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env or os.environ.copy(),
            timeout=timeout,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except Exception as e:
        return "", str(e), -1


def _run_elevated(cmd: list[str], description: str) -> bool:
    """Run ``cmd`` with elevation; return True when returncode is 0."""
    try:
        from ...utils.elevation_linux import run_command_as_admin

        logger.info("Successfully imported run_command_as_admin from elevation_linux")
    except Exception as e:
        logger.error(f"Failed to import run_command_as_admin: {e}")

        def run_command_as_admin(command, description="", interactive=False):
            logger.error("Using fallback run_command_as_admin - NO ELEVATION!")
            return subprocess.run(command, capture_output=True, text=True)

    logger.info(description)
    result = run_command_as_admin(cmd, interactive=True)
    if getattr(result, "returncode", 1) != 0:
        stderr = getattr(result, "stderr", "") or getattr(result, "stdout", "")
        logger.error(f"Failed to install Qt dependencies: {stderr}")
        return False
    logger.info("Qt dependencies installed successfully")
    return True


def _is_apt_package_installed(package: str) -> bool:
    stdout, stderr, rc = _run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        timeout=15,
    )
    if rc != 0:
        logger.debug(
            "dpkg-query failed for %s: %s",
            package,
            stderr.strip() or stdout.strip(),
        )
        return False
    return "install ok installed" in (stdout or "").lower()


def _is_dnf_package_installed(package: str) -> bool:
    _stdout, stderr, rc = _run(["rpm", "-q", package], timeout=15)
    if rc != 0:
        logger.debug("rpm -q failed for %s: %s", package, stderr.strip())
        return False
    return True


def _is_pacman_package_installed(package: str) -> bool:
    _stdout, stderr, rc = _run(["pacman", "-Q", package], timeout=15)
    if rc != 0:
        logger.debug("pacman -Q failed for %s: %s", package, stderr.strip())
        return False
    return True


def _apt_install_shell(packages: Sequence[str]) -> str:
    """Build a shell snippet that updates apt then installs packages.

    Ubuntu's ``command-not-found`` ``APT::Update::Post-Invoke-Success`` hook
    often fails with ``ModuleNotFoundError: No module named 'apt_pkg'`` and
    makes ``apt-get update`` exit non-zero even when indexes refreshed. Clear
    that hook for our update, and do not gate install on update's exit code —
    the later ``dpkg-query`` recheck is authoritative.
    """
    packages_str = " ".join(packages)
    return (
        "set +e; "
        "env DEBIAN_FRONTEND=noninteractive apt-get "
        "-o APT::Update::Post-Invoke-Success::= update; "
        "update_rc=$?; "
        'if [ "$update_rc" -ne 0 ]; then '
        'echo "apt-get update exited $update_rc; continuing with install" >&2; '
        "fi; "
        "env DEBIAN_FRONTEND=noninteractive apt-get install -y "
        f"--no-install-recommends {packages_str}; "
        "exit $?"
    )


def _install_apt_packages(packages: list[str]) -> bool:
    """Install packages with elevated ``apt-get``."""
    if not packages:
        return True
    combined_cmd = ["sh", "-c", _apt_install_shell(packages)]
    return _run_elevated(
        combined_cmd,
        "Updating apt package lists and installing Qt xcb dependencies...",
    )


def _install_dnf_packages(packages: list[str]) -> bool:
    """Install packages with elevated ``dnf``."""
    if not packages:
        return True
    cmd = [
        "dnf",
        "install",
        "-y",
        "--setopt=install_weak_deps=False",
        *packages,
    ]
    return _run_elevated(cmd, "Installing Qt xcb dependencies with dnf...")


def _install_pacman_packages(packages: list[str]) -> bool:
    """Install packages with elevated ``pacman``."""
    if not packages:
        return True
    cmd = [
        "pacman",
        "-Sy",
        "--needed",
        "--noconfirm",
        *packages,
    ]
    return _run_elevated(cmd, "Installing Qt xcb dependencies with pacman...")


def _package_managers() -> tuple[PackageManager, ...]:
    """Registered package managers; first match wins.

    Order: apt, then dnf, then pacman. Prefer apt on mixed PATH oddities.
    """
    return (
        PackageManager(
            id="apt",
            packages=tuple(APT_PACKAGES),
            detect=_detect_apt,
            is_installed=_is_apt_package_installed,
            install=_install_apt_packages,
            manual_hint=_apt_manual_hint(),
        ),
        PackageManager(
            id="dnf",
            packages=tuple(DNF_PACKAGES),
            detect=_detect_dnf,
            is_installed=_is_dnf_package_installed,
            install=_install_dnf_packages,
            manual_hint=_dnf_manual_hint(),
        ),
        PackageManager(
            id="pacman",
            packages=tuple(PACMAN_PACKAGES),
            detect=_detect_pacman,
            is_installed=_is_pacman_package_installed,
            install=_install_pacman_packages,
            manual_hint=_pacman_manual_hint(),
        ),
    )


def _detect_package_manager() -> PackageManager | None:
    for manager in _package_managers():
        if manager.detect():
            return manager
    return None


def _missing_packages(manager: PackageManager) -> list[str]:
    return [pkg for pkg in manager.packages if not manager.is_installed(pkg)]


def _ensure_qt_xcb_dependencies_installed() -> tuple[bool, Optional[str]]:
    """Ensure Qt can load the xcb platform plugin by installing missing system libs if needed.

    Returns ``(True, None)`` when Qt can proceed (including when no supported
    package manager is found). Returns ``(False, hint)`` when install failed
    or packages are still missing afterward.
    """
    manager = _detect_package_manager()
    if manager is None:
        logger.warning(
            "Qt dependency check skipped: no supported package manager found. "
            "If the app fails to start, please install Qt xcb dependencies manually."
        )
        return True, None

    missing = _missing_packages(manager)
    if not missing:
        return True, None
    logger.warning(
        "Qt xcb dependencies missing (%s): %s",
        manager.id,
        ", ".join(missing),
    )
    installed = manager.install(missing)
    if not installed:
        return False, manager.manual_hint

    missing = _missing_packages(manager)
    if missing:
        logger.error(
            "Qt dependencies still missing after installation: %s",
            ", ".join(missing),
        )
        return False, manager.manual_hint
    return True, None


class QtDepsService:
    """Ensure required Qt system dependencies are present."""

    def ensure_dependencies(self, *, skip: bool = False) -> Tuple[bool, Optional[str]]:
        if skip:
            logger.warning(
                "Qt dependency check skipped by explicit --skip-qt-deps "
                "(dev mode alone does not bypass). "
                "The app may fail to start if xcb libs are missing."
            )
            return True, None

        if platform.system().lower() != "linux":
            return True, None

        try:
            ok, hint = _ensure_qt_xcb_dependencies_installed()
            if not ok:
                logger.error("Required Qt xcb dependencies are missing.")
                return False, hint
        except Exception as e:
            logger.error(f"Error while ensuring Qt dependencies: {e}")

        return True, None


def should_skip_qt_deps(argv: Sequence[str] | None = None) -> bool:
    """Return True only when the exact ``--skip-qt-deps`` token is in ``argv``.

    Dev mode (``--dev`` / ``-dev``) never bypasses the check. Chaining
    ``--dev --skip-qt-deps`` skips solely because of ``--skip-qt-deps``.
    """
    args = list(argv) if argv is not None else list(sys.argv)
    return "--skip-qt-deps" in args


__all__ = [
    "QtDepsService",
    "APT_PACKAGES",
    "DNF_PACKAGES",
    "PACMAN_PACKAGES",
    "PackageManager",
    "should_skip_qt_deps",
]
