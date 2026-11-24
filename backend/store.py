"""
Relational Metadata & Governance Store (SQLite local runtime, PostgreSQL schema-compatible).
Stores ONLY metadata, mappings, KPI definitions, jobs, encrypted BYOK keys, and audit logs.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetadataStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_currency TEXT NOT NULL DEFAULT 'INR',
                    fiscal_year_start_month INTEGER NOT NULL DEFAULT 4,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    grain TEXT NOT NULL DEFAULT 'unknown',
                    grain_confirmed INTEGER NOT NULL DEFAULT 0,
                    raw_path TEXT NOT NULL,
                    parquet_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    column_count INTEGER NOT NULL,
                    profile_json TEXT NOT NULL,
                    quality_json TEXT NOT NULL,
                    mappings_json TEXT NOT NULL,
                    schema_signature TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'profiled',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS saved_schema_memory (
                    organization_id TEXT NOT NULL,
                    schema_signature TEXT NOT NULL,
                    mappings_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (organization_id, schema_signature)
                );
                CREATE TABLE IF NOT EXISTS org_ai_configs (
                    organization_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL DEFAULT 'gemini',
                    encrypted_api_key TEXT,
                    demo_mode_enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS background_jobs (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_pct INTEGER NOT NULL DEFAULT 0,
                    error_log TEXT,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def ensure_org(self, org_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
            if row:
                return dict(row)
            now = _utc_now()
            conn.execute(
                "INSERT INTO organizations (id, name, base_currency, fiscal_year_start_month, created_at) VALUES (?, ?, 'INR', 4, ?)",
                (org_id, name or f"Workspace {org_id}", now),
            )
            return {"id": org_id, "name": name or f"Workspace {org_id}", "base_currency": "INR", "fiscal_year_start_month": 4, "created_at": now}

    def update_org_settings(self, org_id: str, base_currency: Optional[str], fiscal_year_start_month: Optional[int]) -> Dict[str, Any]:
        org = self.ensure_org(org_id)
        cur = base_currency or org["base_currency"]
        fy = fiscal_year_start_month or org["fiscal_year_start_month"]
        with self._conn() as conn:
            conn.execute(
                "UPDATE organizations SET base_currency = ?, fiscal_year_start_month = ? WHERE id = ?",
                (cur, fy, org_id),
            )
        return self.ensure_org(org_id)

    def save_dataset(self, record: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO datasets (
                    id, organization_id, name, domain, grain, grain_confirmed,
                    raw_path, parquet_path, file_hash, row_count, column_count,
                    profile_json, quality_json, mappings_json, schema_signature, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"], record["organization_id"], record["name"], record["domain"],
                    record["grain"], int(record.get("grain_confirmed", False)),
                    record["raw_path"], record["parquet_path"], record["file_hash"],
                    record["row_count"], record["column_count"],
                    json.dumps(record["profile"]), json.dumps(record["quality"]),
                    json.dumps(record["mappings"]), record["schema_signature"],
                    record.get("status", "profiled"), _utc_now(),
                ),
            )

    def get_dataset(self, dataset_id: str, org_id: str) -> Optional[Dict[str, Any]]:
        """Strictly tenant-scoped lookup (returns None if owned by another org)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM datasets WHERE id = ? AND organization_id = ?",
                (dataset_id, org_id),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["grain_confirmed"] = bool(d["grain_confirmed"])
            d["profile"] = json.loads(d.pop("profile_json"))
            d["quality"] = json.loads(d.pop("quality_json"))
            d["mappings"] = json.loads(d.pop("mappings_json"))
            return d

    def list_datasets(self, org_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, organization_id, name, domain, grain, grain_confirmed, row_count, column_count, status, created_at FROM datasets WHERE organization_id = ? ORDER BY created_at DESC",
                (org_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_mappings_and_grain(
        self, dataset_id: str, org_id: str, grain: str, mappings: List[Dict[str, Any]], schema_signature: str
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE datasets SET grain = ?, grain_confirmed = 1, mappings_json = ?, status = 'confirmed' WHERE id = ? AND organization_id = ?",
                (grain, json.dumps(mappings), dataset_id, org_id),
            )
            mem = {m["source_column"]: m["canonical_concept"] for m in mappings if m.get("canonical_concept") != "unmapped"}
            conn.execute(
                "INSERT OR REPLACE INTO saved_schema_memory (organization_id, schema_signature, mappings_json, updated_at) VALUES (?, ?, ?, ?)",
                (org_id, schema_signature, json.dumps(mem), _utc_now()),
            )

    def get_saved_schema_memory(self, org_id: str, schema_signature: str) -> Dict[str, str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT mappings_json FROM saved_schema_memory WHERE organization_id = ? AND schema_signature = ?",
                (org_id, schema_signature),
            ).fetchone()
            return json.loads(row["mappings_json"]) if row else {}

    def delete_dataset(self, dataset_id: str, org_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM datasets WHERE id = ? AND organization_id = ?", (dataset_id, org_id))
            return cur.rowcount > 0

    def upsert_ai_config(self, org_id: str, provider: str, encrypted_key: Optional[str], demo_mode: bool) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO org_ai_configs (organization_id, provider, encrypted_api_key, demo_mode_enabled, updated_at) VALUES (?, ?, ?, ?, ?)",
                (org_id, provider, encrypted_key, int(demo_mode), _utc_now()),
            )

    def get_ai_config(self, org_id: str) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM org_ai_configs WHERE organization_id = ?", (org_id,)).fetchone()
            if not row:
                return {"organization_id": org_id, "provider": "gemini", "encrypted_api_key": None, "demo_mode_enabled": True}
            d = dict(row)
            d["demo_mode_enabled"] = bool(d["demo_mode_enabled"])
            return d

    def create_job(self, org_id: str, job_type: str, status: str = "completed", progress_pct: int = 100, result: Optional[Dict[str, Any]] = None) -> str:
        jid = str(uuid.uuid4())
        now = _utc_now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO background_jobs (id, organization_id, job_type, status, progress_pct, result_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (jid, org_id, job_type, status, progress_pct, json.dumps(result or {}), now, now),
            )
        return jid

    def get_job(self, job_id: str, org_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM background_jobs WHERE id = ? AND organization_id = ?", (job_id, org_id)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["result"] = json.loads(d.pop("result_json") or "{}")
            return d

    def log_audit(self, org_id: str, actor_user_id: str, action: str, resource_type: str, resource_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO audit_logs (id, organization_id, actor_user_id, action, resource_type, resource_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), org_id, actor_user_id, action, resource_type, resource_id, json.dumps(metadata or {}), _utc_now()),
            )

    def list_audit_logs(self, org_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE organization_id = ? ORDER BY created_at DESC LIMIT ?",
                (org_id, limit),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["metadata"] = json.loads(d.pop("metadata_json"))
                out.append(d)
            return out
