# 05 — Python Engine, Backend & Libraries Deep Dive

Every Python file in this repository has a single, clear responsibility so you can explain or upgrade any component independently.

## 1. Python Libraries Used & Why Each One Matters
| Library | Role in Project | Plain-English Explanation |
|---|---|---|
| **FastAPI** | REST API web framework (`backend/main.py`, `server.py`) | Receives HTTP requests from the browser and returns fast JSON responses + automatic `/docs` Swagger explorer. |
| **Uvicorn** | ASGI web server (`server.py`) | Runs the FastAPI server locally on `http://localhost:8000`. |
| **Pandas** | Tabular data manipulation (`core/`) | Reads CSV/Excel tables, cleans columns, handles dates, and computes aggregations. |
| **NumPy & SciPy** | Numerical math & statistics (`core/`) | Powers fast vectorized calculations, quantiles/IQR outlier math, and ratios. |
| **PyArrow** | Columnar Apache Parquet storage (`core/ingestion.py`) | Compresses uploaded spreadsheets into tiny, ultra-fast `.parquet` files so 100k rows load in milliseconds. |
| **DuckDB** | In-process analytical SQL engine (`core/kpi_engine.py`) | Runs SQL cross-filters directly on Parquet files with tiny RAM usage (with automatic PyArrow/Pandas fallback if DuckDB isn't installed). |
| **OpenPyXL** | Excel `.xlsx` reader/writer (`core/ingestion.py`, `generate_sample_data.py`) | Streams Excel workbooks safely in read-only mode and writes live Excel formula benchmark sheets. |
| **PyYAML** | Configuration loader (`kpis/*.yaml`) | Loads 15-field KPI definitions from YAML so new metrics require zero Python code changes. |
| **Pydantic** | Strict schema validation (`core/ai_analyst.py`, `backend/main.py`) | Validates every API payload and enforces strict allowlisted JSON Query Plans (AST) so unsafe raw SQL can never run. |
| **Cryptography (Fernet)** | Symmetric encryption (`core/ai_analyst.py`) | Scrambles organization BYOK API keys before saving them in the database. |
| **SQLite3 / PostgreSQL (`schema.sql`)** | Relational metadata & governance store (`backend/store.py`) | Stores org settings, dataset metadata, confirmed mappings, background jobs, and immutable audit logs (never raw spreadsheet rows). |
| **HTTPX / TestClient** | Automated API testing (`tests/test_nexus_6_layers.py`) | Tests every endpoint end-to-end without needing a live browser. |

## 2. Module-by-Module Python Code Map
- **`server.py`**: One-click localhost runner. Mounts `web_app/index.html` at `http://localhost:8000/` alongside the full FastAPI `/api/v1/` backend and opens your browser automatically.
- **`core/ingestion.py`**: Enforces 15 MB & 1,00,000-row caps, inspects Excel ZIP archives against zip-bombs (`MAX_ZIP_UNCOMPRESSED = 60 MB`), archives raw files untouched under `/{org_id}/raw/`, scans top 15 rows for logo/title preamble rows, flags bottom `Grand Total` rows, neutralizes CSV formula injection (`=`, `+`, `-`, `@`), and saves columnar Apache Parquet.
- **`core/profiler.py`**: Computes column stats (null %, distinct count, uniqueness ratio, min/max/mean/median, IQR outliers, PII flags), guesses business domain & dataset grain (`order` vs `line_item` vs `ledger_entry`), and runs the **7-Dimension Data Quality Engine** (Completeness, Uniqueness, Validity, Consistency, Timeliness, Referential Integrity, Business-Rule Compliance).
- **`core/semantic_mapper.py`**: Runs 3-tier hybrid column-to-concept mapping (Tier-1 regex/synonym rules → Tier-2 metadata-only classifier → Tier-3 human confirmation + per-org saved schema memory) plus the **Phase 2 Relationship & Join Safety Validator** that blocks unsafe M:N row-multiplication joins.
- **`core/kpi_engine.py`**: Reads `kpis/*.yaml`, evaluates 4-state KPI eligibility (`Calculable`, `Calculable with Limitations`, `Requires Additional Information`, `Not Calculable` — never returning `0` for missing columns), computes deterministic KPIs with Trust Tooltips, MoM trends, Pareto 80/20, Revenue Variance Waterfalls, Insight Prioritization, and the What-If Simulator.
- **`core/ai_analyst.py`**: Implements `BaseLLMProvider` + `GeminiProvider`, Fernet BYOK cipher, XML-delimited prompt-injection & PII redaction, Pydantic `QueryPlanAST` allowlist validator, 15-minute TTL cache, and 5-part structured response contract with offline fallback.
- **`backend/auth.py` & `backend/store.py` & `backend/main.py`**: Multi-tenant JWT authentication, 5-role RBAC (`platform_admin`, `org_admin`, `dept_manager`, `analyst`, `viewer`), strict `organization_id` isolation (`403`/`404` on cross-tenant access), SQLite local metadata store, and PostgreSQL Row-Level Security schema (`backend/db/schema.sql`).
