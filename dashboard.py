"""
Dashboard rendering. All chart functions take a DuckDB connection (implicit
via data_loader.run_sql) and a set of filter values, then emit Streamlit UI.

Kept separate from app.py so the entry file stays a thin orchestrator.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import run_sql, list_loaded_tables


# ---------- KPIs ----------

def _safe_scalar(sql: str, default=0):
    try:
        df = run_sql(sql)
        if df.empty:
            return default
        val = df.iloc[0, 0]
        return default if pd.isna(val) else val
    except Exception:
        return default


def render_kpis(exec_filter: list[str] | None = None) -> None:
    """Top-of-page KPI tiles. exec_filter limits to selected execCombinationIds."""
    where = ""
    if exec_filter:
        ids = ", ".join(f"'{e}'" for e in exec_filter)
        where = f"WHERE execCombinationId IN ({ids})"

    cols = st.columns(5)
    total_runs = _safe_scalar(f"SELECT COUNT(*) FROM TestExecution {where}")
    total_ods = _safe_scalar(f"SELECT SUM(totalOdCount) FROM TestExecution {where}")
    passed = _safe_scalar(f"SELECT SUM(passedOdCount) FROM TestExecution {where}")
    failed_plan = _safe_scalar(f"SELECT SUM(failedPlanOdCount) FROM TestExecution {where}")
    failed_alf = _safe_scalar(f"SELECT SUM(failedAlfOdCount) FROM TestExecution {where}")

    pass_rate = (passed / total_ods * 100) if total_ods else 0

    cols[0].metric("Test runs", f"{int(total_runs):,}")
    cols[1].metric("Total ODs", f"{int(total_ods):,}")
    cols[2].metric("Pass rate", f"{pass_rate:.1f}%")
    cols[3].metric("Plan failures", f"{int(failed_plan):,}")
    cols[4].metric("ALF failures", f"{int(failed_alf):,}")


# ---------- Overview tab ----------

def render_overview(exec_filter: list[str] | None = None) -> None:
    where = ""
    if exec_filter:
        ids = ", ".join(f"'{e}'" for e in exec_filter)
        where = f"WHERE execCombinationId IN ({ids})"

    st.subheader("Test executions")
    df = run_sql(f"""
        SELECT execCombinationId, expRunId, actRunId, status,
               totalOdCount, passedOdCount, failedPlanOdCount, failedAlfOdCount,
               ROUND(passedOdCount * 100.0 / NULLIF(totalOdCount, 0), 1) AS passRatePct,
               durationTime, createdAt
        FROM TestExecution {where}
        ORDER BY createdAt DESC
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if df.empty:
        return

    left, right = st.columns(2)

    with left:
        st.subheader("Pass / fail breakdown per run")
        long = df.melt(
            id_vars=["execCombinationId"],
            value_vars=["passedOdCount", "failedPlanOdCount", "failedAlfOdCount"],
            var_name="Outcome", value_name="OD count",
        )
        outcome_labels = {
            "passedOdCount": "Passed",
            "failedPlanOdCount": "Plan failure",
            "failedAlfOdCount": "ALF failure",
        }
        long["Outcome"] = long["Outcome"].map(outcome_labels)
        fig = px.bar(
            long, x="execCombinationId", y="OD count", color="Outcome",
            color_discrete_map={"Passed": "#2ecc71", "Plan failure": "#e74c3c", "ALF failure": "#f39c12"},
            barmode="stack",
        )
        fig.update_layout(xaxis_tickangle=-45, height=380, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Duration vs OD count")
        fig = px.scatter(
            df, x="totalOdCount", y="durationTime",
            color="status", hover_data=["execCombinationId"],
            labels={"totalOdCount": "Total ODs", "durationTime": "Duration (s)"},
        )
        fig.update_layout(height=380, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)


# ---------- Plan comparison tab ----------

def render_plan_comparison(exec_filter: list[str] | None = None) -> None:
    where = ""
    if exec_filter:
        ids = ", ".join(f"'{e}'" for e in exec_filter)
        where = f"WHERE execCombinationId IN ({ids})"

    st.subheader("Match rates")
    rates = run_sql(f"""
        SELECT
            execCombinationId,
            SUM(exactMatchPlanCount) AS exactMatch,
            SUM(softMatchPlanCount) AS softMatch,
            SUM(expDistinctPlanCount) AS expectedOnly,
            SUM(actDistinctPlanCount) AS actualOnly
        FROM TestPlanComparisonResult {where}
        GROUP BY execCombinationId
        ORDER BY execCombinationId
    """)
    if rates.empty:
        st.info("No plan comparison rows for this filter.")
        return

    long = rates.melt(id_vars=["execCombinationId"], var_name="Type", value_name="Plans")
    fig = px.bar(
        long, x="execCombinationId", y="Plans", color="Type", barmode="stack",
        color_discrete_map={
            "exactMatch": "#27ae60",
            "softMatch": "#3498db",
            "expectedOnly": "#e67e22",
            "actualOnly": "#9b59b6",
        },
    )
    fig.update_layout(height=380, xaxis_tickangle=-45, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top OD pairs with most mismatches")
    # Build combined WHERE: the mismatch condition is always there, the
    # execution filter is optional. Combining into one WHERE clause avoids
    # the double-WHERE syntax error that occurs when both apply.
    extra_filter = ""
    if exec_filter:
        ids = ", ".join(f"'{e}'" for e in exec_filter)
        extra_filter = f"AND execCombinationId IN ({ids})"
    top = run_sql(f"""
        SELECT
            execCombinationId, originNlc, destinationNlc, journeyDate,
            expTotalPlanCount, actTotalPlanCount,
            expDistinctPlanCount AS expectedOnly,
            actDistinctPlanCount AS actualOnly,
            (expDistinctPlanCount + actDistinctPlanCount) AS totalMismatches
        FROM TestPlanComparisonResult
        WHERE (expDistinctPlanCount + actDistinctPlanCount) > 0 {extra_filter}
        ORDER BY totalMismatches DESC
        LIMIT 50
    """)
    st.dataframe(top, use_container_width=True, hide_index=True)


# ---------- Plan detail drill-down ----------

def render_plan_detail(exec_filter: list[str] | None = None) -> None:
    st.subheader("Plan detail drill-down")

    flows = run_sql("""
        SELECT DISTINCT execCombinationId, planFlowId, originNlc, destinationNlc, journeyDate
        FROM TestPlanComparisonResult
        ORDER BY execCombinationId, planFlowId
    """)
    if exec_filter:
        flows = flows[flows["execCombinationId"].isin(exec_filter)]
    if flows.empty:
        st.info("Load TestPlanComparisonResult to enable drill-down.")
        return

    flows["label"] = flows.apply(
        lambda r: f"{r['execCombinationId']} · {int(r['originNlc'])}→{int(r['destinationNlc'])} · {r['journeyDate']}",
        axis=1,
    )
    pick = st.selectbox("Pick an OD flow", flows["label"].tolist())
    chosen = flows[flows["label"] == pick].iloc[0]

    detail = run_sql(f"""
        SELECT planId, status, expDepartureTime, expArrivalTime, expInterchange,
               actDepartureTime, actArrivalTime, actInterchange, soft_rule_key
        FROM TestPlanComparisonDetail
        WHERE execCombinationId = '{chosen['execCombinationId']}'
          AND planFlowId = {int(chosen['planFlowId'])}
        ORDER BY planId
    """)

    if detail.empty:
        st.info("No detail rows match this flow.")
        return

    status_counts = detail["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig = px.pie(status_counts, values="count", names="status", hole=0.4)
    fig.update_layout(height=300, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(detail, use_container_width=True, hide_index=True)


# ---------- ALF tab ----------

def render_alf(exec_filter: list[str] | None = None) -> None:
    where = ""
    if exec_filter:
        ids = ", ".join(f"'{e}'" for e in exec_filter)
        where = f"WHERE execCombinationId IN ({ids})"

    summary = run_sql(f"""
        SELECT
            execCombinationId,
            COUNT(*) AS alfFlows,
            SUM(exactMatchPcCount) AS exactMatch,
            SUM(softMatchPcCount) AS softMatch,
            SUM(expDistinctPcCount) AS expectedOnly,
            SUM(actDistinctPcCount) AS actualOnly
        FROM TestAlfComparisonResult {where}
        GROUP BY execCombinationId
        ORDER BY execCombinationId
    """)
    if summary.empty:
        st.info("No ALF comparison rows for this filter.")
        return

    st.subheader("ALF match summary")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Mileage parity")
    miles = run_sql(f"""
        SELECT execCombinationId, originNlc, destinationNlc, ticketType,
               expOperatingMiles, actOperatingMiles, expTicketMiles, actTicketMiles
        FROM TestAlfComparisonResult {where}
    """)
    fig = px.scatter(
        miles, x="expOperatingMiles", y="actOperatingMiles",
        color="execCombinationId",
        hover_data=["originNlc", "destinationNlc", "ticketType"],
    )
    max_mile = max(miles["expOperatingMiles"].max() or 0, miles["actOperatingMiles"].max() or 0)
    if max_mile > 0:
        fig.add_shape(type="line", x0=0, y0=0, x1=max_mile, y1=max_mile,
                      line=dict(dash="dash", color="grey"))
    fig.update_layout(height=420, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ---------- Rules tab ----------

def render_rules(exec_filter: list[str] | None = None) -> None:
    where = ""
    if exec_filter:
        ids = ", ".join(f"'{e}'" for e in exec_filter)
        where = f"WHERE execCombinationId IN ({ids})"

    rules = run_sql(f"""
        SELECT ruleKey,
               SUM(appliedOdCount) AS odTotal,
               SUM(appliedPlanCount) AS planTotal,
               COUNT(DISTINCT execCombinationId) AS runs
        FROM TestExecutionRule {where}
        GROUP BY ruleKey
        ORDER BY planTotal DESC
    """)
    if rules.empty:
        st.info("No rule rows for this filter.")
        return

    st.subheader("Soft-rule application frequency")
    rules["ruleShort"] = rules["ruleKey"].str.slice(0, 60) + "…"
    fig = px.bar(rules, x="planTotal", y="ruleShort", orientation="h",
                 hover_data=["ruleKey", "odTotal", "runs"])
    fig.update_layout(height=max(300, 28 * len(rules)), margin=dict(t=20, b=10),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(rules.drop(columns="ruleShort"), use_container_width=True, hide_index=True)
