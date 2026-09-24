"""Checks too awkward for a single SQL statement, referenced from config/dq_rules.yaml.

Each takes a DuckDB connection and the rule parameters, and returns one row per
record checked with record_key, passed, observed (and optionally source_file,
source_row), exactly like a SQL check.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def labour_reconciliation(con: duckdb.DuckDBPyConnection, params: dict) -> pd.DataFrame:
    """Per job: finance labour cost against booked hours at the standard rate."""
    rate = float(params["labour_rate"])
    tolerance = float(params["labour_tolerance"])
    frame = con.execute("""
        WITH booked AS (SELECT job_no, sum(hours) AS hours FROM core.time_bookings WHERE wo_matched GROUP BY 1),
             charged AS (SELECT job_no, sum(amount) AS amount FROM core.job_costs
                         WHERE cost_type = 'labour' AND job_matched GROUP BY 1)
        SELECT coalesce(b.job_no, c.job_no) AS job_no, coalesce(b.hours, 0) AS hours, coalesce(c.amount, 0) AS amount
        FROM booked b FULL JOIN charged c ON c.job_no = b.job_no ORDER BY 1""").df()
    expected = frame.hours.astype(float) * rate
    actual = frame.amount.astype(float)
    variance = (actual - expected) / expected.where(expected != 0)
    passed = variance.abs() <= tolerance
    observed = [f"booked {h:,.1f} h x £{rate:.0f} = £{e:,.0f}; finance £{a:,.0f}"
                + (f" ({v:+.0%})" if pd.notna(v) else " (no hours booked)")
                for h, e, a, v in zip(frame.hours.astype(float), expected, actual, variance, strict=True)]
    return pd.DataFrame({"record_key": frame.job_no, "passed": passed.fillna(False), "observed": observed})
