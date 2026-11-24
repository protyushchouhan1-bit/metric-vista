# 04 — What the Project Is Doing Right Now (End-to-End Walkthrough)

Here is every active feature running in the platform today, from the moment a user opens `http://localhost:8000` to downloading cleaned reports.

## Step 1: Upload-First Entry (`Upload New File`)
- Opens on a clean, pale off-white corporate screen with a **center-aligned editable brand header** (blank by default so you can name it later).
- Accepts **Excel (`.xlsx`, `.xls`)** and **CSV / TSV** files up to **1,00,000 rows (1 Lakh)** via drag-and-drop or file picker.
- Includes a **Load Messy Sample Spreadsheet** button pre-loaded with realistic duplicates, `₹`-formatted text numbers, blank cells, and a bottom `Grand Total` row so you can demonstrate the full cleaner in one click.

## Step 2: 60fps 8-Step Animated ETL & Data Processing Pipeline
Immediately upon upload, the platform runs and visualizes all 8 lifecycle stages:
1. **Business Understanding**: Detects numeric measures, primary/secondary dimensions, product/category columns, and date/time fields.
2. **Data Collection**: Decodes binary Excel workbooks via SheetJS or quoted CSV text, scans the top 15 rows to locate the true header row (skipping logo/title banners).
3. **Data Cleaning & Preparation**: Removes exact duplicate rows, strips bottom `Grand Total` / `Subtotal` rows, strips `₹`, `$`, `%`, and commas from dirty numeric cells, trims extra whitespace, and fills blank numeric cells with column medians (or `"Unknown"` for text).
4. **Exploratory Data Analysis (EDA)**: Computes per-column completeness %, distinct counts, inferred types, min/max/mean, and negative anomalies.
5. **Feature Engineering**: Automatically creates derived time fields (`Season`, `Quarter`, `Month`) when dates exist and calculates `Net Spread / Margin` when paired primary & cost columns exist.
6. **Modeling**: Builds segment concentration rankings, period trends, and Economic Order Quantity (EOQ) baseline inputs.
7. **Evaluation**: Calculates an overall **Column Quality Score (%)** and assigns **Safe Zone / Watch Zone / Danger Zone** badges.
8. **Deployment & Monitoring**: Publishes the verified dataset to the interactive dashboard.

## Step 3: Vibrant Corporate 6-Chart Dashboard (`Dashboard`)
- **Health & Danger Zone Banner**: Instant green/amber/red status bar summarizing key wins and risks.
- **Smart Filters & Measure Switcher**: Dynamic dropdowns built strictly from your uploaded file's columns (Season, Month, Date From/To, top categories), a **Measure** dropdown to switch which numeric column drives all charts, and an adaptive **Play Smart Animation** button (animating Month-by-Month, Season-by-Season, Quarter-by-Quarter, or Category-by-Category).
- **6 Adaptive KPI Cards**: Color-coded top borders with Indian comma formatting (`tabular-nums`).
- **6 Vibrant Interactive Charts**:
  1. **Monthly / Sequence Area-Line or Column Trend** (toggleable)
  2. **Clickable Donut / Pie Share Breakdown** (click any slice to cross-filter)
  3. **Side-by-Side Multi-Series Comparison** (e.g., Revenue vs Cost / Actual vs Budget)
  4. **Executive Polar Area Distribution**
  5. **Ranked Horizontal Bar Chart** (clickable cross-filter)
  6. **Seasonal / Period Breakdown Bar Chart** (clickable cross-filter)
- **Formula-Safe CSV Download**: Exports your filtered, cleaned dataset with spreadsheet formula-injection protection (`=`, `+`, `-`, `@` prefixed cleanly).

## Step 4: Reversible Data Studio (`Data Studio (ETL Backend)`)
- Displays an **8-card Corrections Audit** showing exact counts of duplicates removed, totals stripped, currency cells fixed, missing cells repaired, and features engineered.
- Shows a full **Column-by-Column Quality Scorecard** table.
- Lets the user **toggle any cleaning rule on or off** and click **Re-Run 8-Step Cleaning & Update Dashboard** to re-process the untouched raw file on the spot.

## Step 5: Expanded `Ask Questions` Hub
- Answers plain-English questions directly from the active filtered data:
  - *"What corrections did you make to my data?"* → Full ETL audit breakdown.
  - *"How is my column quality?"* → Per-column completeness & fixes grid.
  - *"What is my company selling?"* → Actual products/categories with top-seller praise and slow-mover bundling solutions.
  - *"What am I doing well and where are the problems?"* → Praises strong metrics and lists concrete fixes for any Danger/Watch Zone.
  - Any specific numeric column name → Computes exact live total and average.

## Step 6: `Health, Praise & Solutions` & `EOQ & Profit Planner`
- Dedicated executive health cards pairing praise for strong wins with actionable fixes.
- Interactive **Economic Order Quantity (EOQ)** calculator (ideal restock batch size, orders/year, combined ordering + holding cost) and **What-If Profit Planner** (interactive sliders for Price, Volume, Direct Cost, and Overhead/Ad Spend).
