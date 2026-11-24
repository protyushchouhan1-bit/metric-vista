# 01 — Architecture & Architecture Decision Records (ADRs)

## System Overview
Project NEXUS V2.0 is a **Modular Monolith** with strict separation between the framework-agnostic Python analytical engine (`core/`), version-controlled KPI configuration (`kpis/*.yaml`), the FastAPI API & governance layer (`backend/`), and the React + TypeScript + Tailwind + Apache ECharts frontend (`frontend/`).

```
[React + TS + ECharts UI] ──HTTPS/JSON──> [FastAPI /api/v1 Gateway (JWT + Tenant + RBAC)]
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
        [Metadata Store]             [core/ Analytical Engine]       [Grounded AI Layer]
   PostgreSQL + RLS (or SQLite)    Ingest → Profile → 7D Quality    BaseLLMProvider (Gemini)
   (orgs, mappings, KPIs, jobs)    Semantic Mapper → YAML KPIs      Pydantic JSON AST Validator
                                   DuckDB / PyArrow on Parquet      Fernet BYOK + 15m Cache
                                                │
                                                ▼
                                   [Immutable Object Storage]
                               /{org_id}/raw/  &  /{org_id}/parquet/
```

## Unified V2.0 Architecture Decision Records
- **ADR-01 (Engine-First Decoupling)**: 100% of business logic lives inside `core/`. Primary UI is React + TypeScript + FastAPI; the same `core/` package supports any optional rapid prototype wrapper with zero analytical rework.
- **ADR-02 (Multi-Tenant Schema Day 1, Progressive Roles)**: `organization_id` is mandatory on every table and storage path from Day 1. MVP activates Org Admin + Analyst/Viewer + One-Click Public Demo Mode; Phase 2/3 unlocks 5-role departmental RBAC and PostgreSQL RLS.
- **ADR-03 (Dual-Layer Storage)**: Relational metadata lives in PostgreSQL; immutable raw files and cleaned columnar Apache Parquet files live in private Object Storage, queried in-process by DuckDB (with deterministic PyArrow/Pandas fallback).
- **ADR-04 (7-Dimension Data Quality)**: Completeness, Uniqueness, Validity, Consistency, Timeliness, Referential Integrity, and Business-Rule Compliance. Critical blockers (mixed currencies, duplicate keys, bottom Grand Total rows) raise loud severity flags that are never masked by a summary index.
- **ADR-05 (Hybrid YAML-to-DB KPI Registry)**: Departmental KPIs are authored in `kpis/*.yaml` and synced into `kpi_definitions` on startup.
- **ADR-06 (Two-Stage Grounded AI)**: Stage 1 uses verified pre-computed KPI JSON; Stage 2 generates a validated Pydantic Structured JSON Query Plan (AST) executed deterministically on Parquet, paired with a "See the Query & Evidence" panel.
- **ADR-07 (Apache ECharts Primary)**: Compact bundle, crisp dark-mode neon styling, synchronized cross-filtering.
- **ADR-08 (Disciplined Neon-Accented Enterprise Dark)**: `#0A0E17` canvas, `#111827` elevated cards, `#1F2937` borders, selective `#06B6D4` / `#3B82F6` / `#8B5CF6` accents, Inter + `tabular-nums`, zero UI emojis.
