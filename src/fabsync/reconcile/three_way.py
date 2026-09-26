"""Three-way match: purchase order line to goods received note to purchase invoice.

Each Corvus PO carries one material line, so a PO is a line. Every line is put
in exactly one category, tested in this order:

* missing GRN: past its promised date (plus grace) with no goods receipt
* missing invoice: received, past the invoice grace period, not invoiced
* not yet due: ordered but not yet due for receipt, or received but not yet
  due for invoice. Not an exception, but shown so every line is accounted for.
* price variance: invoiced amount differs from received quantity x PO price by
  more than the percentage tolerance, the same 5% the data quality rule applies
* quantity variance: received quantity differs from ordered by more than the
  quantity tolerance
* matched: none of the above

Invoices are then checked from the other side. Any invoice that references no
Corvus PO, and is not on an exempt overhead nominal code, is an "invoice with no
PO".

Value at risk per line:

* missing GRN: order value, which is committed spend with nothing received
* missing invoice: received quantity x PO price, an unrecorded liability
* price variance: |invoiced - expected|
* quantity variance: |received - ordered| x PO price
* invoice with no PO: the invoice's net amount, which is uncontrolled spend
* matched and not yet due: nil

Ageing runs from the date the item became an exception: the promised date for
a missing GRN, the receipt date for a missing invoice, and the invoice date
otherwise.
"""

from __future__ import annotations

import pandas as pd

from fabsync.reconcile.common import EngineResult, Headline, age_bucket, bucket_order

CATEGORIES = ["matched", "quantity variance", "price variance", "missing GRN", "missing invoice",
              "invoice with no PO", "not yet due"]
EXCEPTIONS = CATEGORIES[1:6]
NOMINAL_LABEL = {"5010": "consumables", "5100": "galvanising", "5110": "paint", "5120": "erection",
                 "5130": "profiling", "5140": "inspection", "5150": "subcontract fabrication",
                 "5200": "plant hire", "5300": "transport", "7000": "overheads"}

LINES_SQL = """
WITH g AS (SELECT po_no, count(*) AS grns, sum(qty_received) AS qty_received, min(received_date) AS received_date,
                  string_agg(grn_no, ', ' ORDER BY grn_no) AS grn_nos, min(_source_row) AS grn_source_row
           FROM staging.corvus_mrp_goods_received GROUP BY 1),
     i AS (SELECT po_reference, count(*) AS invoices, sum(net_amount) AS invoiced, min(invoice_date) AS invoice_date,
                  string_agg(invoice_no, ', ' ORDER BY invoice_no) AS invoice_nos,
                  min(_source_row) AS invoice_source_row
           FROM staging.finance_purchase_invoices WHERE po_reference IS NOT NULL GROUP BY 1)
SELECT p.po_no, p.supplier_code, trim(p.supplier_name) AS supplier_name, trim(p.material_code) AS material_code,
       p.uom, CAST(p.qty AS DOUBLE) AS qty_ordered, CAST(p.unit_price AS DOUBLE) AS unit_price,
       CAST(p.qty * p.unit_price AS DOUBLE) AS order_value, p.order_date, p.promised_date,
       g.grn_nos, CAST(g.qty_received AS DOUBLE) AS qty_received, g.received_date,
       i.invoice_nos, CAST(i.invoiced AS DOUBLE) AS invoiced, i.invoice_date,
       p._source_row AS po_source_row, g.grn_source_row, i.invoice_source_row
FROM staging.corvus_mrp_purchase_orders p LEFT JOIN g ON g.po_no = p.po_no LEFT JOIN i ON i.po_reference = p.po_no
ORDER BY p.po_no
"""

NO_PO_SQL = """
SELECT i.invoice_no, i.supplier_account, i.supplier_name, i.po_reference, CAST(i.net_amount AS DOUBLE) AS invoiced,
       i.invoice_date, i.nominal_code, i.job_code, i._source_row AS invoice_source_row
FROM staging.finance_purchase_invoices i
LEFT JOIN staging.corvus_mrp_purchase_orders p ON p.po_no = i.po_reference
WHERE p.po_no IS NULL
ORDER BY i.invoice_date, i.invoice_no
"""



