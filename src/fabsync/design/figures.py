"""The measured figures quoted in the design diagrams.

Every break point on the AS-IS process maps quotes a figure. None is typed by
hand: each is a query against the warehouse, mostly against the reconciliation
headlines, so the diagrams always agree with the app and the reports.
"""

from __future__ import annotations

import duckdb


def money(v: float) -> str:
    if v >= 1_000_000:
        return f"£{v / 1_000_000:.2f}m"
    if v >= 1_000:
        return f"£{v / 1_000:,.0f}k"
    return f"£{v:,.0f}"


def count(v: float) -> str:
    return f"{int(round(v)):,}"


def pct(v: float) -> str:
    return f"{v:.1f}%"


def tonnes(v: float) -> str:
    return f"{v:,.0f} tonnes"


def hours(v: float) -> str:
    return f"{v:,.0f} hours"


def headline(engine: str, key: str) -> str:
    return f"SELECT value FROM recon.headline WHERE engine = '{engine}' AND key = '{key}'"


FIGURES: dict[str, tuple[str, callable]] = {
    # purchase to pay (three-way match)
    "missing_grn_lines": (headline("three_way", "missing_GRN_lines"), count),
    "missing_grn_value": (headline("three_way", "missing_GRN_value"), money),
    "missing_invoice_lines": (headline("three_way", "missing_invoice_lines"), count),
    "missing_invoice_value": (headline("three_way", "missing_invoice_value"), money),
    "price_var_lines": (headline("three_way", "price_variance_lines"), count),
    "price_var_value": (headline("three_way", "price_variance_value"), money),
    "qty_var_lines": (headline("three_way", "quantity_variance_lines"), count),
    "qty_var_value": (headline("three_way", "quantity_variance_value"), money),
    "no_po_lines": (headline("three_way", "invoice_with_no_PO_lines"), count),
    "no_po_value": (headline("three_way", "invoice_with_no_PO_value"), money),
    "over_90_days": (headline("three_way", "over_90_days"), count),
    "value_at_risk": (headline("three_way", "value_at_risk"), money),
    # job cost
    "job_finance_only_codes": ("SELECT count(*) FROM core.finance_jobs WHERE NOT mrp_matched", count),
    "job_finance_only_cost": (headline("job_cost", "finance_only_cost"), money),
    "labour_gap": (headline("job_cost", "labour_gap_gross"), money),
    "labour_gap_jobs": ("SELECT count(*) FROM recon.job_cost WHERE in_corvus AND abs(labour_gap_pct) > 0.15", count),
    "material_misallocated": (headline("job_cost", "material_misallocated"), money),
    "job_gap": (headline("job_cost", "gross_gap"), money),
    "unallocated_hours": (headline("job_cost", "unallocated_hours"), hours),
    "orphan_wos": ("SELECT count(DISTINCT wo_no) FROM core.time_bookings WHERE NOT wo_matched", count),
    "sales_unmapped_count": ("SELECT count(*) FROM core.sales_invoices WHERE NOT job_matched", count),
    "sales_unmapped_value": ("SELECT sum(net_amount) FROM core.sales_invoices WHERE NOT job_matched", money),
    # traceability
    "coverage": (headline("traceability", "coverage"), pct),
    "trace_exposed_tonnes": (headline("traceability", "exposed_kg"), tonnes),
    "trace_exposed_jobs": (headline("traceability", "exposed_jobs"), count),
    "trace_exposed_sales": (headline("traceability", "exposed_sales"), money),
    "receipts_missing_cert": ("SELECT count(*) FROM staging.corvus_mrp_goods_received "
                              "WHERE heat_number IS NULL OR mill_cert_ref IS NULL", count),
    # stock and materials
    "stock_accuracy": (headline("stock", "line_accuracy"), pct),
    "stock_value_error": (headline("stock", "value_error"), money),
    "material_variants": ("SELECT count(*) FROM core.material_golden WHERE source_codes LIKE '%,%'", count),
    "uom_conflicts": ("SELECT count(*) FROM core.material_golden WHERE uom_conflict", count),
    "grade_unconfirmed_lines": ("SELECT sum(row_count) FROM core.material_xref WHERE status = 'review' "
                                "AND source_table IN ('purchase_orders', 'goods_received')", count),
    # suppliers
    "supplier_dupes_confirmed": ("SELECT count(*) FROM core.supplier_golden "
                                 "WHERE corvus_codes LIKE '%,%' OR finance_accounts LIKE '%,%'", count),
    "supplier_dupes_likely": ("""SELECT (SELECT count(*) FROM core.supplier_review_queue WHERE evidence_pos > 0)
                                      + (SELECT count(*) FROM core.supplier_candidate_pairs
                                         WHERE status = 'unmatched' AND cross_system AND evidence_pos > 0)""", count),
    # shop floor
    "shopfloor_quarantined": ("SELECT count(*) FROM governance.quarantine WHERE source_file LIKE 'shop_floor/%'",
                              count),
    "promised_missing": ("SELECT count(*) FROM core.delivery_notes WHERE promised_date IS NULL", count),
    "ncr_uncosted": ("SELECT count(*) FROM core.ncrs WHERE cost_impact IS NULL", count),
    "ncr_total": ("SELECT count(*) FROM core.ncrs", count),
    # KPIs
    "otif": ("SELECT value FROM marts.kpi_scorecard WHERE kpi_id = 'KPI-01'", pct),
    "wip_value": ("SELECT value FROM marts.kpi_scorecard WHERE kpi_id = 'KPI-07'", money),
    "wip_over_90": ("SELECT secondary_value FROM marts.kpi_scorecard WHERE kpi_id = 'KPI-07'", pct),
}


def compute(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Every figure, formatted for a diagram label."""
    out = {}
    for key, (sql, fmt) in FIGURES.items():
        value = con.execute(sql).fetchone()[0]
        if value is None:
            raise ValueError(f"figure {key} has no value; run make run-all first")
        out[key] = fmt(float(value))
    return out
