"""
Build metadata injected at packaging/build time.

When building with PyInstaller, a build step can generate
`GUI/app/_build_info_generated.py` to embed information about the build
environment (e.g., build distro).

At runtime, the UI can display these values (e.g., in About dialog).
"""

from __future__ import annotations

BUILD_DISTRO: str = "unknown"
BUILD_TIME_UTC: str = "unknown"
GIT_COMMIT: str = "unknown"

try:
    # Generated at build time (preferred).
    from ._build_info_generated import BUILD_DISTRO as BUILD_DISTRO  # type: ignore
    from ._build_info_generated import BUILD_TIME_UTC as BUILD_TIME_UTC  # type: ignore
    from ._build_info_generated import GIT_COMMIT as GIT_COMMIT  # type: ignore
except Exception:
    # Source runs / builds without generation step.
    pass

# Dynamic fallback when running from source (non-frozen)
if GIT_COMMIT == "unknown":
    import subprocess
    import sys
    from pathlib import Path
    try:
        if not getattr(sys, "frozen", False):
            repo_root = Path(__file__).resolve().parents[2]
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                commit = result.stdout.strip()
                # Check for uncommitted changes
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if status_result.returncode == 0 and status_result.stdout.strip():
                    commit += "-dirty"
                GIT_COMMIT = commit
    except Exception:
        pass

__all__ = ["BUILD_DISTRO", "BUILD_TIME_UTC", "GIT_COMMIT"]

