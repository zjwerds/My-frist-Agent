"""Entry point for PyInstaller bundle."""
import sys
import os

# PyInstaller: sys._MEIPASS is the temp extraction directory
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)
    os.chdir(sys._MEIPASS)

# Import app first so PyInstaller hooks know about it
import app.main
import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        'app.main:app',
        host='127.0.0.1',
        port=8000,
        log_level='info',
        reload=False,
    )
