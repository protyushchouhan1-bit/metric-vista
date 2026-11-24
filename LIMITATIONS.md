# Known Limitations & Honest Scope Boundaries

Project NEXUS V2.0 is built to be transparent about what it verifies today versus what is intentionally scoped for Phase 2/3.

## Current Limitations
1. **Tabular Single-Sheet MVP**: Supports structured `.csv`, `.xlsx`, and `.xls` files up to **15 MB / 100,000 rows**. Complex multi-table, merged-cell statutory financial statements and automatic multi-currency FX conversion are scoped to Phase 2.
2. **Local Metadata Store vs. PostgreSQL RLS**: The local/MVP runtime uses SQLite (`backend/store.py`) with strict FastAPI service-layer `organization_id` scoping. The full PostgreSQL Row-Level Security schema (`backend/db/schema.sql`) is ready for Supabase/PostgreSQL deployment (Phase 2).
3. **Read-Only Public Demo Mode**: Evaluators using `X-Demo-Mode: true` receive a fixed `demo-org-public` workspace with `viewer` permissions—they cannot upload files, modify settings, or write AI keys. Full upload & mapping confirmation requires a signed JWT session (`POST /api/v1/auth/session`).
4. **LLM Free-Tier Quotas & Offline Mode**: Without a live `X-Session-AI-Key`, the AI Analyst runs in explicit `rule_based_offline` or `cached_demo` mode (clearly labeled in every response). Live Gemini execution requires a valid user-supplied API key and is subject to Google's current Gemini API rate limits and terms.
5. **Price/Volume/Mix Variance Waterfall**: Full Price + Volume + Mix decomposition requires both `quantity` and `unit_price` (or derivable average price). When those columns are absent (e.g., Financial P&L ledgers), the waterfall honestly reports `Requires Additional Information` for Price/Volume and falls back to regional/category variance.
6. **Memory Envelope**: Peak RSS depends on dataset width and Python/Pandas/PyArrow runtime overhead (measured honestly across 1k, 25k, and 100k-row tiers in `README.md`). Deployments exceeding 100k rows should upgrade from 512 MB free-tier containers to 2 GB RAM.
