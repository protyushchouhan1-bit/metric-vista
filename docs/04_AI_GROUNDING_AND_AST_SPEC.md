# 04 — Grounded AI Analyst & Structured JSON AST Specification

## Zero Tolerance for AI Math Hallucination
The LLM (`BaseLLMProvider`) **never** performs arithmetic and **never** writes raw SQL. Every natural-language question follows a gated two-stage pipeline:

1. **Stage 1 (Verified KPI Summary)**: Headline/executive questions ("What is our gross margin?", "Summarize top risks") are answered strictly from pre-computed deterministic KPI JSON.
2. **Stage 2 (Structured JSON Query Plan AST)**: Dynamic slice/diagnostic questions ("Why did East drop?", "Top 5 products by revenue in Online channel") produce a Pydantic-validated `QueryPlanAST`:
   - `metric`: allowlisted canonical numeric concept (`revenue`, `cogs`, `quantity`, `discount_amount`, `actual_amount`, `budget_amount`)
   - `aggregation`: allowlisted enum (`sum`, `avg`, `count`, `count_distinct`, `min`, `max`)
   - `group_by`: allowlisted categorical/date concepts (max 2)
   - `filters`: allowlisted column + operator (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`) + typed value
   - `order_by` & `limit` (capped at 50)
3. **Deterministic Execution**: The validated AST is compiled into a parameterized DuckDB/Parquet query and executed locally.
4. **Mandatory 5-Part Response Contract**:
   - `verified_observation_and_evidence`: Exact verified numbers + expandable "See the Query & Numbers" panel.
   - `business_impact`: Financial/operational significance.
   - `possible_explanations_hypotheses`: Explicitly marked as unverified hypotheses (`Correlation != Causation`).
   - `recommended_investigation_actions`: Concrete next steps.
   - `confidence_and_data_limitations`: Reliability rating and explicit data gaps.
5. **Graceful Offline Degradation**: When no API key is configured or quota is exhausted, Demo/Deterministic Fallback mode keeps 100% of dashboards, KPIs, and evidence-backed Q&A operational.
