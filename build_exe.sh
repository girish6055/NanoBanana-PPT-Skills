#!/usr/bin/env bash
# Build a native executable on Linux/macOS (PyInstaller does not cross-compile:
# run build_exe.bat on Windows to get a .exe).
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install --upgrade pyinstaller
python3 -m PyInstaller --clean --noconfirm CCTVAnalyticsManager.spec

echo
echo "Done. Binary: $(pwd)/dist/CCTVAnalyticsManager"
