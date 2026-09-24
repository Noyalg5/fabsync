"""Match quality metrics and docs/match-quality-report.md.

The report holds no run ids or timestamps, so it only changes when the data or
the matching configuration changes.
"""

from __future__ import annotations

import pandas as pd

from fabsync.match.common import MatchContext
from fabsync.match.materials import SURVIVORSHIP


def pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def quality_rows(results: dict, ctx: MatchContext) -> list[dict]:
    rows = []
    m = results["material"]["xref"]
    rows.append({"domain": "material", "population": "distinct written forms per Corvus table",
                 "values_total": len(m), "auto": int((m.status == "auto").sum()),
                 "auto_pct": pct((m.status == "auto").sum(), len(m)),
                 "auto_rows_pct": pct(m[m.status == "auto"].row_count.sum(), m.row_count.sum()),
                 "review_queue": len(results["material"]["queue"]), "unmatched": int((m.status == "unmatched").sum()),
                 "est_minutes": float(results["material"]["queue"].est_minutes.sum())})
    s = results["supplier"]["xref"]
    mrp = s[s.source_system == "corvus_mrp"]
    rows.append({"domain": "supplier", "population": "Corvus supplier codes",
                 "values_total": len(mrp), "auto": int((mrp.status == "auto").sum()),
                 "auto_pct": pct((mrp.status == "auto").sum(), len(mrp)),
                 "auto_rows_pct": pct(mrp[mrp.status == "auto"].documents.sum(), mrp.documents.sum()),
                 "review_queue": len(results["supplier"]["queue"]), "unmatched": int((mrp.status == "unmatched").sum()),
                 "est_minutes": float(results["supplier"]["queue"].est_minutes.sum())})
    j = results["job"]["xref"]
    rows.append({"domain": "job", "population": "job references across all three systems",
                 "values_total": len(j), "auto": int((j.status == "auto").sum()),
                 "auto_pct": pct((j.status == "auto").sum(), len(j)),
                 "auto_rows_pct": pct(j[j.status == "auto"].row_count.sum(), j.row_count.sum()),
                 "review_queue": int((j.status == "review").sum()), "unmatched": int((j.status == "unmatched").sum()),
                 "est_minutes": float(j.est_minutes.sum())})
    w = results["works_order"]["xref"]
    rows.append({"domain": "works_order", "population": "distinct shop-floor works order references",
                 "values_total": len(w), "auto": int((w.status == "auto").sum()),
                 "auto_pct": pct((w.status == "auto").sum(), len(w)),
                 "auto_rows_pct": pct(w[w.status == "auto"].row_count.sum(), w.row_count.sum()),
                 "review_queue": len(results["works_order"]["queue"]),
                 "unmatched": int((w.status == "unmatched").sum()),
                 "est_minutes": float(results["works_order"]["queue"].est_minutes.sum())})
    return rows


def md(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).replace("|", "\\|")


def table(frame: pd.DataFrame, columns: list[str], headers: list[str] | None = None) -> list[str]:
    headers = headers or columns
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    for r in frame[columns].itertuples(index=False):
        out.append("| " + " | ".join(md(v) for v in r) + " |")
    return out


def method_breakdown(xref: pd.DataFrame, weight: str) -> pd.DataFrame:
    return (xref.groupby(["method", "status"], dropna=False)
            .agg(values=("method", "size"), rows=(weight, "sum")).reset_index()
            .sort_values(["status", "values"], ascending=[True, False]))


