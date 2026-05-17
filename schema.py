"""
Schema definitions for the 5 test-execution CSV tables.

Used for:
  1. Validating uploads (expected columns + dtypes)
  2. Loading into DuckDB with predictable table names
  3. Building rich context for the LLM so it can write correct SQL

The `description` and `column_notes` fields are what the LLM sees when it
generates SQL, so keep them informative.
"""

SCHEMA = {
    "TestExecution": {
        "file_hint": "TestExecution.csv",
        "primary_key": ["execCombinationId"],
        "description": (
            "Master record for each test run. One row per execCombinationId. "
            "Tracks counts, duration, status, and timestamps of a full plan/ALF "
            "comparison run between an expected dataset (expRunId) and actual "
            "run (actRunId)."
        ),
        "columns": {
            "execCombinationId": "TEXT — Primary key. Format like '13_DEC25_132'. Links to all other tables.",
            "testExecutionId":   "INTEGER — Numeric internal id of the execution.",
            "expRunId":          "TEXT — Identifier of the expected/baseline run (e.g. 'DEC25').",
            "actRunId":          "INTEGER — Numeric id of the actual run being compared.",
            "durationTime":      "DOUBLE — Total run duration (seconds).",
            "executionCount":    "INTEGER — Number of times this execution has been run.",
            "totalOdCount":      "INTEGER — Total origin-destination pairs in the test.",
            "failedPlanOdCount": "INTEGER — OD pairs where the plan comparison failed.",
            "failedAlfOdCount":  "INTEGER — OD pairs where the ALF (fares) comparison failed.",
            "passedOdCount":     "INTEGER — OD pairs that passed all checks.",
            "processedOdCount":  "INTEGER — OD pairs processed so far (= passed + failedPlan + failedAlf in a complete run).",
            "latestProcessedBatch": "INTEGER — Last completed batch index.",
            "batchSize":         "INTEGER — Number of ODs per batch.",
            "status":            "TEXT — 'DONE', 'RUNNING', 'FAILED', etc.",
            "modifiedAt":        "TIMESTAMP — Last update time (UTC).",
            "createdAt":         "TIMESTAMP — Creation time (UTC).",
            "errorMessage":      "TEXT — Error if the run failed, else NULL.",
        },
    },

    "TestExecutionRule": {
        "file_hint": "TestExecutionRule.csv",
        "primary_key": ["execCombinationId", "ruleKey"],
        "description": (
            "Soft-matching rules that were applied during a given execution. "
            "A 'soft match' is when expected vs actual data agree under a rule "
            "(e.g. 'departure/arrival times match regardless of change location'). "
            "Each row tells you a rule and how many ODs/plans it applied to."
        ),
        "columns": {
            "execCombinationId": "TEXT — Foreign key → TestExecution.execCombinationId.",
            "ruleKey":           "TEXT — Snake_case identifier of the soft-match rule.",
            "appliedOdCount":    "INTEGER — Number of ODs the rule fired on.",
            "appliedPlanCount":  "INTEGER — Number of individual plans the rule fired on.",
            "modifiedAt":        "TIMESTAMP — Last update time (UTC).",
            "createdAt":         "TIMESTAMP — Creation time (UTC).",
        },
    },

    "TestPlanComparisonResult": {
        "file_hint": "TestPlanComparisonResult.csv",
        "primary_key": ["execCombinationId", "planFlowId"],
        "description": (
            "Per origin-destination (OD) summary of journey-plan comparison. "
            "Compares expected plan counts against actual, broken into exact "
            "matches, soft matches, and filtered-out plans. One row per OD-day."
        ),
        "columns": {
            "execCombinationId":       "TEXT — Foreign key → TestExecution.",
            "planFlowId":              "INTEGER — Unique id for an OD-journeyDate combination.",
            "originNlc":               "INTEGER — UK National Location Code of the origin station.",
            "destinationNlc":          "INTEGER — UK NLC of the destination station.",
            "routeCode":               "INTEGER — Fare route code (0 = any-permitted).",
            "journeyDate":             "DATE — Date of the journey (YYYY-MM-DD).",
            "expTotalPlanCount":       "INTEGER — Total plans in the expected dataset for this OD.",
            "actTotalPlanCount":       "INTEGER — Total plans in the actual dataset for this OD.",
            "exactMatchPlanCount":     "INTEGER — Plans that matched exactly between expected and actual.",
            "softMatchPlanCount":      "INTEGER — Plans that matched under a soft rule.",
            "expFilteredOutPlanCount": "INTEGER — Expected plans filtered out (not compared).",
            "actFilteredOutPlanCount": "INTEGER — Actual plans filtered out.",
            "expDistinctPlanCount":    "INTEGER — Expected plans with no actual counterpart (= 'Expected Only').",
            "actDistinctPlanCount":    "INTEGER — Actual plans with no expected counterpart (= 'Actual Only').",
        },
    },

    "TestPlanComparisonDetail": {
        "file_hint": "TestPlanComparisonDetail.csv",
        "primary_key": ["execCombinationId", "planFlowId", "planId", "status"],
        "description": (
            "Plan-by-plan detail rows backing TestPlanComparisonResult. Each "
            "row is one journey plan. The `status` column tells you whether "
            "the plan appeared in expected only, actual only, was an exact "
            "match, or a soft match. expChangeAt and actChangeAt are JSON "
            "strings listing interchange NLCs."
        ),
        "columns": {
            "execCombinationId": "TEXT — Foreign key → TestExecution.",
            "planFlowId":        "INTEGER — Foreign key → TestPlanComparisonResult.planFlowId.",
            "planId":            "INTEGER — Plan index within the flow.",
            "expArrivalTime":    "TIME — Expected arrival (HH:MM:SS), null if Actual Only.",
            "expDepartureTime":  "TIME — Expected departure, null if Actual Only.",
            "expInterchange":    "INTEGER — Number of changes in expected plan.",
            "expChangeAt":       "TEXT(JSON) — JSON listing expected interchange NLCs/times.",
            "actArrivalTime":    "TIME — Actual arrival, null if Expected Only.",
            "actDepartureTime":  "TIME — Actual departure, null if Expected Only.",
            "actInterchange":    "INTEGER — Number of changes in actual plan.",
            "actChangeAt":       "TEXT(JSON) — JSON listing actual interchange NLCs/times.",
            "soft_rule_key":     "TEXT — Which soft rule matched this plan, if any.",
            "status":            "TEXT — 'Exact Match', 'Soft Match', 'Expected Only', or 'Actual Only'.",
            "expHasWalkLeg":     "BOOLEAN — Whether the expected plan has a walking leg.",
            "actHasWalkLeg":     "BOOLEAN — Whether the actual plan has a walking leg.",
        },
    },

    "TestAlfComparisonResult": {
        "file_hint": "TestAlfComparisonResult.csv",
        "primary_key": ["execCombinationId", "alfFlowId"],
        "description": (
            "ALF (Aggregated Location Fare / fares-mileage) comparison results. "
            "Compares expected vs actual mileage figures and permitted-coverage "
            "(PC) counts per OD and ticket type."
        ),
        "columns": {
            "execCombinationId":   "TEXT — Foreign key → TestExecution.",
            "alfFlowId":           "INTEGER — Unique id for the ALF flow row.",
            "originNlc":           "INTEGER — UK NLC of origin.",
            "destinationNlc":      "INTEGER — UK NLC of destination.",
            "ticketType":          "INTEGER — Ticket type code.",
            "routeCode":           "INTEGER — Fare route code.",
            "expOperatingMiles":   "DOUBLE — Expected operating miles.",
            "expTicketMiles":      "DOUBLE — Expected ticket miles.",
            "actOperatingMiles":   "DOUBLE — Actual operating miles.",
            "actTicketMiles":      "DOUBLE — Actual ticket miles.",
            "expTotalPcCount":     "INTEGER — Expected permitted-coverage rows.",
            "actTotalPcCount":     "INTEGER — Actual permitted-coverage rows.",
            "actDistinctPcCount":  "INTEGER — PC rows in actual but not expected.",
            "expDistinctPcCount":  "INTEGER — PC rows in expected but not actual.",
            "softMatchPcCount":    "INTEGER — PC rows that soft-matched.",
            "exactMatchPcCount":   "INTEGER — PC rows that exact-matched.",
        },
    },
}


