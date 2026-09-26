"""Build the management pack: every chart and diagram as a 300 dpi PNG, then the A4 PDF that uses them.

The same PNGs are left in the figures folder for slides. The build is reproducible: the same warehouse and
the same committed documents give byte-identical files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
from matplotlib.figure import Figure

from fabsync.pack import charts, diagrams
from fabsync.pack.document import SECTION_NAMES, build_pdf
from fabsync.pack.facts import Facts, load
from fabsync.palette import SYSTEM_COLOURS, SYSTEM_LABELS

PDF_NAME = "fabsync-management-pack.pdf"


@dataclass
class Result:
    pdf: Path
    figures: dict[str, Path]


def make_figures(f: Facts) -> list[tuple[str, str, Figure]]:
    """Every figure the pack uses, in pack order, each with a file name fit for a slide library."""
    fig = f.fig
    tw, jt, st, br, cu = f.three_way, f.job_top, f.stock, f.trace_breaks, f.trace_customers
    by_system = f.dq_by_system
    by_owner = f.dq_by_owner
    gaps = {
        "corvus_finance_1": "Job J-24-0871 is 24871 in finance",
        "corvus_finance_2": f"{fig['supplier_dupes_confirmed']:.0f} suppliers under more than one record",
        "corvus_shop": f"{fig['unallocated_hours']:,.0f} hours booked to works orders Corvus never issued",
        "finance_shop": f"£{fig['labour_gap'] / 1000:,.0f}k of labour cost that disagrees with the hours booked",
    }
    rules_met = [f"{r.dq_index:.1f}  ({r.rules_met} of {r.rules} rules met)" for r in by_system.itertuples()]
    figures = [
        ("three_systems", "01-three-systems",
         diagrams.three_systems("The three systems today", gaps)),
        ("dq_by_system", "02-data-quality-by-system",
         charts.bar_h("Data quality index by the system that holds the data",
                      [SYSTEM_LABELS[s] for s in by_system.system], by_system.dq_index, rules_met,
                      "Data quality index (0 to 100)", colours=[SYSTEM_COLOURS[s] for s in by_system.system],
                      x_max=100)),
        ("order_to_cash", "03-order-to-cash",
         diagrams.swimlane("Order to cash, as it runs today", f.diagrams["as-is-order-to-cash"])),
        ("procure_to_pay", "04-procure-to-pay",
         diagrams.swimlane("Procure to pay, as it runs today", f.diagrams["as-is-procure-to-pay"])),
        ("value_at_risk", "05-value-at-risk",
         charts.bar_h("Purchase-to-pay value at risk, by what went wrong",
                      [c[0].upper() + c[1:] for c in tw.category], tw.value,
                      [f"{charts.gbp(v)}  ({n:,} lines)" for v, n in zip(tw.value, tw.lines, strict=True)],
                      "Value at risk (£)", money=True)),
        ("job_cost", "06-job-cost-gap",
         charts.bar_h("The 15 jobs whose cost is furthest from reconciling",
                      [f"{j}  {c}" for j, c in zip(jt.job_no, jt.customer_name, strict=True)], jt.unexplained_gap,
                      [charts.gbp(v) for v in jt.unexplained_gap],
                      "Unexplained gap (£); positive where finance holds more cost than the operational records, "
                      "negative where it holds less", money=True, row=0.19)),
        ("stock", "07-stock-accuracy",
         charts.bar_h("Stock line accuracy by site and section type; dashed line is the 95% target",
                      [f"{f.sites[s]}, {SECTION_NAMES.get(t, t)}" for s, t in zip(st.site_code, st.section_type,
                                                                                  strict=True)],
                      st.accuracy, [f"{a:.0f}%  ({n} of {m} lines)" for a, n, m in
                                    zip(st.accuracy, st.accurate_lines, st.lines, strict=True)],
                      "Counted lines that agree with the book (%)",
                      target=100 * f.reconcile["stock"]["accuracy_target"], x_max=100, row=0.2)),
        ("trace_breaks", "08-traceability-breaks",
         charts.bar_h("Where the chain from certificate to despatch first breaks",
                      [b[0].upper() + b[1:] for b in br.break_at], br.tonnes,
                      [f"{t:,.0f} t  ({n:,} BOM lines)" for t, n in zip(br.tonnes, br.lines, strict=True)],
                      "Steel where the chain first breaks (tonnes)")),
        ("trace_customers", "09-traceability-by-customer",
         charts.bar_h("Despatched steel without full traceability, the 12 most exposed customers",
                      list(cu.customer_name), cu.tonnes,
                      [f"{t:,.0f} t  ({j} jobs)" for t, j in zip(cu.tonnes, cu.exposed_jobs, strict=True)],
                      "Steel without full traceability (tonnes)", row=0.17)),
        ("architecture", "10-target-architecture",
         diagrams.architecture("The target: one integrated set of systems", f.diagrams["to-be-architecture"])),
        ("dq_by_owner", "11-data-quality-by-owner",
         charts.bar_h("Data quality index by owning role",
                      list(by_owner.owner), by_owner.dq_index,
                      [f"{r.dq_index:.1f}  ({r.rules_met} of {r.rules} rules met)" for r in by_owner.itertuples()],
                      "Data quality index (0 to 100)", x_max=100)),
        ("timeline", "12-rollout-timeline", charts.timeline("The 18-month rollout", f.timeline)),
        ("risk_heat_map", "13-risk-heat-map",
         charts.heat_maps(f"Risk register: {len(f.roadmap['risks'])} risks before and after mitigation",
                          f.roadmap["risks"])),
    ]
    return figures


def draw_figures(f: Facts, folder: Path) -> dict[str, Path]:
    return {key: charts.save(figure, folder / f"{name}.png") for key, name, figure in make_figures(f)}


def build_pack(warehouse: Path, out_dir: Path) -> Result:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        facts = load(con)
    finally:
        con.close()
    figures = draw_figures(facts, out_dir / "figures")
    pdf = build_pdf(facts, figures, out_dir / PDF_NAME)
    return Result(pdf, figures)
