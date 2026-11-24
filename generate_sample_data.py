#!/usr/bin/env python3
"""
Generate all 8 Mandatory Adversarial Test Datasets, Excel Ground-Truth Benchmark
Workbooks, Phase 2 Multi-Table/Departmental Datasets, and One-Click Demo Datasets
for Project NEXUS V2.0.
"""
import os
import math
import random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter

SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")
ADV_DIR = os.path.join(SAMPLE_DIR, "adversarial")
DEMO_DIR = os.path.join(SAMPLE_DIR, "demo")
BENCH_DIR = os.path.join(SAMPLE_DIR, "benchmarks")
P2_DIR = os.path.join(SAMPLE_DIR, "phase2")

for d in [SAMPLE_DIR, ADV_DIR, DEMO_DIR, BENCH_DIR, P2_DIR]:
    os.makedirs(d, exist_ok=True)


def make_clean_sales(n_orders=250):
    """Dataset 1: Clean Baseline Sales (Line-item grain with multi-line orders)."""
    regions = ["North", "South", "East", "West"]
    channels = ["Direct", "Partner", "Online", "Marketplace"]
    categories = ["Electronics", "Apparel", "Home & Living", "Accessories"]
    products = {
        "Electronics": [("Smart Watch Pro", 4500, 2600), ("Wireless Earbuds", 2200, 1100)],
        "Apparel": [("Performance Jacket", 3200, 1400), ("Merino Tee", 1200, 480)],
        "Home & Living": [("Air Purifier Mini", 6800, 3900), ("Ceramic Lamp", 1800, 820)],
        "Accessories": [("Leather Backpack", 3600, 1650), ("USB-C Hub", 1500, 620)],
    }
    start = datetime(2025, 4, 1)
    rows = []
    line_id = 1
    for i in range(1, n_orders + 1):
        order_id = f"ORD-{10000 + i}"
        order_date = start + timedelta(days=int(rng.integers(0, 365)))
        cust_id = f"CUST-{int(rng.integers(1, 95)):04d}"
        region = regions[int(rng.integers(0, len(regions)))]
        channel = channels[int(rng.integers(0, len(channels)))]
        n_lines = int(rng.choice([1, 1, 2, 2, 3]))
        for _ in range(n_lines):
            cat = categories[int(rng.integers(0, len(categories)))]
            prod_name, base_price, base_cost = products[cat][int(rng.integers(0, 2))]
            qty = int(rng.integers(1, 6))
            disc_pct = float(rng.choice([0.0, 0.0, 0.05, 0.10, 0.15]))
            gross_rev = round(base_price * qty, 2)
            disc_amt = round(gross_rev * disc_pct, 2)
            net_rev = round(gross_rev - disc_amt, 2)
            cogs = round(base_cost * qty, 2)
            rows.append({
                "line_id": f"LN-{line_id:05d}",
                "order_id": order_id,
                "order_date": order_date.strftime("%Y-%m-%d"),
                "customer_id": cust_id,
                "region": region,
                "channel": channel,
                "product_category": cat,
                "product_name": prod_name,
                "quantity": qty,
                "unit_price": base_price,
                "discount_amount": disc_amt,
                "revenue": net_rev,
                "cogs": cogs,
                "order_status": "Completed",
            })
            line_id += 1
    return pd.DataFrame(rows)


def make_clean_finance():
    """Clean Monthly Financial P&L with Budget vs Actual across 12 fiscal months."""
    months = pd.date_range("2025-04-01", periods=12, freq="MS")
    accounts = [
        ("Product Sales", "Revenue", 850000),
        ("Subscription Services", "Revenue", 320000),
        ("Direct Materials & Hosting", "COGS", 390000),
        ("Fulfillment & Logistics", "COGS", 115000),
        ("Payroll & Benefits", "OpEx", 265000),
        ("Sales & Marketing", "OpEx", 125000),
        ("Cloud & Software", "OpEx", 58000),
        ("Rent & General Admin", "OpEx", 62000),
    ]
    rows = []
    for idx, dt in enumerate(months):
        growth = 1.0 + 0.022 * idx
        for acct, cat, base in accounts:
            budget = round(base * growth, 2)
            noise = float(rng.normal(1.0, 0.06))
            actual = round(budget * noise, 2)
            rows.append({
                "period_date": dt.strftime("%Y-%m-%d"),
                "fiscal_quarter": f"Q{(idx // 3) + 1} FY26",
                "account_name": acct,
                "account_category": cat,
                "department": "Finance" if cat != "OpEx" else acct.split(" ")[0],
                "budget_amount": budget,
                "actual_amount": actual,
                "currency": "INR",
            })
    return pd.DataFrame(rows)


