"""Headless smoke tests for GUI services and daemon protocol.

Run from the repository root::

    python -m pytest GUI/tests -q

These tests do not require a display or elevated privileges.
Offscreen Qt tests set ``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is importable when pytest is invoked from elsewhere
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
