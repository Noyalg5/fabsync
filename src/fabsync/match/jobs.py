"""Job crosswalk across the three systems.

* Corvus MRP ``job_no`` (``J-24-0871``) is the job of record.
* Finance ``job_code`` (``24871``) is mapped by rule: two-digit year plus the
  sequence without leading zeros. A code whose derived job number does not
  exist in Corvus is listed as unmatched, never guessed.
* Shop-floor delivery notes carry free-text job references (``J-24-0871``,
  ``j-24-0871``, ``J24-0871``, ``24-0871``, ``J-24-871``). Each form is parsed
  with a score for how far it had to be normalised. The customer written on
  the same delivery notes is fuzzy-compared with the customer finance invoices
  that job to, as corroboration; a reference whose customer disagrees is sent
  to review rather than accepted.

Every source value on every side appears in ``core.job_xref``; everything that
failed to link, on any side, is listed in ``core.job_unmatched`` with a reason.
``core.job_crosswalk`` has one row per job with the confidence of its weakest
link.
"""

from __future__ import annotations

import re

import pandas as pd
from rapidfuzz import fuzz

from fabsync.match.common import MatchContext
from fabsync.match.suppliers import normalise

OPS_FORMS = [
    ("exact", re.compile(r"^J-(\d{2})-(\d{4})$"), 100.0),
    ("case_normalised", re.compile(r"^j-(\d{2})-(\d{4})$"), 99.0),
    ("missing_hyphen", re.compile(r"^[Jj](\d{2})-(\d{4})$"), 97.0),
    ("missing_prefix", re.compile(r"^(\d{2})-(\d{4})$"), 96.0),
    ("zero_padding_restored", re.compile(r"^[Jj]-(\d{2})-(\d{1,3})$"), 95.0),
]
CORROBORATION_FLOOR = 80.0


def parse_ops_job(text: str) -> tuple[str | None, str, float]:
    for method, pattern, score in OPS_FORMS:
        m = pattern.match(text.strip())
        if m:
            return f"J-{m.group(1)}-{int(m.group(2)):04d}", method, score
    return None, "unparsed", 0.0


def finance_to_job_no(code: str) -> str | None:
    return f"J-{code[:2]}-{int(code[2:]):04d}" if re.fullmatch(r"\d{3,6}", code or "") else None