def generate_adversarial_suite():
    # 1. Clean Baseline
    df1 = make_clean_sales(250)
    df1.to_csv(os.path.join(ADV_DIR, "01_clean_baseline.csv"), index=False)

    # 2. Heavy Missing Values & Missing Columns (no cogs column -> Gross Margin Not Calculable)
    df2 = df1.drop(columns=["cogs"]).copy()
    mask_rev = rng.random(len(df2)) < 0.28
    mask_reg = rng.random(len(df2)) < 0.35
    df2.loc[mask_rev, "revenue"] = np.nan
    df2.loc[mask_reg, "region"] = None
    df2.to_csv(os.path.join(ADV_DIR, "02_missing_values_and_columns.csv"), index=False)

    # 3. Exact & Near Duplicates
    df3 = df1.head(120).copy()
    exact_dups = df3.iloc[:15].copy()
    near_dups = df3.iloc[15:25].copy()
    near_dups["region"] = near_dups["region"].str.lower()
    df3_out = pd.concat([df3, exact_dups, near_dups], ignore_index=True)
    df3_out.to_csv(os.path.join(ADV_DIR, "03_exact_and_near_duplicates.csv"), index=False)

    # 4. Wrong/Mixed Data Types & Currencies
    df4 = df1.head(150).copy()
    df4["revenue"] = df4["revenue"].astype(str)
    for i in range(0, 30):
        df4.loc[i, "revenue"] = f"₹{df4.loc[i, 'revenue']}"
    for i in range(30, 55):
        df4.loc[i, "revenue"] = f"${df4.loc[i, 'revenue']}"
    for i in range(55, 65):
        df4.loc[i, "revenue"] = "N/A"
    df4.loc[70:78, "order_date"] = "31/13/2025"  # invalid date
    df4.to_csv(os.path.join(ADV_DIR, "04_mixed_types_and_currencies.csv"), index=False)

    # 5. Extreme Outliers & Negative/Return/Cancelled Rows + CSV injection payload
    df5 = df1.head(180).copy()
    df5.loc[0:9, "order_status"] = "Cancelled"
    df5.loc[10:19, "order_status"] = "Returned"
    df5.loc[10:19, "revenue"] = -df5.loc[10:19, "revenue"].abs()
    df5.loc[20:24, "quantity"] = -3
    df5.loc[25, "revenue"] = 9850000.00  # extreme outlier
    df5.loc[26, "product_name"] = "=CMD|' /C calc'!A0"  # CSV formula injection test
    df5.to_csv(os.path.join(ADV_DIR, "05_outliers_returns_and_injection.csv"), index=False)

    # 6. Ambiguous Cryptic Column Headers
    df6 = df1.head(160).copy().rename(columns={
        "line_id": "LN_SEQ",
        "order_id": "ORD_REF_NO",
        "order_date": "TXN_DT",
        "customer_id": "ACCT_ID",
        "region": "GEO_ZONE",
        "channel": "SLS_CHNL",
        "product_category": "PROD_GRP",
        "product_name": "ITEM_DESC",
        "quantity": "QTY_SOLD",
        "unit_price": "LIST_PX",
        "discount_amount": "DISC_VAL",
        "revenue": "NET_REV_AMT",
        "cogs": "DIR_COST_VAL",
        "order_status": "STS_FLG",
    })
    df6.to_csv(os.path.join(ADV_DIR, "06_ambiguous_cryptic_headers.csv"), index=False)

    # 7. Messy Multi-Header Logo Rows + Bottom "Grand Total" Row (XLSX)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Monthly_Sales_Export"
    ws.append(["ACME ENTERPRISES PVT. LTD. — CONFIDENTIAL SALES LEDGER"])
    ws.append(["Generated: FY 2025-26 | Currency: INR | Prepared by Regional Ops"])
    ws.append([""])
    df7 = df1.head(100).copy()
    ws.append(list(df7.columns))
    for r in df7.itertuples(index=False):
        ws.append(list(r))
    ws.append([
        "Grand Total", "", "", "", "", "", "", "",
        int(df7["quantity"].sum()), "", round(float(df7["discount_amount"].sum()), 2),
        round(float(df7["revenue"].sum()), 2), round(float(df7["cogs"].sum()), 2), ""
    ])
    wb.save(os.path.join(ADV_DIR, "07_messy_header_and_grand_total.xlsx"))

    # 8. Stress-Test 100k-Row File (vectorized for speed & <15MB CSV)
    n = 100_000
    order_nums = rng.integers(1, 55000, size=n)
    dates = pd.to_datetime("2025-04-01") + pd.to_timedelta(rng.integers(0, 365, size=n), unit="D")
    qty = rng.integers(1, 8, size=n)
    price = rng.choice([999.0, 1499.0, 2499.0, 3999.0, 5499.0], size=n)
    disc = np.round(qty * price * rng.choice([0.0, 0.05, 0.10], size=n), 2)
    rev = np.round(qty * price - disc, 2)
    cogs = np.round(rev * rng.uniform(0.45, 0.65, size=n), 2)
    df8 = pd.DataFrame({
        "order_id": [f"O{x:06d}" for x in order_nums],
        "order_date": dates.strftime("%Y-%m-%d"),
        "customer_id": [f"C{x:05d}" for x in rng.integers(1, 8000, size=n)],
        "region": rng.choice(["North", "South", "East", "West"], size=n),
        "channel": rng.choice(["Direct", "Online", "Partner"], size=n),
        "product_category": rng.choice(["Electronics", "Apparel", "Home", "Accessories"], size=n),
        "quantity": qty,
        "unit_price": price,
        "discount_amount": disc,
        "revenue": rev,
        "cogs": cogs,
        "order_status": "Completed",
    })
    df8.to_csv(os.path.join(ADV_DIR, "08_stress_test_100k_rows.csv"), index=False)

    # Shared deterministic Finance benchmark dataset
    fin = make_clean_finance()

    # Excel Ground-Truth Benchmark Workbook with live formulas
    create_excel_benchmark(df1, fin)

    # One-Click Demo Company Datasets
    df1.to_csv(os.path.join(DEMO_DIR, "acme_retail_sales.csv"), index=False)
    fin.to_excel(os.path.join(DEMO_DIR, "apex_saas_finance.xlsx"), index=False, sheet_name="PnL_FY26")
    df6.to_csv(os.path.join(DEMO_DIR, "nova_cryptic_sales.csv"), index=False)

    # Phase 2 Datasets (Join safety + Marketing + HR + Supply Chain)
    cust_ids = sorted(df1["customer_id"].unique())
    cust_df = pd.DataFrame({
        "customer_id": cust_ids + cust_ids[:5],  # intentional duplicate keys for join validator
        "customer_name": [f"Account {c}" for c in cust_ids + cust_ids[:5]],
        "segment": rng.choice(["Enterprise", "Mid-Market", "SMB"], size=len(cust_ids) + 5),
        "city": rng.choice(["Mumbai", "Bengaluru", "Delhi", "Kolkata", "Pune"], size=len(cust_ids) + 5),
    })
    cust_df.to_csv(os.path.join(P2_DIR, "customers_with_duplicates.csv"), index=False)

    mkt_df = pd.DataFrame({
        "campaign_id": [f"CMP-{i:03d}" for i in range(1, 25)],
        "campaign_date": pd.date_range("2025-04-01", periods=24, freq="15D").strftime("%Y-%m-%d"),
        "channel": rng.choice(["Google Ads", "Meta", "LinkedIn", "Email"], size=24),
        "marketing_spend": np.round(rng.uniform(25000, 150000, size=24), 2),
        "impressions": rng.integers(50000, 500000, size=24),
        "clicks": rng.integers(1200, 18000, size=24),
        "leads": rng.integers(80, 1400, size=24),
        "conversions": rng.integers(20, 350, size=24),
        "attributed_revenue": np.round(rng.uniform(90000, 620000, size=24), 2),
    })
    mkt_df.to_csv(os.path.join(P2_DIR, "marketing_campaigns.csv"), index=False)

    hr_df = pd.DataFrame({
        "employee_id": [f"EMP-{i:04d}" for i in range(1, 61)],
        "department": rng.choice(["Sales", "Engineering", "Finance", "Operations", "HR"], size=60),
        "hire_date": (pd.to_datetime("2022-01-01") + pd.to_timedelta(rng.integers(0, 1200, size=60), unit="D")).strftime("%Y-%m-%d"),
        "employment_status": rng.choice(["Active", "Active", "Active", "Active", "Exited"], size=60),
        "annual_salary": np.round(rng.uniform(600000, 2800000, size=60), 2),
        "attendance_rate": np.round(rng.uniform(0.88, 0.99, size=60), 4),
        "time_to_hire_days": rng.integers(18, 65, size=60),
    })
    hr_df.to_csv(os.path.join(P2_DIR, "hr_workforce.csv"), index=False)

    sc_df = pd.DataFrame({
        "sku_id": [f"SKU-{i:03d}" for i in range(1, 41)],
        "supplier_name": rng.choice(["Apex Logistics", "Zenith Components", "Kaveri Supply", "Metro Freight"], size=40),
        "warehouse": rng.choice(["West Hub", "South Hub", "East Hub"], size=40),
        "on_hand_units": rng.integers(0, 1200, size=40),
        "cogs": np.round(rng.uniform(120000, 950000, size=40), 2),
        "avg_inventory_value": np.round(rng.uniform(40000, 280000, size=40), 2),
        "orders_total": rng.integers(50, 400, size=40),
        "orders_on_time": rng.integers(42, 390, size=40),
        "lead_time_days": np.round(rng.uniform(3.0, 18.0, size=40), 1),
        "defect_rate": np.round(rng.uniform(0.005, 0.045, size=40), 4),
    })
    sc_df["orders_on_time"] = np.minimum(sc_df["orders_on_time"], sc_df["orders_total"])
    sc_df.to_csv(os.path.join(P2_DIR, "supply_chain_ops.csv"), index=False)


