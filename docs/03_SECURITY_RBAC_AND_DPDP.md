# 03 — Security, Multi-Tenant RBAC & India DPDP Governance

## Defense-in-Depth Isolation
- **Layer 1 (JWT Claims)**: Every authenticated request extracts `organization_id`, `user_id`, and `role` server-side.
- **Layer 2 (FastAPI Dependency Injection)**: Every dataset, dashboard, job, and AI endpoint scopes queries strictly by `tenant.organization_id`, returning `403`/`404` on cross-tenant access attempts.
- **Layer 3 (PostgreSQL RLS)**: `schema.sql` enables Row-Level Security on tenant tables bound to `app.current_org_id`.
- **Immutable Raw Storage**: Raw uploads are hashed (SHA-256) and stored read-only under `/{org_id}/raw/`.

## Progressive 5-Role RBAC Matrix
| Capability | Platform Admin | Org Admin (MVP) | Dept Manager (P2) | Analyst (MVP) | Viewer (MVP) |
|---|---|---|---|---|---|
| Org Settings & BYOK Keys | No* | Yes | No | No | No |
| Upload & Confirm Mappings | No* | Yes | Own Dept | Assigned | No |
| View Dashboards & AI Analyst | No* | All Depts | Own Dept | Assigned | Permitted |
| View Individual HR Salary PII | No* | Opt-In | HR Head Only | No | No |
| Export Data & View Audit Logs | Platform Only | Org-Wide | Own Dept | Export Only | No |

*Zero-Standing-Access Rule: Platform Admins cannot inspect customer files or API keys without auditable tenant consent.

## Untrusted Data, CSV Injection & Prompt-Injection Defense
- **CSV Formula Neutralization**: On export, cells starting with `=`, `+`, `-`, or `@` are prefixed with `'` to prevent spreadsheet formula execution.
- **Prompt Injection Defense**: Sample values sent to the LLM are stripped of control tokens, truncated, redacted for PII patterns (email, phone, PAN/SSN), and wrapped in `<sample_value>` XML delimiters.
- **India DPDP Alignment**: User-controlled dataset deletion, configurable retention policies, Fernet-encrypted BYOK AI keys, immutable audit logs, and minimum group aggregation thresholds (`k >= 5`) combined with role-based column masking for HR compensation data.
