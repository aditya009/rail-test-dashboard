# Deployment guide — Streamlit Community Cloud

This walks you through getting the dashboard live in ~5 minutes.

## Prerequisites

- A GitHub account
- Git installed locally
- The contents of this zip extracted somewhere

## Step 1 — Create a GitHub repository

1. Go to <https://github.com/new>
2. Name it something like `rail-test-dashboard`
3. **Important**: keep it **Public**. Streamlit Community Cloud's free tier
   only supports public repos.
4. Don't initialize with a README — we'll push our own.
5. Click **Create repository**

GitHub will show you setup commands. Use the "push an existing repository" ones.

## Step 2 — Push the code

Open a terminal in the unzipped folder:

```bash
git init
git add .
git commit -m "Rail test execution dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/rail-test-dashboard.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

If `git push` asks for credentials and password authentication fails, use a
[Personal Access Token](https://github.com/settings/tokens) instead of your
account password (Settings → Developer settings → Personal access tokens →
classic, with the `repo` scope).

## Step 3 — Connect to Streamlit Community Cloud

1. Go to <https://share.streamlit.io>
2. Click **Continue with GitHub** and authorise the Streamlit app
3. Click **Create app** (or **New app**)
4. Choose **Deploy a public app from GitHub**
5. Fill in:
   - **Repository**: `YOUR_USERNAME/rail-test-dashboard`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: keep the default or pick a custom subdomain
6. Click **Deploy**

You'll see build logs streaming. First deploy takes 2–4 minutes while it
installs `duckdb`, `pandas`, `plotly`, and `streamlit`.

When it's done, you'll have a URL like
`https://your-username-rail-test-dashboard.streamlit.app`.

## Step 4 — Test it

Open the URL. You should see the welcome screen. Either:

- Click **Try demo data** in the sidebar to load the bundled CSVs, or
- Upload your own CSVs.

## Step 5 — Share the link

Just hand the URL to your team. No login is needed (free tier is public).

## Updating the deployed app

Any time you change a file locally:

```bash
git add .
git commit -m "describe what changed"
git push
```

Streamlit Cloud detects the push and redeploys within ~1 minute. The app
itself just reloads — users see the new version on next interaction.

## Things to keep in mind

- **Public access**: anyone with the URL can use the app and see whatever
  is bundled in `sample_data/`. Remove that folder from the repo if you
  don't want it public.
- **Upload limit**: configured to 50 MB per file in `.streamlit/config.toml`.
  Bump it if you have bigger CSVs (Streamlit Cloud allows up to 200 MB).
- **Memory**: free tier gives ~1 GB RAM. Your CSVs are <60 KB total so
  you're nowhere near limits.
- **Idle sleep**: if no one visits for a few days, the app sleeps. First
  request after sleep takes ~30s to wake up. After that it's instant.

## Troubleshooting deployment

| Symptom | Likely cause | Fix |
|---|---|---|
| Build fails with `ModuleNotFoundError` | Missing dep | Add it to `requirements.txt`, push |
| Build fails on `duckdb` | Old Python | `runtime.txt` should pin `3.11` — verify it's at the repo root |
| App shows "Error 404" | Wrong main file path | In app settings, confirm it's `app.py` not `streamlit_app.py` |
| Upload fails silently | File >50 MB | Bump `maxUploadSize` in `.streamlit/config.toml` |
| Charts don't render | Plotly version mismatch | `pip install -r requirements.txt` locally to check it works there first |

## Removing the deployment

Go to <https://share.streamlit.io>, click your app, click **Settings** in
the bottom-right, then **Delete app**. Repo stays on GitHub.