def beyond(variance: float, tolerance: float) -> bool:
    """True if the variance exceeds the tolerance. A variance exactly on the tolerance is within it: quantities and
    prices carry float rounding noise, so without the margin a delivery exactly 2% short could fall either side."""
    return abs(variance) > tolerance + 1e-9 * max(1.0, abs(tolerance))

def classify(r, cfg: dict) -> dict:
    tw, as_of = cfg["three_way"], pd.Timestamp(cfg["as_of"])
    out = {"expected_invoice": None, "qty_variance": None, "price_variance": None, "price_tolerance": None,
           "value_at_risk": 0.0, "exception_date": None}
    if pd.isna(r.received_date):
        due = pd.Timestamp(r.promised_date) + pd.Timedelta(days=tw["receipt_grace_days"])
        if due > as_of:
            return {**out, "category": "not yet due",
                    "reason": f"promised {r.promised_date:%d/%m/%Y}; not due for receipt until {due:%d/%m/%Y}"}
        return {**out, "category": "missing GRN", "value_at_risk": r.order_value, "exception_date": r.promised_date,
                "reason": f"promised {r.promised_date:%d/%m/%Y}, nothing received; £{r.order_value:,.2f} committed"}
    received_value = r.qty_received * r.unit_price
    qty_var = r.qty_received - r.qty_ordered
    out.update(qty_variance=qty_var, expected_invoice=received_value)
    if pd.isna(r.invoiced):
        due = pd.Timestamp(r.received_date) + pd.Timedelta(days=tw["invoice_grace_days"])
        if due > as_of:
            return {**out, "category": "not yet due",
                    "reason": f"received {r.received_date:%d/%m/%Y}; invoice not due until {due:%d/%m/%Y}"}
        return {**out, "category": "missing invoice", "value_at_risk": received_value,
                "exception_date": r.received_date,
                "reason": f"received {r.received_date:%d/%m/%Y}, not invoiced; £{received_value:,.2f} unaccrued"}
    price_var = r.invoiced - received_value
    tolerance = tw["price_tolerance_pct"] * received_value
    out.update(price_variance=price_var, price_tolerance=tolerance, exception_date=r.invoice_date)
    if beyond(price_var, tolerance):
        return {**out, "category": "price variance", "value_at_risk": abs(price_var),
                "reason": f"invoiced £{r.invoiced:,.2f} against £{received_value:,.2f} expected "
                          f"({price_var:+,.2f}); tolerance £{tolerance:,.2f}"}
    if beyond(qty_var, tw["qty_tolerance"] * r.qty_ordered):
        return {**out, "category": "quantity variance", "value_at_risk": abs(qty_var) * r.unit_price,
                "reason": f"ordered {r.qty_ordered:g}, received {r.qty_received:g} {r.uom} "
                          f"({qty_var / r.qty_ordered:+.1%}); tolerance {tw['qty_tolerance']:.0%}"}
    return {**out, "category": "matched", "exception_date": None,
            "reason": f"received {r.qty_received:g} of {r.qty_ordered:g} {r.uom}; invoice within £{tolerance:,.2f}"}


