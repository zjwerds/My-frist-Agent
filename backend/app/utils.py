"""Shared utilities — path resolution for PyInstaller and dev modes."""

import sys
import os


def get_data_dir() -> str:
    """Return the directory for data files (agent.db, config.json).
    PyInstaller bundle: next to the .exe. Dev mode: backend/ directory.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
