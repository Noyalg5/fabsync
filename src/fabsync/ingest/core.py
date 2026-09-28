"""Core layer: conformed and joined.

Core conforms references that the three systems write differently (works
orders, jobs, sites, operations) and joins child records to their parents.
Joins are always left joins with an explicit matched flag: an orphan booking or
a finance job with no MRPII job stays in core, flagged, rather than vanishing.
Every core table is checked to hold exactly as many rows as its staging source.

Matching of materials, suppliers and customers across systems is a separate
stage and is not done here.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import duckdb

from fabsync.ingest.warehouse import Recorder, now

CONFORMANCE_PATH = Path("config/conformance.toml")

# Five-digit Corvus works order number from free text: "WO 10432", "wo-10432", "10432 (rev B)".
WO_FROM_TEXT = r"try_cast(regexp_extract({col}, '(\d{{5}})', 1) AS INTEGER)"
# J-24-0871, J24-0871, 24-0871, j-24-0871 and J-24-871 all conform to J-24-0871.
JOB_FROM_TEXT = (r"CASE WHEN regexp_matches({col}, '(?i)^j?-?\d{{2}}-?\d{{1,4}}$') THEN 'J-' || "
                 r"regexp_extract({col}, '(?i)^j?-?(\d{{2}})', 1) || '-' || "
                 r"lpad(regexp_extract({col}, '(\d{{1,4}})$', 1), 4, '0') END")
# J-24-0871 becomes 24871 in the finance system.
FINANCE_CODE = "substr({col}, 3, 2) || CAST(CAST(substr({col}, 6) AS INTEGER) AS VARCHAR)"


@dataclass(frozen=True)
class Check:
    """A rule applied while building a core table, measured after the build."""

    rule_id: str
    affected_sql: str  # count of rows the rule changed or flagged, over the built table
    detail: str  # format string; receives affected and any extra counts named in extra_sql
    extra_sql: tuple[tuple[str, str], ...] = ()


def load_reference(con: duckdb.DuckDBPyConnection, rec: Recorder, config_path: Path) -> None:
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    con.execute("CREATE TABLE core.sites (site_code VARCHAR PRIMARY KEY, site_name VARCHAR)")
    con.execute("CREATE TABLE core.site_aliases (alias_key VARCHAR PRIMARY KEY, site_code VARCHAR)")
    con.execute("CREATE TABLE core.operation_aliases (alias_key VARCHAR PRIMARY KEY, operation_code VARCHAR)")
    aliases: dict[str, str] = {}
    for site in config["site"]:
        con.execute("INSERT INTO core.sites VALUES (?, ?)", [site["site_code"], site["site_name"]])
        for alias in site["aliases"]:
            aliases[alias.strip().casefold()] = site["site_code"]
    con.executemany("INSERT INTO core.site_aliases VALUES (?, ?)", sorted(aliases.items()))
    ops: dict[str, str] = {}
    for code, names in config["operation_aliases"].items():
        for name in names:
            ops[name.strip().casefold()] = code
    con.executemany("INSERT INTO core.operation_aliases VALUES (?, ?)", sorted(ops.items()))
    started = now()
    for table, n in (("core.site_aliases", len(aliases)), ("core.operation_aliases", len(ops))):
        rule = "CO-02" if "site" in table else "CO-04"
        rec.lineage(layer="core", source_system="config", source_table="conformance", source_file=str(config_path),
                    target_table=table, rule_id=rule, rows_in=n, rows_out=n, detail="reference loaded from config",
                    started_at=started)


def build(con: duckdb.DuckDBPyConnection, rec: Recorder, *, target: str, source: str, system: str,
          sql: str, checks: tuple[Check, ...] = ()) -> int:
    started = now()
    rows_in = con.execute(f"SELECT count(*) FROM {source}").fetchone()[0]
    con.execute(f"CREATE TABLE {target} AS {sql}")
    rows_out = con.execute(f"SELECT count(*) FROM {target}").fetchone()[0]
    if rows_out != rows_in:
        raise AssertionError(f"{target}: {rows_in} rows in, {rows_out} out; core must not gain or lose rows")
    table = source.split(".", 1)[1].removeprefix(f"{system}_")
    file = f"{system}/{table}.csv"
    rec.lineage(layer="core", source_system=system, source_table=table, source_file=file, target_table=target,
                rule_id="CO-06", rows_in=rows_in, rows_out=rows_out, detail=f"from {source}", started_at=started)
    for check in checks:
        affected = con.execute(f"SELECT count(*) FROM {target} WHERE {check.affected_sql}").fetchone()[0]
        extras = {name: con.execute(q.format(t=target)).fetchone()[0] for name, q in check.extra_sql}
        rec.lineage(layer="core", source_system=system, source_table=table, source_file=file, target_table=target,
                    rule_id=check.rule_id, rows_in=rows_out, rows_out=rows_out, rows_affected=affected,
                    detail=check.detail.format(affected=affected, **extras), started_at=started)
    return rows_out


LINEAGE_COLS = "_source_file, _source_row"


def build_core(con: duckdb.DuckDBPyConnection, rec: Recorder, config_path: Path = CONFORMANCE_PATH) -> dict[str, int]:
    load_reference(con, rec, config_path)
    counts: dict[str, int] = {}

    def b(target: str, source: str, system: str, sql: str, *checks: Check) -> None:
        counts[target] = build(con, rec, target=target, source=source, system=system, sql=sql, checks=checks)

    site = "(SELECT site_code FROM core.site_aliases WHERE alias_key = lower(trim({col})))"

    # ---- Corvus MRP --------------------------------------------------------
    b("core.works_orders", "staging.corvus_mrp_works_orders", "corvus_mrp", f"""
        SELECT w.wo_no, w.job_no, {FINANCE_CODE.format(col='w.job_no')} AS finance_job_code,
               w.customer_ref, w.part_code, w.description, w.qty, w.uom, w.planned_hours,
               w.planned_start, w.planned_finish, w.actual_finish, w.status,
               w.site AS site_code, s.site_name, w.execution_class, w.{LINEAGE_COLS.replace(', ', ', w.')}
        FROM staging.corvus_mrp_works_orders w LEFT JOIN core.sites s ON s.site_code = w.site
        ORDER BY w.wo_no""",
      Check("CO-03", "finance_job_code IS NOT NULL", "{affected:,} finance job codes derived from job_no"))

    finance_codes = """(SELECT job_code FROM staging.finance_job_costs UNION
                        SELECT job_code FROM staging.finance_sales_invoices UNION
                        SELECT job_code FROM staging.finance_purchase_invoices WHERE job_code IS NOT NULL)"""
    started = now()
    con.execute(f"""
        CREATE TABLE core.jobs AS
        SELECT job_no, any_value(finance_job_code) AS finance_job_code, min(customer_ref) AS customer_ref,
               mode(site_code) AS site_code, count(*) AS works_orders, sum(planned_hours) AS planned_hours,
               min(planned_start) AS planned_start, max(planned_finish) AS planned_finish,
               any_value(finance_job_code) IN {finance_codes} AS in_finance,
               -- One class per structure; a job whose works orders disagree has none, and is treated as EXC3.
               CASE WHEN count(DISTINCT execution_class) = 1 THEN min(execution_class) END AS execution_class
        FROM core.works_orders GROUP BY job_no ORDER BY job_no""")
    n_jobs, not_in_fin = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE NOT in_finance) FROM core.jobs").fetchone()
    counts["core.jobs"] = n_jobs
    rec.lineage(layer="core", source_system="corvus_mrp", source_table="works_orders",
                source_file="corvus_mrp/works_orders.csv", target_table="core.jobs", rule_id="CO-05",
                rows_in=n_jobs, rows_out=n_jobs, rows_affected=not_in_fin,
                detail=f"{n_jobs} jobs from works orders; {not_in_fin} have no finance job code", started_at=started)

    started = now()
    con.execute(f"""
        CREATE TABLE core.finance_jobs AS
        SELECT f.job_code AS finance_job_code, j.job_no, j.job_no IS NOT NULL AS mrp_matched
        FROM {finance_codes} f LEFT JOIN core.jobs j ON j.finance_job_code = f.job_code
        ORDER BY f.job_code""")
    n_fin, unmatched = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE NOT mrp_matched) FROM core.finance_jobs").fetchone()
    counts["core.finance_jobs"] = n_fin
    rec.lineage(layer="core", source_system="finance", source_table="job_costs",
                source_file="finance/*.csv", target_table="core.finance_jobs", rule_id="CO-05",
                rows_in=n_fin, rows_out=n_fin, rows_affected=unmatched,
                detail=f"{n_fin} distinct finance job codes; {unmatched} have no MRPII job ({unmatched / n_fin:.1%})",
                started_at=started)

    b("core.bom_lines", "staging.corvus_mrp_bom_lines", "corvus_mrp", """
        SELECT l.* EXCLUDE (_run_id), w.job_no, w.wo_no IS NOT NULL AS wo_matched
        FROM staging.corvus_mrp_bom_lines l LEFT JOIN core.works_orders w USING (wo_no)
        ORDER BY l.wo_no, l.line_no""",
      Check("CO-05", "NOT wo_matched", "{affected:,} lines with no works order"))

    b("core.stock", "staging.corvus_mrp_stock", "corvus_mrp", """
        SELECT material_code, description, location, site AS site_code, qty_on_hand, uom, unit_cost,
               last_count_date, counted_qty, counted_qty - qty_on_hand AS count_variance, _source_file, _source_row
        FROM staging.corvus_mrp_stock ORDER BY material_code, site, location""")

    b("core.purchase_orders", "staging.corvus_mrp_purchase_orders", "corvus_mrp", """
        SELECT * EXCLUDE (_run_id), qty * unit_price AS order_value
        FROM staging.corvus_mrp_purchase_orders ORDER BY po_no""")

    b("core.goods_received", "staging.corvus_mrp_goods_received", "corvus_mrp", """
        SELECT g.* EXCLUDE (_run_id), p.po_no IS NOT NULL AS po_matched
        FROM staging.corvus_mrp_goods_received g LEFT JOIN staging.corvus_mrp_purchase_orders p USING (po_no)
        ORDER BY g.grn_no""",
      Check("CO-05", "NOT po_matched", "{affected:,} receipts with no purchase order"))

    # ---- Finance -------------------------------------------------------------
    def job_join(alias: str) -> str:
        return f"LEFT JOIN core.jobs j ON j.finance_job_code = {alias}.job_code"

    b("core.purchase_invoices", "staging.finance_purchase_invoices", "finance", f"""
        SELECT i.* EXCLUDE (_run_id), j.job_no,
               CASE WHEN i.job_code IS NULL THEN NULL ELSE j.job_no IS NOT NULL END AS job_matched,
               CASE WHEN i.po_reference IS NULL THEN NULL ELSE p.po_no IS NOT NULL END AS po_matched
        FROM staging.finance_purchase_invoices i {job_join('i')}
        LEFT JOIN staging.corvus_mrp_purchase_orders p ON p.po_no = i.po_reference
        ORDER BY i.invoice_date, i.invoice_no""",
      Check("CO-03", "job_no IS NOT NULL", "{affected:,} invoices mapped to an MRPII job"),
      Check("CO-05", "job_matched = false OR po_matched = false",
            "{affected:,} invoices flagged: {nojob:,} job code not in MRPII, {nopo:,} PO not in MRPII",
            (("nojob", "SELECT count(*) FROM {t} WHERE job_matched = false"),
             ("nopo", "SELECT count(*) FROM {t} WHERE po_matched = false"))))

    b("core.sales_invoices", "staging.finance_sales_invoices", "finance", f"""
        SELECT i.* EXCLUDE (_run_id), j.job_no, j.job_no IS NOT NULL AS job_matched
        FROM staging.finance_sales_invoices i {job_join('i')} ORDER BY i.invoice_date, i.invoice_no""",
      Check("CO-05", "NOT job_matched", "{affected:,} invoices on a job code with no MRPII job"))

    b("core.job_costs", "staging.finance_job_costs", "finance", f"""
        SELECT c.* EXCLUDE (_run_id), j.job_no, j.job_no IS NOT NULL AS job_matched
        FROM staging.finance_job_costs c {job_join('c')} ORDER BY c.job_code, c.period, c.cost_type""",
      Check("CO-05", "NOT job_matched", "{affected:,} cost lines on a job code with no MRPII job"))

    b("core.supplier_master", "staging.finance_supplier_master", "finance", """
        SELECT * EXCLUDE (_run_id) FROM staging.finance_supplier_master ORDER BY supplier_account""")

    # ---- Shop floor ------------------------------------------------------------
    b("core.time_bookings", "staging.shop_floor_time_bookings", "shop_floor", f"""
        SELECT b.booking_id, b.operator, b.works_order AS works_order_raw,
               {WO_FROM_TEXT.format(col='b.works_order')} AS wo_no,
               b.operation AS operation_raw, o.operation_code, b.hours, b.booking_date,
               b.site AS site_raw, {site.format(col='b.site')} AS site_code,
               w.job_no, w.wo_no IS NOT NULL AS wo_matched, b._source_file, b._source_row
        FROM staging.shop_floor_time_bookings b
        LEFT JOIN core.operation_aliases o ON o.alias_key = lower(trim(b.operation))
        LEFT JOIN core.works_orders w ON w.wo_no = {WO_FROM_TEXT.format(col='b.works_order')}
        ORDER BY b.booking_date, b.booking_id""",
      Check("CO-01", "works_order_raw <> CAST(wo_no AS VARCHAR) OR wo_no IS NULL",
            "{affected:,} references rewritten to the bare number; {unparsed:,} with no five-digit number",
            (("unparsed", "SELECT count(*) FROM {t} WHERE wo_no IS NULL"),)),
      Check("CO-02", "site_raw <> site_code OR site_code IS NULL",
            "{affected:,} site names conformed; {unresolved:,} unresolved",
            (("unresolved", "SELECT count(*) FROM {t} WHERE site_code IS NULL"),)),
      Check("CO-04", "operation_raw IS NOT NULL AND (operation_code IS NULL OR operation_raw <> operation_code)",
            "{affected:,} operation names conformed; {blank:,} blank; {unresolved:,} unresolved",
            (("blank", "SELECT count(*) FROM {t} WHERE operation_raw IS NULL"),
             ("unresolved", "SELECT count(*) FROM {t} WHERE operation_raw IS NOT NULL AND operation_code IS NULL"))),
      Check("CO-05", "NOT wo_matched",
            "{affected:,} bookings on {orphans} works orders that do not exist in Corvus MRP",
            (("orphans", "SELECT count(DISTINCT wo_no) FROM {t} WHERE NOT wo_matched"),)))

    b("core.delivery_notes", "staging.shop_floor_delivery_notes", "shop_floor", f"""
        SELECT d.dn_no, d.job AS job_raw, {JOB_FROM_TEXT.format(col='d.job')} AS job_no, d.customer AS customer_raw,
               d.despatch_date, d.promised_date, d.tonnage, d.vehicle,
               j.job_no IS NOT NULL AS job_matched, d._source_file, d._source_row
        FROM staging.shop_floor_delivery_notes d
        LEFT JOIN core.jobs j ON j.job_no = {JOB_FROM_TEXT.format(col='d.job')}
        ORDER BY d.despatch_date, d.dn_no""",
      Check("CO-03", "job_raw <> job_no OR job_no IS NULL", "{affected:,} job references conformed to J-YY-NNNN"),
      Check("CO-05", "NOT job_matched", "{affected:,} despatches on a job not in Corvus MRP"))

    b("core.ncrs", "staging.shop_floor_ncr_log", "shop_floor", f"""
        SELECT n.ncr_no, n.works_order AS works_order_raw, {WO_FROM_TEXT.format(col='n.works_order')} AS wo_no,
               w.job_no, n.raised_date, n.category AS category_raw, n.description, n.cost_impact, n.closed_date,
               w.wo_no IS NOT NULL AS wo_matched, n._source_file, n._source_row
        FROM staging.shop_floor_ncr_log n
        LEFT JOIN core.works_orders w ON w.wo_no = {WO_FROM_TEXT.format(col='n.works_order')}
        ORDER BY n.ncr_no""",
      Check("CO-01", "works_order_raw <> CAST(wo_no AS VARCHAR) OR wo_no IS NULL",
            "{affected:,} references rewritten to the bare number"),
      Check("CO-05", "NOT wo_matched", "{affected:,} NCRs on works orders not in Corvus MRP"))

    b("core.weekly_capacity", "staging.shop_floor_weekly_capacity", "shop_floor", f"""
        SELECT c.week_commencing, c.site AS site_raw, {site.format(col='c.site')} AS site_code,
               c.available_hours, c.booked_hours, c._source_file, c._source_row
        FROM staging.shop_floor_weekly_capacity c ORDER BY c.week_commencing, site_code""",
      Check("CO-02", "site_raw <> site_code OR site_code IS NULL",
            "{affected:,} site names conformed; {unresolved:,} unresolved",
            (("unresolved", "SELECT count(*) FROM {t} WHERE site_code IS NULL"),)))
    return counts
