"""The data quality scorecard: docs/dq-scorecard.md.

Aggregated three ways, by source system, by quality dimension and by owning
role, with the headline index and how it is calculated. The report describes
the latest run and holds no run ids or timestamps, so it changes only when the
data or the rules change. The trend lives in governance.v_dq_trend.
"""

from __future__ import annotations

import pandas as pd

from fabsync.quality.engine import QualityResult

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SYSTEM_LABEL = {"corvus_mrp": "Corvus MRP", "finance": "Finance system", "shop_floor": "Shop-floor spreadsheets"}


def group_scorecard(results: pd.DataFrame, by: str) -> pd.DataFrame:
    ok = results[results.status == "ok"]
    rows = []
    for key, g in ok.groupby(by):
        rows.append({by: key, "rules": len(g), "met": int(g.threshold_met.sum()),
                     "critical_breaches": int(((g.severity == "critical") & ~g.threshold_met).sum()),
                     "checked": int(g.records_checked.sum()), "failed": int(g.records_failed.sum()),
                     "index": round(100 * float((g.weight * g.score).sum() / g.weight.sum()), 1)})
    return pd.DataFrame(rows).sort_values(["index", by]).reset_index(drop=True)


def md(v) -> str:
    return str(v).replace("|", "\\|")


def scorecard_table(frame: pd.DataFrame, by: str, label: str, names: dict | None = None) -> list[str]:
    out = [f"| {label} | Index | Rules met | Critical breaches | Records checked | Records failing |",
           "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in frame.itertuples():
        name = (names or {}).get(getattr(r, by), getattr(r, by))
        out.append(f"| {name} | **{r.index:.1f}** | {r.met} of {r.rules} | {r.critical_breaches or ''} | "
                   f"{r.checked:,} | {r.failed:,} |")
    return out


def render_scorecard(result: QualityResult) -> str:
    res = result.results.copy()
    rules = {r.id: r for r in result.rules.rules}
    weights = result.rules.weights
    ok = res[res.status == "ok"]
    exc = result.exceptions
    breaches = ok[~ok.threshold_met].assign(rank=lambda d: d.severity.map(SEVERITY_RANK)) \
        .sort_values(["rank", "pass_rate", "rule_id"])
    out = [
        "# Data quality scorecard",
        "",
        "**All data assessed here is synthetic.** It represents no real company, supplier, customer or job.",
        "",
        f"Produced by `make quality` from the {len(res)} rules declared in `config/dq_rules.yaml`, evaluated as at "
        f"{result.rules.parameters.get('as_of_date')}. Every run is kept in `governance.dq_results` so the index can "
        "be trended (`governance.v_dq_trend`). Failing records are in `governance.v_dq_exception_queue`.",
        "",
        f"## Headline data quality index: {result.dq_index:.1f} / 100",
        "",
        f"{int(ok.threshold_met.sum())} of {len(ok)} rules meet their threshold. "
        f"{int(((ok.severity == 'critical') & ~ok.threshold_met).sum())} critical rules are breached. "
        f"{len(exc):,} failing records are in the exception queue."
        + (f" Rules that could not be evaluated: {', '.join(res[res.status == 'error'].rule_id)}."
           if (res.status == "error").any() else ""),
        "",
        "### How the index is calculated",
        "",
        "For each rule, the pass rate is the share of records checked that pass. The rule's score is its pass",
        "rate divided by its threshold, capped at 1. A rule that meets its threshold scores 1; one that falls short",
        "scores in proportion. The index is the severity-weighted average of rule scores, times 100:",
        "",
        "```",
        "score_r = min(1, pass_rate_r / threshold_r)",
        "DQI     = 100 x sum(weight_r x score_r) / sum(weight_r)",
        "```",
        "",
        "Severity weights: " + ", ".join(f"{k} {v:g}" for k, v in weights.items()) + ". Each step up doubles the",
        "weight, so one critical rule counts as much as eight low ones. Every scorecard line below uses the same",
        "formula over its own rules. Rules that error are excluded and reported separately.",
        "",
        "## By owning role",
        "",
        "This is the view that makes governance actionable: each role owns its rules, its exceptions and",
        "its score.",
        "",
        *scorecard_table(group_scorecard(res, "owner"), "owner", "Owner"),
        "",
    ]
    for owner, g in exc.groupby("owner", sort=True):
        top = g.groupby(["rule_id", "rule_name", "severity"]).size().reset_index(name="n") \
            .assign(rank=lambda d: d.severity.map(SEVERITY_RANK)).sort_values(["rank", "n"], ascending=[True, False])
        items = "; ".join(f"{r.rule_id} {r.rule_name} ({r.n:,})" for r in top.head(4).itertuples())
        out.append(f"- **{owner}:** {len(g):,} open exceptions. Most severe first: {items}.")
    out += [
        "",
        "## By source system",
        "",
        *scorecard_table(group_scorecard(res, "system_of_record"), "system_of_record", "System of record",
                         SYSTEM_LABEL),
        "",
        "## By quality dimension",
        "",
        *scorecard_table(group_scorecard(res, "dimension"), "dimension", "Dimension"),
        "",
        "## Rules breaching their threshold",
        "",
        "| Rule | Severity | Owner | Pass rate | Threshold | Failing | Consequence |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for r in breaches.itertuples():
        out.append(f"| {r.rule_id} {md(r.rule_name)} | {r.severity} | {r.owner} | {r.pass_rate:.1%} | "
                   f"{r.threshold:.1%} | {r.records_failed:,} | {md(rules[r.rule_id].consequence)} |")
    out += [
        "",
        "## Seeded defects detected",
        "",
        "Each defect seeded into the synthetic sources (data/raw/DEFECTS.md) and the rules that catch it.",
        "",
        "| Defect | Rules | Failing records |",
        "| ---: | --- | ---: |",
    ]
    by_defect: dict[int, list[str]] = {}
    for rid, rule in rules.items():
        for d in rule.covers_defects:
            by_defect.setdefault(d, []).append(rid)
    for d in sorted(by_defect):
        ids = by_defect[d]
        failing = int(ok[ok.rule_id.isin(ids)].records_failed.sum())
        out.append(f"| {d} | {', '.join(ids)} | {failing:,} |")
    out += [
        "",
        "## All rules",
        "",
        "| Rule | Dimension | Severity | System | Owner | Checked | Failing | Pass rate | Threshold | Met |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | :---: |",
    ]
    for r in res.itertuples():
        if r.status != "ok":
            out.append(f"| {r.rule_id} {md(r.rule_name)} | {r.dimension} | {r.severity} | {r.system_of_record} | "
                       f"{r.owner} | | | error | {r.threshold:.1%} | |")
            continue
        out.append(f"| {r.rule_id} {md(r.rule_name)} | {r.dimension} | {r.severity} | "
                   f"{SYSTEM_LABEL[r.system_of_record]} | {r.owner} | {r.records_checked:,} | {r.records_failed:,} | "
                   f"{r.pass_rate:.1%} | {r.threshold:.1%} | {'yes' if r.threshold_met else '**no**'} |")
    out.append("")
    return "\n".join(out)
