"""
Streamlit Cloud entry point for the Rail Test Dashboard.

Public, no LLM. Run locally with:
    streamlit run app.py
Deploy by pushing to GitHub and connecting at https://share.streamlit.io
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import dashboard
from data_loader import (
    describe_table,
    list_loaded_tables,
    load_uploads_to_duckdb,
    run_sql,
    table_to_df,
)
from schema import DISPLAY_NAMES, SCHEMA


st.set_page_config(
    page_title="Rail Test Dashboard",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Session state ----------
if "loaded_report" not in st.session_state:
    st.session_state.loaded_report = {}


# ---------- Helpers ----------

class _LocalUpload:
    """Mimics a Streamlit UploadedFile for the demo-data loader path."""
    def __init__(self, path: Path):
        self.name = path.name
        self._bytes = path.read_bytes()
        self._pos = 0
    def read(self, n=-1):
        if n < 0:
            chunk = self._bytes[self._pos:]
            self._pos = len(self._bytes)
            return chunk
        chunk = self._bytes[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk
    def seek(self, pos):
        self._pos = pos


def _load_demo_data() -> None:
    """Load CSVs from sample_data/ if present (for the public demo)."""
    sample_dir = Path(__file__).parent / "sample_data"
    if not sample_dir.exists():
        st.error("No sample_data/ directory in the repo.")
        return
    csv_paths = sorted(sample_dir.glob("*.csv"))
    if not csv_paths:
        st.error("No CSVs found in sample_data/.")
        return
    files = [_LocalUpload(p) for p in csv_paths]
    with st.spinner("Loading demo data…"):
        st.session_state.loaded_report = load_uploads_to_duckdb(files)


# ---------- Sidebar ----------

with st.sidebar:
    st.title("🚆 Rail Test Dashboard")
    st.caption("Upload your 5 test-execution CSVs to explore them as an interactive dashboard.")

    uploaded = st.file_uploader(
        "Upload CSVs",
        type=["csv"],
        accept_multiple_files=True,
        help="TestExecution / TestExecutionRule / TestPlanComparisonResult / "
             "TestPlanComparisonDetail / TestAlfComparisonResult",
    )
    col_a, col_b = st.columns(2)
    if uploaded and col_a.button("Load", type="primary", use_container_width=True):
        with st.spinner("Loading…"):
            st.session_state.loaded_report = load_uploads_to_duckdb(uploaded)
    if col_b.button("Try demo data", use_container_width=True):
        _load_demo_data()

    loaded = list_loaded_tables()
    if loaded:
        st.divider()
        st.markdown("**Loaded tables**")
        for t in loaded:
            info = st.session_state.loaded_report.get(t, {})
            rows = info.get("rows", "?")
            cols = info.get("cols", "?")
            label = f"✅ {DISPLAY_NAMES.get(t, t)}"
            sub = f"{rows:,} rows · {cols} cols" if isinstance(rows, int) else ""
            st.markdown(label)
            if sub:
                st.caption(sub)
            for w in info.get("warnings", []):
                st.caption(f"⚠️ {w}")
        unmatched = [k for k in st.session_state.loaded_report if k.startswith("_unmatched")]
        for k in unmatched:
            st.caption(f"⚠️ {st.session_state.loaded_report[k]['source_filename']}: skipped, no schema match")

    exec_filter = None
    if "TestExecution" in loaded:
        st.divider()
        ids = table_to_df("TestExecution")["execCombinationId"].dropna().unique().tolist()
        exec_filter = st.multiselect("Filter by execution", ids, default=ids)

    st.divider()
    st.caption(
        "🔒 Data lives in your browser session only — nothing is stored on the server. "
        "Refresh to clear."
    )


# ---------- Welcome state ----------

if not list_loaded_tables():
    st.title("Rail Test Execution Dashboard")
    st.markdown(
        """
        Upload the 5 CSVs from the left sidebar to begin, or click **Try demo data**
        to explore with a sample dataset.

        ### What this dashboard does
        - Cross-references **expected vs actual** rail journey plans across 5 related tables
        - Shows pass / fail rates per test execution
        - Drills down to individual plan-level comparison
        - Highlights ALF / fares mileage mismatches
        - Tracks which soft-matching rules fired most often
        """
    )

    with st.expander("📋 Expected schema (the 5 CSVs)"):
        for table, spec in SCHEMA.items():
            st.markdown(f"### {DISPLAY_NAMES.get(table, table)} — `{table}.csv`")
            st.caption(spec["description"])
            cols_df = [{"column": c, "description": d} for c, d in spec["columns"].items()]
            st.dataframe(cols_df, hide_index=True, use_container_width=True)
    st.stop()


# ---------- Main area ----------

st.title("Rail Test Execution Dashboard")
dashboard.render_kpis(exec_filter)

tab_overview, tab_plan, tab_detail, tab_alf, tab_rules, tab_sql = st.tabs([
    "📊 Overview",
    "🛤️ Plan Comparison",
    "🔍 Drill-down",
    "💷 ALF / Fares",
    "📐 Rules",
    "🛠️ SQL Playground",
])

with tab_overview:
    if "TestExecution" in list_loaded_tables():
        dashboard.render_overview(exec_filter)
    else:
        st.warning("Upload TestExecution.csv to see the overview.")

with tab_plan:
    if "TestPlanComparisonResult" in list_loaded_tables():
        dashboard.render_plan_comparison(exec_filter)
    else:
        st.warning("Upload TestPlanComparisonResult.csv to see plan comparison.")

with tab_detail:
    if {"TestPlanComparisonResult", "TestPlanComparisonDetail"}.issubset(list_loaded_tables()):
        dashboard.render_plan_detail(exec_filter)
    else:
        st.warning("Upload both TestPlanComparisonResult.csv and TestPlanComparisonDetail.csv for drill-down.")

with tab_alf:
    if "TestAlfComparisonResult" in list_loaded_tables():
        dashboard.render_alf(exec_filter)
    else:
        st.warning("Upload TestAlfComparisonResult.csv to see ALF comparison.")

with tab_rules:
    if "TestExecutionRule" in list_loaded_tables():
        dashboard.render_rules(exec_filter)
    else:
        st.warning("Upload TestExecutionRule.csv to see rule application.")


# ---------- SQL Playground tab ----------

PRESET_QUERIES = {
    "— pick a preset —": "",
    "Pass rate per execution": """\
