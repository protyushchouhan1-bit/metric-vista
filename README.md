# METRIC VISTA — Automated Data Cleaning, Multi-Department Analytics & Q&A Studio

[Live Demo](https://www.google.com/search?q=https%3A%2F%2Fmetric-vista.onrender.com)
[Python](https://www.google.com/search?q=https%3A%2F%2Fwww.python.org%2F)
[FastAPI](https://www.google.com/search?q=https%3A%2F%2Ffastapi.tiangolo.com%2F)

**METRIC VISTA** turns messy Excel (`.xlsx`, `.xls`) and CSV exports—up to **1,00,000 rows**—into clean, verified executive dashboards and plain-English answers in seconds, without writing a single formula or SQL query.

Built over a focused two-week sprint to solve the everyday spreadsheet headaches faced by founders, analysts, and department managers.

---

## What Problem It Solves

Growing teams lose hours every week cleaning the exact same raw exports:
- Blank or half-empty columns cluttering every sheet
- Grand-total rows accidentally mixed into raw data
- Inconsistent casing (such as `James` vs. `james` or `MATT` vs. `Matt`) quietly splitting totals
- Mixed currency symbols (`₹`, `$`, `€`, `£`, `INR`, `USD`) breaking numeric columns
- Heavy BI tools that require manual data modeling before anyone can see a single chart

**METRIC VISTA** automates cleaning, column mapping, and quality scoring right during upload, then adapts its charts automatically to whatever dataset you drop in.

---

## Core Capabilities

- **Live Upload Cleaning & Quality Audit:** Filters blank columns, repairs nulls, normalizes inconsistent name casing, strips duplicate and grand-total rows, and scores 7 data-health dimensions live on screen.
- **Priority-First Overview Map:** Ranks your most important metrics first and connects them visually to regional, product, and channel drivers with click-to-filter support.
- **Comprehensive Executive Dashboard (12 Animated Charts):** Growth & Moving Average, Share Donut, Price/Volume/Mix Waterfall, 80/20 Pareto, Ranked Leaderboard, Cumulative Running Total, Period-over-Period Momentum, Leaders vs. Laggards, Distribution Bands, Concentration Bubble, Polar Balance, and Strength Radar—all formatted with compact axis ticks (`K`, `L`, `Cr`) so labels never overlap.
- **4 Plain-English Department Hubs (6 Charts Each):**
  - **Finance:** Budget vs. Actual, Monthly Money In vs. Out, Revenue/COGS/OpEx Mix, Quarterly Profit & Margin %, Budget Variance, Account Weight Balance
  - **Supply Chain:** Warehouse COGS, On-Time vs. Late Deliveries, Supplier Share, Lead Time, Defect Rate %, On-Hand vs. Avg Inventory + EOQ
  - **Marketing:** Ad Spend vs. Revenue, ROAS by Platform, Budget Share, Conversion Funnel, CAC, Monthly Revenue & Conversions
  - **HR & People:** Active vs. Exited Staff, Hiring Speed, Workforce Share, Attendance %, Retention Radar, Quarterly Hiring Momentum
- **Always-On Backend Gemini Q&A:** FastAPI reads `GEMINI_API_KEY` directly from server environment variables (with a clean offline fallback), so end users ask plain-English questions without ever being prompted for API keys.

---

## Verified Benchmarks & Quality Checks

| Dataset Scale | Ingest + Profile + KPI Time | Peak Memory (RSS) |
| :--- | :---: | :---: |
| Small (1,000 × 12) | 0.09s | 170.3 MB |
| Medium (25,000 × 12) | 0.55s | 267.3 MB |
| Max Target (1,00,000 × 12) | 2.31s | 290.8 MB |

- **Excel Parity:** 13/13 core Sales & Finance KPIs verified against LibreOffice-recalculated Excel formulas with **0.00 delta**.
- **Automated Test Suite:** 13/13 security, currency-parsing, cross-filtering, and API tests passing (`python tests/test_nexus_6_layers.py`).
- **Golden AI Evaluation:** 100% plan validity, adversarial rejection, and verified number accuracy across 35 benchmark questions (`python tests/eval_ai_golden.py`).

---

## Quick Start (Localhost)

```bash
git clone https://github.com/protyushchouhan1-bit/metric-vista.git
cd metric-vista
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your GEMINI_API_KEY inside .env
python server.py
```

Open `http://localhost:8000` in your browser (Swagger API docs at `http://localhost:8000/docs` and Gemini status at `http://localhost:8000/api/v1/ai-status`).

---

## One-Click Cloud Deployment (Render)

This repository includes `render.yaml` and `Procfile` pre-configured for Render:
1. Connect `protyushchouhan1-bit/metric-vista` on [Render](https://www.google.com/search?q=https%3A%2F%2Fdashboard.render.com) via **New + → Blueprint**.
2. Paste your `GEMINI_API_KEY` into Render's Environment Variables panel.
3. Click **Deploy Blueprint**—Render builds the sample data and serves the live dashboard via `uvicorn server:app --host 0.0.0.0 --port $PORT`.

---

## Repository Structure

```text
metric-vista/
├── server.py               # Unified dashboard + FastAPI entrypoint (local & Render)
├── render.yaml             # Render Blueprint deployment config
├── Procfile                # Process file for cloud hosting
├── requirements.txt        # Python dependencies
├── web_app/index.html      # METRIC VISTA interactive frontend
├── backend/                # FastAPI routes, JWT auth & SQLite metadata store
├── core/                   # Ingestion, cleaning, profiler, KPI engine & Gemini analyst
├── kpis/                   # YAML KPI definitions (Sales, Finance, SCM, Marketing, HR)
├── sample_data/            # Demo workspaces, adversarial test sets & Excel benchmarks
├── tests/                  # Automated test suite & 35-question Golden AI eval
└── docs/ & handbook/       # Architecture docs and technical walkthroughs
```