def three_way_match(con, cfg: dict) -> EngineResult:
    tw, as_of = cfg["three_way"], pd.Timestamp(cfg["as_of"])
    lines = con.execute(LINES_SQL).df()
    classified = pd.DataFrame([classify(r, cfg) for r in lines.itertuples()], index=lines.index)
    lines = pd.concat([lines, classified], axis=1)
    lines.insert(0, "line_type", "PO line")
    lines.insert(0, "line_id", lines.po_no)

    no_po = con.execute(NO_PO_SQL).df()
    no_po = no_po[~no_po.nominal_code.isin(tw["po_exempt_nominals"])].copy()
    no_po["line_id"] = no_po.invoice_no
    no_po["line_type"] = "invoice"
    no_po["invoice_nos"] = no_po.invoice_no
    no_po["category"] = "invoice with no PO"
    no_po["value_at_risk"] = no_po.invoiced
    no_po["exception_date"] = no_po.invoice_date
    no_po["reason"] = [f"{NOMINAL_LABEL.get(n, n)} invoice from {s}"
                       + (f" referencing {p}, which is not a Corvus PO" if isinstance(p, str) else " with no PO")
                       for n, s, p in zip(no_po.nominal_code, no_po.supplier_name, no_po.po_reference, strict=True)]
    no_po["spend_type"] = no_po.nominal_code.map(lambda n: NOMINAL_LABEL.get(n, n))
    no_po = no_po.rename(columns={"supplier_account": "supplier_code"}).drop(columns=["invoice_no"])

    rows = pd.concat([lines, no_po], ignore_index=True)
    rows["age_days"] = [(as_of - pd.Timestamp(d)).days if pd.notna(d) else None for d in rows.exception_date]
    rows["age_bucket"] = [age_bucket(d, tw["ageing_buckets"]) if c in EXCEPTIONS else None
                          for d, c in zip(rows.age_days, rows.category, strict=True)]
    rows["is_exception"] = rows.category.isin(EXCEPTIONS)
    rows["source_file"] = ["finance/purchase_invoices.csv" if t == "invoice" else "corvus_mrp/purchase_orders.csv"
                           for t in rows.line_type]
    rows["source_row"] = rows.invoice_source_row.where(rows.line_type == "invoice", rows.po_source_row)
    for c in ("exception_date", "order_date", "promised_date", "received_date", "invoice_date"):
        rows[c] = pd.to_datetime(rows[c]).dt.date

    summary = (rows.groupby("category").agg(lines=("line_id", "size"), value_at_risk=("value_at_risk", "sum"),
                                            oldest_days=("age_days", "max"))
               .reindex(CATEGORIES).fillna({"lines": 0, "value_at_risk": 0.0}).reset_index())
    ageing = (rows[rows.is_exception].groupby(["category", "age_bucket"])
              .agg(lines=("line_id", "size"), value_at_risk=("value_at_risk", "sum")).reset_index())
    ageing["bucket_order"] = ageing.age_bucket.map({b: i for i, b in enumerate(bucket_order(tw["ageing_buckets"]))})
    ageing = ageing.sort_values(["category", "bucket_order"]).drop(columns="bucket_order").reset_index(drop=True)
    exposure = float(rows[rows.is_exception].value_at_risk.sum())

    t = "recon.three_way_lines"
    heads = [Headline("three_way", "value_at_risk", "Purchase-to-pay value at risk", round(exposure, 2), "GBP", t,
                      "is_exception", "round(sum(value_at_risk), 2)",
                      "Sum of value at risk over every line in an exception category")]
    for cat in CATEGORIES:
        n = int((rows.category == cat).sum())
        v = round(float(rows.loc[rows.category == cat, "value_at_risk"].sum()), 2)
        key = cat.replace(" ", "_")
        heads.append(Headline("three_way", f"{key}_lines", f"Lines: {cat}", n, "count", t,
                              f"category = '{cat}'", "count(*)", f"Lines classified {cat}"))
        if cat in EXCEPTIONS:
            heads.append(Headline("three_way", f"{key}_value", f"Value at risk: {cat}", v, "GBP", t,
                                  f"category = '{cat}'", "round(sum(value_at_risk), 2)",
                                  f"Value at risk on lines classified {cat}"))
    heads.append(Headline("three_way", "over_90_days", "Exceptions older than 90 days",
                          int((rows.is_exception & (rows.age_days > 90)).sum()), "count", t,
                          "is_exception AND age_days > 90", "count(*)", "Exception lines aged over 90 days"))
    return EngineResult("three_way", rows, summary, exposure, "purchase-to-pay value at risk (GBP)", heads,
                        {"three_way_lines": rows, "three_way_summary": summary, "three_way_ageing": ageing})
