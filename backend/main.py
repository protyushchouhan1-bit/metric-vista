"""
Phase 1/2 Hardened FastAPI Backend (/api/v1/):
- Locked CORS (NEXUS_ALLOWED_ORIGINS, no wildcard '*')
- Zero forged-header trust; Demo Mode strictly read-only ('demo-org-public', role='viewer')
- Instant pre-seeded Demo Workspaces (<2s) + 10 pre-verified AI Q&As
- Session-only X-Session-AI-Key header (never persisted or logged)
- Single synchronized POST /api/v1/dashboards/{id}/query returning KPIs, charts,
  Price/Volume/Mix Variance Waterfall, Pareto 80/20, Weekly Brief, and sortable table
"""
from __future__ import annotations

import io
import json
import os
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.auth import DEMO_ORG_ID, TenantContext, get_tenant_context, issue_token
from backend.store import MetadataStore
from core.ai_analyst import GeminiProvider, GroundedAIAnalyst, OfflineFallbackProvider
from core.ingestion import ingest_file, sanitize_dataframe_for_csv_export
from core.kpi_engine import compute_dashboard_analytics, compute_kpis, prioritize_insights, run_what_if_simulation
from core.profiler import evaluate_data_quality, profile_dataset
from core.semantic_mapper import compute_schema_signature, propose_semantic_mappings, validate_dataset_relationship

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KPIS_DIR = os.path.join(PROJECT_ROOT, "kpis")
STORAGE_ROOT = os.getenv("NEXUS_STORAGE_ROOT", os.path.join(PROJECT_ROOT, "runtime_storage"))
DB_PATH = os.getenv("NEXUS_DB_PATH", os.path.join(STORAGE_ROOT, "nexus_metadata.db"))
DEMO_DIR = os.path.join(PROJECT_ROOT, "sample_data", "demo")
PREVERIFIED_QA_PATH = os.path.join(DEMO_DIR, "preverified_qa.json")

store = MetadataStore(DB_PATH)

def _load_preverified_qa() -> Dict[str, Any]:
    if os.path.exists(PREVERIFIED_QA_PATH):
        try:
            with open(PREVERIFIED_QA_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}

ai_analyst = GroundedAIAnalyst(preverified_qa=_load_preverified_qa())

app = FastAPI(
    title="Project NEXUS V2.0 API",
    version="2.0.0",
    description="AI-Powered Enterprise Intelligence, Data Quality & Decision Support Platform",
)

# Phase 1.3: Lock CORS to explicit origins (never wildcard '*')
_raw_origins = os.getenv(
    "NEXUS_ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173",
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Demo-Mode", "X-Session-AI-Key"],
)


class SessionRequest(BaseModel):
    user_id: str = "founder-01"
    organization_id: str = "org-alpha"
    role: str = "org_admin"
    email: str = "founder@acme.io"


class OrgSettingsUpdate(BaseModel):
    base_currency: Optional[str] = None
    fiscal_year_start_month: Optional[int] = None


class MappingConfirmItem(BaseModel):
    source_column: str
    canonical_concept: str


class MappingConfirmRequest(BaseModel):
    grain: str
    mappings: List[MappingConfirmItem]


class DashboardQueryRequest(BaseModel):
    filters: Dict[str, Any] = {}


class AIAskRequest(BaseModel):
    question: str


class RelationshipValidateRequest(BaseModel):
    left_dataset_id: str
    right_dataset_id: str
    left_key: str
    right_key: str


class WhatIfRequest(BaseModel):
    baseline_revenue: float
    baseline_cogs: float
    baseline_opex: float = 0.0
    price_change_pct: float = 0.0
    volume_change_pct: float = 0.0
    cogs_change_pct: float = 0.0
    opex_change_pct: float = 0.0


