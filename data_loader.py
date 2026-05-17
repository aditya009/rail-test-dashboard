"""
CSV upload → pandas → DuckDB. Cached so we don't re-load on every rerun.

Now refuses to load a table with missing expected columns (better than
silently creating a half-broken table), tries comma then auto-detects
the delimiter, and verifies the column list lands in DuckDB intact.
"""
from __future__ import annotations

from typing import Optional

import duckdb
import pandas as pd
import streamlit as st

from schema import SCHEMA


@st.cache_resource(show_spinner=False)
def get_connection() -> duckdb.DuckDBPyConnection:
    """Single in-process DuckDB connection, kept alive across reruns."""
    return duckdb.connect(":memory:")


def _match_file_to_table(filename: str) -> Optional[str]:
    base = filename.rsplit("/", 1)[-1].lower()
    for table, spec in SCHEMA.items():
        if spec["file_hint"].lower() in base or table.lower() in base:
            return table
    return None


def _read_csv(file_or_bytes) -> pd.DataFrame:
    """Read a CSV. Tries comma first, falls back to delimiter auto-detect."""
    if hasattr(file_or_bytes, "read"):
        file_or_bytes.seek(0)
        try:
            df = pd.read_csv(file_or_bytes)
            if df.shape[1] > 1:
                return df
            # Single column — almost certainly the wrong delimiter.
        except Exception:
            pass
        file_or_bytes.seek(0)
        return pd.read_csv(file_or_bytes, sep=None, engine="python")
    return pd.read_csv(file_or_bytes)


def load_uploads_to_duckdb(uploaded_files) -> dict[str, dict]:
    """Register each uploaded CSV into DuckDB under its canonical table name."""
    con = get_connection()
    report: dict[str, dict] = {}

    for f in uploaded_files:
        filename = getattr(f, "name", str(f))
        table = _match_file_to_table(filename)
        if table is None:
            report[f"_unmatched::{filename}"] = {
                "rows": 0, "cols": 0, "loaded": False,
                "source_filename": filename,
                "warnings": [f"Filename does not match any known table in schema."],
            }
            continue

        try:
            df = _read_csv(f)
        except Exception as exc:
            report[table] = {
                "rows": 0, "cols": 0, "loaded": False,
                "source_filename": filename,
                "warnings": [f"Failed to read CSV: {exc}"],
            }
            continue

        warnings = _validate_columns(table, df)
        df = _coerce_types(table, df)

        # Refuse to load when expected columns are missing — prevents
        # cryptic "column not found" errors later in the dashboard.
        expected = set(SCHEMA[table]["columns"].keys())
        if not expected.issubset(set(df.columns)):
            report[table] = {
                "rows": len(df), "cols": len(df.columns), "loaded": False,
                "source_filename": filename,
                "warnings": warnings + [
                    f"REFUSING to load: required columns missing. "
                    f"Got {list(df.columns)}."
                ],
            }
            continue

        # Clean rebuild
        con.execute(f"DROP TABLE IF EXISTS {table}")
        temp_name = f"_{table}_df"
        try:
            con.unregister(temp_name)
        except Exception:
            pass
        con.register(temp_name, df)
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM {temp_name}")
        con.unregister(temp_name)

        actual_cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
        if set(actual_cols) != set(df.columns):
            warnings.append(
                f"DuckDB column drift: pandas had {list(df.columns)}, "
                f"DuckDB has {actual_cols}."
            )

        report[table] = {
            "rows": len(df), "cols": len(df.columns), "loaded": True,
            "source_filename": filename,
            "warnings": warnings,
            "duckdb_columns": actual_cols,
        }

    return report


def _validate_columns(table: str, df: pd.DataFrame) -> list[str]:
    expected = set(SCHEMA[table]["columns"].keys())
    got = set(df.columns)
    warnings: list[str] = []
    missing = expected - got
    extra = got - expected
    if missing:
        warnings.append(f"Missing expected columns: {sorted(missing)}")
    if extra:
        warnings.append(f"Unexpected extra columns: {sorted(extra)}")
    return warnings


def _coerce_types(table: str, df: pd.DataFrame) -> pd.DataFrame:
    spec = SCHEMA[table]["columns"]
    for col in df.columns:
        if col not in spec:
            continue
        desc = spec[col].upper()
        try:
            if desc.startswith("TIMESTAMP") or desc.startswith("DATE"):
                df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            elif desc.startswith("TIME"):
                df[col] = df[col].astype("string")
            elif desc.startswith("BOOLEAN"):
                df[col] = df[col].astype("boolean")
        except Exception:
            pass
    return df


def list_loaded_tables() -> list[str]:
    con = get_connection()
    in_db = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    return [t for t in SCHEMA if t in in_db]


def describe_table(table: str) -> list[str]:
    """Actual columns DuckDB currently has for a table (empty if missing)."""
    try:
        return [r[0] for r in get_connection().execute(f"DESCRIBE {table}").fetchall()]
    except Exception:
        return []


def table_to_df(table: str) -> pd.DataFrame:
    return get_connection().execute(f"SELECT * FROM {table}").df()


def run_sql(sql: str) -> pd.DataFrame:
    return get_connection().execute(sql).df()
