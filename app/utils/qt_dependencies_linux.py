"""Qt dependencies management for Linux platforms.

This module handles detection and installation of Qt xcb platform dependencies
required for Qt applications to run on Linux systems.
"""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

APT_PACKAGES = [
    'libxcb-cursor0',
    'libxcb-xinerama0',
    'libxcb-icccm4',
    'libxcb-image0',
    'libxcb-keysyms1',
    'libxcb-render-util0',
    'libxkbcommon-x11-0',
    'qtwayland5',
]


def _detect_distribution_id() -> str:
    """Detect the Linux distribution ID.
    
    Returns:
        Distribution ID string (e.g., 'debian', 'ubuntu') or 'unknown'
    """
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('ID='):
                    return line.split('=', 1)[1].strip().strip('"').lower()
    except FileNotFoundError:
        pass

    if os.path.exists('/etc/debian_version'):
        return 'debian'
    return 'unknown'


def _run(cmd: list[str], env: dict[str, str] | None = None, timeout: int = 600) -> tuple[str, str, int]:
    """Run a command and return stdout, stderr, and return code.
    
    Args:
        cmd: Command and arguments as a list
        env: Optional environment variables dictionary
        timeout: Command timeout in seconds (default 600)
        
    Returns:
        Tuple of (stdout, stderr, returncode)
    """
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
        return '', 'Command timed out', -1
    except Exception as e:
        return '', str(e), -1


def _is_package_installed_debian(package: str) -> bool:
    stdout, stderr, rc = _run(
        ['dpkg-query', '-W', '-f=${Status}', package],
        timeout=15,
    )
    if rc != 0:
        logger.debug(
            "dpkg-query failed for %s: %s",
            package,
            stderr.strip() or stdout.strip(),
        )
        return False
    return 'install ok installed' in (stdout or '').lower()


def _get_missing_packages_debian(packages: list[str]) -> list[str]:
    missing = []
    for package in packages:
        if not _is_package_installed_debian(package):
            missing.append(package)
    return missing


def _install_qt_xcb_dependencies_debian(packages: list[str] | None = None) -> bool:
    """Install required Qt xcb dependencies on Debian/Ubuntu systems.
    
    Returns:
        True if installation succeeded, False otherwise
    """
    apt_packages = packages or APT_PACKAGES

    try:
        # Use interactive=True so password prompt can display
        # Use relative import since we're in the same directory
        from .elevation_linux import run_command_as_admin
        logger.info("Successfully imported run_command_as_admin from elevation_linux")
    except Exception as e:
        logger.error(f"Failed to import run_command_as_admin: {e}")
        # Fallback that won't work for elevation but prevents crashes
        def run_command_as_admin(cmd, description="", interactive=False):
            logger.error(f"Using fallback run_command_as_admin - NO ELEVATION!")
            return subprocess.run(cmd, capture_output=True, text=True)

    env = os.environ.copy()
    env['DEBIAN_FRONTEND'] = 'noninteractive'

    # Combine apt-get update and install into a single command to avoid double authentication
    logger.info('Updating apt package lists and installing Qt xcb dependencies...')
    packages_str = ' '.join(apt_packages)
    combined_cmd = [
        'sh', '-c',
        f'env DEBIAN_FRONTEND=noninteractive apt-get update && '
        f'env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends {packages_str}'
    ]
    result = run_command_as_admin(combined_cmd, interactive=True)
    if getattr(result, 'returncode', 1) != 0:
        stderr = getattr(result, 'stderr', '') or getattr(result, 'stdout', '')
        logger.error(f"Failed to update package lists or install Qt dependencies: {stderr}")
        return False
    logger.info("Package lists updated and Qt dependencies installed successfully")
    return True


def ensure_qt_xcb_dependencies_installed() -> bool:
    """Ensure Qt can load the xcb platform plugin by installing missing system libs if needed.
    
    Returns True if Qt can initialize with xcb after this call, False otherwise.
    """
    distro = _detect_distribution_id()
    if distro in ('debian', 'ubuntu', 'linuxmint'):
        missing = _get_missing_packages_debian(APT_PACKAGES)
        if not missing:
            return True
        logger.warning(
            "Qt xcb dependencies missing: %s",
            ", ".join(missing),
        )
        installed = _install_qt_xcb_dependencies_debian(missing)
    else:
        # Skip dependency check on non-Debian distros for now - assume Qt deps are available
        logger.warning(f"Qt dependency check skipped for distribution '{distro}'. If the app fails to start, please install Qt xcb dependencies manually.")
        return True

    if not installed:
        return False

    missing = _get_missing_packages_debian(APT_PACKAGES)
    if missing:
        logger.error(
            "Qt dependencies still missing after installation: %s",
            ", ".join(missing),
        )
        return False
    return True


__all__ = ['ensure_qt_xcb_dependencies_installed', 'APT_PACKAGES']
