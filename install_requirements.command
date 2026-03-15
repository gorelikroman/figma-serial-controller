#!/bin/bash
# Install Python dependencies for Figma Serial Controller (double-click friendly)

set -e

cd "$(dirname "$0")/agent"

echo "Installing Python dependencies..."

echo ""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python is not installed. Install Python 3 first: https://www.python.org/downloads/"
  echo ""
  read -n 1 -s -r -p "Press any key to close..."
  echo ""
  exit 1
fi

"$PYTHON_BIN" -m pip install -r requirements.txt

echo ""
echo "Done. Dependencies installed successfully."
read -n 1 -s -r -p "Press any key to close..."
echo ""
