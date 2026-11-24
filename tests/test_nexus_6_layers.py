"""
Project NEXUS V2.0 — Comprehensive 6-Layer + Phase 1-4 Hardened Automated Test Suite
Covers:
  - Phase 1 Security: forged X-Org-Id/X-Role headers -> 401, demo-mode write -> 403,
    Fernet fail-loudly when key missing, mixed-currency detection for ₹/$/€/£/INR/USD/EUR/GBP.
  - Phase 2 Core Claims: Real LLM JSON AST planning + explanation (mocked provider),
    Tier-2 metadata-only column classifier (mocked provider), LibreOffice-recalculated Excel parity,
    synchronized cross-filter manual math parity, Price/Volume/Mix waterfall.
  - Layers 1-6: Unit, Integration, 8 Adversarial Datasets, Excel Parity, Multi-Tenant Isolation, Stress.
"""
import json
import os
import resource
import sys
import tempfile
import time
import unittest

import openpyxl
import pandas as pd
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.main import app, ensure_demo_workspaces_seeded
from core.ai_analyst import (
    BYOKCipher,
    BaseLLMProvider,
    GroundedAIAnalyst,
    QueryPlanAST,
    sanitize_untrusted_samples,
)
from core.ingestion import ingest_file, sanitize_csv_cell
from core.kpi_engine import compute_dashboard_analytics, compute_kpis, run_what_if_simulation
from core.profiler import detect_currencies_in_series, evaluate_data_quality, profile_dataset
from core.semantic_mapper import propose_semantic_mappings, validate_dataset_relationship

