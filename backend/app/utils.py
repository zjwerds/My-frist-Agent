"""Shared utilities — path resolution, timezone constants."""

import sys
import os
from datetime import timezone, timedelta

BEIJING = timezone(timedelta(hours=8))


def get_data_dir() -> str:
    """Return the directory for data files (agent.db, config.json).
    PyInstaller bundle: next to the .exe. Dev mode: backend/ directory.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
