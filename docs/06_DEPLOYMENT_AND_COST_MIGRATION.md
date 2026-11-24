# 06 — Deployment & Free-to-Commercial Cost Migration Path

## Stage 1: Student / Portfolio MVP ($0 / month)
- **Frontend**: Vercel Free (`frontend/` via `vercel.json`)
- **Backend**: Render Free (512 MB RAM, `render.yaml`)
- **Database & Storage**: Supabase Free (500 MB PostgreSQL + 1 GB Private Storage)
- **AI**: Gemini Free Tier / Encrypted Organization BYOK + Demo Mode Toggle
- **Mitigations**: 15 MB / 100k-row upload cap, immediate Parquet conversion, DuckDB streaming queries, 15-minute query cache, friendly cold-start banner.

## Stage 2: Early Commercial Pilot (1–15 SMEs, ~$50–$120 / month)
- Vercel Pro + Render Standard (2 GB RAM, Always-On) + Supabase Pro (8 GB DB, 100 GB Storage, Daily Backups) + Paid Gemini/OpenAI API + Sentry.
- Zero code rewrite required; swap `FastAPI BackgroundTasks` to Redis + ARQ workers for concurrent multi-company loads.

## Stage 3: Commercial Growth (50+ SMEs, $300+ / month)
- Dedicated cloud containers (AWS/GCP/Fly.io), Managed PostgreSQL with strict RLS, S3/R2 Object Storage, Redis/ARQ workers, and Multi-Provider LLM routing via `BaseLLMProvider`.
