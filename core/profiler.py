"""
Stage B, C & F — Automated Profiling, Business Context & Grain Discovery,
and 7-Dimension Multidimensional Data Quality Engine (ADR-04).
Phase 1 Upgrade: Full mixed-currency detection for BOTH symbols (₹, $, €, £)
AND ISO currency codes (INR, USD, EUR, GBP) within a single column.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

CURRENCY_PATTERNS = {
    "INR": re.compile(r"(?:₹|\bINR\b|\bRs\.?\b)", re.IGNORECASE),
    "USD": re.compile(r"(?:\$|\bUSD\b)", re.IGNORECASE),
    "EUR": re.compile(r"(?:€|\bEUR\b)", re.IGNORECASE),
    "GBP": re.compile(r"(?:£|\bGBP\b)", re.IGNORECASE),
}
EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
PHONE_RE = re.compile(r"^\+?\d[\d\s\-]{8,14}\d$")


def detect_currencies_in_series(series: pd.Series) -> List[str]:
    """Detect all currency symbols and ISO codes (₹, $, €, £, INR, USD, EUR, GBP) in a column."""
    if pd.api.types.is_numeric_dtype(series):
        return []
    sample = series.dropna().astype(str).head(1000)
    found = set()
    for code, pat in CURRENCY_PATTERNS.items():
        if sample.str.contains(pat, regex=True).any():
            found.add(code)
    return sorted(found)


def _try_numeric(series: pd.Series) -> Tuple[pd.Series, int]:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce"), 0
    cleaned = (
        series.astype(str)
        .str.replace(r"(₹|\$|€|£|\bINR\b|\bUSD\b|\bEUR\b|\bGBP\b|\bRs\.?\b|,|\s)", "", regex=True)
        .replace({"": np.nan, "nan": np.nan, "None": np.nan, "N/A": np.nan, "null": np.nan})
    )
    parsed = pd.to_numeric(cleaned, errors="coerce")
    non_null_orig = series.notna().sum()
    invalid_count = int(non_null_orig - parsed.notna().sum())
    return parsed, max(invalid_count, 0)


def _try_datetime(series: pd.Series) -> Tuple[pd.Series, int]:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series, 0
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    non_null_orig = series.notna().sum()
    invalid_count = int(non_null_orig - parsed.notna().sum())
    return parsed, max(invalid_count, 0)


def profile_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """Stage B & C: Inspect schema, stats, outliers, PII flags, grain, and business entities."""
    n_rows = int(len(df))
    n_cols = int(len(df.columns))
    exact_duplicates = int(df.duplicated().sum()) if n_rows > 0 else 0

    if n_rows > 0 and n_rows <= 50_000:
        norm_df = df.copy()
        for c in norm_df.select_dtypes(include=["object", "string"]).columns:
            norm_df[c] = norm_df[c].astype(str).str.strip().str.lower()
        near_duplicates = max(int(norm_df.duplicated().sum()) - exact_duplicates, 0)
    else:
        near_duplicates = 0

    columns_profile: List[Dict[str, Any]] = []
    candidate_pks: List[str] = []
    date_ranges: Dict[str, Dict[str, str]] = {}
    detected_currencies: set = set()
    mixed_currency_cols: List[str] = []
    invalid_date_cols: List[str] = []
    outlier_cols: List[Dict[str, Any]] = []

    for col in df.columns:
        s = df[col]
        null_count = int(s.isna().sum())
        null_pct = round((null_count / n_rows) * 100.0, 2) if n_rows > 0 else 0.0
        distinct_count = int(s.nunique(dropna=True))
        uniqueness_ratio = round(distinct_count / max(n_rows - null_count, 1), 4)

        col_lower = col.lower()
        currencies = detect_currencies_in_series(s)
        if currencies:
            detected_currencies.update(currencies)
        if len(currencies) > 1:
            mixed_currency_cols.append(col)

        inferred_dtype = "categorical"
        stats: Dict[str, Any] = {}
        is_date_hint = any(k in col_lower for k in ("date", "dt", "period", "month", "time"))
        if pd.api.types.is_numeric_dtype(s):
            inferred_dtype = "numeric"
            num_s = pd.to_numeric(s, errors="coerce").dropna()
        else:
            num_parsed, num_invalid = _try_numeric(s)
            valid_num_ratio = num_parsed.notna().sum() / max(s.notna().sum(), 1)
            if valid_num_ratio >= 0.70 and not is_date_hint:
                inferred_dtype = "numeric_dirty" if (num_invalid > 0 or currencies) else "numeric"
                num_s = num_parsed.dropna()
            elif is_date_hint:
                dt_parsed, dt_invalid = _try_datetime(s)
                if dt_parsed.notna().sum() / max(s.notna().sum(), 1) >= 0.50:
                    inferred_dtype = "date"
                    if dt_invalid > 0:
                        invalid_date_cols.append(col)
                    valid_dt = dt_parsed.dropna()
                    if not valid_dt.empty:
                        date_ranges[col] = {
                            "min": valid_dt.min().strftime("%Y-%m-%d"),
                            "max": valid_dt.max().strftime("%Y-%m-%d"),
                        }
                        stats["min_date"] = date_ranges[col]["min"]
                        stats["max_date"] = date_ranges[col]["max"]
                        stats["invalid_dates"] = dt_invalid
                num_s = pd.Series(dtype=float)
            else:
                num_s = pd.Series(dtype=float)

        if inferred_dtype in ("numeric", "numeric_dirty") and not num_s.empty:
            q1 = float(num_s.quantile(0.25))
            q3 = float(num_s.quantile(0.75))
            iqr = q3 - q1
            outliers = int(((num_s < q1 - 3.0 * iqr) | (num_s > q3 + 3.0 * iqr)).sum()) if iqr > 0 else 0
            stats.update({
                "min": round(float(num_s.min()), 2),
                "max": round(float(num_s.max()), 2),
                "mean": round(float(num_s.mean()), 2),
                "median": round(float(num_s.median()), 2),
                "negative_count": int((num_s < 0).sum()),
                "outlier_count": outliers,
            })
            if outliers > 0:
                outlier_cols.append({"column": col, "outlier_count": outliers, "max": stats["max"]})

        sample_vals = [str(v) for v in s.dropna().head(50).tolist()]
        pii_flag = any(k in col_lower for k in ("email", "phone", "mobile", "salary", "ssn", "pan", "aadhaar")) or any(
            EMAIL_RE.match(v) or PHONE_RE.match(v) for v in sample_vals[:15]
        )

        if uniqueness_ratio >= 0.99 and null_count == 0 and n_rows > 0:
            candidate_pks.append(col)

        columns_profile.append({
            "name": col,
            "inferred_dtype": inferred_dtype,
            "null_count": null_count,
            "null_pct": null_pct,
            "distinct_count": distinct_count,
            "uniqueness_ratio": uniqueness_ratio,
            "currencies_detected": currencies,
            "pii_flag": pii_flag,
            "sample_values": [str(v)[:60] for v in s.dropna().head(5).tolist()],
            "stats": stats,
        })

    cols_lower = [c.lower() for c in df.columns]
    domain = "sales"
    if any("account_category" in c or "budget" in c or "opex" in c for c in cols_lower):
        domain = "finance"
    elif any("impressions" in c or "clicks" in c or "campaign" in c for c in cols_lower):
        domain = "marketing"
    elif any("employee" in c or "salary" in c or "hire_date" in c for c in cols_lower):
        domain = "hr"
    elif any("sku" in c or "warehouse" in c or "lead_time" in c for c in cols_lower):
        domain = "supply_chain"

    detected_grain = "unknown"
    grain_confidence = 0.65
    grain_reason = "Requires human confirmation."
    if domain == "finance":
        detected_grain = "ledger_entry"
        grain_confidence = 0.88
        grain_reason = "Each row represents a period-level financial account entry."
    elif domain == "sales":
        order_col = next((c for c in df.columns if ("order" in c.lower() and "id" in c.lower()) or "ord_ref" in c.lower()), None)
        if order_col:
            ratio = df[order_col].nunique(dropna=True) / max(n_rows, 1)
            if ratio < 0.95:
                detected_grain = "line_item"
                grain_confidence = 0.92
                grain_reason = f"Multiple rows share '{order_col}' ({df[order_col].nunique():,} unique orders across {n_rows:,} rows). Distinct order counting prevents AOV inflation."
            else:
                detected_grain = "order"
                grain_confidence = 0.90
                grain_reason = f"'{order_col}' is nearly unique per row ({ratio:.1%})."
    elif domain == "hr":
        detected_grain = "employee_record"
        grain_confidence = 0.90
        grain_reason = "Each row represents an individual employee record."
    elif domain == "marketing":
        detected_grain = "campaign_period"
        grain_confidence = 0.85
        grain_reason = "Each row represents a campaign performance period."
    elif domain == "supply_chain":
        detected_grain = "sku_record"
        grain_confidence = 0.85
        grain_reason = "Each row represents a SKU/supplier inventory record."

    return {
        "row_count": n_rows,
        "column_count": n_cols,
        "exact_duplicates": exact_duplicates,
        "near_duplicates": near_duplicates,
        "candidate_primary_keys": candidate_pks,
        "date_ranges": date_ranges,
        "detected_currencies": sorted(detected_currencies) or ["INR"],
        "mixed_currency_columns": mixed_currency_cols,
        "invalid_date_columns": invalid_date_cols,
        "outlier_columns": outlier_cols,
        "domain_guess": domain,
        "grain_discovery": {
            "detected_grain": detected_grain,
            "confidence": grain_confidence,
            "reason": grain_reason,
            "requires_confirmation": True,
        },
        "columns": columns_profile,
    }


def evaluate_data_quality(
    df: pd.DataFrame,
    profile: Dict[str, Any],
    flagged_total_rows: Optional[List[Dict[str, Any]]] = None,
    referential_integrity_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Stage F — 7-Dimension Multidimensional Data Quality Engine (ADR-04)."""
    n_rows = max(profile["row_count"], 1)
    n_cols = max(profile["column_count"], 1)
    flagged_total_rows = flagged_total_rows or []

    total_cells = n_rows * n_cols
    missing_cells = sum(c["null_count"] for c in profile["columns"])
    completeness = round(max(0.0, (1.0 - missing_cells / max(total_cells, 1)) * 100.0), 2)
    high_missing_cols = [c["name"] for c in profile["columns"] if c["null_pct"] >= 15.0]
    comp_sev = "Critical Blocker" if completeness < 70 else ("Warning" if high_missing_cols else "Info")

    dup_total = profile["exact_duplicates"] + profile["near_duplicates"]
    uniqueness = round(max(0.0, (1.0 - dup_total / n_rows) * 100.0), 2)
    uniq_sev = "Critical Blocker" if profile["exact_duplicates"] / n_rows > 0.10 else ("Warning" if dup_total > 0 else "Info")

    dirty_cols = [c["name"] for c in profile["columns"] if c["inferred_dtype"] == "numeric_dirty"] + profile["invalid_date_columns"]
    validity = round(max(0.0, 100.0 - len(dirty_cols) * 18.0), 2)
    val_sev = "Critical Blocker" if profile["mixed_currency_columns"] or profile["invalid_date_columns"] else ("Warning" if dirty_cols else "Info")

    consistency = 100.0
    cons_affected: List[str] = []
    if profile["mixed_currency_columns"]:
        consistency -= 45.0
        cons_affected.extend(profile["mixed_currency_columns"])
    if profile["near_duplicates"] > 0:
        consistency -= 15.0
    if flagged_total_rows:
        consistency -= 15.0
    consistency = round(max(0.0, consistency), 2)
    cons_sev = "Critical Blocker" if profile["mixed_currency_columns"] else ("Warning" if (flagged_total_rows or profile["near_duplicates"] > 0) else "Info")

    timeliness = 95.0 if profile["date_ranges"] else 75.0
    time_sev = "Info" if profile["date_ranges"] else "Warning"

    ref_score = 100.0 if referential_integrity_score is None else round(referential_integrity_score, 2)
    ref_sev = "Critical Blocker" if ref_score < 70 else ("Warning" if ref_score < 95 else "Info")

    rule_issues: List[str] = []
    rule_affected: List[str] = []
    for c in profile["columns"]:
        cname = c["name"].lower()
        neg_cnt = c["stats"].get("negative_count", 0)
        if neg_cnt > 0 and any(k in cname for k in ("qty", "quantity", "unit_price")):
            rule_issues.append(f"{neg_cnt} negative value(s) in '{c['name']}'")
            rule_affected.append(c["name"])
        if c["stats"].get("outlier_count", 0) > 0 and any(k in cname for k in ("rev", "amount", "sales")):
            rule_issues.append(f"{c['stats']['outlier_count']} extreme IQR outlier(s) in '{c['name']}'")
            rule_affected.append(c["name"])
    biz_score = round(max(0.0, 100.0 - len(rule_issues) * 15.0), 2)
    biz_sev = "Warning" if rule_issues else "Info"

    dimensions = [
        {"dimension": "Completeness", "score": completeness, "severity": comp_sev, "affected_columns": high_missing_cols, "remediation": "Impute or exclude incomplete rows; verify missing columns before publishing KPIs." if high_missing_cols else "Completeness is healthy."},
        {"dimension": "Uniqueness", "score": uniqueness, "severity": uniq_sev, "affected_columns": profile["candidate_primary_keys"] or [], "remediation": f"Found {profile['exact_duplicates']} exact and {profile['near_duplicates']} near-duplicate rows; deduplicate before aggregation." if dup_total > 0 else "No duplicate rows detected."},
        {"dimension": "Validity", "score": validity, "severity": val_sev, "affected_columns": sorted(set(dirty_cols)), "remediation": "Standardize malformed dates and strip non-numeric text from financial columns." if dirty_cols else "All inferred types parsed cleanly."},
        {"dimension": "Consistency", "score": consistency, "severity": cons_sev, "affected_columns": sorted(set(cons_affected)), "remediation": "Mixed currency symbols/codes detected—normalize to a single reporting currency." if profile["mixed_currency_columns"] else ("Bottom Grand Total row excluded automatically to prevent double-counting." if flagged_total_rows else "Formatting and currency signals are consistent.")},
        {"dimension": "Timeliness", "score": timeliness, "severity": time_sev, "affected_columns": list(profile["date_ranges"].keys()), "remediation": "Date range verified for fiscal/calendar trending." if profile["date_ranges"] else "No date column detected; period-over-period growth unavailable."},
        {"dimension": "Referential Integrity", "score": ref_score, "severity": ref_sev, "affected_columns": [], "remediation": "Single-table upload; run Relationship Validator when joining multiple tables." if referential_integrity_score is None else "Review orphan/duplicate join keys."},
        {"dimension": "Business-Rule Compliance", "score": biz_score, "severity": biz_sev, "affected_columns": sorted(set(rule_affected)), "remediation": "; ".join(rule_issues) if rule_issues else "No business-rule anomalies detected."},
    ]

    critical_blockers = [d for d in dimensions if d["severity"] == "Critical Blocker"]
    overall = round(sum(d["score"] for d in dimensions) / len(dimensions), 2)

    return {
        "overall_score": overall,
        "has_critical_blockers": len(critical_blockers) > 0,
        "critical_blockers": [{"dimension": b["dimension"], "affected_columns": b["affected_columns"], "remediation": b["remediation"]} for b in critical_blockers],
        "flagged_total_rows": flagged_total_rows,
        "dimensions": dimensions,
    }
