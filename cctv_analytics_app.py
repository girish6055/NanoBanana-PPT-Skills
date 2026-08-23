#!/usr/bin/env python3
"""Launcher for CCTV Analytics Manager - also the PyInstaller entry point."""

import sys

from cctv_analytics.cli import main

if __name__ == "__main__":
    sys.exit(main())
