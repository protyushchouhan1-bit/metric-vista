#!/usr/bin/env python3
"""
METRIC VISTA — Unified Web Dashboard & FastAPI Backend Server
Runs both locally (http://localhost:8000) and on Render (0.0.0.0:$PORT).
"""
import os
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

from fastapi.responses import FileResponse, HTMLResponse
import uvicorn
from backend.main import app

WEB_APP_HTML = os.path.join(ROOT, "web_app", "index.html")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_dashboard():
    if os.path.exists(WEB_APP_HTML):
        return FileResponse(WEB_APP_HTML, media_type="text/html")
    return HTMLResponse("<h1>Dashboard file not found at web_app/index.html</h1>", status_code=404)


@app.get("/api/v1/ai-status", include_in_schema=False)
def ai_status():
    return {
        "status": "ok",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
    }


def _open_browser_later(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    is_cloud = bool(os.getenv("RENDER"))
    host = "0.0.0.0" if is_cloud else "127.0.0.1"
    url = f"http://localhost:{port}"
    print("=" * 64)
    print("  METRIC VISTA is starting:")
    print(f"  Dashboard : {url}")
    print(f"  API Docs  : {url}/docs")
    print(f"  Gemini AI : {'ENABLED (server key)' if os.getenv('GEMINI_API_KEY') else 'OFFLINE FALLBACK (set GEMINI_API_KEY)'}")
    print("=" * 64)
    if not is_cloud and os.getenv("NO_BROWSER") != "1":
        threading.Thread(target=_open_browser_later, args=(url,), daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="info")
