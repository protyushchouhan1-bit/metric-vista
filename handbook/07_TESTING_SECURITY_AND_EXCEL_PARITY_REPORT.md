# 07 — 6-Layer Testing, Security & Adversarial Validation Report

This platform is verified across **6 automated testing layers** (`tests/test_nexus_6_layers.py`). Run all 17 tests anytime with:

```bash
python3 -m unittest discover -s tests -v
```

## The 6 Automated Verification Layers
1. **Layer 1 — Unit Testing**: Validates Pydantic JSON AST rejection of raw SQL injection (`revenue; DROP TABLE users;--`), Fernet BYOK key encryption roundtrip, CSV formula-injection escaping (`=`, `+`, `-`, `@` while keeping pure negative numbers like `-450.25`), XML prompt-injection & PII redaction, Phase 2 M:N join fan-out blocking, and What-If sensitivity math.
2. **Layer 2 — End-to-End API Integration**: Exercises the full FastAPI `/api/v1/` lifecycle via `TestClient`: JWT session issuance → CSV upload → profile & quality → mapping & grain confirmation → synchronized cross-filtering → grounded query → One-Click Demo (<10s).
3. **Layer 3 — 8 Mandatory Adversarial Datasets (`sample_data/adversarial/`)**:
   - `01_clean_baseline.csv`: Confirms `line_item` grain detection and zero critical blockers.
   - `02_missing_values_and_columns.csv`: Confirms missing `cogs` marks Gross Margin as `Not Calculable` (`Unavailable`), never `0`.
   - `03_exact_and_near_duplicates.csv`: Confirms exact + case-insensitive near duplicates reduce Uniqueness score.
   - `04_mixed_types_and_currencies.csv`: Confirms mixed `₹`/`$` currencies and invalid dates trigger loud `Critical Blocker` alerts.
   - `05_outliers_returns_and_injection.csv`: Confirms extreme IQR outliers and negative return rows flag Business-Rule Compliance warnings, and `=CMD|...` is neutralized on CSV export.
   - `06_ambiguous_cryptic_headers.csv`: Confirms cryptic headers (`NET_REV_AMT`, `ORD_REF_NO`, `TXN_DT`) map accurately and trigger mandatory human confirmation flags.
   - `07_messy_header_and_grand_total.xlsx`: Confirms Header-Row Scanner skips decorative logo/title rows (row index 3) and excludes the bottom `Grand Total` row so revenue is never double-counted.
   - `08_stress_test_100k_rows.csv`: Confirms 100,000-row ingestion, Parquet conversion, profiling, and KPI computation stay within **1.56s** and **296.1 MB Peak RSS**.
4. **Layer 4 — Business Correctness & Excel Parity**: Verifies 2-decimal parity (`0.00` delta) across all 13 Sales & Finance KPIs against `sample_data/benchmarks/nexus_excel_ground_truth.xlsx`.
5. **Layer 5 — Multi-Tenant Security & RBAC Isolation**: Proves Org B receives `404`/`403` when requesting Org A's datasets, KPIs, or audit logs, Viewer role receives `403` on upload, and exported CSVs neutralize `=CMD|` payloads.
6. **Layer 6 — Performance & Offline Graceful Degradation**: Verifies peak RAM `<380 MB` on 100,000 rows and 100% dashboard continuity when no external API key is configured.
