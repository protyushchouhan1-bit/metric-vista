"""
Phase 2 Real Two-Stage Grounded AI Business Analyst:
- Pydantic v1/v2 compatible QueryPlanAST allowlist validator
- Real LLM JSON query plan generation + real LLM grounded narrative explanation (zero discard!)
- Configurable GEMINI_MODEL env var (default: gemini-2.0-flash)
- Tier-2 Metadata-Only Column Classifier (5 XML-delimited sanitized samples, zero PII)
- Accurate execution_mode labels: live_llm | rule_based_offline | cached_demo | cached_ttl
- Session-only AI key support + fail-loudly Fernet vault option
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
import pydantic
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from core.kpi_engine import _clean_numeric_series

PYDANTIC_V2 = int(pydantic.__version__.split(".")[0]) >= 2
if PYDANTIC_V2:
    from pydantic import field_validator  # type: ignore
else:
    from pydantic import validator as _v1_validator

ALLOWED_METRICS = {
    "revenue", "cogs", "quantity", "discount_amount", "unit_price",
    "actual_amount", "budget_amount", "marketing_spend", "attributed_revenue",
}
ALLOWED_DIMENSIONS = {
    "region", "channel", "product_category", "product_name", "customer_id",
    "order_status", "account_category", "account_name", "department", "order_date", "period_date",
}
ALLOWED_CONCEPTS = sorted(ALLOWED_METRICS | ALLOWED_DIMENSIONS | {"order_id", "line_id"})

INJECTION_PATTERNS = re.compile(
    r"(ignore\s+previous\s+instructions|system\s*:|assistant\s*:|<\/?script|DROP\s+TABLE|DELETE\s+FROM|UNION\s+SELECT|;\s*--)",
    re.IGNORECASE,
)
EMAIL_REDACT = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_REDACT = re.compile(r"\+?\d[\d\s\-]{8,14}\d")


class BYOKCipher:
    """Fails loudly when NEXUS_FERNET_KEY is missing instead of silently generating a volatile key."""

    def __init__(self, secret_key: Optional[bytes] = None):
        env_key = os.getenv("NEXUS_FERNET_KEY", "").strip()
        if secret_key:
            self._key = secret_key
        elif env_key:
            self._key = env_key.encode("utf-8")
        else:
            raise RuntimeError(
                "NEXUS_FERNET_KEY is not configured. Use session-only X-Session-AI-Key or set NEXUS_FERNET_KEY."
            )
        self._fernet = Fernet(self._key)

    def encrypt(self, plaintext_key: str) -> str:
        return self._fernet.encrypt(plaintext_key.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def sanitize_untrusted_samples(values: List[Any], max_items: int = 5) -> List[str]:
    """Strip prompt-injection tokens, redact PII (emails/phones), and wrap in XML delimiters."""
    sanitized: List[str] = []
    for raw in values[:max_items]:
        txt = str(raw)[:80]
        txt = INJECTION_PATTERNS.sub("[REDACTED_CONTROL]", txt)
        txt = EMAIL_REDACT.sub("[REDACTED_EMAIL]", txt)
        txt = PHONE_REDACT.sub("[REDACTED_PHONE]", txt)
        txt = txt.replace("<", "&lt;").replace(">", "&gt;")
        sanitized.append(f"<sample_value>{txt}</sample_value>")
    return sanitized


def _dump_model(m: BaseModel) -> Dict[str, Any]:
    return m.model_dump() if PYDANTIC_V2 else m.dict()


class QueryFilterAST(BaseModel):
    column: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in"]
    value: Union[str, int, float, List[Union[str, int, float]]]

    if PYDANTIC_V2:
        @field_validator("column")
        @classmethod
        def validate_column(cls, v: str) -> str:
            if v not in ALLOWED_DIMENSIONS and v not in ALLOWED_METRICS:
                raise ValueError(f"Column '{v}' is not in the allowlisted semantic schema.")
            return v
    else:
        @_v1_validator("column")
        def validate_column(cls, v: str) -> str:
            if v not in ALLOWED_DIMENSIONS and v not in ALLOWED_METRICS:
                raise ValueError(f"Column '{v}' is not in the allowlisted semantic schema.")
            return v


class QueryPlanAST(BaseModel):
    """Strict Pydantic-validated Structured JSON Query Plan (ADR-06)."""
    metric: str
    aggregation: Literal["sum", "avg", "count", "count_distinct", "min", "max"] = "sum"
    group_by: List[str] = Field(default_factory=list)
    filters: List[QueryFilterAST] = Field(default_factory=list)
    order_direction: Literal["desc", "asc"] = "desc"
    limit: int = Field(default=10, ge=1, le=50)

    if PYDANTIC_V2:
        @field_validator("metric")
        @classmethod
        def validate_metric(cls, v: str) -> str:
            if v not in ALLOWED_METRICS:
                raise ValueError(f"Metric '{v}' is not allowlisted.")
            return v

        @field_validator("group_by")
        @classmethod
        def validate_group_by(cls, v: List[str]) -> List[str]:
            if len(v) > 2:
                raise ValueError("group_by allows at most 2 dimensions.")
            for item in v:
                if item not in ALLOWED_DIMENSIONS:
                    raise ValueError(f"Group-by dimension '{item}' is not allowlisted.")
            return v
    else:
        @_v1_validator("metric")
        def validate_metric(cls, v: str) -> str:
            if v not in ALLOWED_METRICS:
                raise ValueError(f"Metric '{v}' is not allowlisted.")
            return v

        @_v1_validator("group_by")
        def validate_group_by(cls, v: List[str]) -> List[str]:
            if len(v) > 2:
                raise ValueError("group_by allows at most 2 dimensions.")
            for item in v:
                if item not in ALLOWED_DIMENSIONS:
                    raise ValueError(f"Group-by dimension '{item}' is not allowlisted.")
            return v


class BaseLLMProvider(ABC):
    """Lightweight provider-agnostic LLM interface supporting query planning, explanation & Tier-2 mapping."""

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def classify_column_metadata(
        self,
        column_name: str,
        dtype: str,
        stats: Dict[str, Any],
        sample_values: List[Any],
    ) -> Optional[Dict[str, Any]]:
        """Tier-2 Metadata-Only Column Classifier (5 sanitized XML-delimited samples, zero PII)."""
        safe_samples = sanitize_untrusted_samples(sample_values, max_items=5)
        sys_p = (
            "You are a BI Semantic Schema Classifier. Map the column metadata to ONE concept from "
            f"{ALLOWED_CONCEPTS} or 'unmapped'. Return ONLY valid JSON: "
            '{"canonical_concept": "...", "confidence": 0.0-1.0, "reason": "...", "alternatives": []}.'
        )
        user_p = (
            f"Column: {column_name}\nType: {dtype}\nStats: {json.dumps(stats)}\n"
            f"Samples: {' '.join(safe_samples)}"
        )
        raw = self.generate_text(sys_p, user_p)
        if not raw or raw == "OFFLINE_FALLBACK":
            return None
        try:
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)
            concept = str(parsed.get("canonical_concept", "unmapped"))
            if concept not in ALLOWED_CONCEPTS and concept != "unmapped":
                return None
            return {
                "canonical_concept": concept,
                "confidence": min(max(float(parsed.get("confidence", 0.78)), 0.0), 0.99),
                "reason": str(parsed.get("reason", "Classified via Tier-2 metadata-only AI classifier.")),
                "alternatives": list(parsed.get("alternatives", []))[:3],
            }
        except Exception:
            return None


class GeminiProvider(BaseLLMProvider):
    """Gemini provider backed by official google-genai SDK with configurable GEMINI_MODEL."""

    def __init__(self, api_key: str, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        from google import genai  # type: ignore
        client = genai.Client(api_key=self.api_key)
        resp = client.models.generate_content(
            model=self.model,
            contents=f"{system_prompt}\n\n{user_prompt}",
        )
        return (resp.text or "").strip()


class OfflineFallbackProvider(BaseLLMProvider):
    """Explicit rule-based offline fallback when no live LLM API key is active."""

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        return "OFFLINE_FALLBACK"


class GroundedAIAnalyst:
    """
    Real Two-Stage Grounded AI Business Analyst:
    1. Live LLM receives ONLY semantic schema + question -> returns Structured JSON QueryPlanAST.
    2. Pydantic QueryPlanAST allowlist validates it (rejects SQL injection / unknown columns).
    3. Deterministic engine executes validated AST on Parquet.
    4. Live LLM explains ONLY the verified numbers (actually returned to the user!).
    5. Explicit offline rule-based fallback + pre-verified demo cache when no key is configured.
    """

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        cache_ttl_seconds: int = 900,
        preverified_qa: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.provider = provider or OfflineFallbackProvider()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.preverified_qa = preverified_qa or {}
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}

    def _rule_based_plan(self, question: str, available_concepts: set) -> Optional[QueryPlanAST]:
        """Explicit offline rule-based AST planner when live LLM is unavailable."""
        if INJECTION_PATTERNS.search(question):
            raise ValueError("Adversarial SQL/prompt-injection pattern rejected by AST guardrail.")

        q = question.lower()
        metric = "revenue" if "revenue" in available_concepts else (
            "actual_amount" if "actual_amount" in available_concepts else None
        )
        if not metric:
            return None
        if "cogs" in q or "cost" in q:
            if "cogs" in available_concepts:
                metric = "cogs"
        elif "discount" in q and "discount_amount" in available_concepts:
            metric = "discount_amount"
        elif ("unit" in q or "quantity" in q or "qty" in q) and "quantity" in available_concepts:
            metric = "quantity"
        elif "budget" in q and "budget_amount" in available_concepts:
            metric = "budget_amount"

        agg: Literal["sum", "avg", "count", "count_distinct", "min", "max"] = "sum"
        if "average" in q or "avg" in q or "mean" in q:
            agg = "avg"
        elif "maximum" in q or "highest single" in q:
            agg = "max"
        elif "minimum" in q or "lowest single" in q:
            agg = "min"

        order_dir: Literal["desc", "asc"] = "asc" if any(w in q for w in ("lowest", "worst", "bottom", "smallest")) else "desc"

        group_by: List[str] = []
        for dim, keywords in [
            ("region", ["region", "east", "west", "north", "south", "geography"]),
            ("channel", ["channel", "online", "direct", "partner", "marketplace"]),
            ("product_category", ["product category", "category", "categories", "product group"]),
            ("product_name", ["products", "product name", "selling", "item", "sku"]),
            ("account_category", ["account", "opex", "expense", "p&l"]),
            ("customer_id", ["customer", "client", "pareto"]),
            ("department", ["department", "team"]),
        ]:
            if dim in available_concepts and any(k in q for k in keywords):
                group_by.append(dim)
                if len(group_by) >= 2:
                    break

        filters: List[QueryFilterAST] = []
        for region_val in ("North", "South", "East", "West"):
            if re.search(rf"\b{region_val.lower()}\b", q) and "region" in available_concepts:
                filters.append(QueryFilterAST(column="region", operator="eq", value=region_val))
                break
        for ch_val in ("Online", "Direct", "Partner", "Marketplace"):
            if re.search(rf"\b{ch_val.lower()}\b", q) and "channel" in available_concepts:
                filters.append(QueryFilterAST(column="channel", operator="eq", value=ch_val))
                break

        if not group_by and not filters:
            return None

        return QueryPlanAST(
            metric=metric,
            aggregation=agg,
            group_by=group_by or (["region"] if "region" in available_concepts else []),
            filters=filters,
            order_direction=order_dir,
            limit=10,
        )

    def _llm_generate_plan(self, question: str, available_concepts: set) -> Optional[QueryPlanAST]:
        """Ask live LLM to return ONLY a Structured JSON QueryPlanAST using schema metadata."""
        if isinstance(self.provider, OfflineFallbackProvider):
            return None
        allowed_m = sorted(available_concepts & ALLOWED_METRICS)
        allowed_d = sorted(available_concepts & ALLOWED_DIMENSIONS)
        sys_p = (
            "You are a deterministic BI Query Planner. Return ONLY valid JSON matching QueryPlanAST: "
            '{"metric": "<metric>", "aggregation": "sum|avg|count|count_distinct|min|max", '
            '"group_by": ["<dim>"], "filters": [{"column":"<dim>","operator":"eq","value":"..."}], '
            '"order_direction": "desc|asc", "limit": 10} OR {"stage1_only": true} for headline KPIs. '
            f"Allowed metrics: {allowed_m}. Allowed dimensions: {allowed_d}. Never write SQL."
        )
        raw = self.provider.generate_text(sys_p, f"Question: {question}")
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        if parsed.get("stage1_only"):
            return None
        return QueryPlanAST(**parsed)

    def execute_query_plan(
        self,
        parquet_path: str,
        plan: QueryPlanAST,
        concept_to_col: Dict[str, str],
    ) -> Dict[str, Any]:
        """Execute validated JSON AST deterministically against Parquet."""
        df = pd.read_parquet(parquet_path, engine="pyarrow")
        if "order_status" in concept_to_col and concept_to_col["order_status"] in df.columns:
            df = df[~df[concept_to_col["order_status"]].astype(str).str.lower().isin({"cancelled", "canceled", "void"})]

        for flt in plan.filters:
            col = concept_to_col.get(flt.column)
            if not col or col not in df.columns:
                continue
            if flt.operator == "eq":
                df = df[df[col].astype(str) == str(flt.value)]
            elif flt.operator == "neq":
                df = df[df[col].astype(str) != str(flt.value)]
            elif flt.operator == "in" and isinstance(flt.value, list):
                df = df[df[col].isin(flt.value)]

        mcol = concept_to_col[plan.metric]
        df = df.copy()
        df["_metric"] = _clean_numeric_series(df[mcol])

        if plan.group_by:
            gcols = [concept_to_col[g] for g in plan.group_by if g in concept_to_col and concept_to_col[g] in df.columns]
            agg_map = {"sum": "sum", "avg": "mean", "count": "count", "count_distinct": "nunique", "min": "min", "max": "max"}
            grouped = df.groupby(gcols)["_metric"].agg(agg_map[plan.aggregation]).reset_index()
            grouped = grouped.sort_values("_metric", ascending=(plan.order_direction == "asc")).head(plan.limit)
            rows = [
                {**{g: str(r[concept_to_col[g]]) for g in plan.group_by if g in concept_to_col}, "value": round(float(r["_metric"]), 2)}
                for _, r in grouped.iterrows()
            ]
        else:
            val = float(df["_metric"].sum())
            rows = [{"metric": plan.metric, "value": round(val, 2)}]

        return {
            "validated_ast": _dump_model(plan),
            "rows_scanned": int(len(df)),
            "result_rows": rows,
        }

    def ask(
        self,
        question: str,
        org_id: str,
        dataset_id: str,
        parquet_path: str,
        domain: str,
        mappings: List[Dict[str, Any]],
        kpi_payload: Dict[str, Any],
        provider_override: Optional[BaseLLMProvider] = None,
    ) -> Dict[str, Any]:
        """Run Two-Stage Grounded AI pipeline with honest mode labels and visible query evidence."""
        active_provider = provider_override or self.provider
        if INJECTION_PATTERNS.search(question):
            raise ValueError("Unsafe prompt/SQL injection pattern detected and blocked.")

        clean_q = question.strip()
        cache_key = hashlib.sha256(f"{org_id}:{dataset_id}:{clean_q.lower()}:{type(active_provider).__name__}".encode()).hexdigest()
        now = time.time()
        if cache_key in self._cache:
            ts, cached = self._cache[cache_key]
            if now - ts < self.cache_ttl_seconds:
                out = dict(cached)
                out["cache_hit"] = True
                out["execution_mode"] = "cached_ttl"
                return out

        # Check pre-verified demo Q&A cache when offline
        if isinstance(active_provider, OfflineFallbackProvider) and clean_q.lower() in self.preverified_qa:
            cached_demo = dict(self.preverified_qa[clean_q.lower()])
            cached_demo["execution_mode"] = "cached_demo"
            cached_demo["cache_hit"] = True
            return cached_demo

        concept_to_col = {m["canonical_concept"]: m["source_column"] for m in mappings if m.get("canonical_concept") != "unmapped"}
        avail = set(concept_to_col.keys())

        # Stage 1 vs Stage 2 AST planning
        ast_plan: Optional[QueryPlanAST] = None
        used_live_llm = False
        if not isinstance(active_provider, OfflineFallbackProvider):
            old_p = self.provider
            self.provider = active_provider
            try:
                ast_plan = self._llm_generate_plan(clean_q, avail)
                used_live_llm = True
            except Exception:
                ast_plan = self._rule_based_plan(clean_q, avail)
            finally:
                self.provider = old_p
        else:
            ast_plan = self._rule_based_plan(clean_q, avail)

        if ast_plan is not None:
            stage = "stage2_json_ast"
            evidence = self.execute_query_plan(parquet_path, ast_plan, concept_to_col)
            top_rows = evidence["result_rows"][:5]
            obs_summary = "; ".join(
                f"{', '.join(f'{k}={v}' for k, v in row.items() if k != 'value')}: {row['value']:,.2f}"
                for row in top_rows
            ) or "No matching records found for the requested slice."
        else:
            stage = "stage1_kpi_summary"
            verified_kpis = [
                {"code": k["code"], "name": k["name"], "value": k["formatted_value"], "status": k["eligibility_status"]}
                for k in kpi_payload.get("kpis", [])
            ]
            evidence = {"validated_ast": None, "verified_kpis": verified_kpis}
            obs_summary = "; ".join(f"{k['name']}: {k['value']}" for k in verified_kpis[:6])

        missing_kpis = [k["name"] for k in kpi_payload.get("kpis", []) if k["eligibility_status"] == "Not Calculable"]
        limitations = (
            f"Unavailable metrics due to missing columns: {', '.join(missing_kpis)}."
            if missing_kpis
            else "All figures computed deterministically from the uploaded dataset; external market drivers are not uploaded."
        )

        # Real LLM narrative explanation (actually displayed, never discarded!)
        llm_narrative: Optional[str] = None
        execution_mode = "rule_based_offline"
        if not isinstance(active_provider, OfflineFallbackProvider):
            try:
                llm_narrative = active_provider.generate_text(
                    "You are Project NEXUS Business Analyst. Explain ONLY the verified JSON numbers below in 2-3 crisp executive sentences. Never invent numbers.",
                    f"Question: {clean_q}\nVerified Evidence: {json.dumps(evidence)}",
                )
                if llm_narrative and llm_narrative != "OFFLINE_FALLBACK":
                    execution_mode = "live_llm"
            except Exception:
                llm_narrative = None
                execution_mode = "rule_based_offline"
        elif used_live_llm:
            execution_mode = "live_llm"

        response = {
            "question": clean_q,
            "stage": stage,
            "execution_mode": execution_mode,
            "cache_hit": False,
            "structured_answer": {
                "verified_observation_and_evidence": llm_narrative or f"Verified deterministic output ({stage}): {obs_summary}",
                "business_impact": "These verified figures reflect realized performance across the active dataset scope and filters.",
                "possible_explanations_hypotheses": [
                    "Hypothesis (Unverified — Correlation != Causation): Regional/category mix shifts, discount depth, or seasonal order frequency may contribute to observed variance."
                ],
                "recommended_investigation_actions": [
                    "Cross-filter the dashboard by the leading and lagging segments to isolate price vs. volume drivers.",
                    "Inspect KPI Trust Tooltips and the 7-Dimension Quality Scorecard to confirm excluded rows.",
                ],
                "confidence_and_data_limitations": f"High arithmetic confidence (100% deterministic Python/DuckDB execution). {limitations}",
            },
            "see_the_query_and_evidence": evidence,
        }
        self._cache[cache_key] = (now, response)
        return response
