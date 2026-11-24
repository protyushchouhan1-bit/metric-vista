# Deploying METRIC VISTA to GitHub & Render (Using D: Drive Only)

Everything is pre-configured (`render.yaml`, `Procfile`, `.gitignore`, `.env.example`, `server.py`, and `requirements.txt`). Follow these exact steps on your Windows PC using **D: drive only**:

## Step 1: Extract to D: Drive
1. Download `metric-vista-github-render.zip`.
2. Extract it to `D:\metric-vista` (never touches `C:` drive).

## Step 2: Push to GitHub (PowerShell on D: Drive)
Create a new empty repository named `metric-vista` on https://github.com/new (do not initialize with README), then run:

```powershell
D:
cd D:\metric-vista
git init
git add .
git commit -m "Launch METRIC VISTA analytics dashboard and FastAPI backend"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/metric-vista.git
git push -u origin main
```

> **Security Note:** `.env` is listed in `.gitignore` so your Gemini API key is never exposed in your public GitHub repository.

## Step 3: Deploy Live on Render.com (Free Public URL)
1. Go to https://dashboard.render.com and sign in with GitHub.
2. Click **New +** -> **Blueprint** (or **Web Service**) and select your `metric-vista` repository.
3. Render automatically reads `render.yaml` (`uvicorn server:app --host 0.0.0.0 --port $PORT`).
4. When prompted for **`GEMINI_API_KEY`**, paste your Gemini API key into Render's Environment Variables panel and click **Apply / Deploy**.
5. Once live, your public link will be `https://metric-vista.onrender.com` (and you can confirm Gemini is active at `https://metric-vista.onrender.com/api/v1/ai-status`).

## Optional: Run Locally on D: Drive
```powershell
D:
cd D:\metric-vista
copy .env.example .env
# Open .env in Notepad and paste your GEMINI_API_KEY
python -m venv D:\metric-vista\.venv
D:\metric-vista\.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```