def create_excel_benchmark(sales_df: pd.DataFrame, fin_df: pd.DataFrame):
    wb = openpyxl.Workbook()
    ws_s = wb.active
    ws_s.title = "Sales_Data"
    ws_s.append(list(sales_df.columns))
    for r in sales_df.itertuples(index=False):
        ws_s.append(list(r))

    ws_f = wb.create_sheet("Finance_Data")
    ws_f.append(list(fin_df.columns))
    for r in fin_df.itertuples(index=False):
        ws_f.append(list(r))

    ws_b = wb.create_sheet("Ground_Truth_KPIs")
    n_s = len(sales_df) + 1
    n_f = len(fin_df) + 1
    ws_b.append(["Domain", "KPI Code", "KPI Name", "Excel Formula", "Verified Expected Value"])

    total_rev = round(float(sales_df["revenue"].sum()), 2)
    distinct_orders = int(sales_df["order_id"].nunique())
    aov = round(total_rev / distinct_orders, 2)
    units = int(sales_df["quantity"].sum())
    asp = round(total_rev / units, 2)
    total_cogs = round(float(sales_df["cogs"].sum()), 2)
    gross_profit = round(total_rev - total_cogs, 2)
    gross_margin = round((gross_profit / total_rev) * 100.0, 2)

    fin_rev = round(float(fin_df.loc[fin_df["account_category"] == "Revenue", "actual_amount"].sum()), 2)
    fin_cogs = round(float(fin_df.loc[fin_df["account_category"] == "COGS", "actual_amount"].sum()), 2)
    fin_opex = round(float(fin_df.loc[fin_df["account_category"] == "OpEx", "actual_amount"].sum()), 2)
    fin_gp = round(fin_rev - fin_cogs, 2)
    fin_op = round(fin_gp - fin_opex, 2)
    fin_op_margin = round((fin_op / fin_rev) * 100.0, 2)

    benchmarks = [
        ("Sales", "SALES_TOTAL_REVENUE", "Total Revenue", f"=SUM(Sales_Data!L2:L{n_s})", total_rev),
        ("Sales", "SALES_DISTINCT_ORDERS", "Distinct Orders", f"=SUMPRODUCT(1/COUNTIF(Sales_Data!B2:B{n_s},Sales_Data!B2:B{n_s}))", distinct_orders),
        ("Sales", "SALES_AOV", "Average Order Value (AOV)", "=E2/E3", aov),
        ("Sales", "SALES_UNITS_SOLD", "Total Units Sold", f"=SUM(Sales_Data!I2:I{n_s})", units),
        ("Sales", "SALES_ASP", "Average Selling Price (ASP)", "=E2/E5", asp),
        ("Sales", "SALES_GROSS_PROFIT", "Gross Profit", f"=SUM(Sales_Data!L2:L{n_s})-SUM(Sales_Data!M2:M{n_s})", gross_profit),
        ("Sales", "SALES_GROSS_MARGIN_PCT", "Gross Margin %", "=(E7/E2)*100", gross_margin),
        ("Finance", "FIN_TOTAL_REVENUE", "P&L Revenue", f'=SUMIF(Finance_Data!D2:D{n_f},"Revenue",Finance_Data!G2:G{n_f})', fin_rev),
        ("Finance", "FIN_COGS", "P&L COGS", f'=SUMIF(Finance_Data!D2:D{n_f},"COGS",Finance_Data!G2:G{n_f})', fin_cogs),
        ("Finance", "FIN_OPEX", "P&L OpEx", f'=SUMIF(Finance_Data!D2:D{n_f},"OpEx",Finance_Data!G2:G{n_f})', fin_opex),
        ("Finance", "FIN_GROSS_PROFIT", "P&L Gross Profit", "=E9-E10", fin_gp),
        ("Finance", "FIN_OPERATING_PROFIT", "Operating Profit", "=E12-E11", fin_op),
        ("Finance", "FIN_OPERATING_MARGIN_PCT", "Operating Margin %", "=(E13/E9)*100", fin_op_margin),
    ]
    for row in benchmarks:
        ws_b.append(list(row))

    wb.save(os.path.join(BENCH_DIR, "nexus_excel_ground_truth.xlsx"))


if __name__ == "__main__":
    generate_adversarial_suite()
    print("Generated all 8 adversarial datasets, Excel ground-truth workbook, demo datasets, and Phase 2 datasets.")
