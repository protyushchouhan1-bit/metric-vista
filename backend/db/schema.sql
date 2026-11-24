-- Project NEXUS V2.0 — Multi-Tenant PostgreSQL Metadata & Governance Schema
-- Dual-Layer Storage (ADR-03): PostgreSQL stores relational metadata, mappings, KPI definitions,
-- cached verified results, background jobs, and audit logs. Raw & Parquet datasets live in Object Storage.
-- Multi-Tenant Schema Day 1 (ADR-02): Every tenant-owned table includes organization_id + RLS policies.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Tenancy & RBAC
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'INR',
    fiscal_year_start_month SMALLINT NOT NULL DEFAULT 4 CHECK (fiscal_year_start_month BETWEEN 1 AND 12),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL, -- platform_admin, org_admin, dept_manager, analyst, viewer
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL, -- dataset:upload, mapping:confirm, dashboard:view, pii:view_salary, audit:read
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id),
    department_id UUID REFERENCES departments(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, user_id)
);

-- 2. Data Catalog & Quality
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    department_id UUID REFERENCES departments(id),
    name TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'sales',
    grain TEXT DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'uploaded', -- uploaded, profiled, confirmed, published
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version_number INT NOT NULL DEFAULT 1,
    raw_storage_path TEXT NOT NULL,
    parquet_storage_path TEXT NOT NULL,
    row_count INT NOT NULL,
    column_count INT NOT NULL,
    file_hash_sha256 TEXT NOT NULL,
    schema_diff_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, version_number)
);

CREATE TABLE IF NOT EXISTS dataset_columns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    inferred_dtype TEXT NOT NULL,
    null_pct NUMERIC(5,2) NOT NULL,
    distinct_count INT NOT NULL,
    pii_flag BOOLEAN NOT NULL DEFAULT FALSE,
    stats_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS data_quality_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    overall_score NUMERIC(5,2) NOT NULL,
    has_critical_blockers BOOLEAN NOT NULL DEFAULT FALSE,
    dimensions_json JSONB NOT NULL, -- 7 explicit dimensions
    messy_rows_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Semantics & Relationships
CREATE TABLE IF NOT EXISTS semantic_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    source_column TEXT NOT NULL,
    canonical_concept TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL,
    mapping_tier TEXT NOT NULL, -- tier1_rule, tier2_ai, tier3_human
    confirmed_by_human BOOLEAN NOT NULL DEFAULT FALSE,
    schema_signature TEXT,
    reason TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS business_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    detected_grain TEXT NOT NULL,
    currency TEXT DEFAULT 'INR',
    fiscal_start_month SMALLINT DEFAULT 4
);

CREATE TABLE IF NOT EXISTS dataset_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    source_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    target_dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    source_key TEXT NOT NULL,
    target_key TEXT NOT NULL,
    cardinality TEXT NOT NULL, -- 1:1, 1:N, N:1, M:N
    is_safe_to_join BOOLEAN NOT NULL DEFAULT FALSE,
    validation_report_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- 4. KPIs & Data Lineage
CREATE TABLE IF NOT EXISTS kpi_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE, -- NULL for global YAML templates
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1.0',
    definition_json JSONB NOT NULL, -- Full 15-field KPI contract
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, code, version)
);

CREATE TABLE IF NOT EXISTS kpi_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    kpi_code TEXT NOT NULL,
    eligibility_status TEXT NOT NULL, -- Calculable, Calculable with Limitations, Requires Additional Information, Not Calculable
    value NUMERIC,
    formatted_value TEXT,
    lineage_json JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_lineage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    kpi_result_id UUID NOT NULL REFERENCES kpi_results(id) ON DELETE CASCADE,
    source_columns JSONB NOT NULL,
    active_filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    excluded_row_count INT NOT NULL DEFAULT 0,
    formula_expression TEXT NOT NULL,
    calculation_version TEXT NOT NULL
);

-- 5. Dashboards, Insights & AI
CREATE TABLE IF NOT EXISTS dashboard_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    layout_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    priority_score NUMERIC(5,2) NOT NULL,
    payload_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS org_ai_configs (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'gemini',
    encrypted_api_key TEXT, -- Fernet encrypted BYOK
    demo_mode_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_id UUID REFERENCES datasets(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_query_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    stage TEXT NOT NULL, -- stage1_kpi_summary, stage2_json_ast
    query_plan_json JSONB,
    evidence_json JSONB NOT NULL,
    structured_response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scenario_simulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    assumptions_json JSONB NOT NULL,
    outputs_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Reliability & Governance
CREATE TABLE IF NOT EXISTS background_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued', -- queued, running, completed, failed, cancelled
    progress_pct SMALLINT NOT NULL DEFAULT 0,
    error_log TEXT,
    result_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_retention_policies (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    retain_raw_days INT NOT NULL DEFAULT 365,
    retain_audit_days INT NOT NULL DEFAULT 730,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast tenant scoping
CREATE INDEX IF NOT EXISTS idx_datasets_org ON datasets(organization_id);
CREATE INDEX IF NOT EXISTS idx_dataset_versions_org ON dataset_versions(organization_id);
CREATE INDEX IF NOT EXISTS idx_kpi_results_org ON kpi_results(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org ON audit_logs(organization_id, created_at DESC);

-- Row-Level Security (RLS) Enforcement Policies
ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE dataset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE semantic_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE kpi_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_datasets ON datasets
    USING (organization_id = current_setting('app.current_org_id', true)::uuid);
CREATE POLICY tenant_isolation_versions ON dataset_versions
    USING (organization_id = current_setting('app.current_org_id', true)::uuid);
CREATE POLICY tenant_isolation_mappings ON semantic_mappings
    USING (organization_id = current_setting('app.current_org_id', true)::uuid);
CREATE POLICY tenant_isolation_kpi_results ON kpi_results
    USING (organization_id = current_setting('app.current_org_id', true)::uuid);
CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    USING (organization_id = current_setting('app.current_org_id', true)::uuid);
