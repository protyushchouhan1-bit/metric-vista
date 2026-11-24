# 02 — How It Was Made & Complete Evolution Log (Every Change Made)

This document traces the exact journey from the initial 19-page Engineering Specification to the final localhost-ready platform, documenting every design decision and user-driven iteration.

## Stage 1: Foundation & Full-Stack Core Build
- **Monorepo Scaffolding**: Created `core/`, `kpis/`, `backend/`, `frontend/`, `sample_data/`, `tests/`, `docs/`, and `.github/workflows/`.
- **8 Mandatory Adversarial Datasets + Excel Benchmarks**: Built `generate_sample_data.py` to produce clean, missing-column, duplicate, mixed-currency, outlier/CSV-injection, cryptic-header, messy multi-header + Grand Total Excel, and 100k-row stress datasets, plus `nexus_excel_ground_truth.xlsx` with live Excel formulas.
- **Deterministic Core Engine**: Implemented safe ingestion, 7-dimension data quality scoring, 3-tier semantic mapping, YAML KPI registry (`sales.yaml`, `finance.yaml`, `marketing.yaml`, `hr.yaml`, `supply_chain.yaml`), DuckDB/Parquet analytics, and 6-layer automated test verification (17/17 tests passing, 0.00 Excel delta).

## Stage 2: Visual Overhaul — From Dark Neon to Corporate Pale Off-White
- **What Changed**: Replaced the initial dark-neon aesthetic with a refined **corporate off-white canvas (`#F7F6F2`)**, pure white elevated cards (`#FFFFFF`), crisp `#E2E8F0` borders, and a **vibrant, saturated corporate chart palette** (Sapphire `#1D4ED8`, Emerald `#059669`, Amber-Gold `#F59E0B`, Crimson `#E11D48`, Violet `#7C3AED`, Teal `#0891B2`).
- **Branding Cleanup**: Removed hardcoded platform names and version banners; replaced with a **center-aligned editable blank brand header** so you can type your own company or product name anytime.
- **Plain-English Language**: Translated technical BI jargon (`grain`, `AOV`, `COGS`, `Calculable`) into everyday layman language (*Orders Placed*, *Average Bill Size*, *Profit After Cost*, *Safe Zone / Danger Zone*).

## Stage 3: Upload-First Dynamic Architecture & 8-Step Animated ETL Pipeline
- **Removed Fixed Department Tabs**: Instead of locking the app to pre-made Sales/Finance/HR tabs, the app now opens directly on a clean **Upload Your Company Spreadsheet** landing page supporting up to **1,00,000 rows (1 Lakh rows)**.
- **Added 60fps 8-Step Data Processing Animation**: Every upload runs through an animated 8-step lifecycle (*1. Business Understanding → 2. Data Collection → 3. Data Cleaning → 4. EDA → 5. Feature Engineering → 6. Modeling → 7. Evaluation → 8. Deployment & Monitoring*) with converging 60fps data particles and live progress logs.
- **Added Reversible Data Studio (ETL Backend)**: Users can return to **Data Studio (ETL Backend)** anytime to inspect every exact correction made (duplicates removed, Grand Total rows stripped, currency symbols cleaned, missing cells filled), view the **Column-by-Column Quality Scorecard**, toggle any cleaning rule on/off, and re-run processing immediately.

## Stage 4: Dynamic Schema Adaptation, Smart Animations & Expanded Q&A
- **Dynamic Schema-Agnostic Metrics**: Automatically inspects any uploaded file's columns to build 6 adaptive KPIs, dynamic slicers (Season, Month, Date Range, plus detected category columns), a live **Measure** switcher, and 6 vibrant interactive charts (Area/Column Trend, Donut/Pie Share, Multi-Series Comparison, Polar Balance, Horizontal Top Performers, Seasonal Breakdown).
- **Smart Adaptive Animation**: Replaced fixed quarterly cycling with an adaptive **Animate By** engine (Month-by-Month, Season-by-Season, Quarter-by-Quarter, or Category-by-Category depending on the uploaded dataset).
- **Fixed & Expanded `Ask Questions`**: Removed all visible mentions of "AI"; fixed question answering so asking *"What is my company selling?"*, *"What corrections did you make?"*, *"How is my column quality?"*, or *"Any problems and solutions?"* inspects the actual products, categories, ETL audit log, and health rules to praise strong metrics and recommend concrete fixes.

## Stage 5: Native Excel (`.xlsx` / `.xls`) Bug Fix & Localhost Packaging
- **Root Cause Fixed**: Uploading an `.xlsx` file previously triggered plain-text CSV reading, displaying raw ZIP bytes (`PK...DocProps/App.Xml...`). Integrated **SheetJS (`xlsx@0.18.5`)** with magic-byte detection (`0x50 0x4B` for `.xlsx`, `0xD0 0xCF` for `.xls`), automatic top-15-row header scanning, quoted-CSV parsing, and binary-file protection.
- **One-Click Localhost Launcher**: Added `server.py`, `run_local.bat` (Windows), and `run_local.sh` (macOS/Linux) to launch the complete dashboard + FastAPI backend at `http://localhost:8000`.
