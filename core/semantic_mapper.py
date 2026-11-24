"""
Stage D — 3-Tier Hybrid Semantic Mapping & Per-Org Saved Schema Memory
Stage E — Phase 2 Dataset Relationship & Join Safety Validator (Fan-Out Protection).
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

CRITICAL_CONCEPTS = {
    "revenue", "cogs", "order_date", "order_id", "period_date",
    "actual_amount", "budget_amount", "account_category",
}

# Tier 1: Deterministic synonym dictionary + regex rules
TIER1_RULES: Dict[str, List[str]] = {
    "order_id": [r"^order[_\s]?id$", r"^ord[_\s]?(ref|no|num|id)", r"^invoice[_\s]?(no|id)$"],
    "line_id": [r"^line[_\s]?id$", r"^ln[_\s]?seq$", r"^row[_\s]?id$"],
    "order_date": [r"^order[_\s]?date$", r"^txn[_\s]?dt$", r"^sale[_\s]?date$", r"^invoice[_\s]?date$"],
    "period_date": [r"^period[_\s]?date$", r"^fiscal[_\s]?date$", r"^month[_\s]?date$", r"^reporting[_\s]?date$"],
    "customer_id": [r"^cust(omer)?[_\s]?id$", r"^acct[_\s]?id$", r"^client[_\s]?id$"],
    "region": [r"^region$", r"^geo[_\s]?zone$", r"^territory$", r"^area$"],
    "channel": [r"^channel$", r"^sls[_\s]?chnl$", r"^sales[_\s]?channel$"],
    "product_category": [r"^prod(uct)?[_\s]?(cat(egory)?|grp|group)$", r"^category$"],
    "product_name": [r"^prod(uct)?[_\s]?name$", r"^item[_\s]?desc(ription)?$", r"^sku[_\s]?name$"],
    "quantity": [r"^qty([_\s]?sold)?$", r"^quantity$", r"^units([_\s]?sold)?$"],
    "unit_price": [r"^unit[_\s]?price$", r"^list[_\s]?px$", r"^selling[_\s]?price$"],
    "discount_amount": [r"^disc(ount)?[_\s]?(amt|amount|val)$"],
    "revenue": [r"^(net[_\s]?)?rev(enue)?([_\s]?amt)?$", r"^sales([_\s]?amt)?$", r"^total[_\s]?sales$"],
    "cogs": [r"^cogs$", r"^dir(ect)?[_\s]?cost([_\s]?val)?$", r"^cost[_\s]?of[_\s]?goods$"],
    "order_status": [r"^order[_\s]?status$", r"^sts[_\s]?flg$", r"^status$"],
    "account_name": [r"^account[_\s]?name$", r"^gl[_\s]?account$"],
    "account_category": [r"^account[_\s]?cat(egory)?$", r"^pnl[_\s]?cat(egory)?$"],
    "budget_amount": [r"^budget([_\s]?amount)?$", r"^plan[_\s]?amt$"],
    "actual_amount": [r"^actual([_\s]?amount)?$", r"^realized[_\s]?amt$"],
    "department": [r"^dept$", r"^department$"],
    "marketing_spend": [r"^marketing[_\s]?spend$", r"^ad[_\s]?spend$"],
    "attributed_revenue": [r"^attributed[_\s]?revenue$"],
    "impressions": [r"^impressions$"],
    "clicks": [r"^clicks$"],
    "conversions": [r"^conversions$"],
    "employee_id": [r"^emp(loyee)?[_\s]?id$"],
    "employment_status": [r"^employment[_\s]?status$"],
    "annual_salary": [r"^annual[_\s]?salary$", r"^salary$", r"^ctc$"],
    "time_to_hire_days": [r"^time[_\s]?to[_\s]?hire([_\s]?days)?$"],
    "sku_id": [r"^sku[_\s]?id$"],
    "avg_inventory_value": [r"^avg[_\s]?inventory[_\s]?value$"],
    "on_hand_units": [r"^on[_\s]?hand[_\s]?units$"],
    "orders_total": [r"^orders[_\s]?total$"],
    "orders_on_time": [r"^orders[_\s]?on[_\s]?time$"],
}


def compute_schema_signature(columns: List[str]) -> str:
    """Deterministic SHA-256 signature of normalized column names for per-org saved memory."""
    norm = "|".join(sorted(c.strip().lower() for c in columns))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]


def _tier1_match(col_name: str, col_profile: Dict[str, Any]) -> Tuple[Optional[str], float, str]:
    norm = col_name.strip().lower()
    for concept, patterns in TIER1_RULES.items():
        for idx, pat in enumerate(patterns):
            if re.match(pat, norm):
                conf = 0.96 if idx == 0 else 0.84
                return concept, conf, f"Matched deterministic rule '{pat}' for '{concept}'."
    # Data-shape heuristic fallback for unresolved cryptic headers
    dtype = col_profile.get("inferred_dtype", "")
    if dtype == "date":
        return "order_date", 0.72, "Inferred as date column from parsed date values."
    return None, 0.0, "No Tier-1 rule matched."


def propose_semantic_mappings(
    profile: Dict[str, Any],
    saved_memory: Optional[Dict[str, str]] = None,
    llm_classifier: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Execute 3-Tier Hybrid Semantic Mapping:
    - Check per-org saved schema memory first.
    - Run Tier 1 deterministic rules.
    - Route unresolved or <0.85 confidence columns to Tier 2 metadata-only AI classifier (if available).
    - Mark Tier 3 mandatory human confirmation for any column <0.85 confidence OR critical financial/date/ID concepts.
    """
    columns = profile.get("columns", [])
    col_names = [c["name"] for c in columns]
    signature = compute_schema_signature(col_names)
    saved_memory = saved_memory or {}

    proposals: List[Dict[str, Any]] = []
    for col in columns:
        cname = col["name"]
        if cname in saved_memory:
            concept = saved_memory[cname]
            proposals.append({
                "source_column": cname,
                "canonical_concept": concept,
                "confidence": 0.99,
                "mapping_tier": "tier3_saved_memory",
                "reason": "Reused previously confirmed organizational schema mapping.",
                "alternatives": [],
                "sample_values": col.get("sample_values", [])[:5],
                "requires_human_confirmation": False,
                "confirmed_by_human": True,
            })
            continue

        concept, conf, reason = _tier1_match(cname, col)
        tier = "tier1_rule" if concept else "unmapped"
        alternatives: List[str] = []

        if (concept is None or conf < 0.85) and llm_classifier is not None:
            ai_res = llm_classifier.classify_column_metadata(
                column_name=cname,
                dtype=col.get("inferred_dtype", "unknown"),
                stats=col.get("stats", {}),
                sample_values=col.get("sample_values", [])[:5],
            )
            if ai_res and ai_res.get("canonical_concept"):
                concept = ai_res["canonical_concept"]
                conf = float(ai_res.get("confidence", 0.78))
                reason = ai_res.get("reason", "Classified via metadata-only AI semantic classifier.")
                alternatives = ai_res.get("alternatives", [])
                tier = "tier2_ai"

        requires_confirm = (conf < 0.85) or (concept in CRITICAL_CONCEPTS) or (concept is None)
        proposals.append({
            "source_column": cname,
            "canonical_concept": concept or "unmapped",
            "confidence": round(conf, 3),
            "mapping_tier": tier,
            "reason": reason,
            "alternatives": alternatives,
            "sample_values": col.get("sample_values", [])[:5],
            "requires_human_confirmation": requires_confirm,
            "confirmed_by_human": False,
        })

    pending_confirmations = [p["source_column"] for p in proposals if p["requires_human_confirmation"]]
    return {
        "schema_signature": signature,
        "grain_discovery": profile.get("grain_discovery", {}),
        "proposals": proposals,
        "pending_confirmation_count": len(pending_confirmations),
        "pending_confirmation_columns": pending_confirmations,
    }


