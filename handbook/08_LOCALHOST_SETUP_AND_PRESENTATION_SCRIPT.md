# 08 — Localhost Setup Guide & 2-Minute Explanation Script

## 1. How to Run on Localhost (`http://localhost:8000`) in 1 Click

### On Windows
1. Unzip `enterprise-analytics-complete.zip` anywhere on your computer (for example, Desktop or Documents).
2. Open the unzipped folder and **double-click `run_local.bat`**.
3. Wait a few seconds while it sets up Python and starts the server.
4. Your browser will automatically open **`http://localhost:8000`**!
   - Dashboard & 8-Step Data Studio: **`http://localhost:8000`**
   - Interactive Python API Explorer: **`http://localhost:8000/docs`**

### On macOS / Linux
```bash
cd enterprise-analytics-complete
chmod +x run_local.sh
./run_local.sh
```
Then open **`http://localhost:8000`** in your browser.

### Manual Command (If you already have Python installed)
```bash
pip install -r requirements.txt
python server.py
```

---

## 2. Ready-to-Use 2-Minute Pitch Script (For Interviews, Clients, or Explaining to Any Person)
> "Small and medium businesses run their operations across messy Excel and CSV spreadsheets—full of duplicate rows, mixed currency symbols, missing values, and accidental Grand Total rows. I built an end-to-end **Enterprise Analytics & Data Studio** that solves this with zero coding required.
>
> When a user uploads any Excel (`.xlsx`, `.xls`) or CSV file—up to **1,00,000 rows (1 Lakh)**—the platform runs a live **8-step automated data processing pipeline**: Business Understanding, Data Collection, Data Cleaning, Exploratory Analysis, Feature Engineering, Modeling, Evaluation, and Deployment. It automatically removes duplicates, strips Grand Total rows, cleans broken currency formats, repairs missing cells, and scores every column's quality.
>
> Immediately after, it builds a **corporate off-white interactive dashboard** with six vibrant charts, dynamic slicers, smart adaptive animations, an **Economic Order Quantity (EOQ) & Profit Planner**, **Safe Zone / Danger Zone** alerts, and a plain-English **Ask Questions** hub that explains what the business is selling, praises strong metrics, gives actionable solutions, and lists every exact cleaning correction made. If the user disagrees with any automated fix, they can open **Data Studio (ETL Backend)**, toggle cleaning rules off, and re-process the raw file instantly.
>
> Under the hood, it's backed by a framework-agnostic Python analytical core (`Pandas`, `PyArrow`, `DuckDB`, `OpenPyXL`, `FastAPI`), verified by a **6-layer automated test suite** (17/17 tests passing), achieving **0.00 variance against hand-verified Excel formulas** and processing **100,000 rows in 1.56 seconds at 296 MB RAM**."