def render_report(results: dict, quality: pd.DataFrame, ctx: MatchContext) -> str:
    t = ctx.config["thresholds"]
    effort = ctx.config["effort_minutes"]
    total_minutes = quality.est_minutes.sum()
    out = [
        "# Match quality report",
        "",
        "**All data matched here is synthetic.** It represents no real company, supplier, customer or job.",
        "",
        "Produced by the match stage (`make run-all`). Every figure is queryable in `governance.match_quality`,",
        "the crosswalks in `core.*_xref`, and the combined review queue in `core.v_match_review_queue`.",
        "",
        f"Bands: a score of {t['auto_accept']:g} or more is accepted automatically; {t['review_floor']:g} to "
        f"{t['auto_accept']:g} goes to a person; below {t['review_floor']:g} is never merged. Source values are",
        "never overwritten: every crosswalk row keeps the value as written beside the canonical value, with",
        "`method`, `score`, `matched_on` and `matched_at`.",
        "",
        "## Summary",
        "",
        "| Domain | Population | Values | Auto | Auto % | Auto % of rows | Review queue | Unmatched | Effort (h) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in quality.itertuples():
        out.append(f"| {r.domain.replace('_', ' ')} | {r.population} | {r.values_total:,} | {r.auto:,} | "
                   f"{r.auto_pct:.1f}% | {r.auto_rows_pct:.1f}% | {r.review_queue:,} | {r.unmatched:,} | "
                   f"{r.est_minutes / 60:.1f} |")
    out += [
        "",
        f"**Estimated manual effort to clear the review queue: {total_minutes / 60:.1f} hours** "
        f"({int(quality.review_queue.sum())} items). Minutes per item are assumptions in "
        "`config/matching.toml`: " + ", ".join(f"{k.replace('_', ' ')} {v:g}" for k, v in effort.items()) + ".",
        "Unmatched values need investigation rather than review and are not in that estimate.",
    ]

    # ---- materials -------------------------------------------------------------
    m = results["material"]
    x, g, q = m["xref"], m["golden"], m["queue"]
    doc_rows = int(q[q.source_table.isin(["purchase_orders", "goods_received"])].row_count.sum())
    out += ["", "## Materials", "",
            f"{len(x)} distinct ways of writing a material across four Corvus tables resolve to {len(g)} golden",
            f"materials. {int(g.uom_conflict.sum())} of them are transacted in more than one unit of measure, and "
            f"{int(g.mass_deviation.sum())} carry a BOM unit weight off the reference by more than "
            f"{ctx.config['material']['mass_tolerance']:.0%}.", "",
            "Every BOM line resolves, because the BOM carries a grade column. Codes on purchase orders, goods",
            "received and stock that omit the grade cannot be resolved from the data: where the section is held in",
            "one grade the grade is proposed for confirmation; where it is held in several, a person must read the",
            f"mill certificate. Those review items cover {doc_rows:,} purchase order and goods received lines, "
            "each needing its own",
            "certificate check. This is an EN 1090 traceability exposure, not a formatting problem.", "",
            *table(method_breakdown(x, "row_count"), ["method", "status", "values", "rows"],
                   ["Method", "Status", "Values", "Rows"]),
            "", f"Survivorship: {SURVIVORSHIP}.", "",
            "Golden records with most variant spellings:", "",
            *table(g.assign(variants=g.source_codes.str.count(",") + 1)
                   .sort_values(["variants", "canonical_code"], ascending=[False, True]).head(8),
                   ["canonical_code", "description", "mass", "mass_basis", "observed_uoms", "source_codes"],
                   ["Canonical", "Description", "Mass", "Basis", "Units seen", "Written as"])]

    # ---- suppliers -------------------------------------------------------------
    s = results["supplier"]
    xs, pairs, gs, qs = s["xref"], s["pairs"], s["golden"], s["queue"]
    fin_dupes = gs[gs.finance_accounts.str.count(",") >= 1]
    mrp_dupes = gs[gs.corvus_codes.str.count(",") >= 1]
    missed = pairs[(pairs.status == "unmatched") & (pairs.evidence_pos > 0) & pairs.cross_system]
    out += ["", "## Suppliers", "",
            f"{len(xs[xs.source_system == 'corvus_mrp'])} Corvus supplier codes and "
            f"{len(xs[xs.source_system == 'finance'])} finance accounts were blocked on the first normalised token",
            f"and {len(pairs)} pairs scored with rapidfuzz. Accepted links form {len(gs)} supplier entities.",
            f"{len(mrp_dupes)} entities hold more than one Corvus code and {len(fin_dupes)} hold more than one "
            "finance account: duplicates that exist today.", "",
            "Finance accounts with no Corvus counterpart are expected: subcontractors, hauliers and overheads are",
            "paid through finance but never appear on a Corvus steel purchase order.", "",
            "### Review queue", "",
            "One item per pair of supplier entities; approving it settles every record pair between them.", "",
            *(table(qs, ["review_id", "left_members", "right_members", "score", "evidence", "suggested_action"],
                    ["Item", "Entity A", "Entity B", "Best score", "Evidence", "Suggested action"]) if len(qs)
              else ["Empty."]),
            "", "### Duplicate entities found", "",
            *table(gs[gs.members > 1 + (gs.in_corvus & gs.in_finance)].sort_values("supplier_id"),
                   ["supplier_id", "canonical_name", "corvus_codes", "finance_accounts"],
                   ["Entity", "Canonical name", "Corvus codes", "Finance accounts"])]
    if len(missed):
        out += ["", "### Likely missed: below the review floor but corroborated by invoices", "",
                "These pairs score under the floor so they are never merged, but the invoices say they are the",
                "same supplier. Name matching alone has limits; a steward should look at these.", "",
                *table(missed, ["left_name", "right_name", "score", "evidence"],
                       ["Record", "Candidate", "Score", "Evidence"])]
    unmatched_mrp = xs[(xs.source_system == "corvus_mrp") & (xs.status == "unmatched")]
    if len(unmatched_mrp):
        out += ["", "Corvus codes with no finance counterpart at or above the floor:", "",
                *table(unmatched_mrp, ["source_code", "source_name", "best_counterpart", "score"],
                       ["Code", "Name", "Best candidate", "Score"])]

    # ---- jobs --------------------------------------------------------------------
    j = results["job"]
    xj, cw, un = j["xref"], j["crosswalk"], j["unmatched"]
    out += ["", "## Jobs", "",
            f"{len(cw[cw.job_no.notna()])} Corvus jobs: {int((cw.in_finance & cw.job_no.notna()).sum())} have a "
            f"finance job code and {int(cw.in_ops.sum())} are referenced on shop-floor delivery notes. "
            f"{int(cw.job_no.isna().sum())} finance job codes have no Corvus job.", "",
            *table(method_breakdown(xj, "row_count"), ["method", "status", "values", "rows"],
                   ["Method", "Status", "Values", "Rows"]), "",
            "Unmatched, by side:", "",
            *table(un.groupby(["side", "reason"]).size().reset_index(name="values")
                   .assign(reason=lambda d: d.reason.str.replace(r"^'(\d+)' = .*", "finance code with no Corvus job",
                                                                 regex=True))
                   .groupby(["side", "reason"]).values.sum().reset_index(), ["side", "reason", "values"],
                   ["Side", "Reason", "Values"]), "",
            "Finance codes with no Corvus job: "
            + ", ".join(f"`{v}`" for v in sorted(xj[(xj.source_system == "finance") &
                                                    (xj.status == "unmatched")].source_value)) + "."]

    # ---- works orders --------------------------------------------------------------
    w = results["works_order"]
    xw, qw = w["xref"], w["queue"]
    unparsed = xw[xw.parse_method == "unparsed"]
    out += ["", "## Works orders", "",
            f"{len(xw):,} distinct ways a works order is written on time bookings and NCRs. "
            f"{len(unparsed)} could not be parsed; "
            f"{int((xw.wo_no.isna() & (xw.parse_method != 'unparsed')).sum())} parse to a number Corvus does not hold.",
            "", *table(method_breakdown(xw, "row_count"), ["method", "status", "values", "rows"],
                       ["Method", "Status", "Values", "Rows"])]
    if len(unparsed):
        out += ["", "Could not be parsed: " + ", ".join(f"`{v}`" for v in unparsed.source_value) + "."]
    missing = sorted(set(xw[xw.wo_no.isna() & xw.parsed_number.notna()].parsed_number.astype(int)))
    if missing:
        out += ["", "Numbers not in Corvus MRP: " + ", ".join(str(n) for n in missing) + ".", "",
                "### Transposition candidates for review", "",
                *(table(qw, ["review_id", "parsed_number", "written_as", "rows_affected", "candidate_wo_no",
                             "candidate_job_no", "site_matches", "dates_in_window", "suggested_action"],
                        ["Item", "Number", "Written as", "Rows", "Candidate", "Job", "Site matches", "Dates fit",
                         "Suggested action"])
                  if len(qw) else ["None found."])]
    out.append("")
    return "\n".join(out)