def match_jobs(ctx: MatchContext) -> dict:
    jobs = ctx.df("SELECT job_no, finance_job_code, works_orders FROM core.jobs ORDER BY job_no")
    known = set(jobs.job_no)
    fin = ctx.df("""SELECT job_code, sum(n) AS rows FROM (
                      SELECT job_code, count(*) n FROM staging.finance_job_costs GROUP BY 1 UNION ALL
                      SELECT job_code, count(*) FROM staging.finance_sales_invoices GROUP BY 1 UNION ALL
                      SELECT job_code, count(*) FROM staging.finance_purchase_invoices
                      WHERE job_code IS NOT NULL GROUP BY 1) GROUP BY 1 ORDER BY 1""")
    customers = dict(ctx.con.execute("""SELECT job_code, mode(customer_name) FROM staging.finance_sales_invoices
                                        GROUP BY 1""").fetchall())
    ops = ctx.df("""SELECT job AS source_value, customer, count(*) AS rows FROM staging.shop_floor_delivery_notes
                    GROUP BY ALL ORDER BY 1, 2""")

    rows = []
    for r in jobs.itertuples():
        rows.append({"source_system": "corvus_mrp", "source_value": r.job_no, "row_count": int(r.works_orders),
                     "job_no": r.job_no, "finance_job_code": r.finance_job_code, "method": "job_of_record",
                     "score": 100.0, "matched_on": "Corvus MRP is the system of record for jobs"})
    for r in fin.itertuples():
        derived = finance_to_job_no(r.job_code)
        hit = derived in known
        rows.append({"source_system": "finance", "source_value": r.job_code, "row_count": int(r.rows),
                     "job_no": derived if hit else None, "finance_job_code": r.job_code,
                     "method": "derived_key" if hit else "derived_key_not_found", "score": 100.0 if hit else 0.0,
                     "matched_on": f"'{r.job_code}' = year {r.job_code[:2]} + sequence {int(r.job_code[2:])} "
                                   f"-> {derived}" + ("" if hit else "; no such job in Corvus MRP")})

    for value, grp in ops.groupby("source_value", sort=True):
        job_no, method, score = parse_ops_job(value)
        n = int(grp.rows.sum())
        if job_no is None:
            rows.append({"source_system": "shop_floor", "source_value": value, "row_count": n, "job_no": None,
                         "finance_job_code": None, "method": method, "score": 0.0,
                         "matched_on": f"'{value}' is not a recognisable job reference"})
            continue
        if job_no not in known:
            rows.append({"source_system": "shop_floor", "source_value": value, "row_count": n, "job_no": None,
                         "finance_job_code": None, "method": method + "_not_found", "score": 0.0,
                         "matched_on": f"'{value}' parsed as {job_no} ({method}); no such job in Corvus MRP"})
            continue
        code = jobs.loc[jobs.job_no == job_no, "finance_job_code"].iloc[0]
        fin_customer = customers.get(code)
        if fin_customer:
            target = normalise(fin_customer, ctx.config)
            sims = [fuzz.token_set_ratio(normalise(c or "", ctx.config), target) for c in grp.customer]
            corroboration = round(sum(s * w for s, w in zip(sims, grp.rows, strict=True)) / n, 1)
            note = f"customer on delivery notes vs finance '{fin_customer}': {corroboration:.0f}"
            if corroboration < CORROBORATION_FLOOR:
                method, score = method + "+customer_disagrees", min(score, 85.0)
        else:
            note = "no finance customer to corroborate"
        rows.append({"source_system": "shop_floor", "source_value": value, "row_count": n, "job_no": job_no,
                     "finance_job_code": code, "method": method, "score": score,
                     "matched_on": f"'{value}' parsed as {job_no} ({method}); {note}"})

    xref = pd.DataFrame(rows)
    xref["status"] = xref.score.map(ctx.status)
    xref.loc[xref.status == "unmatched", "job_no"] = None  # a review row keeps its proposal
    xref["est_minutes"] = xref.status.map(lambda s: ctx.minutes("job") if s == "review" else 0.0)

    auto = xref[xref.status == "auto"]
    ops_by_job = auto[auto.source_system == "shop_floor"].groupby("job_no")
    crosswalk = []
    for r in jobs.itertuples():
        fin_row = auto[(auto.source_system == "finance") & (auto.job_no == r.job_no)]
        refs = ops_by_job.get_group(r.job_no) if r.job_no in ops_by_job.groups else xref.iloc[0:0]
        scores = [100.0] + list(fin_row.score) + list(refs.score)
        fin_code = fin_row.source_value.iloc[0] if len(fin_row) else None
        crosswalk.append({"job_no": r.job_no, "finance_job_code": fin_code,
                          "in_finance": len(fin_row) > 0, "ops_reference_forms": ", ".join(refs.source_value),
                          "ops_rows": int(refs.row_count.sum()), "in_ops": len(refs) > 0,
                          "confidence": min(scores), "weakest_link": (refs.sort_values("score").method.iloc[0]
                                                                      if len(refs) else "finance derived key")})
    for r in xref[(xref.source_system == "finance") & (xref.status != "auto")].itertuples():
        crosswalk.append({"job_no": None, "finance_job_code": r.source_value, "in_finance": True,
                          "ops_reference_forms": "", "ops_rows": 0, "in_ops": False, "confidence": 0.0,
                          "weakest_link": "no Corvus job"})
    crosswalk = pd.DataFrame(crosswalk)

    unmatched = []
    for r in crosswalk[~crosswalk.in_finance & crosswalk.job_no.notna()].itertuples():
        unmatched.append({"side": "corvus_mrp", "value": r.job_no, "reason": "no finance job code"})
    for r in crosswalk[~crosswalk.in_ops & crosswalk.job_no.notna()].itertuples():
        unmatched.append({"side": "corvus_mrp", "value": r.job_no, "reason": "no shop-floor delivery note"})
    for r in xref[(xref.source_system != "corvus_mrp") & (xref.status != "auto")].itertuples():
        unmatched.append({"side": r.source_system, "value": r.source_value,
                          "reason": ("held for review: " if r.status == "review" else "") + r.matched_on})
    unmatched = pd.DataFrame(unmatched, columns=["side", "value", "reason"])

    ctx.write("core.job_xref", xref)
    ctx.write("core.job_crosswalk", crosswalk)
    ctx.write("core.job_unmatched", unmatched)
    ctx.lineage(rule_id="MA-04", source_table="jobs, finance job codes, delivery_notes",
                source_file="core.jobs, finance/*.csv, shop_floor/delivery_notes.csv", target_table="core.job_xref",
                rows=len(xref), affected=len(auto),
                detail=f"{len(xref)} source values; {len(auto)} auto, {int((xref.status == 'review').sum())} review, "
                       f"{int((xref.status == 'unmatched').sum())} unmatched; {len(unmatched)} unmatched-list rows")
    return {"xref": xref, "crosswalk": crosswalk, "unmatched": unmatched}