def _process_uploaded_bytes(
    file_bytes: bytes,
    filename: str,
    org_id: str,
    actor_user_id: str,
    sheet_name: Optional[str] = None,
    auto_confirm: bool = False,
    fixed_dataset_id: Optional[str] = None,
) -> Dict[str, Any]:
    store.ensure_org(org_id)
    dataset_id = fixed_dataset_id or str(uuid.uuid4())
    ing = ingest_file(
        file_bytes=file_bytes,
        filename=filename,
        org_id=org_id,
        dataset_id=dataset_id,
        storage_root=STORAGE_ROOT,
        sheet_name=sheet_name,
    )
    df = pd.read_parquet(ing.parquet_path, engine="pyarrow")
    prof = profile_dataset(df)
    qual = evaluate_data_quality(df, prof, flagged_total_rows=ing.flagged_total_rows)
    sig = compute_schema_signature(ing.columns)
    saved_mem = store.get_saved_schema_memory(org_id, sig)
    mapping_result = propose_semantic_mappings(prof, saved_memory=saved_mem)

    proposals = mapping_result["proposals"]
    if auto_confirm:
        for p in proposals:
            if p["canonical_concept"] != "unmapped":
                p["confirmed_by_human"] = True
                p["requires_human_confirmation"] = False

    grain = prof["grain_discovery"]["detected_grain"]
    record = {
        "id": dataset_id,
        "organization_id": org_id,
        "name": filename,
        "domain": prof["domain_guess"],
        "grain": grain,
        "grain_confirmed": auto_confirm,
        "raw_path": ing.raw_path,
        "parquet_path": ing.parquet_path,
        "file_hash": ing.file_hash_sha256,
        "row_count": ing.row_count,
        "column_count": ing.column_count,
        "profile": {**prof, "ingestion_warnings": ing.warnings, "sheet_names": ing.sheet_names, "flagged_preamble_rows": ing.flagged_preamble_rows},
        "quality": qual,
        "mappings": proposals,
        "schema_signature": sig,
        "status": "confirmed" if auto_confirm else "profiled",
    }
    store.save_dataset(record)
    job_id = store.create_job(org_id, "dataset_ingest", "completed", 100, {"dataset_id": dataset_id})
    store.log_audit(org_id, actor_user_id, "dataset.upload", "dataset", dataset_id, {"filename": filename, "rows": ing.row_count})
    return {
        "dataset_id": dataset_id,
        "job_id": job_id,
        "name": filename,
        "domain": prof["domain_guess"],
        "row_count": ing.row_count,
        "column_count": ing.column_count,
        "warnings": ing.warnings,
        "grain_discovery": prof["grain_discovery"],
        "quality_summary": {
            "overall_score": qual["overall_score"],
            "has_critical_blockers": qual["has_critical_blockers"],
            "critical_blockers": qual["critical_blockers"],
        },
        "pending_confirmation_count": sum(1 for p in proposals if p["requires_human_confirmation"]),
    }


DEMO_CATALOG = {
    "acme_retail": ("demo-acme-retail", "acme_retail_sales.csv", "Acme Retail (Sales Line-Item)", True),
    "apex_finance": ("demo-apex-finance", "apex_saas_finance.xlsx", "Apex SaaS (Financial P&L)", True),
    "nova_cryptic": ("demo-nova-cryptic", "nova_cryptic_sales.csv", "Nova Corp (Cryptic Headers)", False),
}


