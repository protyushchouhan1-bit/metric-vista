@echo off
title Enterprise Analytics Localhost Server
echo ============================================================
echo   Starting Enterprise Analytics & Data Studio on Localhost
echo ============================================================
if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate
echo Installing required Python libraries...
pip install -q -r requirements.txt
echo Launching server at http://localhost:8000 ...
python server.py
pause