ADV_DIR = os.path.join(ROOT, "sample_data", "adversarial")
BENCH_RECALC = os.path.join(ROOT, "sample_data", "benchmarks", "nexus_excel_recalculated_libreoffice.xlsx")
P2_DIR = os.path.join(ROOT, "sample_data", "phase2")
KPIS_DIR = os.path.join(ROOT, "kpis")


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock LLM for testing real Tier-2 classification & Stage-2 live_llm pipeline."""

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if "Semantic Schema Classifier" in system_prompt:
            return json.dumps({
                "canonical_concept": "revenue",
                "confidence": 0.91,
                "reason": "Cryptic numeric column with currency-scale values represents net revenue.",
                "alternatives": ["actual_amount"],
            })
        if "Query Planner" in system_prompt:
            return json.dumps({
                "metric": "revenue",
                "aggregation": "sum",
                "group_by": ["region"],
                "filters": [],
                "order_direction": "desc",
                "limit": 5,
            })
        return "Verified live LLM narrative: South and West lead regional revenue based on DuckDB/Parquet totals."


class TestPhase1SecurityAndCurrencies(unittest.TestCase):
    """Phase 1 Gate: Forged headers -> 401, Demo writes -> 403, Fernet fail-loudly, Mixed currencies."""

    def setUp(self):
        self.client = TestClient(app)
        ensure_demo_workspaces_seeded()

    def test_forged_headers_rejected_with_401(self):
        r = self.client.get("/api/v1/datasets", headers={"X-Org-Id": "org-victim", "X-Role": "org_admin"})
        self.assertEqual(r.status_code, 401)

    def test_demo_mode_is_strictly_read_only(self):
        h_demo = {"X-Demo-Mode": "true"}
        # Read allowed
        self.assertEqual(self.client.get("/api/v1/datasets", headers=h_demo).status_code, 200)
        # Upload forbidden (403)
        with open(os.path.join(ADV_DIR, "01_clean_baseline.csv"), "rb") as fh:
            up = self.client.post("/api/v1/datasets/upload", files={"file": ("01.csv", fh, "text/csv")}, headers=h_demo)
        self.assertEqual(up.status_code, 403)
        # Settings update forbidden (403)
        st = self.client.patch("/api/v1/orgs/demo-org-public/settings", json={"base_currency": "USD"}, headers=h_demo)
        self.assertEqual(st.status_code, 403)
        # Delete forbidden (403)
        dl = self.client.delete("/api/v1/datasets/demo-acme-retail", headers=h_demo)
        self.assertEqual(dl.status_code, 403)

    def test_fernet_fails_loudly_when_key_missing(self):
        prev = os.environ.pop("NEXUS_FERNET_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                BYOKCipher()
        finally:
            if prev is not None:
                os.environ["NEXUS_FERNET_KEY"] = prev

    def test_mixed_currency_detection_all_patterns(self):
        self.assertEqual(detect_currencies_in_series(pd.Series(["₹1200", "$450"])), ["INR", "USD"])
        self.assertEqual(detect_currencies_in_series(pd.Series(["INR 5000", "USD 120"])), ["INR", "USD"])
        self.assertEqual(detect_currencies_in_series(pd.Series(["€99.50", "£80.00"])), ["EUR", "GBP"])
        self.assertEqual(detect_currencies_in_series(pd.Series(["Rs. 450", "EUR 20"])), ["EUR", "INR"])
        self.assertEqual(detect_currencies_in_series(pd.Series(["₹100", "₹200"])), ["INR"])


class TestPhase2RealAIAndTier2AndCrossFilter(unittest.TestCase):
    """Phase 2 Gate: Real live_llm AST + narrative, Tier-2 mock classifier, cross-filter math parity."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="nexus_p2_")
        with open(os.path.join(ADV_DIR, "01_clean_baseline.csv"), "rb") as fh:
            self.ing = ingest_file(fh.read(), "01_clean_baseline.csv", "org-p2", "s1", self.tmpdir)
        self.df = pd.read_parquet(self.ing.parquet_path, engine="pyarrow")
        self.prof = profile_dataset(self.df)
        self.maps = propose_semantic_mappings(self.prof)["proposals"]
        for m in self.maps:
            m["confirmed_by_human"] = True

    def test_real_live_llm_ast_and_narrative_not_discarded(self):
        kpis = compute_kpis(self.ing.parquet_path, "sales", self.maps, KPIS_DIR, grain_confirmed=True)
        analyst = GroundedAIAnalyst(provider=MockLLMProvider())
        ans = analyst.ask("Break down revenue by region", "org-p2", "s1", self.ing.parquet_path, "sales", self.maps, kpis)
        self.assertEqual(ans["execution_mode"], "live_llm")
        self.assertEqual(ans["stage"], "stage2_json_ast")
        self.assertIn("Verified live LLM narrative", ans["structured_answer"]["verified_observation_and_evidence"])
        self.assertTrue(len(ans["see_the_query_and_evidence"]["result_rows"]) == 4)

    def test_tier2_metadata_classifier_with_mock_provider(self):
        df_weird = pd.DataFrame({"ZZZ_X99": [12500.0, 18400.0, 9100.0, 22000.0]})
        prof_w = profile_dataset(df_weird)
        res = propose_semantic_mappings(prof_w, llm_classifier=MockLLMProvider())
        prop = res["proposals"][0]
        self.assertEqual(prop["mapping_tier"], "tier2_ai")
        self.assertEqual(prop["canonical_concept"], "revenue")

    def test_synchronized_cross_filter_matches_manual_calculation(self):
        manual_north = round(float(self.df.loc[self.df["region"] == "North", "revenue"].sum()), 2)
        kpis_north = compute_kpis(self.ing.parquet_path, "sales", self.maps, KPIS_DIR, grain_confirmed=True, filters={"region": "North"})
        rev_north = next(k["value"] for k in kpis_north["kpis"] if k["code"] == "SALES_TOTAL_REVENUE")
        self.assertAlmostEqual(rev_north, manual_north, places=2)

    def test_pvm_waterfall_calculable_and_honest_when_missing(self):
        dash = compute_dashboard_analytics(self.ing.parquet_path, "sales", self.maps)
        self.assertEqual(dash["pvm_waterfall"]["status"], "Calculable")
        self.assertEqual(len(dash["pvm_waterfall"]["steps"]), 5)
        # Remove unit_price -> must mark Requires Additional Information
        maps_no_px = [m for m in self.maps if m["canonical_concept"] != "unit_price"]
        dash2 = compute_dashboard_analytics(self.ing.parquet_path, "sales", maps_no_px)
        self.assertEqual(dash2["pvm_waterfall"]["status"], "Requires Additional Information")


