"""Works order references: parse shop-floor free text into a Corvus ``wo_no``.

Supervisors write ``WO 12345``, ``WO12345``, ``wo-12345``, ``12345`` and
``12345 (rev B)``. Each distinct way a reference is written, in each file, is
parsed by the first form that fits; the drawing revision is kept, not thrown
away. A reference that parses to a number Corvus does not hold is not guessed
at: the matcher looks for Corvus works orders one adjacent-digit swap away
(a transposition, the commonest keying error) and puts them in the review
queue with evidence from the bookings: same site, dates inside the candidate's
window.

Scores: 100 bare number, 99 ``WO`` prefix, 97 revision suffix, 85 number found
inside other text (review), 0 unparsed. A parsed number absent from Corvus
scores 0 and is unmatched unless a transposition candidate exists (85, review).
"""

from __future__ import annotations

import re

import pandas as pd

from fabsync.match.common import MatchContext

FORMS = [
    ("bare_number", re.compile(r"^(\d{5})$"), 100.0),
    ("wo_prefix", re.compile(r"^WO[\s-]?(\d{5})$", re.I), 99.0),
    ("revision_suffix", re.compile(r"^(\d{5})\s*\(rev\s*([A-Z])\)$", re.I), 97.0),
    ("embedded_number", re.compile(r"(?<!\d)(\d{5})(?!\d)"), 85.0),
]
TRANSPOSITION_SCORE = 85.0
QUEUE_COLUMNS = ["source_table", "source_value", "parsed_number", "candidate_wo_no", "candidate_job_no",
                 "rows_affected", "site_matches", "dates_in_window", "method", "score", "matched_on",
                 "suggested_action", "est_minutes"]
WINDOW_DAYS = 30


def parse_wo(text: str) -> tuple[int | None, str | None, str, float]:
    """Return wo_no, drawing revision, method, score."""
    for method, pattern, score in FORMS:
        m = pattern.search(text.strip()) if method == "embedded_number" else pattern.match(text.strip())
        if m:
            revision = m.group(2).upper() if method == "revision_suffix" else None
            return int(m.group(1)), revision, method, score
    return None, None, "unparsed", 0.0


def transpositions(n: int) -> list[int]:
    s = str(n)
    return sorted({int(s[:i] + s[i + 1] + s[i] + s[i + 2:]) for i in range(len(s) - 1) if s[i] != s[i + 1]})