def ensure_demo_workspaces_seeded() -> List[Dict[str, Any]]:
    """Pre-seed read-only demo workspaces inside demo-org-public so evaluators load in <2s."""
    seeded = []
    for key, (ds_id, fname, label, auto_confirm) in DEMO_CATALOG.items():
        existing = store.get_dataset(ds_id, DEMO_ORG_ID)
        if not existing:
            fpath = os.path.join(DEMO_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as fh:
                    _process_uploaded_bytes(
                        fh.read(), fname, DEMO_ORG_ID, "system-seeder",
                        auto_confirm=auto_confirm, fixed_dataset_id=ds_id,
                    )
                existing = store.get_dataset(ds_id, DEMO_ORG_ID)
        if existing:
            seeded.append({
                "sample_key": key,
                "dataset_id": ds_id,
                "label": label,
                "filename": fname,
                "domain": existing["domain"],
                "row_count": existing["row_count"],
                "grain": existing["grain"],
                "grain_confirmed": existing["grain_confirmed"],
            })
    return seeded


@app.on_event("startup")
def _startup_seed_demo():
    ensure_demo_workspaces_seeded()


@app.get("/health")
def health():
    return {"status": "ok", "service": "project-nexus-v2", "version": "2.0.0"}


# --- Auth & Org ---
@app.post("/api/v1/auth/session")
def create_session(req: SessionRequest):
    store.ensure_org(req.organization_id)
    token = issue_token(req.user_id, req.organization_id, req.role, req.email)
    return {"access_token": token, "token_type": "bearer", "organization_id": req.organization_id, "role": req.role}


@app.patch("/api/v1/orgs/{org_id}/settings")
def patch_org_settings(org_id: str, req: OrgSettingsUpdate, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("org:settings")
    if tenant.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant settings modification blocked.")
    updated = store.update_org_settings(org_id, req.base_currency, req.fiscal_year_start_month)
    store.log_audit(org_id, tenant.user_id, "org.settings.update", "organization", org_id, {"currency": req.base_currency})
    return updated


@app.get("/api/v1/orgs/{org_id}/audit-logs")
def get_audit_logs(org_id: str, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("audit:read")
    if tenant.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant audit log access blocked.")
    return {"organization_id": org_id, "logs": store.list_audit_logs(org_id)}


# --- Instant Read-Only Demo Endpoints ---
@app.get("/api/v1/demo/workspaces")
def list_demo_workspaces():
    """Instant public read-only catalog of pre-seeded demo companies."""
    return {"organization_id": DEMO_ORG_ID, "read_only": True, "workspaces": ensure_demo_workspaces_seeded()}


@app.post("/api/v1/demo/load/{sample_key}")
def load_demo_company(sample_key: str):
    """Returns pre-seeded read-only demo dataset metadata in <2 seconds without mutating state."""
    workspaces = ensure_demo_workspaces_seeded()
    match = next((w for w in workspaces if w["sample_key"] == sample_key), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Unknown demo sample '{sample_key}'.")
    return match


# --- Data Intelligence (Writes strictly require authenticated non-demo role) ---
@app.post("/api/v1/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
):
    tenant.require("dataset:upload")
    raw = await file.read()
    try:
        return _process_uploaded_bytes(raw, file.filename or "upload.csv", tenant.organization_id, tenant.user_id, sheet_name=sheet_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, tenant: TenantContext = Depends(get_tenant_context)):
    job = store.get_job(job_id, tenant.organization_id)
    if not job:
        raise HTTPException(status_code=404, detail="Background job not found.")
    return job


@app.get("/api/v1/datasets")
def list_datasets(tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("dashboard:view")
    if tenant.is_demo:
        ensure_demo_workspaces_seeded()
    return {"datasets": store.list_datasets(tenant.organization_id)}


@app.get("/api/v1/datasets/{dataset_id}/profile")
def get_dataset_profile(dataset_id: str, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("dashboard:view")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    return {
        "dataset_id": ds["id"],
        "name": ds["name"],
        "domain": ds["domain"],
        "grain": ds["grain"],
        "grain_confirmed": ds["grain_confirmed"],
        "profile": ds["profile"],
        "mappings": ds["mappings"],
    }


@app.get("/api/v1/datasets/{dataset_id}/quality")
def get_dataset_quality(dataset_id: str, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("dashboard:view")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    return {"dataset_id": ds["id"], "quality": ds["quality"]}


@app.post("/api/v1/datasets/{dataset_id}/mappings/confirm")
def confirm_mappings(dataset_id: str, req: MappingConfirmRequest, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("mapping:confirm")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")

    overrides = {m.source_column: m.canonical_concept for m in req.mappings}
    updated = []
    for existing in ds["mappings"]:
        col = existing["source_column"]
        new_concept = overrides.get(col, existing["canonical_concept"])
        updated.append({
            **existing,
            "canonical_concept": new_concept,
            "mapping_tier": "tier3_human",
            "confirmed_by_human": True,
            "requires_human_confirmation": False,
        })
    store.update_mappings_and_grain(dataset_id, tenant.organization_id, req.grain, updated, ds["schema_signature"])
    store.log_audit(tenant.organization_id, tenant.user_id, "mapping.confirm", "dataset", dataset_id, {"grain": req.grain})
    return {"dataset_id": dataset_id, "status": "confirmed", "grain": req.grain, "mappings": updated}


@app.post("/api/v1/datasets/relationships/validate")
def validate_relationship(req: RelationshipValidateRequest, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("mapping:confirm")
    left = store.get_dataset(req.left_dataset_id, tenant.organization_id)
    right = store.get_dataset(req.right_dataset_id, tenant.organization_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="One or both datasets not found in your organization.")
    ldf = pd.read_parquet(left["parquet_path"], engine="pyarrow")
    rdf = pd.read_parquet(right["parquet_path"], engine="pyarrow")
    try:
        return validate_dataset_relationship(ldf, rdf, req.left_key, req.right_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/v1/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("dataset:delete")
    ok = store.delete_dataset(dataset_id, tenant.organization_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    store.log_audit(tenant.organization_id, tenant.user_id, "dataset.delete", "dataset", dataset_id, {})
    return {"deleted": True, "dataset_id": dataset_id}


# --- Synchronized KPIs & Dashboards (Single Source of Truth) ---
@app.get("/api/v1/datasets/{dataset_id}/kpis")
def get_dataset_kpis(dataset_id: str, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("dashboard:view")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    org = store.ensure_org(tenant.organization_id)
    return compute_kpis(
        parquet_path=ds["parquet_path"],
        domain=ds["domain"],
        mappings=ds["mappings"],
        kpis_dir=KPIS_DIR,
        grain_confirmed=ds["grain_confirmed"],
        currency=org["base_currency"],
        quality_report=ds["quality"],
    )


@app.post("/api/v1/dashboards/{dataset_id}/query")
def query_dashboard(dataset_id: str, req: DashboardQueryRequest, tenant: TenantContext = Depends(get_tenant_context)):
    """Unified synchronized cross-filter endpoint: returns KPIs, charts, Pareto, Waterfall, Weekly Brief & table."""
    tenant.require("dashboard:view")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    org = store.ensure_org(tenant.organization_id)
    kpis = compute_kpis(
        parquet_path=ds["parquet_path"],
        domain=ds["domain"],
        mappings=ds["mappings"],
        kpis_dir=KPIS_DIR,
        grain_confirmed=ds["grain_confirmed"],
        currency=org["base_currency"],
        filters=req.filters,
        quality_report=ds["quality"],
    )
    analytics = compute_dashboard_analytics(
        parquet_path=ds["parquet_path"],
        domain=ds["domain"],
        mappings=ds["mappings"],
        filters=req.filters,
    )
    insights = prioritize_insights(kpis, analytics)
    return {
        "dataset_id": dataset_id,
        "name": ds["name"],
        "domain": ds["domain"],
        "grain": ds["grain"],
        "grain_confirmed": ds["grain_confirmed"],
        "filters": req.filters,
        "kpis": kpis,
        "analytics": analytics,
        "insights": insights,
    }


@app.post("/api/v1/dashboards/{dataset_id}/export")
def export_dashboard_csv(dataset_id: str, req: DashboardQueryRequest, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("export:data")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    df = pd.read_parquet(ds["parquet_path"], engine="pyarrow")
    if tenant.role not in {"org_admin"}:
        for col in list(df.columns):
            if "salary" in col.lower() or "ctc" in col.lower():
                df[col] = "[MASKED_PII]"
    safe_df = sanitize_dataframe_for_csv_export(df)
    buf = io.StringIO()
    safe_df.to_csv(buf, index=False)
    buf.seek(0)
    store.log_audit(tenant.organization_id, tenant.user_id, "dashboard.export", "dataset", dataset_id, {"rows": len(safe_df)})
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="nexus_export_{dataset_id[:8]}.csv"'},
    )


# --- Grounded AI (Session-Only Key, Never Persisted or Logged) ---
@app.post("/api/v1/ai/conversations/{dataset_id}/ask")
def ask_ai_analyst(
    dataset_id: str,
    req: AIAskRequest,
    x_session_ai_key: Optional[str] = Header(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
):
    tenant.require("ai:ask")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    org = store.ensure_org(tenant.organization_id)
    kpis = compute_kpis(
        parquet_path=ds["parquet_path"],
        domain=ds["domain"],
        mappings=ds["mappings"],
        kpis_dir=KPIS_DIR,
        grain_confirmed=ds["grain_confirmed"],
        currency=org["base_currency"],
    )
    # Always use server-configured GEMINI_API_KEY from backend env (Render / .env) without prompting users
    server_gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    provider = OfflineFallbackProvider()
    if server_gemini_key:
        provider = GeminiProvider(api_key=server_gemini_key)
    elif x_session_ai_key and not tenant.is_demo:
        provider = GeminiProvider(api_key=x_session_ai_key.strip())

    try:
        return ai_analyst.ask(
            question=req.question,
            org_id=tenant.organization_id,
            dataset_id=dataset_id,
            parquet_path=ds["parquet_path"],
            domain=ds["domain"],
            mappings=ds["mappings"],
            kpi_payload=kpis,
            provider_override=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/datasets/{dataset_id}/insights")
def get_insights(dataset_id: str, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("dashboard:view")
    ds = store.get_dataset(dataset_id, tenant.organization_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found in your organization.")
    org = store.ensure_org(tenant.organization_id)
    kpis = compute_kpis(ds["parquet_path"], ds["domain"], ds["mappings"], KPIS_DIR, ds["grain_confirmed"], org["base_currency"])
    dash = compute_dashboard_analytics(ds["parquet_path"], ds["domain"], ds["mappings"])
    return prioritize_insights(kpis, dash)


@app.post("/api/v1/scenarios/simulate")
def simulate_what_if(req: WhatIfRequest, tenant: TenantContext = Depends(get_tenant_context)):
    tenant.require("dashboard:view")
    return run_what_if_simulation(**(req.model_dump() if hasattr(req, "model_dump") else req.dict()))
