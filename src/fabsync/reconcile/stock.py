"""Stock accuracy: book quantity against counted quantity.

Per stock line: difference = counted - book, absolute error in the line's own
unit and in kilograms (steel only, using the golden record's mass), and value
error = |difference| x unit cost. A line is accurate when |difference| is within
the line tolerance (config/reconcile.toml, zero by default).

By site and section type: line accuracy = accurate lines / counted lines,
compared with the target (95%), and value accuracy = 1 - value error / book
value. Consumables are grouped as CONSUMABLE; stock held under a code without a
grade takes its section type from the parsed designation.

Exposure is the total value error, the adjustment a full recount would post if
every counted difference is real. Net adjustment is also shown.
"""

from __future__ import annotations

from fabsync.reconcile.common import EngineResult, Headline

LINES_SQL = """
SELECT trim(s.material_code) || '|' || s.site_code || '|' || trim(s.location) AS line_id,
       trim(s.material_code) AS material_code, trim(s.description) AS description, s.site_code,
       trim(s.location) AS location, coalesce(x.section_type, 'CONSUMABLE') AS section_type,
       coalesce(x.canonical_code, x.proposed_code) AS canonical_code, x.status AS match_status, s.uom,
       CAST(s.qty_on_hand AS DOUBLE) AS book_qty, CAST(s.counted_qty AS DOUBLE) AS counted_qty,
       CAST(s.unit_cost AS DOUBLE) AS unit_cost, s.last_count_date,
       CASE s.uom WHEN 'KG' THEN 1.0 WHEN 'M' THEN g.mass WHEN 'EA' THEN g.kg_per_ea END AS kg_per_unit,
       s._source_file AS source_file, s._source_row AS source_row
FROM core.stock s
JOIN core.material_xref x ON x.source_table = 'stock' AND x.source_code = s.material_code
     AND x.source_description IS NOT DISTINCT FROM s.description
LEFT JOIN core.material_golden g ON g.canonical_code = coalesce(x.canonical_code, x.proposed_code,
                                                                split_part(x.candidates, ', ', 1))
ORDER BY s.site_code, section_type, line_id
"""


def stock_accuracy(con, cfg: dict) -> EngineResult:
    sc = cfg["stock"]
    lines = con.execute(LINES_SQL).df()
    lines["difference"] = lines.counted_qty - lines.book_qty
    lines["abs_error"] = lines.difference.abs()
    lines["abs_error_kg"] = (lines.abs_error * lines.kg_per_unit).round(1)
    lines["book_value"] = (lines.book_qty * lines.unit_cost).round(2)
    lines["value_error"] = (lines.abs_error * lines.unit_cost).round(2)
    lines["net_value_adjustment"] = (lines.difference * lines.unit_cost).round(2)
    lines["accurate"] = lines.abs_error <= sc["line_tolerance"] * lines.book_qty
    lines["reason"] = [
        "agrees" if a else f"book {b:g} {u}, counted {c:g}: {d:+g} {u}, £{v:,.2f}"
        for a, b, c, d, u, v in zip(lines.accurate, lines.book_qty, lines.counted_qty, lines.difference, lines.uom,
                                    lines.value_error, strict=True)]
    offenders = lines[~lines.accurate].sort_values(["value_error", "line_id"], ascending=[False, True])
    lines["offender_rank"] = lines.line_id.map({k: i for i, k in enumerate(offenders.line_id, start=1)})
    lines["top_offender"] = lines.offender_rank <= sc["top_offenders"]

    grp = lines.groupby(["site_code", "section_type"])
    summary = grp.agg(lines=("line_id", "size"), accurate_lines=("accurate", "sum"),
                      abs_error_kg=("abs_error_kg", "sum"), book_value=("book_value", "sum"),
                      value_error=("value_error", "sum"), net_adjustment=("net_value_adjustment", "sum")).reset_index()
    summary["line_accuracy"] = (summary.accurate_lines / summary.lines).round(4)
    summary["value_accuracy"] = (1 - summary.value_error / summary.book_value).round(4)
    summary["meets_target"] = summary.line_accuracy >= sc["accuracy_target"]

    by_site = lines.groupby("site_code").agg(lines=("line_id", "size"), accurate_lines=("accurate", "sum"),
                                              value_error=("value_error", "sum"), book_value=("book_value", "sum"))
    by_site["line_accuracy"] = (by_site.accurate_lines / by_site.lines).round(4)
    by_site["meets_target"] = by_site.line_accuracy >= sc["accuracy_target"]

    accuracy = float(lines.accurate.mean())
    exposure = float(lines.value_error.sum())
    t = "recon.stock_lines"
    heads = [
        Headline("stock", "line_accuracy", "Stock line accuracy", round(100 * accuracy, 2), "percent", t, "true",
                 "round(100 * avg(CAST(accurate AS DOUBLE)), 2)",
                 f"Share of counted lines agreeing with the book; target {sc['accuracy_target']:.0%}"),
        Headline("stock", "value_error", "Stock value error", round(exposure, 2), "GBP", t, "NOT accurate",
                 "round(sum(value_error), 2)", "Sum of |counted - book| x unit cost"),
        Headline("stock", "net_adjustment", "Net stock adjustment if counts are right",
                 round(float(lines.net_value_adjustment.sum()), 2), "GBP", t, "NOT accurate",
                 "round(sum(net_value_adjustment), 2)", "Sum of (counted - book) x unit cost"),
        Headline("stock", "inaccurate_lines", "Lines where count disagrees with book", int((~lines.accurate).sum()),
                 "count", t, "NOT accurate", "count(*)", "Counted lines outside tolerance"),
        Headline("stock", "abs_error_kg", "Steel miscounted", round(float(lines.abs_error_kg.sum()), 1), "kg", t,
                 "NOT accurate AND abs_error_kg IS NOT NULL", "round(sum(abs_error_kg), 1)",
                 "Sum of |counted - book| converted to kg with the golden mass"),
        Headline("stock", "groups_below_target", "Site and section groups below target",
                 int((~summary.meets_target).sum()), "count", "recon.stock_summary", "NOT meets_target", "count(*)",
                 "Site x section type groups whose line accuracy is below target"),
    ]
    for site, r in by_site.iterrows():
        heads.append(Headline("stock", f"accuracy_{site}", f"Stock line accuracy, {site}",
                              round(100 * float(r.line_accuracy), 2), "percent", t, f"site_code = '{site}'",
                              "round(100 * avg(CAST(accurate AS DOUBLE)), 2)", f"Line accuracy at {site}"))
    return EngineResult("stock", lines, summary, exposure, "stock value error (GBP)", heads,
                        {"stock_lines": lines, "stock_summary": summary,
                         "stock_by_site": by_site.reset_index()})
