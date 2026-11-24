# 05 — 6-Layer Testing & MVP Benchmark Protocol

## 6 Automated Verification Layers
1. **Unit Testing**: Validates KPI formulas, fiscal calendar helpers, Tier-1 semantic rules, 7-dimension quality scorer, and Pydantic AST validator in isolation.
2. **Integration Testing (HTTPX)**: Exercises full FastAPI `/api/v1/` lifecycle: upload → Parquet conversion → profile/quality → mapping & grain confirmation → synchronized cross-filtering → grounded AI Q&A → CSV export.
3. **Adversarial Data Validation (8 Mandatory Datasets)**:
   - `01_clean_baseline.csv`
   - `02_missing_values_and_columns.csv` (verifies `Not Calculable` without `0` fallback)
   - `03_exact_and_near_duplicates.csv` (verifies uniqueness penalty & warning)
   - `04_mixed_types_and_currencies.csv` (verifies critical mixed-currency blocker)
   - `05_outliers_returns_and_injection.csv` (verifies IQR outlier detection, negative return rules, CSV formula neutralization)
   - `06_ambiguous_cryptic_headers.csv` (verifies Tier-1/Tier-2 mapping + mandatory human confirmation flags)
   - `07_messy_header_and_grand_total.xlsx` (verifies header-row scanner skips logo rows & flags bottom Grand Total row)
   - `08_stress_test_100k_rows.csv` (verifies 100k-row profiling, Parquet conversion, and cross-filter latency/memory)
4. **Business Correctness & Excel Parity**: Compares NEXUS KPI outputs against `sample_data/benchmarks/nexus_excel_ground_truth.xlsx` to 2 decimal places.
5. **Security & Isolation**: Proves Org A cannot access Org B datasets/dashboards (`403`/`404`), Viewer cannot upload (`403`), CSV injection prefixes are escaped, and prompt-injection strings are sanitized.
6. **Performance & Graceful Degradation**: Measures p50/p95 latency and peak RAM on the 100k-row stress file (target `<380 MB` RAM) and confirms 100% dashboard continuity with AI API key disabled.
