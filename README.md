# 🚆 Rail Test Execution Dashboard

Interactive Streamlit dashboard for the 5 rail-test-execution CSVs. Upload your
CSVs, explore them across 5 dashboard tabs, and run ad-hoc SQL queries in a
built-in playground.

**Live demo**: _add your share.streamlit.app URL here after deploying_

## Features

- 📊 **Overview** — pass / fail KPIs and per-run breakdown
- 🛤️ **Plan Comparison** — exact / soft / mismatch counts across OD pairs
- 🔍 **Drill-down** — plan-by-plan view for any OD flow
- 💷 **ALF / Fares** — mileage parity scatter with reference line
- 📐 **Rules** — which soft-matching rules fired and how often
- 🛠️ **SQL Playground** — query any table with preset templates and CSV export

## Deploy to Streamlit Community Cloud (free)

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: rail test dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/rail-test-dashboard.git
git push -u origin main
```

The repo **must be public** for Streamlit Community Cloud's free tier.

### 2. Connect to Streamlit Cloud

1. Go to <https://share.streamlit.io>
2. Sign in with GitHub
3. Click **New app**
4. Pick the repo, branch `main`, main file `app.py`
5. Click **Deploy**

First build takes 2–3 minutes. You'll get a URL like
`https://YOUR_USERNAME-rail-test-dashboard.streamlit.app`.

### 3. Updating the app

Just push to `main`. Streamlit Cloud picks up changes within a minute.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at <http://localhost:8501>.

## Project layout

```
rail-test-dashboard/
├── app.py              # Streamlit entry point + SQL playground
├── schema.py           # canonical schema for the 5 tables
├── data_loader.py      # CSV → DuckDB with validation
├── dashboard.py        # KPIs, charts, drill-down rendering
├── requirements.txt    # pip dependencies (Streamlit Cloud reads this)
├── runtime.txt         # pins Python 3.11 on Streamlit Cloud
├── .streamlit/
│   └── config.toml     # theme + upload limit
└── sample_data/        # CSVs used by the "Try demo data" button
```

## Privacy / data handling

The app keeps everything in the user's browser session — uploaded CSVs are
held only in DuckDB's in-memory database that's torn down when the session
ends. Nothing is written to disk on the server. The footer in the sidebar
states this for users.

**Note**: Streamlit Community Cloud is a public-by-default platform. Anyone
with the URL can use the app. If you don't want the sample data to be
publicly visible, delete `sample_data/` from the repo before pushing.

## Customising

- **Theme**: edit colours in `.streamlit/config.toml`.
- **New chart**: add a function to `dashboard.py`, wire it into a tab in `app.py`.
- **New preset query**: add an entry to `PRESET_QUERIES` in `app.py`.
- **Schema changes**: update `schema.py` — the validation, dashboard, and
  SQL playground all read from it.

## Troubleshooting

**"Column not found" error after upload** — open the sidebar, look at the
warnings under the loaded table. If you see _"Missing expected columns"_,
the CSV doesn't match the schema (wrong delimiter, truncated file, or
wrong file uploaded). The loader auto-detects delimiters but won't
hallucinate missing columns.

**Streamlit Cloud build fails** — check the logs in the share.streamlit.io
dashboard. The two common causes are (1) the repo being private on the
free tier, and (2) `requirements.txt` listing a package that can't be
installed on Linux. The deps in this repo are all pure Python or have
manylinux wheels.

**App is slow on first load** — Streamlit Cloud apps sleep when unused.
First request after a long idle takes ~30s to wake up. After that it's
fast.
