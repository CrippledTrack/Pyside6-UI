"""
Entry point for `python -m GUI` when run from the directory that contains the GUI package.

Does not set GUI_STANDALONE_MODE; base path remains the parent project root.
Behavior is the same as running main.py at the project root.
"""

from __future__ import annotations

import sys

from GUI.app.app import run

if __name__ == "__main__":
    raise SystemExit(run(sys.argv))