def match_works_orders(ctx: MatchContext) -> dict:
    refs = ctx.df("""
        SELECT 'time_bookings' AS source_table, works_order AS source_value, count(*) AS row_count,
               min(booking_date) AS first_date, max(booking_date) AS last_date,
               string_agg(DISTINCT site, ', ') AS sites_written
        FROM staging.shop_floor_time_bookings GROUP BY ALL
        UNION ALL
        SELECT 'ncr_log', works_order, count(*), min(raised_date), max(raised_date), NULL
        FROM staging.shop_floor_ncr_log GROUP BY ALL
        ORDER BY 1, 2""")
    wos = ctx.df("""SELECT wo_no, job_no, site_code, planned_start, coalesce(actual_finish, planned_finish) AS finish
                    FROM core.works_orders""").set_index("wo_no")
    site_of = dict(ctx.con.execute("SELECT alias_key, site_code FROM core.site_aliases").fetchall())

    rows, queue = [], []
    for r in refs.itertuples():
        wo, revision, method, score = parse_wo(r.source_value)
        row = {"source_system": "shop_floor", "source_table": r.source_table, "source_value": r.source_value,
               "row_count": int(r.row_count), "wo_no": None, "parsed_number": wo, "drawing_revision": revision,
               "job_no": None, "parse_method": method, "method": method, "score": score, "matched_on": ""}
        if wo is None:
            row["matched_on"] = f"'{r.source_value}' holds no five-digit works order number"
        elif wo in wos.index:
            row.update(wo_no=wo, job_no=wos.at[wo, "job_no"],
                       matched_on=f"'{r.source_value}' parsed as {wo} ({method})"
                                  + (f", drawing rev {revision} kept" if revision else "") + "; exists in Corvus MRP")
        else:
            candidates = [c for c in transpositions(wo) if c in wos.index]
            sites = {site_of.get(s.strip().casefold()) for s in (r.sites_written or "").split(", ") if s}
            best, best_ev = None, ""
            for c in candidates:
                start, finish = wos.at[c, "planned_start"], wos.at[c, "finish"]
                in_window = (pd.Timestamp(r.first_date) >= pd.Timestamp(start) - pd.Timedelta(days=WINDOW_DAYS) and
                             pd.Timestamp(r.last_date) <= pd.Timestamp(finish) + pd.Timedelta(days=WINDOW_DAYS))
                same_site = wos.at[c, "site_code"] in sites if sites else None
                ev = (f"{c} ({wos.at[c, 'job_no']}, {wos.at[c, 'site_code']}): site "
                      f"{'matches' if same_site else 'differs' if same_site is False else 'unknown'}, dates "
                      f"{'inside' if in_window else 'outside'} its window")
                queue.append({"source_table": r.source_table, "source_value": r.source_value, "parsed_number": wo,
                              "candidate_wo_no": c, "candidate_job_no": wos.at[c, "job_no"],
                              "rows_affected": int(r.row_count), "site_matches": same_site,
                              "dates_in_window": bool(in_window), "method": "adjacent_digit_transposition",
                              "score": TRANSPOSITION_SCORE, "matched_on": f"{wo} is not in Corvus; {ev}",
                              "suggested_action": ("likely keying error: confirm and correct the booking sheet"
                                                   if same_site and in_window else
                                                   "weak candidate: ask the supervisor which job this was"),
                              "est_minutes": ctx.minutes("works_order")})
                if best is None:
                    best, best_ev = c, ev
            row.update(method=f"{method}_not_in_corvus", score=TRANSPOSITION_SCORE if candidates else 0.0,
                       matched_on=f"'{r.source_value}' parsed as {wo} ({method}); {wo} is not in Corvus MRP; "
                                  + (f"transposition candidates: {best_ev}" if candidates
                                     else "no transposition candidate"))
        rows.append(row)

    xref = pd.DataFrame(rows)
    xref["status"] = xref.score.map(ctx.status)
    queue = pd.DataFrame(queue, columns=QUEUE_COLUMNS)
    # One review item per wrong number and candidate, however many ways it was written.
    queue = (queue.groupby(["parsed_number", "candidate_wo_no"], sort=True)
             .agg(written_as=("source_value", lambda v: ", ".join(sorted(set(v)))),
                  source_tables=("source_table", lambda v: ", ".join(sorted(set(v)))),
                  candidate_job_no=("candidate_job_no", "first"), rows_affected=("rows_affected", "sum"),
                  site_matches=("site_matches", "max"), dates_in_window=("dates_in_window", "max"),
                  method=("method", "first"), score=("score", "first"), matched_on=("matched_on", "first"),
                  suggested_action=("suggested_action", "first"), est_minutes=("est_minutes", "first"))
             .reset_index())
    queue.insert(0, "review_id", [f"WR{i:03d}" for i in range(1, len(queue) + 1)])
    ctx.write("core.works_order_xref", xref)
    ctx.write("core.works_order_review_queue", queue)
    ctx.lineage(rule_id="MA-05", system="shop_floor", source_table="time_bookings, ncr_log",
                source_file="shop_floor/time_bookings.csv, shop_floor/ncr_log.csv",
                target_table="core.works_order_xref", rows=len(xref), affected=int((xref.status == "auto").sum()),
                detail=f"{len(xref)} distinct references; {int((xref.parse_method == 'unparsed').sum())} unparsed; "
                       f"{int(xref.wo_no.isna().sum() - (xref.parse_method == 'unparsed').sum())} parsed to numbers "
                       f"not in Corvus; {len(queue)} transposition candidates queued")
    return {"xref": xref, "queue": queue}
