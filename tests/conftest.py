"""Headless smoke tests for GUI services and daemon protocol.

Run from the repository root::

    python -m pytest GUI/tests -q

These tests do not require a display or elevated privileges.
Offscreen Qt tests set ``QT_QPA_PLATFORM=offscreen``.
Settings and logs are redirected to a temporary HostConfig data dir.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure repo root is importable when pytest is invoked from elsewhere
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from GUI.app.host_config import HostConfig, set_host_config


@pytest.fixture(autouse=True)
def _isolate_host_paths():
    """Keep tests from reading or writing the developer's settings.json."""
    data_dir = Path(tempfile.mkdtemp(prefix="gui-host-"))
    set_host_config(
        HostConfig(app_id="gui-test", user_data_dir=data_dir, portable=False)
    )
    yield data_dir
    set_host_config(None)
    shutil.rmtree(data_dir, ignore_errors=True)
