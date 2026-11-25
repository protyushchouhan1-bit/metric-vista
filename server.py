#!/usr/bin/env python3
"""
METRIC VISTA — Unified Web Dashboard & FastAPI Backend Server
Runs both locally (http://localhost:8000) and on Render (0.0.0.0:$PORT).
Includes /api/v1/ask-live for always-on server-side Gemini Q&A over any uploaded dataset.
"""
import json
import os
import sys
import threading
import time
import webbrowser
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

import httpx
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn
from backend.main import app

WEB_APP_HTML = os.path.join(ROOT, "web_app", "index.html")


class LiveAskPayload(BaseModel):
    question: str
    dataset_name: str = "Uploaded Dataset"
    row_count: int = 0
    columns: List[str] = []
    overall_stats: Dict[str, Any] = {}
    matched_filters: List[Dict[str, Any]] = []
    dimension_breakdowns: Dict[str, Any] = {}
    cleaning_stats: Dict[str, Any] = {}


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


def _call_gemini_rest(api_key: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    preferred = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    candidates = []
    for m in [preferred, "gemini-2.5-flash", "gemini-2.0-flash"]:
        if m and m not in candidates:
            candidates.append(m)

    endpoints = [
        ("gemini_api", "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"),
        ("vertex_express", "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"),
    ]
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 450},
    }

    last_err = "Unknown Gemini error"
    for ep_name, tmpl in endpoints:
        for model in candidates:
            url = tmpl.format(model=model)
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=22.0)
                if resp.status_code == 200:
                    data = resp.json()
                    cands = data.get("candidates") or []
                    if cands:
                        parts = (cands[0].get("content") or {}).get("parts") or []
                        text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            return {"ok": True, "answer": text, "model": f"{model} ({ep_name})"}
                    last_err = f"{ep_name}/{model}: empty response"
                elif resp.status_code in (400, 403, 404):
                    last_err = f"{ep_name}/{model}: HTTP {resp.status_code}"
                    continue
                else:
                    last_err = f"{ep_name}/{model}: HTTP {resp.status_code}"
                    break
            except Exception as exc:
                last_err = str(exc)
                break
    return {"ok": False, "error": last_err}


@app.post("/api/v1/ask-live", include_in_schema=False)
def ask_live_dataset(payload: LiveAskPayload):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "answer": None,
            "mode": "offline_no_key",
            "detail": "GEMINI_API_KEY is not set in server environment variables.",
        }

    system_prompt = (
        "You are the built-in plain-English business analyst for METRIC VISTA. "
        "Answer the user's question directly, accurately, and concisely (2 to 4 short sentences or crisp bullets) "
        "using ONLY the verified numbers provided in the JSON context. "
        "Rules:\n"
        "1. If 'matched_filters' contains an exact match for a region, product, person, or category mentioned in the question "
        "(for example 'West'), lead immediately with that exact filtered total and row count.\n"
        "2. Never invent or guess numbers that are not present in the context.\n"
        "3. If the user asks a wrong, misspelled, unclear, or mismatched question (for example asking about a column or time like '10 pm' or 'salary' that does not exist in this dataset), you MUST:\n"
        "   - First politely explain why the question does not match the uploaded dataset.\n"
        "   - Second, write '**Suggested Right Question:**' followed by a rewritten, accurate question that fits the dataset's real columns.\n"
        "   - Third, immediately answer that corrected question using only the verified numbers in the context.\n"
        "4. Use everyday layman business language with clean number formatting (no raw JSON, no SQL, no code blocks)."
    )

    context_blob = {
        "dataset_name": payload.dataset_name,
        "row_count": payload.row_count,
        "columns": payload.columns[:30],
        "overall_stats": payload.overall_stats,
        "matched_filters": payload.matched_filters[:10],
        "dimension_breakdowns": payload.dimension_breakdowns,
        "cleaning_stats": payload.cleaning_stats,
    }
    user_prompt = (
        f"User Question: {payload.question}\n\n"
        f"Verified Dataset Context (JSON):\n{json.dumps(context_blob, ensure_ascii=False)[:14000]}"
    )

    res = _call_gemini_rest(api_key, system_prompt, user_prompt)
    if res.get("ok"):
        return {
            "answer": res["answer"],
            "mode": "gemini_live",
            "model": res["model"],
        }
    return {
        "answer": None,
        "mode": "gemini_error",
        "detail": res.get("error", "Gemini request failed"),
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
