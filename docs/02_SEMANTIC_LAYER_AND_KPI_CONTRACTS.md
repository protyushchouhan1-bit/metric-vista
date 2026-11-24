# 02 — Enterprise Semantic Layer & 15-Field KPI Contracts

## 3-Tier Hybrid Semantic Mapping
1. **Tier 1 (Deterministic Rules)**: Normalized synonym dictionary, regex patterns, and data-shape heuristics (uniqueness ratio, date parseability, numeric/currency shape).
2. **Tier 2 (AI Semantic Classifier — Metadata Only)**: Unresolved or `<0.85` confidence columns are sent to `BaseLLMProvider` with ONLY column name, dtype, summary stats, and up to 5 anonymized XML-delimited sample values. Zero raw PII rows are transmitted.
3. **Tier 3 (Mandatory Human Confirmation & Saved Memory)**: Any column `<85%` confidence and all critical financial, date, and identifier concepts (`revenue`, `cogs`, `order_date`, `order_id`, `actual_amount`, `account_category`) require explicit human confirmation alongside dataset grain (`order` vs `line_item` vs `ledger_entry` vs `employee_record`). Confirmed schema signatures are cached per `organization_id`.

## 15-Field Formal KPI Contract
Every YAML entry in `kpis/*.yaml` defines:
1. `code` 2. `name` 3. `department` 4. `business_meaning`
5. `formula_expression` 6. `required_concepts` 7. `required_grain` 8. `aggregation_method`
9. `time_period_logic` 10. `inclusion_exclusion_rules` 11. `unit_format`
12. `quality_prerequisites` 13. `validation_rules` 14. `calculation_version` 15. `known_limitations`

## 4-State Eligibility Matrix
- **Calculable**: All required concepts confirmed, grain compatible, zero blocking quality failures.
- **Calculable with Limitations**: Required concepts present, but non-fatal missing values or excluded rows exist (explicitly reported in Trust Tooltip).
- **Requires Additional Information**: Concepts mapped provisionally without human confirmation or grain confirmation.
- **Not Calculable**: One or more required concepts missing — exact missing concept names listed, never displayed as `0`.