SELECT
    execCombinationId,
    totalOdCount,
    passedOdCount,
    failedPlanOdCount,
    failedAlfOdCount,
    ROUND(passedOdCount * 100.0 / NULLIF(totalOdCount, 0), 1) AS passRatePct
FROM TestExecution
ORDER BY passRatePct DESC""",
    "Top 20 OD pairs with most mismatches": """\
SELECT
    execCombinationId, originNlc, destinationNlc, journeyDate,
    expTotalPlanCount, actTotalPlanCount,
    expDistinctPlanCount AS expectedOnly,
    actDistinctPlanCount AS actualOnly
FROM TestPlanComparisonResult
WHERE expDistinctPlanCount + actDistinctPlanCount > 0
ORDER BY (expDistinctPlanCount + actDistinctPlanCount) DESC
LIMIT 20""",
    "Soft rule application totals": """\
SELECT
    ruleKey,
    SUM(appliedOdCount) AS odTotal,
    SUM(appliedPlanCount) AS planTotal,
    COUNT(DISTINCT execCombinationId) AS runs
FROM TestExecutionRule
GROUP BY ruleKey
ORDER BY planTotal DESC""",
    "ALF mileage mismatches": """\
SELECT
    execCombinationId, originNlc, destinationNlc, ticketType,
    expOperatingMiles, actOperatingMiles,
    (actOperatingMiles - expOperatingMiles) AS mileageDelta
FROM TestAlfComparisonResult
WHERE expOperatingMiles <> actOperatingMiles
ORDER BY ABS(actOperatingMiles - expOperatingMiles) DESC""",
    "Plans only in expected (per execution)": """\
SELECT
    execCombinationId,
    COUNT(*) AS expectedOnlyPlans
FROM TestPlanComparisonDetail
WHERE status = 'Expected Only'
GROUP BY execCombinationId
ORDER BY expectedOnlyPlans DESC""",
    "Reconciliation check (counts should add up)": """\
SELECT
    execCombinationId,
    totalOdCount,
    passedOdCount + failedPlanOdCount + failedAlfOdCount AS sumOfParts,
    totalOdCount - (passedOdCount + failedPlanOdCount + failedAlfOdCount) AS gap
FROM TestExecution""",
}


with tab_sql:
    st.subheader("Write your own SQL")
    st.caption(
        "Query any of the loaded tables. Read-only DuckDB — only SELECT statements run. "
        "Use the presets to get started."
    )

    preset = st.selectbox("Preset", list(PRESET_QUERIES.keys()))
    default_sql = PRESET_QUERIES.get(preset, "") or "SELECT * FROM TestExecution LIMIT 10"
    sql = st.text_area("SQL", value=default_sql, height=200, key=f"sql_input_{preset}")

    cols = st.columns([1, 1, 4])
    run_clicked = cols[0].button("▶ Run", type="primary")
    cols[1].markdown("")

    if run_clicked:
        upper = sql.strip().upper()
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            st.error("Only SELECT or WITH statements are allowed.")
        else:
            try:
                with st.spinner("Running…"):
                    df_result = run_sql(sql)
                st.success(f"{len(df_result):,} rows")
                st.dataframe(df_result, use_container_width=True, hide_index=True)
                csv_bytes = df_result.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "💾 Download as CSV",
                    csv_bytes,
                    file_name="query_result.csv",
                    mime="text/csv",
                )
            except Exception as exc:
                st.error(f"Query failed: {exc}")

    with st.expander("🔎 Available tables"):
        for t in list_loaded_tables():
            cols_here = describe_table(t)
            st.markdown(f"**{t}** — {len(cols_here)} columns")
            st.caption(", ".join(cols_here))
