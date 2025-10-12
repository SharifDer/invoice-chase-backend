#!/usr/bin/env python3
"""
Development server script for Invoice Chase API
"""

import uvicorn
import os
import subprocess
from config import settings

def start_sqlite_web():
    """Start sqlite_web in a new terminal session, detached from parent."""
    try:
        # Windows
        if os.name == "nt":
            subprocess.Popen(
                [
                    "start", "cmd", "/k",
                    f"sqlite_web {settings.DATABASE_URL} --host 127.0.0.1 --port 8080 --no-browser"
                ],
                shell=True
            )
        # Unix / macOS
        else:
            subprocess.Popen(
                [
                    "x-terminal-emulator", "-e",
                    f"sqlite_web {settings.DATABASE_URL} --host 127.0.0.1 --port 8080 --no-browser"
                ]
            )
        print("SQLite web interface launched at http://127.0.0.1:8080 (in a separate terminal)")
    except FileNotFoundError:
        print("sqlite_web is not installed. Install it with: pip install sqlite-web")
    except Exception as e:
        print(f"Failed to start sqlite_web: {e}")

if __name__ == "__main__":
    # Ensure database exists
    if not os.path.exists(settings.DATABASE_URL):
        print(f"Creating database at: {settings.DATABASE_URL}")
        open(settings.DATABASE_URL, 'a').close()

    # Start sqlite_web in a separate terminal
    start_sqlite_web()

    # Run FastAPI development server with reload enabled
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # auto-reload on code changes
        log_level="debug" if settings.DEBUG else "info"
    )
