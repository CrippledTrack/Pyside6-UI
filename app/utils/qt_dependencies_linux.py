import os
import sys
import subprocess
import logging


logger = logging.getLogger(__name__)


def _detect_distribution_id() -> str:
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


def _run(cmd, env=None, timeout=600):
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


def _probe_qt_xcb_in_subprocess() -> tuple:
    """Attempt to initialize a minimal QApplication forcing the xcb platform in a subprocess.
    
    Returns (ok: bool, stderr: str)
    """
    python_exe = sys.executable or 'python3'
    code = (
        'import os; os.environ["QT_QPA_PLATFORM"] = "xcb"; '
        'from PySide6.QtWidgets import QApplication; '
        'app = QApplication([]); print("OK")'
    )
    env = os.environ.copy()
    env.setdefault('QT_DEBUG_PLUGINS', '0')
    stdout, stderr, rc = _run([python_exe, '-c', code], env=env, timeout=30)
    ok = (rc == 0 and 'OK' in (stdout or ''))
    return ok, stderr


def _install_qt_xcb_dependencies_debian() -> bool:
    """Install required Qt xcb dependencies on Debian/Ubuntu using apt."""
    # Minimal set known to be required by Qt 6.5+ for xcb
    apt_packages = [
        'libxcb-cursor0',
        'libxcb-xinerama0',
        'libxcb-icccm4',
        'libxcb-image0',
        'libxcb-keysyms1',
        'libxcb-render-util0',
        'libxkbcommon-x11-0',
        'qtwayland5',
    ]

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

    # apt-get update - must succeed before installation
    logger.info('Updating apt package lists to prepare Qt dependency installation...')
    update_cmd = ['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'update']
    result = run_command_as_admin(update_cmd, interactive=True)
    if getattr(result, 'returncode', 1) != 0:
        stderr = getattr(result, 'stderr', '') or getattr(result, 'stdout', '')
        logger.error(f"Failed to update package lists: {stderr}")
        logger.error("Cannot proceed with Qt dependency installation without updated package lists")
        return False
    logger.info("Package lists updated successfully")

    install_cmd = ['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', '--no-install-recommends'] + apt_packages
    logger.info('Installing missing Qt xcb dependencies via apt...')
    result = run_command_as_admin(install_cmd, interactive=True)
    if getattr(result, 'returncode', 1) != 0:
        stderr = getattr(result, 'stderr', '') or getattr(result, 'stdout', '')
        logger.error(f"Failed to install Qt dependencies: {stderr}")
        return False
    return True


def ensure_qt_xcb_dependencies_installed() -> bool:
    """Ensure Qt can load the xcb platform plugin by installing missing system libs if needed.
    
    Returns True if Qt can initialize with xcb after this call, False otherwise.
    """
    ok, stderr = _probe_qt_xcb_in_subprocess()
    if ok:
        return True

    logger.warning('Qt xcb platform initialization failed; attempting to install required system libraries...')
    if stderr:
        logger.debug(f"Initial Qt error: {stderr}")

    distro = _detect_distribution_id()
    installed = False
    if distro in ('debian', 'ubuntu', 'linuxmint'):
        installed = _install_qt_xcb_dependencies_debian()
    else:
        logger.error(f"Automatic installation not implemented for distribution '{distro}'. Please install Qt xcb dependencies manually.")
        return False

    if not installed:
        return False

    # Re-probe after install
    ok, stderr = _probe_qt_xcb_in_subprocess()
    if not ok and stderr:
        logger.error(f"Qt still failed to initialize xcb after installation: {stderr}")
    return ok


