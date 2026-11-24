"""
Stage 5 — YAML KPI Registry, 4-State Eligibility Matrix, Deterministic DuckDB/Parquet
Analytics Engine, Pareto 80/20, Revenue Variance Waterfall, Insight Prioritizer,
and Transparent What-If Simulator.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

try:
    import duckdb  # type: ignore
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


def load_kpi_registry(kpis_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load all version-controlled YAML KPI definitions from kpis/*.yaml."""
    registry: Dict[str, List[Dict[str, Any]]] = {}
    if not os.path.isdir(kpis_dir):
        return registry
    for fname in sorted(os.listdir(kpis_dir)):
        if fname.endswith((".yaml", ".yml")):
            with open(os.path.join(kpis_dir, fname), "r", encoding="utf-8") as fh:
                doc = yaml.safe_load(fh) or {}
            dept = doc.get("department", os.path.splitext(fname)[0])
            registry[dept] = doc.get("kpis", [])
    return registry


def _clean_numeric_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    cleaned = (
        s.astype(str)
        .str.replace(r"(₹|\$|€|£|\bINR\b|\bUSD\b|\bEUR\b|\bGBP\b|\bRs\.?\b|,|\s)", "", regex=True)
        .replace({"": np.nan, "nan": np.nan, "None": np.nan, "N/A": np.nan, "null": np.nan})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def load_parquet_filtered(
    parquet_path: str,
    concept_to_col: Dict[str, str],
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, int]:
    """
    Read Parquet and apply synchronized cross-filters in a single DuckDB query (when available)
    or deterministic PyArrow/Pandas equivalent. Returns (filtered_df, excluded_row_count).
    """
    filters = filters or {}
    if HAS_DUCKDB:
        con = duckdb.connect(database=":memory:")
        where_clauses = []
        params: List[Any] = []
        for concept, val in filters.items():
            col = concept_to_col.get(concept, concept)
            if val is None or val == "" or val == "All":
                continue
            if concept == "date_from":
                dcol = concept_to_col.get("order_date") or concept_to_col.get("period_date")
                if dcol:
                    where_clauses.append(f'CAST("{dcol}" AS VARCHAR) >= ?')
                    params.append(str(val))
            elif concept == "date_to":
                dcol = concept_to_col.get("order_date") or concept_to_col.get("period_date")
                if dcol:
                    where_clauses.append(f'CAST("{dcol}" AS VARCHAR) <= ?')
                    params.append(str(val))
            elif isinstance(val, list) and val:
                placeholders = ",".join(["?"] * len(val))
                where_clauses.append(f'"{col}" IN ({placeholders})')
                params.extend(val)
            else:
                where_clauses.append(f'"{col}" = ?')
                params.append(val)
        total_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')").fetchone()[0]
        sql = f"SELECT * FROM read_parquet('{parquet_path}')"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        df = con.execute(sql, params).fetchdf()
        con.close()
        return df, max(int(total_rows - len(df)), 0)

    # Deterministic PyArrow/Pandas fallback (identical semantics)
    df_all = pd.read_parquet(parquet_path, engine="pyarrow")
    total_rows = len(df_all)
    df = df_all
    for concept, val in filters.items():
        if val is None or val == "" or val == "All":
            continue
        if concept == "date_from":
            dcol = concept_to_col.get("order_date") or concept_to_col.get("period_date")
            if dcol and dcol in df.columns:
                df = df[df[dcol].astype(str) >= str(val)]
        elif concept == "date_to":
            dcol = concept_to_col.get("order_date") or concept_to_col.get("period_date")
            if dcol and dcol in df.columns:
                df = df[df[dcol].astype(str) <= str(val)]
        else:
            col = concept_to_col.get(concept, concept)
            if col in df.columns:
                if isinstance(val, list):
                    df = df[df[col].isin(val)]
                else:
                    df = df[df[col].astype(str) == str(val)]
    return df.reset_index(drop=True), max(int(total_rows - len(df)), 0)


def _format_value(val: Optional[float], unit_format: str, currency: str = "INR") -> str:
    if val is None:
        return "Unavailable"
    sym = "₹" if currency == "INR" else "$"
    if unit_format == "currency":
        return f"{sym}{val:,.2f}"
    if unit_format == "percent":
        return f"{val:.2f}%"
    if unit_format == "integer":
        return f"{int(round(val)):,}"
    if unit_format == "ratio":
        return f"{val:.2f}x"
    return f"{val:,.2f}"


def compute_kpis(
    parquet_path: str,
    domain: str,
    mappings: List[Dict[str, Any]],
    kpis_dir: str,
    grain_confirmed: bool = True,
    currency: str = "INR",
    filters: Optional[Dict[str, Any]] = None,
    quality_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate 4-State KPI Eligibility & compute deterministic KPIs with full Trust Tooltips.
    Never displays 0 for Not Calculable KPIs—explicitly names missing concepts.
    """
    registry = load_kpi_registry(kpis_dir)
    kpi_defs = registry.get(domain, registry.get("sales", []))

    concept_to_col: Dict[str, str] = {}
    confirmed_concepts: set = set()
    for m in mappings:
        c = m.get("canonical_concept")
        if c and c != "unmapped":
            concept_to_col[c] = m["source_column"]
            if m.get("confirmed_by_human", False):
                confirmed_concepts.add(c)

    df, filter_excluded = load_parquet_filtered(parquet_path, concept_to_col, filters)

    # Exclude cancelled/void orders for Sales domain
    status_excluded = 0
    if domain == "sales" and "order_status" in concept_to_col:
        scol = concept_to_col["order_status"]
        if scol in df.columns:
            mask = ~df[scol].astype(str).str.strip().str.lower().isin({"cancelled", "canceled", "void"})
            status_excluded = int((~mask).sum())
            df = df[mask].reset_index(drop=True)

    total_excluded = filter_excluded + status_excluded
    now_iso = datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []

    # Pre-parse numeric columns referenced by mappings
    num_cache: Dict[str, pd.Series] = {}
    for concept in (
        "revenue", "cogs", "quantity", "discount_amount", "actual_amount", "budget_amount",
        "marketing_spend", "attributed_revenue", "impressions", "clicks", "conversions",
        "time_to_hire_days", "avg_inventory_value", "on_hand_units", "orders_total", "orders_on_time"
    ):
        if concept in concept_to_col and concept_to_col[concept] in df.columns:
            num_cache[concept] = _clean_numeric_series(df[concept_to_col[concept]])

    # Helper for finance P&L categories
    fin_cat = None
    if domain == "finance" and "account_category" in concept_to_col and concept_to_col["account_category"] in df.columns:
        fin_cat = df[concept_to_col["account_category"]].astype(str).str.strip().str.lower()

    for kdef in kpi_defs:
        code = kdef["code"]
        req = kdef.get("required_concepts", [])
        missing = [r for r in req if r not in concept_to_col]
        src_cols = [concept_to_col[r] for r in req if r in concept_to_col]

        if missing:
            results.append({
                "code": code,
                "name": kdef["name"],
                "department": kdef["department"],
                "eligibility_status": "Not Calculable",
                "value": None,
                "formatted_value": "Unavailable",
                "missing_concepts": missing,
                "reason": f"Missing required concept(s): {', '.join(missing)}.",
                "trust_tooltip": {
                    "formula": kdef["formula_expression"],
                    "source_columns": src_cols,
                    "active_filters": filters or {},
                    "excluded_row_count": total_excluded,
                    "calculation_version": kdef.get("calculation_version", "v2.0"),
                    "timestamp": now_iso,
                    "known_limitations": kdef.get("known_limitations", ""),
                },
            })
            continue

        unconfirmed = [r for r in req if r not in confirmed_concepts]
        if not grain_confirmed or unconfirmed:
            eligibility = "Requires Additional Information"
            limitation_note = f"Awaiting confirmation for grain or concept(s): {', '.join(unconfirmed) or 'dataset grain'}."
        else:
            eligibility = "Calculable"
            limitation_note = ""

        # Check null ratio on required columns -> Calculable with Limitations
        null_rows = 0
        for r in req:
            col = concept_to_col[r]
            if col in df.columns:
                null_rows = max(null_rows, int(df[col].isna().sum()))
        if eligibility == "Calculable" and (null_rows > 0 or status_excluded > 0):
            eligibility = "Calculable with Limitations"
            limitation_note = f"Excluded {status_excluded} cancelled row(s) and {null_rows} null value(s)."

        # Deterministic Calculation
        val: Optional[float] = None
        if code == "SALES_TOTAL_REVENUE":
            val = float(num_cache["revenue"].sum())
        elif code == "SALES_DISTINCT_ORDERS":
            val = float(df[concept_to_col["order_id"]].dropna().nunique())
        elif code == "SALES_AOV":
            denom = df[concept_to_col["order_id"]].dropna().nunique()
            val = float(num_cache["revenue"].sum() / denom) if denom > 0 else None
        elif code == "SALES_UNITS_SOLD":
            val = float(num_cache["quantity"].sum())
        elif code == "SALES_ASP":
            denom = float(num_cache["quantity"].sum())
            val = float(num_cache["revenue"].sum() / denom) if denom > 0 else None
        elif code == "SALES_GROSS_PROFIT":
            val = float(num_cache["revenue"].sum() - num_cache["cogs"].sum())
        elif code == "SALES_GROSS_MARGIN_PCT":
            rev = float(num_cache["revenue"].sum())
            gp = rev - float(num_cache["cogs"].sum())
            val = float((gp / rev) * 100.0) if rev != 0 else None
        elif code == "SALES_REPEAT_PURCHASE_RATE":
            grp = df.groupby(concept_to_col["customer_id"])[concept_to_col["order_id"]].nunique()
            val = float(((grp > 1).sum() / len(grp)) * 100.0) if len(grp) > 0 else None
        elif code == "FIN_TOTAL_REVENUE" and fin_cat is not None:
            val = float(num_cache["actual_amount"][fin_cat == "revenue"].sum())
        elif code == "FIN_COGS" and fin_cat is not None:
            val = float(num_cache["actual_amount"][fin_cat == "cogs"].sum())
        elif code == "FIN_OPEX" and fin_cat is not None:
            val = float(num_cache["actual_amount"][fin_cat == "opex"].sum())
        elif code == "FIN_GROSS_PROFIT" and fin_cat is not None:
            rev = float(num_cache["actual_amount"][fin_cat == "revenue"].sum())
            cogs = float(num_cache["actual_amount"][fin_cat == "cogs"].sum())
            val = rev - cogs
        elif code == "FIN_OPERATING_PROFIT" and fin_cat is not None:
            rev = float(num_cache["actual_amount"][fin_cat == "revenue"].sum())
            cogs = float(num_cache["actual_amount"][fin_cat == "cogs"].sum())
            opex = float(num_cache["actual_amount"][fin_cat == "opex"].sum())
            val = rev - cogs - opex
        elif code == "FIN_OPERATING_MARGIN_PCT" and fin_cat is not None:
            rev = float(num_cache["actual_amount"][fin_cat == "revenue"].sum())
            cogs = float(num_cache["actual_amount"][fin_cat == "cogs"].sum())
            opex = float(num_cache["actual_amount"][fin_cat == "opex"].sum())
            val = float(((rev - cogs - opex) / rev) * 100.0) if rev != 0 else None
        elif code == "FIN_BUDGET_VARIANCE_PCT" and fin_cat is not None:
            act_rev = float(num_cache["actual_amount"][fin_cat == "revenue"].sum())
            bud_rev = float(num_cache["budget_amount"][fin_cat == "revenue"].sum())
            val = float(((act_rev - bud_rev) / bud_rev) * 100.0) if bud_rev != 0 else None
        elif code == "MKT_ROAS":
            denom = float(num_cache["marketing_spend"].sum())
            val = float(num_cache["attributed_revenue"].sum() / denom) if denom > 0 else None
        elif code == "MKT_CAC":
            denom = float(num_cache["conversions"].sum())
            val = float(num_cache["marketing_spend"].sum() / denom) if denom > 0 else None
        elif code == "MKT_CTR_PCT":
            denom = float(num_cache["impressions"].sum())
            val = float((num_cache["clicks"].sum() / denom) * 100.0) if denom > 0 else None
        elif code == "HR_HEADCOUNT":
            st = df[concept_to_col["employment_status"]].astype(str).str.lower()
            val = float(df.loc[st == "active", concept_to_col["employee_id"]].nunique())
        elif code == "HR_ATTRITION_PCT":
            st = df[concept_to_col["employment_status"]].astype(str).str.lower()
            tot = df[concept_to_col["employee_id"]].nunique()
            val = float((df.loc[st == "exited", concept_to_col["employee_id"]].nunique() / tot) * 100.0) if tot > 0 else None
        elif code == "HR_AVG_TIME_TO_HIRE":
            val = float(num_cache["time_to_hire_days"].mean())
        elif code == "SC_INVENTORY_TURNOVER":
            denom = float(num_cache["avg_inventory_value"].sum())
            val = float(num_cache["cogs"].sum() / denom) if denom > 0 else None
        elif code == "SC_ON_TIME_DELIVERY_PCT":
            denom = float(num_cache["orders_total"].sum())
            val = float((num_cache["orders_on_time"].sum() / denom) * 100.0) if denom > 0 else None
        elif code == "SC_STOCKOUT_RATE_PCT":
            tot = len(df)
            val = float(((num_cache["on_hand_units"] == 0).sum() / tot) * 100.0) if tot > 0 else None

        rounded_val = round(val, 2) if val is not None else None
        results.append({
            "code": code,
            "name": kdef["name"],
            "department": kdef["department"],
            "business_meaning": kdef.get("business_meaning", ""),
            "eligibility_status": eligibility,
            "value": rounded_val,
            "formatted_value": _format_value(rounded_val, kdef.get("unit_format", "number"), currency),
            "missing_concepts": [],
            "reason": limitation_note or "All prerequisites verified.",
            "trust_tooltip": {
                "formula": kdef["formula_expression"],
                "source_columns": src_cols,
                "active_filters": filters or {},
                "excluded_row_count": total_excluded,
                "calculation_version": kdef.get("calculation_version", "v2.0"),
                "timestamp": now_iso,
                "known_limitations": kdef.get("known_limitations", ""),
            },
        })

    return {
        "domain": domain,
        "engine": "duckdb" if HAS_DUCKDB else "pyarrow_pandas_deterministic",
        "rows_evaluated": int(len(df)),
        "excluded_rows": total_excluded,
        "kpis": results,
    }


def compute_dashboard_analytics(
    parquet_path: str,
    domain: str,
    mappings: List[Dict[str, Any]],
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synchronized cross-filtered dashboard payload:
    - Time-series trend + MoM growth
    - Dimensional breakdowns (Region, Channel, Product Category / Account Category)
    - Pareto 80/20 Concentration
    - Revenue Variance Waterfall (first half vs second half period decomposition by region/category)
    - Available slicer values
    """
    concept_to_col = {m["canonical_concept"]: m["source_column"] for m in mappings if m.get("canonical_concept") != "unmapped"}
    df_full = pd.read_parquet(parquet_path, engine="pyarrow")
    df, excluded = load_parquet_filtered(parquet_path, concept_to_col, filters)

    if domain == "sales" and "order_status" in concept_to_col and concept_to_col["order_status"] in df.columns:
        df = df[~df[concept_to_col["order_status"]].astype(str).str.lower().isin({"cancelled", "canceled", "void"})].reset_index(drop=True)

    # Slicer options from full dataset
    slicers: Dict[str, List[str]] = {}
    for dim in ("region", "channel", "product_category", "account_category", "department"):
        if dim in concept_to_col and concept_to_col[dim] in df_full.columns:
            slicers[dim] = sorted(df_full[concept_to_col[dim]].dropna().astype(str).unique().tolist())

    metric_concept = "revenue" if domain == "sales" else "actual_amount"
    date_concept = "order_date" if "order_date" in concept_to_col else "period_date"

    trend: List[Dict[str, Any]] = []
    if metric_concept in concept_to_col and date_concept in concept_to_col:
        mcol = concept_to_col[metric_concept]
        dcol = concept_to_col[date_concept]
        tmp = df.copy()
        tmp["_val"] = _clean_numeric_series(tmp[mcol])
        if domain == "finance" and "account_category" in concept_to_col:
            cat_col = concept_to_col["account_category"]
            tmp = tmp[tmp[cat_col].astype(str).str.lower() == "revenue"]
        tmp["_dt"] = pd.to_datetime(tmp[dcol], errors="coerce", format="mixed")
        tmp = tmp.dropna(subset=["_dt", "_val"])
        if not tmp.empty:
            tmp["_month"] = tmp["_dt"].dt.to_period("M").astype(str)
            monthly = tmp.groupby("_month")["_val"].sum().sort_index()
            prev = None
            for m, v in monthly.items():
                mom = round(((v - prev) / prev) * 100.0, 2) if prev and prev != 0 else None
                trend.append({"period": m, "value": round(float(v), 2), "mom_growth_pct": mom})
                prev = float(v)

    breakdowns: Dict[str, List[Dict[str, Any]]] = {}
    if metric_concept in concept_to_col:
        mcol = concept_to_col[metric_concept]
        vals = _clean_numeric_series(df[mcol])
        for dim in ("region", "channel", "product_category", "account_category", "account_name"):
            if dim in concept_to_col and concept_to_col[dim] in df.columns:
                grp = pd.DataFrame({"dim": df[concept_to_col[dim]].astype(str), "val": vals}).groupby("dim")["val"].sum().sort_values(ascending=False)
                breakdowns[dim] = [{"name": str(k), "value": round(float(v), 2)} for k, v in grp.items()]

    # Pareto 80/20 Concentration (by customer_id or product_name)
    pareto: List[Dict[str, Any]] = []
    pareto_dim = "customer_id" if "customer_id" in concept_to_col else ("product_name" if "product_name" in concept_to_col else None)
    if pareto_dim and metric_concept in concept_to_col:
        pcol = concept_to_col[pareto_dim]
        vals = _clean_numeric_series(df[concept_to_col[metric_concept]])
        grp = pd.DataFrame({"entity": df[pcol].astype(str), "val": vals}).groupby("entity")["val"].sum().sort_values(ascending=False)
        total = float(grp.sum())
        cum = 0.0
        for idx, (ent, v) in enumerate(grp.head(15).items(), start=1):
            cum += float(v)
            pareto.append({
                "rank": idx,
                "entity": str(ent),
                "value": round(float(v), 2),
                "cumulative_pct": round((cum / total) * 100.0, 2) if total > 0 else 0.0,
            })

    # Revenue Variance Waterfall (First half vs Second half of months decomposed by region or category)
    waterfall: List[Dict[str, Any]] = []
    wf_dim = "region" if "region" in concept_to_col else ("account_category" if "account_category" in concept_to_col else None)
    if wf_dim and metric_concept in concept_to_col and date_concept in concept_to_col:
        tmp = df.copy()
        tmp["_val"] = _clean_numeric_series(tmp[concept_to_col[metric_concept]])
        tmp["_dt"] = pd.to_datetime(tmp[concept_to_col[date_concept]], errors="coerce", format="mixed")
        tmp = tmp.dropna(subset=["_dt", "_val"])
        if len(tmp) >= 4:
            mid = tmp["_dt"].median()
            p1 = tmp[tmp["_dt"] <= mid]
            p2 = tmp[tmp["_dt"] > mid]
            base_total = round(float(p1["_val"].sum()), 2)
            end_total = round(float(p2["_val"].sum()), 2)
            waterfall.append({"label": "Prior Half Baseline", "delta": base_total, "type": "total"})
            dcol = concept_to_col[wf_dim]
            g1 = p1.groupby(dcol)["_val"].sum()
            g2 = p2.groupby(dcol)["_val"].sum()
            for key in sorted(set(g1.index) | set(g2.index)):
                delta = round(float(g2.get(key, 0.0) - g1.get(key, 0.0)), 2)
                waterfall.append({"label": str(key), "delta": delta, "type": "positive" if delta >= 0 else "negative"})
            waterfall.append({"label": "Current Half Total", "delta": end_total, "type": "total"})

    # Price / Volume / Mix Revenue Variance Waterfall (marks Requires Additional Information if qty/price missing)
    pvm_waterfall: Dict[str, Any] = {
        "status": "Requires Additional Information",
        "reason": "Requires revenue, quantity, unit_price, and date columns for Price/Volume/Mix decomposition.",
        "steps": [],
    }
    if all(k in concept_to_col for k in ("revenue", "quantity", "unit_price")) and date_concept in concept_to_col:
        tmp_pvm = df.copy()
        tmp_pvm["_rev"] = _clean_numeric_series(tmp_pvm[concept_to_col["revenue"]])
        tmp_pvm["_qty"] = _clean_numeric_series(tmp_pvm[concept_to_col["quantity"]])
        tmp_pvm["_dt"] = pd.to_datetime(tmp_pvm[concept_to_col[date_concept]], errors="coerce", format="mixed")
        tmp_pvm = tmp_pvm.dropna(subset=["_dt", "_rev", "_qty"])
        if len(tmp_pvm) >= 4:
            mid = tmp_pvm["_dt"].median()
            h1 = tmp_pvm[tmp_pvm["_dt"] <= mid]
            h2 = tmp_pvm[tmp_pvm["_dt"] > mid]
            q1, q2 = float(h1["_qty"].sum()), float(h2["_qty"].sum())
            r1, r2 = float(h1["_rev"].sum()), float(h2["_rev"].sum())
            if q1 > 0 and q2 > 0:
                p1, p2 = r1 / q1, r2 / q2
                vol_eff = round((q2 - q1) * p1, 2)
                price_eff = round((p2 - p1) * q1, 2)
                mix_eff = round((r2 - r1) - vol_eff - price_eff, 2)
                pvm_waterfall = {
                    "status": "Calculable",
                    "reason": "Decomposed first-half vs second-half revenue shift into Volume, Price, and Mix effects.",
                    "steps": [
                        {"label": "Prior Half Revenue", "delta": round(r1, 2), "type": "total"},
                        {"label": "Volume Effect", "delta": vol_eff, "type": "positive" if vol_eff >= 0 else "negative"},
                        {"label": "Price Effect", "delta": price_eff, "type": "positive" if price_eff >= 0 else "negative"},
                        {"label": "Mix / Interaction", "delta": mix_eff, "type": "positive" if mix_eff >= 0 else "negative"},
                        {"label": "Current Half Revenue", "delta": round(r2, 2), "type": "total"},
                    ],
                }

    # Sortable table preview (top 50 filtered rows)
    table_cols = list(df.columns)[:10]
    table_rows = df[table_cols].head(50).fillna("").astype(str).to_dict(orient="records")

    return {
        "rows_evaluated": int(len(df)),
        "excluded_rows": excluded,
        "slicers": slicers,
        "trend": trend,
        "breakdowns": breakdowns,
        "pareto": pareto,
        "variance_waterfall": waterfall,
        "pvm_waterfall": pvm_waterfall,
        "table_columns": table_cols,
        "table_rows": table_rows,
    }


def prioritize_insights(kpi_payload: Dict[str, Any], dash_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic Insight Prioritization Engine & Auto-Generated Weekly Executive Brief.
    Ranks findings by Financial Impact, Risk Severity, Confidence, and Urgency.
    """
    findings: List[Dict[str, Any]] = []
    kpi_map = {k["code"]: k for k in kpi_payload.get("kpis", [])}

    # Check Gross Margin or Operating Margin
    gm = kpi_map.get("SALES_GROSS_MARGIN_PCT") or kpi_map.get("FIN_OPERATING_MARGIN_PCT")
    if gm and gm.get("value") is not None:
        v = gm["value"]
        findings.append({
            "category": "Risk" if v < 35 else "Opportunity",
            "title": f"{gm['name']} stands at {v:.2f}%",
            "metric_code": gm["code"],
            "verified_value": gm["formatted_value"],
            "priority_score": 92.0 if v < 35 else 78.0,
            "impact": "Margin directly governs cash generation and pricing headroom.",
            "action": "Audit discount bands and top-COGS categories before next fiscal cycle.",
        })

    # Check Pareto concentration
    pareto = dash_payload.get("pareto", [])
    if len(pareto) >= 5:
        top5_pct = pareto[4]["cumulative_pct"]
        findings.append({
            "category": "Risk" if top5_pct >= 30 else "Change",
            "title": f"Top 5 entities drive {top5_pct:.1f}% of total revenue",
            "metric_code": "PARETO_80_20",
            "verified_value": f"{top5_pct:.1f}%",
            "priority_score": 88.0 if top5_pct >= 30 else 72.0,
            "impact": "High revenue concentration increases churn sensitivity.",
            "action": "Review retention SLAs for top accounts and diversify mid-market pipeline.",
        })

    # Check MoM Growth
    trend = dash_payload.get("trend", [])
    if len(trend) >= 2 and trend[-1].get("mom_growth_pct") is not None:
        mom = trend[-1]["mom_growth_pct"]
        findings.append({
            "category": "Change",
            "title": f"Latest month ({trend[-1]['period']}) moved {mom:+.2f}% MoM",
            "metric_code": "MOM_GROWTH",
            "verified_value": f"{mom:+.2f}%",
            "priority_score": 85.0,
            "impact": "Momentum shift across the most recent reporting period.",
            "action": "Inspect regional and product variance waterfall drivers.",
        })

    # Check Not Calculable KPIs
    missing_kpis = [k for k in kpi_payload.get("kpis", []) if k["eligibility_status"] == "Not Calculable"]
    if missing_kpis:
        findings.append({
            "category": "Risk",
            "title": f"{len(missing_kpis)} KPI(s) unavailable due to missing columns",
            "metric_code": missing_kpis[0]["code"],
            "verified_value": "Unavailable",
            "priority_score": 82.0,
            "impact": "Incomplete source data restricts full profitability visibility.",
            "action": f"Upload missing concepts: {', '.join(missing_kpis[0]['missing_concepts'])}.",
        })

    findings.sort(key=lambda x: x["priority_score"], reverse=True)
    return {
        "ranked_findings": findings,
        "weekly_brief": {
            "top_changes": [f for f in findings if f["category"] == "Change"][:3],
            "top_risks": [f for f in findings if f["category"] == "Risk"][:3],
            "top_opportunities": [f for f in findings if f["category"] == "Opportunity"][:3],
        },
    }


def run_what_if_simulation(
    baseline_revenue: float,
    baseline_cogs: float,
    baseline_opex: float,
    price_change_pct: float = 0.0,
    volume_change_pct: float = 0.0,
    cogs_change_pct: float = 0.0,
    opex_change_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Phase 2 Transparent Formula-Driven What-If Simulator.
    Strictly separates Historical Actuals, User Assumptions, and Scenario Outputs.
    """
    sim_rev = baseline_revenue * (1.0 + price_change_pct / 100.0) * (1.0 + volume_change_pct / 100.0)
    sim_cogs = baseline_cogs * (1.0 + volume_change_pct / 100.0) * (1.0 + cogs_change_pct / 100.0)
    sim_opex = baseline_opex * (1.0 + opex_change_pct / 100.0)
    base_gp = baseline_revenue - baseline_cogs
    sim_gp = sim_rev - sim_cogs
    base_op = base_gp - baseline_opex
    sim_op = sim_gp - sim_opex

    return {
        "disclaimer": "Deterministic arithmetic sensitivity model (not predictive AI).",
        "historical_actuals": {
            "revenue": round(baseline_revenue, 2),
            "cogs": round(baseline_cogs, 2),
            "opex": round(baseline_opex, 2),
            "gross_profit": round(base_gp, 2),
            "operating_profit": round(base_op, 2),
            "gross_margin_pct": round((base_gp / baseline_revenue) * 100.0, 2) if baseline_revenue else 0.0,
        },
        "user_assumptions": {
            "price_change_pct": price_change_pct,
            "volume_change_pct": volume_change_pct,
            "cogs_change_pct": cogs_change_pct,
            "opex_change_pct": opex_change_pct,
        },
        "scenario_outputs": {
            "revenue": round(sim_rev, 2),
            "cogs": round(sim_cogs, 2),
            "opex": round(sim_opex, 2),
            "gross_profit": round(sim_gp, 2),
            "operating_profit": round(sim_op, 2),
            "gross_margin_pct": round((sim_gp / sim_rev) * 100.0, 2) if sim_rev else 0.0,
            "net_profit_delta": round(sim_op - base_op, 2),
        },
    }