def schema_for_llm() -> str:
    """Render the schema as a compact markdown string for the LLM prompt."""
    blocks = []
    for table, spec in SCHEMA.items():
        cols = "\n".join(f"  - {c}: {d}" for c, d in spec["columns"].items())
        pk = ", ".join(spec["primary_key"])
        blocks.append(
            f"### Table: {table}\n"
            f"Primary key: ({pk})\n"
            f"{spec['description']}\n"
            f"Columns:\n{cols}"
        )
    relationships = (
        "### Relationships\n"
        "- TestExecution is the parent. All other tables reference it via execCombinationId.\n"
        "- TestPlanComparisonResult.planFlowId joins TestPlanComparisonDetail.planFlowId\n"
        "  (within the same execCombinationId).\n"
        "- TestExecutionRule.ruleKey can match TestPlanComparisonDetail.soft_rule_key.\n"
    )
    return "\n\n".join(blocks) + "\n\n" + relationships


# Friendly names shown in the UI
DISPLAY_NAMES = {
    "TestExecution": "Test Executions (master)",
    "TestExecutionRule": "Applied Soft Rules",
    "TestPlanComparisonResult": "Plan Comparison – Per OD",
    "TestPlanComparisonDetail": "Plan Comparison – Per Plan",
    "TestAlfComparisonResult": "ALF / Fares Comparison",
}