def validate_dataset_relationship(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_key: str,
    right_key: str,
) -> Dict[str, Any]:
    """
    Stage E — Phase 2 Relationship & Join Safety Validator.
    Profiles key overlap, duplicate keys, orphan records, cardinality (1:1, 1:N, N:1, M:N),
    and accidental row multiplication (fan-out) — blocking unsafe M:N joins automatically.
    """
    if left_key not in left_df.columns or right_key not in right_df.columns:
        raise ValueError(f"Join key missing: left='{left_key}', right='{right_key}'.")

    left_keys = left_df[left_key].dropna().astype(str)
    right_keys = right_df[right_key].dropna().astype(str)

    left_unique = left_keys.nunique()
    right_unique = right_keys.nunique()
    left_has_dups = len(left_keys) > left_unique
    right_has_dups = len(right_keys) > right_unique

    if not left_has_dups and not right_has_dups:
        cardinality = "1:1"
    elif not left_has_dups and right_has_dups:
        cardinality = "1:N"
    elif left_has_dups and not right_has_dups:
        cardinality = "N:1"
    else:
        cardinality = "M:N"

    left_set = set(left_keys.unique())
    right_set = set(right_keys.unique())
    overlap = left_set & right_set
    left_orphans = len(left_set - right_set)
    right_orphans = len(right_set - left_set)
    overlap_pct = round((len(overlap) / max(len(left_set), 1)) * 100.0, 2)

    # Estimate joined row count to detect fan-out multiplication
    right_counts = right_keys.value_counts()
    projected_rows = int(left_keys.map(right_counts).fillna(0).sum())
    fanout_ratio = round(projected_rows / max(len(left_df), 1), 3)

    is_safe = (cardinality in {"1:1", "N:1"}) and (fanout_ratio <= 1.0)
    blockers: List[str] = []
    if cardinality == "M:N":
        blockers.append(
            f"Unsafe M:N join detected: both '{left_key}' and '{right_key}' contain duplicate keys "
            f"(projected fan-out {fanout_ratio}x, inflating {len(left_df):,} rows to {projected_rows:,} rows)."
        )
    elif right_has_dups:
        blockers.append(
            f"Right table key '{right_key}' has {len(right_keys) - right_unique} duplicate key(s), risking row multiplication."
        )
    if left_orphans > 0:
        blockers.append(f"{left_orphans} orphan key(s) in left table have no match in right table.")

    return {
        "left_key": left_key,
        "right_key": right_key,
        "cardinality": cardinality,
        "left_rows": int(len(left_df)),
        "right_rows": int(len(right_df)),
        "projected_joined_rows": projected_rows,
        "fanout_ratio": fanout_ratio,
        "overlap_pct": overlap_pct,
        "left_orphan_keys": left_orphans,
        "right_orphan_keys": right_orphans,
        "is_safe_to_join": is_safe,
        "status": "SAFE" if is_safe else "BLOCKED",
        "blockers": blockers,
    }
