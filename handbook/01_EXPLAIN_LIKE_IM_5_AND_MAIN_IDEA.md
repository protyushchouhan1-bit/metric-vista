# 01 — Explain Like I'm 5 & The Main Idea

## 1. How to Explain This Project to a 5-Year-Old
Imagine you have a giant messy toy box with Lego bricks, toy cars, puzzle pieces, and a few broken toys all mixed together.
- If someone asks you *"How many red Lego bricks do we have?"*, you can't answer until you dump the box out, throw away broken duplicates, sort every toy onto labeled shelves, and count them carefully.
- **This project is an automatic toy-box organizer for company spreadsheets.**
- A business owner drops a messy Excel or CSV file into the app. Our program automatically cleans the mess (removes duplicate rows, fixes broken currency signs like `₹1,200`, fills blank spots, removes accidental "Grand Total" rows), sorts everything neatly, draws colorful moving charts, tells the owner if anything is in a **Danger Zone**, and answers plain-English questions like *"What is my company selling?"* or *"What corrections did you make?"*

## 2. How to Explain This Project to Any Layman (Non-Technical Business Owner)
Most small and medium businesses run Sales, Finance, Supply Chain, HR, and Marketing in separate, messy Excel sheets.
- Traditional BI tools (like Power BI or Tableau) require trained analysts and rigid schemas.
- Generic chat tools guess or hallucinate numbers when you paste spreadsheets into them.
- **Our platform bridges that gap:** You upload any Excel (`.xlsx`, `.xls`) or CSV file (up to **1,00,000 rows / 1 Lakh rows**), watch an **8-step automated cleaning & processing pipeline** tidy your data right in front of you, and immediately get an executive corporate dashboard with colorful interactive charts, **Safe Zone / Watch Zone / Danger Zone** alerts, an **Economic Order Quantity (EOQ) & Profit Planner**, and a plain-English **Ask Questions** hub—with zero coding required. If you don't like any automated cleaning fix, you can click straight into **Data Studio (ETL Backend)** to toggle rules off and re-process your raw file.

## 3. How to Explain This Project to Another AI or Senior Engineer
This is a **Modular Monolith Enterprise Analytics & Data Quality Platform** combining:
1. A **framework-agnostic Python analytical core (`core/`)** performing safe ingestion, 7-dimension data quality auditing, 3-tier hybrid semantic mapping, YAML-driven 15-field KPI contracts, DuckDB/PyArrow deterministic computation on Apache Parquet, Pareto 80/20, Revenue Variance Waterfalls, and Phase 2 M:N join fan-out protection.
2. A **versioned FastAPI `/api/v1/` backend (`backend/`)** with multi-tenant `organization_id` isolation, 5-role RBAC, PostgreSQL RLS schema (`backend/db/schema.sql`), Fernet BYOK key encryption, CSV formula-injection neutralization, and audit logging.
3. A **corporate off-white interactive frontend (`web_app/index.html` + React/TS/ECharts `frontend/`)** featuring native browser Excel (`.xlsx`/`.xls`) & CSV parsing, a 60fps HTML5 `<canvas>` 8-step ETL pipeline, reversible backend cleaning controls, dynamic schema-agnostic KPI & slicer generation, 6 vibrant interactive charts, EOQ & What-If simulation, and deterministic Q&A.