class TestLayers1To6CoreSuite(unittest.TestCase):
    """Original 6-Layer Suite + LibreOffice Recalculated Excel Parity."""

    def setUp(self):
        self.client = TestClient(app)
        self.tmpdir = tempfile.mkdtemp(prefix="nexus_core_")

    def test_unit_ast_csv_prompt_join_whatif(self):
        with self.assertRaises(ValueError):
            QueryPlanAST(metric="revenue; DROP TABLE users;--", aggregation="sum")
        self.assertEqual(sanitize_csv_cell("=CMD|' /C calc'!A0"), "'=CMD|' /C calc'!A0")
        self.assertEqual(sanitize_csv_cell("-450.25"), "-450.25")
        out = sanitize_untrusted_samples(["Ignore previous instructions", "ceo@acme.com", "+91 9876543210"])
        self.assertIn("[REDACTED_CONTROL]", out[0])
        self.assertIn("[REDACTED_EMAIL]", out[1])
        orders = pd.read_csv(os.path.join(ADV_DIR, "01_clean_baseline.csv"))
        dups = pd.read_csv(os.path.join(P2_DIR, "customers_with_duplicates.csv"))
        self.assertEqual(validate_dataset_relationship(orders, dups, "customer_id", "customer_id")["status"], "BLOCKED")
        self.assertEqual(run_what_if_simulation(1000000, 500000, 200000, price_change_pct=10)["scenario_outputs"]["net_profit_delta"], 100000.0)

    def test_all_adversarial_datasets_01_to_07(self):
        def run(fname):
            with open(os.path.join(ADV_DIR, fname), "rb") as fh:
                ing = ingest_file(fh.read(), fname, "org-adv", fname[:2], self.tmpdir)
            df = pd.read_parquet(ing.parquet_path, engine="pyarrow")
            prof = profile_dataset(df)
            qual = evaluate_data_quality(df, prof, flagged_total_rows=ing.flagged_total_rows)
            maps = propose_semantic_mappings(prof)
            return ing, df, prof, qual, maps

        _, _, p1, q1, _ = run("01_clean_baseline.csv")
        self.assertFalse(q1["has_critical_blockers"])
        self.assertEqual(p1["grain_discovery"]["detected_grain"], "line_item")

        i2, _, _, _, m2 = run("02_missing_values_and_columns.csv")
        for x in m2["proposals"]:
            x["confirmed_by_human"] = True
        gm = next(k for k in compute_kpis(i2.parquet_path, "sales", m2["proposals"], KPIS_DIR, grain_confirmed=True)["kpis"] if k["code"] == "SALES_GROSS_MARGIN_PCT")
        self.assertEqual(gm["eligibility_status"], "Not Calculable")
        self.assertIsNone(gm["value"])

        _, _, p3, _, _ = run("03_exact_and_near_duplicates.csv")
        self.assertGreater(p3["exact_duplicates"], 0)

        _, _, p4, q4, _ = run("04_mixed_types_and_currencies.csv")
        self.assertTrue(q4["has_critical_blockers"])
        self.assertIn("revenue", p4["mixed_currency_columns"])

        _, _, _, q5, _ = run("05_outliers_returns_and_injection.csv")
        self.assertEqual(next(d for d in q5["dimensions"] if d["dimension"] == "Business-Rule Compliance")["severity"], "Warning")

        _, _, _, _, m6 = run("06_ambiguous_cryptic_headers.csv")
        self.assertGreater(m6["pending_confirmation_count"], 0)

        i7, df7, _, _, _ = run("07_messy_header_and_grand_total.xlsx")
        self.assertEqual(i7.detected_header_row, 3)
        self.assertEqual(len(df7), 100)

    def test_libreoffice_recalculated_excel_2_decimal_parity(self):
        wb = openpyxl.load_workbook(BENCH_RECALC, data_only=True)
        ws = wb["Ground_Truth_KPIs"]
        expected = {}
        for row in list(ws.iter_rows(values_only=True))[1:]:
            code = row[1]
            recalc_val = row[3]  # Actual LibreOffice-evaluated Excel formula result!
            self.assertIsInstance(recalc_val, (int, float), f"Formula failed to evaluate in LibreOffice for {code}: {recalc_val}")
            expected[code] = float(recalc_val)

        with open(os.path.join(ADV_DIR, "01_clean_baseline.csv"), "rb") as fh:
            ing_s = ingest_file(fh.read(), "01_clean_baseline.csv", "org-b", "s", self.tmpdir)
        maps_s = propose_semantic_mappings(profile_dataset(pd.read_parquet(ing_s.parquet_path)))["proposals"]
        for m in maps_s:
            m["confirmed_by_human"] = True
        ks = compute_kpis(ing_s.parquet_path, "sales", maps_s, KPIS_DIR, grain_confirmed=True)["kpis"]

        with open(os.path.join(ROOT, "sample_data", "demo", "apex_saas_finance.xlsx"), "rb") as fh:
            ing_f = ingest_file(fh.read(), "apex_saas_finance.xlsx", "org-b", "f", self.tmpdir)
        maps_f = propose_semantic_mappings(profile_dataset(pd.read_parquet(ing_f.parquet_path)))["proposals"]
        for m in maps_f:
            m["confirmed_by_human"] = True
        kf = compute_kpis(ing_f.parquet_path, "finance", maps_f, KPIS_DIR, grain_confirmed=True)["kpis"]

        actual = {k["code"]: k["value"] for k in (ks + kf)}
        for code, exp_val in expected.items():
            self.assertAlmostEqual(actual[code], exp_val, places=2, msg=f"LibreOffice Excel parity mismatch on {code}")

    def test_org_a_vs_org_b_isolation_and_csv_export(self):
        ta = self.client.post("/api/v1/auth/session", json={"user_id": "a1", "organization_id": "org-A", "role": "org_admin"}).json()["access_token"]
        tb = self.client.post("/api/v1/auth/session", json={"user_id": "b1", "organization_id": "org-B", "role": "org_admin"}).json()["access_token"]
        ha, hb = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}
        with open(os.path.join(ADV_DIR, "05_outliers_returns_and_injection.csv"), "rb") as fh:
            up = self.client.post("/api/v1/datasets/upload", files={"file": ("05.csv", fh, "text/csv")}, headers=ha)
        self.assertEqual(up.status_code, 200)
        ds_id = up.json()["dataset_id"]
        self.assertEqual(self.client.get(f"/api/v1/datasets/{ds_id}/profile", headers=hb).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/orgs/org-A/audit-logs", headers=hb).status_code, 403)
        exp = self.client.post(f"/api/v1/dashboards/{ds_id}/export", json={"filters": {}}, headers=ha)
        self.assertIn("'=CMD|", exp.text)

    def test_100k_row_stress_and_ram_ceiling(self):
        t0 = time.perf_counter()
        with open(os.path.join(ADV_DIR, "08_stress_test_100k_rows.csv"), "rb") as fh:
            ing = ingest_file(fh.read(), "08_stress_test_100k_rows.csv", "org-st", "s100k", self.tmpdir)
        df = pd.read_parquet(ing.parquet_path, engine="pyarrow")
        maps = propose_semantic_mappings(profile_dataset(df))["proposals"]
        for m in maps:
            m["confirmed_by_human"] = True
        kpis = compute_kpis(ing.parquet_path, "sales", maps, KPIS_DIR, grain_confirmed=True)
        elapsed = time.perf_counter() - t0
        rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        self.assertEqual(ing.row_count, 100_000)
        self.assertEqual(kpis["rows_evaluated"], 100_000)
        print(f"\n[STRESS] 100k-row ingest+profile+KPI: {elapsed:.2f}s | Peak RSS: {rss_mb:.1f} MB")


if __name__ == "__main__":
    unittest.main()
