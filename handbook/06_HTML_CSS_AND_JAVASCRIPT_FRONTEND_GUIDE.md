# 06 — HTML, CSS, JavaScript & Frontend Architecture Guide

This project ships with **two synchronized frontend options**:
1. **`web_app/index.html`** — The self-contained, zero-build-step **Corporate Off-White 8-Step ETL & Interactive Dashboard** served directly at `http://localhost:8000/` by `server.py` (works immediately without `npm install`).
2. **`frontend/`** — The full modular **React 18 + TypeScript + Tailwind CSS + Vite + Apache ECharts** codebase ready for Vercel deployment.

## 1. Frontend Libraries Used & Why
| Library | Where Used | Plain-English Purpose |
|---|---|---|
| **Tailwind CSS (`3.4.17`)** | `web_app/index.html` & `frontend/` | Utility-first CSS framework for clean spacing, responsive grids, rounded corporate cards, and crisp borders. |
| **Chart.js (`4.4.1`)** | `web_app/index.html` | Powers all 6 animated, clickable corporate charts (Area/Column Trend, Donut/Pie Share, Multi-Series Comparison, Polar Area, Ranked Horizontal Bar, Seasonal Bar). |
| **SheetJS / `xlsx` (`0.18.5`)** | `web_app/index.html` | Decodes native binary Microsoft Excel workbooks (`.xlsx` and `.xls`) directly inside the browser so users never see garbled ZIP bytes (`PK...`). |
| **HTML5 `<canvas>` + `requestAnimationFrame`** | `web_app/index.html` | Renders the smooth 60fps 8-step ETL data-assembly particle & rising-bar animation when a file is uploaded. |
| **Inter Google Font (`tabular-nums`)** | Both frontends | Clean corporate sans-serif typography where every number aligns vertically in tables and KPI cards. |
| **React + TypeScript + Apache ECharts + Lucide Icons** | `frontend/` | Modular SaaS frontend wired to `/api/v1/` endpoints for cloud deployment on Vercel. |

## 2. Corporate Off-White CSS Design System
- **Canvas Background**: `#F7F6F2` (warm pale alabaster off-white — eliminates eye fatigue and looks executive).
- **Elevated Cards**: `#FFFFFF` pure white with `1px solid #E2E8F0` borders, `0.9rem` rounded corners, and subtle hover lift shadow.
- **Typography**: Deep Slate `#0F172A` / `#1E293B` headings and KPI values, `#64748B` subtitles, `font-variant-numeric: tabular-nums` on every metric.
- **Vibrant Corporate Chart Palette**:
  - Sapphire `#1D4ED8`, Emerald `#059669`, Amber-Gold `#F59E0B`, Crimson `#E11D48`, Violet `#7C3AED`, Teal `#0891B2`, Tangerine `#EA580C`, Rose `#DB2777`.
- **Health Zone Badges**:
  - Safe Zone: `#ECFDF5` fill / `#047857` text / `#6EE7B7` border
  - Watch Zone: `#FFFBEB` fill / `#B45309` text / `#FCD34D` border
  - Danger Zone: `#FFF1F2` fill / `#BE123C` text / `#FDA4AF` border

## 3. How the Browser ETL & Interactive JavaScript Works (`web_app/index.html`)
1. **Binary Magic-Byte Detection (`handleCSVFile`)**: Reads the uploaded file as an `ArrayBuffer`. If the first two bytes are `0x50 0x4B` (`PK`, i.e., `.xlsx`) or `0xD0 0xCF` (legacy `.xls`), it decodes the workbook via `XLSX.read(...)` with automatic header-row scanning (`detectBestHeaderIndex`). Otherwise it parses CSV using a proper quote-aware parser (`parseCSVLine`).
2. **Reversible 8-Step Cleaning (`runRealETLPipeline`)**: Keeps `state.rawUpload` completely untouched so toggling any checkbox in **Data Studio (ETL Backend)** and clicking **Re-Run 8-Step Cleaning** re-computes everything cleanly from the original raw data.
3. **Dynamic Slicers & Cross-Filtering (`buildDynamicSlicers` & `renderCharts`)**: Clicking any pie slice, horizontal bar, or seasonal bar updates `state.filters[column]` and re-renders all 6 KPI cards, the Danger Zone banner, and all 6 animated charts in sync.
4. **Expanded `Ask Questions` (`answerQuestion`)**: Inspects the user's question against actual ETL corrections, column quality stats, product/category columns, wins, risks, and numeric columns to produce accurate, grounded answers with praise and actionable solutions.
