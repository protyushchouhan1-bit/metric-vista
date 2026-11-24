# Project NEXUS — Enterprise Intelligence, Data Quality & Decision Support Platform (V2.0)

[![CI Verification](https://img.shields.io/badge/CI-Tests%20%2B%20Security%20%2B%20AI%20Eval%20%2B%20Ruff-06B6D4)](#reproduce-every-claim-in-one-command)

**Project NEXUS** is an adaptive, AI-assisted BI Semantic Layer, 7-Dimension Data Quality Evaluator, Deterministic DuckDB/Parquet Analytics Engine, and Evidence-Based Business Analyst built to eliminate spreadsheet fragmentation in SMEs without AI math hallucination.

## Architecture Diagram (Single Unified Frontend + Modular Monolith)

```
[Unified Dark-Neon UI: web_app/index.html (Zero JS Math)]
                        │ HTTPS / JSON (/api/v1/)
                        ▼
[FastAPI Gateway — Verified JWT Only · Locked CORS · Read-Only Demo Mode]
        ├── core/ (Framework-Agnostic Python Analytical Core)
        │     ├── ingestion.py       (15 MB / 100k cap, zip-bomb check, Header & Grand Total scanner, Parquet)
        │     ├── profiler.py        (Grain discovery + 7-Dim Quality + Mixed Currency ₹/$/€/£/INR/USD/EUR/GBP)
        │     ├── semantic_mapper.py (Tier-1 Rules + Tier-2 Metadata-Only AI Classifier + Tier-3 Confirmation)
        │     ├── kpi_engine.py      (YAML 15-Field KPI Registry, Price/Volume/Mix Waterfall, Pareto 80/20)
        │     └── ai_analyst.py      (Real Two-Stage LLM JSON AST + Narrative + Session-Only Key + Demo Cache)
        ├── kpis/*.yaml              (Sales, Finance, Marketing, HR, Supply Chain contracts)
        └── Storage                  (Immutable Raw + Columnar Parquet + SQLite Metadata; PG RLS in Phase 2)
```

## How AI Hallucination Is Prevented
1. **Zero LLM Arithmetic**: Python/DuckDB executes 100% of sums, distinct counts, margins, Pareto rankings, and Price/Volume/Mix waterfalls.
2. **Two-Stage Grounded Pipeline**: When a live Gemini key is supplied via session-only `X-Session-AI-Key` (configurable `GEMINI_MODEL`, default `gemini-2.0-flash`), Gemini receives ONLY the semantic schema and question to produce a **Structured JSON Query Plan (`QueryPlanAST`)**. Pydantic validates the allowlist, Parquet executes it deterministically, and Gemini explains ONLY the verified output.
3. **Transparent Modes & Audit Panel**: Every AI answer displays its exact `execution_mode` (`live_llm`, `rule_based_offline`, `cached_demo`, `cached_ttl`) and an expandable **"See the Query & Numbers"** audit panel.
4. **Honest Missing-Data Rules**: Missing required columns mark KPIs as `Not Calculable` (never `0`), and missing `quantity`/`unit_price` marks the Price/Volume/Mix waterfall as `Requires Additional Information`.

## Independently Recalculated Excel-vs-NEXUS Parity Table
All 13 Excel formulas in `sample_data/benchmarks/nexus_excel_ground_truth.xlsx` were recalculated independently via **LibreOffice Calc headless** (`nexus_excel_recalculated_libreoffice.xlsx`) and verified to 2 decimal places by `tests/test_nexus_6_layers.py`:

| Domain | KPI Code | KPI Name | LibreOffice Excel Formula | NEXUS Output | Delta |
|---|---|---|---:|---:|---:|
| Sales | `SALES_TOTAL_REVENUE` | Total Revenue | 3,784,295.00 | 3,784,295.00 | 0.00 |
| Sales | `SALES_DISTINCT_ORDERS` | Distinct Orders | 250.00 | 250.00 | 0.00 |
| Sales | `SALES_AOV` | Average Order Value (AOV) | 15,137.18 | 15,137.18 | 0.00 |
| Sales | `SALES_UNITS_SOLD` | Total Units Sold | 1,281.00 | 1,281.00 | 0.00 |
| Sales | `SALES_ASP` | Average Selling Price (ASP) | 2,954.17 | 2,954.17 | 0.00 |
| Sales | `SALES_GROSS_PROFIT` | Gross Profit | 1,740,975.00 | 1,740,975.00 | 0.00 |
| Sales | `SALES_GROSS_MARGIN_PCT` | Gross Margin % | 46.01 | 46.01 | 0.00 |
| Finance | `FIN_TOTAL_REVENUE` | P&L Revenue | 15,810,621.72 | 15,810,621.72 | 0.00 |
| Finance | `FIN_COGS` | P&L COGS | 6,845,643.61 | 6,845,643.61 | 0.00 |
| Finance | `FIN_OPEX` | P&L OpEx | 6,828,261.49 | 6,828,261.49 | 0.00 |
| Finance | `FIN_GROSS_PROFIT` | P&L Gross Profit | 8,964,978.11 | 8,964,978.11 | 0.00 |
| Finance | `FIN_OPERATING_PROFIT` | Operating Profit | 2,136,716.62 | 2,136,716.62 | 0.00 |
| Finance | `FIN_OPERATING_MARGIN_PCT` | Operating Margin % | 13.51 | 13.51 | 0.00 |

## 35-Question Golden AI Evaluation Suite (`tests/eval_ai_golden.py`)
- **Slice Plan Validity Rate (25 slice questions)**: **100.0%**
- **Headline KPI Grounding Rate (5 executive questions)**: **100.0%**
- **Adversarial SQL/Prompt-Injection Rejection Rate (5 attack prompts)**: **100.0%**
- **Numbers-Match-Engine Rate**: **100.0%**

## Honest Multi-Tier Performance Benchmarks
Measured locally across 3 iterations per tier (full ingest → Parquet → profile → semantic map → KPI suite):

| Tier | Dataset Shape | p50 Latency | p95 Latency | Peak RSS Memory |
|---|---|---:|---:|---:|
| **Small** | 1,000 × 12 | 0.09s | 0.11s | 170.3 MB |
| **Medium** | 25,000 × 12 | 0.55s | 0.57s | 267.3 MB |
| **Max MVP** | 100,000 × 12 | 1.87s | 1.91s | 387.9 MB |

## One Real Analytical Insight Found in the Benchmark Dataset
In `acme_retail_sales.csv` (430 line-item rows spanning 250 distinct orders), a naive row-count AOV calculation (`SUM(revenue) / COUNT(*)`) would report **₹8,800.69**, understating true Average Order Value by **41.9%** compared to grain-aware `COUNT(DISTINCT order_id)` (**₹15,137.18**). Enforcing mandatory dataset grain confirmation (`line_item` vs `order`) prevents this silent financial distortion before any chart is published.

## Reproduce Every Claim in One Command
```bash
pip install -r requirements.txt
python3 -m unittest discover -s tests -v && python3 tests/eval_ai_golden.py
```

## Run Locally (`http://localhost:8000`)
- **Windows**: Double-click `run_local.bat`
- **macOS / Linux**: `./run_local.sh`
- **Manual**: `python3 server.py` → opens **`http://localhost:8000`** (API Swagger docs at **`http://localhost:8000/docs`**).

## What I Learned & Known Limitations
- **One calculator beats two**: Wiring the unified dark-neon frontend (`web_app/index.html`) directly to `POST /api/v1/dashboards/{id}/query` eliminated frontend/backend calculation drift; the prototype React folder was moved to `future/react_frontend/`.
- **Security is binary**: Trusting client-supplied `X-Org-Id` headers or allowing writes in Demo Mode defeats multi-tenancy; every route now enforces verified JWT claims and read-only demo viewer permissions.
- **Formulas must be recalculated independently**: Running LibreOffice Calc headless caught a `UNIQUE()` compatibility bug in Excel formulas and verified true independent 2-decimal parity.
- See [`LIMITATIONS.md`](LIMITATIONS.md), [`docs/PHASE2_ROADMAP.md`](docs/PHASE2_ROADMAP.md), and [`handbook/`](handbook/01_EXPLAIN_LIKE_IM_5_AND_MAIN_IDEA.md) for full details.
