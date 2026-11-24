#!/usr/bin/env bash
set -e
echo "============================================================"
echo "  Starting Enterprise Analytics & Data Studio on Localhost"
echo "============================================================"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
echo "Launching server at http://localhost:8000 ..."
python3 server.py
