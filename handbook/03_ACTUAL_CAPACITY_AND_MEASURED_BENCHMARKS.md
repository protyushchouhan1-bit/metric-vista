# 03 — Actual Capacity & Measured Engineering Benchmarks

Every number below was directly measured on this codebase using our automated 6-layer test suite (`tests/test_nexus_6_layers.py`) and benchmark workbook (`sample_data/benchmarks/nexus_excel_ground_truth.xlsx`).

## 1. Hard Capacity Limits (Built-In Guardrails)
| Dimension | Current Configured Capacity | Why This Limit Exists | Upgrade Path |
|---|---|---|---|
| **Maximum Rows per Upload** | **1,00,000 rows (1 Lakh)** | Keeps browser rendering snappy and backend RAM safely under 512 MB free-tier containers | Raise `MAX_ROWS` in `core/ingestion.py` & `MAX_ROWS_LIMIT` in `web_app/index.html` when hosted on 2 GB+ RAM |
| **Maximum File Size (Backend)** | **15 MB** | Prevents Out-Of-Memory (OOM) crashes on 512 MB RAM cloud tiers | Raise `MAX_FILE_BYTES` in `core/ingestion.py` |
| **Excel Zip-Bomb Ceiling** | **60 MB uncompressed XML** | Blocks malicious compressed `.xlsx` zip bombs | Configurable via `MAX_ZIP_UNCOMPRESSED` |
| **Supported File Formats** | `.xlsx`, `.xls`, `.csv`, `.tsv` | Covers 99% of SME departmental exports | Add SQL/API connectors & Google Sheets refresh in Phase 2/3 |
| **Departments Supported** | **Any arbitrary schema** (plus pre-built YAML registries for Sales, Finance, Marketing, HR, Supply Chain) | Schema-agnostic column discovery adapts to any business file | Add new `kpis/<domain>.yaml` files with zero Python code changes |

## 2. Measured Performance Benchmarks (100,000-Row Stress Test)
Tested on `sample_data/adversarial/08_stress_test_100k_rows.csv` (**100,000 rows × 12 columns, 8.5 MB**):
- **End-to-End Pipeline Latency** (Ingest + Parquet Conversion + Full Profiling + All Sales KPIs): **1.56 seconds**
- **Peak Memory Footprint (RSS)**: **296.1 MB** (safely below the 380 MB target envelope and 512 MB free-tier container ceiling)
- **One-Click Demo Load Time**: **< 0.5 seconds** (target: under 10 seconds)

## 3. Measured Business Correctness (Excel vs. Platform 2-Decimal Parity)
All 13 Sales & Finance benchmark KPIs matched independently calculated Excel formulas (`sample_data/benchmarks/nexus_excel_ground_truth.xlsx`) with **0.00 variance**:

| Domain | KPI Code | KPI Name | Excel Ground Truth | Platform Output | Delta |
|---|---|---|---:|---:|---:|
| Sales | `SALES_TOTAL_REVENUE` | Total Revenue | 3,784,295.00 | 3,784,295.00 | 0.00 |
| Sales | `SALES_DISTINCT_ORDERS` | Distinct Orders | 250.00 | 250.00 | 0.00 |
| Sales | `SALES_AOV` | Average Order Value | 15,137.18 | 15,137.18 | 0.00 |
| Sales | `SALES_UNITS_SOLD` | Total Units Sold | 1,281.00 | 1,281.00 | 0.00 |
| Sales | `SALES_ASP` | Average Selling Price | 2,954.17 | 2,954.17 | 0.00 |
| Sales | `SALES_GROSS_PROFIT` | Gross Profit | 1,740,975.00 | 1,740,975.00 | 0.00 |
| Sales | `SALES_GROSS_MARGIN_PCT` | Gross Margin % | 46.01 | 46.01 | 0.00 |
| Finance | `FIN_TOTAL_REVENUE` | P&L Revenue | 15,810,621.72 | 15,810,621.72 | 0.00 |
| Finance | `FIN_COGS` | P&L COGS | 6,845,643.61 | 6,845,643.61 | 0.00 |
| Finance | `FIN_OPEX` | P&L OpEx | 6,828,261.49 | 6,828,261.49 | 0.00 |
| Finance | `FIN_GROSS_PROFIT` | P&L Gross Profit | 8,964,978.11 | 8,964,978.11 | 0.00 |
| Finance | `FIN_OPERATING_PROFIT` | Operating Profit | 2,136,716.62 | 2,136,716.62 | 0.00 |
| Finance | `FIN_OPERATING_MARGIN_PCT` | Operating Margin % | 13.51 | 13.51 | 0.00 |

## 4. Automated Test Coverage
- **17 / 17 automated tests passing** in **2.58 seconds** across all 6 verification layers (Unit, HTTPX Integration, 8 Adversarial Datasets, Excel 2-Decimal Parity, Multi-Tenant Security & CSV Injection, and 100k-Row Stress Testing).
