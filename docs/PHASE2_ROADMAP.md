# Phase 2 & Phase 3 Roadmap (Deferred Architecture Assets)

To keep the MVP focused on a single rock-solid vertical slice (**Sales + Financial P&L + Executive Overview + Grounded AI**), the following enterprise assets are preserved in the repository for Phase 2/3 activation:

1. **PostgreSQL Row-Level Security (`backend/db/schema.sql`)**: Ready to deploy on Supabase PostgreSQL when migrating from the lightweight local SQLite metadata store.
2. **Full 5-Role Departmental RBAC & HR Salary Masking**: Role matrix defined in `backend/auth.py`; MVP ships with `org_admin` + `analyst` + read-only `viewer` (Demo Mode).
3. **Standalone React + TypeScript + Apache ECharts SPA (`future/react_frontend/`)**: Moved to `future/react_frontend/` so the MVP runs cleanly on a single unified frontend (`web_app/index.html` wired 100% to FastAPI `/api/v1/`) with zero split-calculator drift.
4. **Multi-Table Join Validator (`core/semantic_mapper.py`)**: Tested against M:N duplicate-key fan-out in `tests/`, ready for Phase 2 multi-file uploads.
5. **Live Connectors & Redis/ARQ Workers**: Planned for Phase 3 commercial growth (50+ SMEs).
