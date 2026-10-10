#!/usr/bin/env python3
"""
Root launcher script for The Researcher HTTP server.
Executes the server CLI entry point with zero external dependencies.

Usage:
    python run_server.py
    python run_server.py --port 8000
    python run_server.py --host 0.0.0.0 --port 8080 --verbose
"""

from __future__ import annotations

import os
import sys

# Ensure src/ directory is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from the_researcher.main import main

if __name__ == "__main__":
    sys.exit(main())
