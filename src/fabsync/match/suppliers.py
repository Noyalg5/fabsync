"""Supplier matching: Corvus supplier names typed on purchase orders against the finance supplier master.

Corvus has no supplier master: each purchase order carries a supplier code and
a name as typed, and the same stockholder can appear under several codes. The
finance system has its own accounts, sometimes two for one supplier. Records
from both sides are compared pairwise within blocks.

* Normalise: upper case, ``&`` to ``AND``, punctuation removed, abbreviations
  expanded and legal suffixes dropped (config/matching.toml).
* Block: only records sharing the first normalised token are compared.
* Score: the higher of rapidfuzz ``token_sort_ratio`` on the normalised names
  and ``ratio`` on the names with spaces removed ("STEEL WORKS" = "STEELWORKS").
* Decide: >= 95 auto-accept, 80 to 95 human review queue, < 80 never merged.

Accepted links are grouped into supplier entities by connected components; a
pair in review is not merged until someone approves it. Each record keeps its
own code and name alongside the entity's canonical name.

Review items carry transactional evidence: how many of a Corvus code's
purchase orders were invoiced under the finance account in question.

Golden name survivorship: the finance supplier-master name with the most
invoices in the entity (the legal payee), else the most-used Corvus name.
"""

from __future__ import annotations

import itertools
import re
from collections import Counter, defaultdict

import pandas as pd
from rapidfuzz import fuzz

from fabsync.match.common import MatchContext

RECORDS_SQL = """
SELECT 'corvus_mrp' AS source_system, supplier_code AS source_code, supplier_name AS source_name,
       count(*) AS documents
FROM staging.corvus_mrp_purchase_orders GROUP BY ALL
UNION ALL
SELECT 'finance', m.supplier_account, m.supplier_name, count(i.invoice_no)
FROM staging.finance_supplier_master m LEFT JOIN staging.finance_purchase_invoices i USING (supplier_account)
GROUP BY ALL
ORDER BY 1, 2
"""
# Which finance account invoiced each Corvus supplier code's purchase orders.
INVOICED_SQL = """
SELECT p.supplier_code, i.supplier_account, count(DISTINCT p.po_no) AS pos
FROM staging.corvus_mrp_purchase_orders p JOIN staging.finance_purchase_invoices i ON i.po_reference = p.po_no
GROUP BY ALL
"""


def normalise(name: str, config: dict) -> str:
    s = name.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    abbreviations = config["supplier"]["abbreviations"]
    suffixes = set(config["supplier"]["legal_suffixes"])
    tokens = [abbreviations.get(t, t) for t in s.split()]
    return " ".join(t for t in tokens if t not in suffixes)


def score(a: str, b: str) -> tuple[float, str]:
    sort = fuzz.token_sort_ratio(a, b)
    compact = fuzz.ratio(a.replace(" ", ""), b.replace(" ", ""))
    return (round(sort, 1), "token_sort_ratio") if sort >= compact else (round(compact, 1), "compact_ratio")


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def evidence(a, b, invoiced: dict[str, Counter]) -> tuple[str, int]:
    """Transactional evidence for a pair, and how many purchase orders support it."""
    sides = {a.source_system: a, b.source_system: b}
    if len(sides) == 2:
        mrp, fin = sides["corvus_mrp"], sides["finance"]
        n = invoiced.get(mrp.source_code, Counter()).get(fin.source_code, 0)
        return f"{n} of {mrp.source_code}'s {mrp.documents} POs invoiced under {fin.source_code}", n
    if a.source_system == "corvus_mrp":
        shared = set(invoiced.get(a.source_code, {})) & set(invoiced.get(b.source_code, {}))
        n = sum(min(invoiced[a.source_code][s], invoiced[b.source_code][s]) for s in shared)
        return (f"both codes' POs invoiced under {', '.join(sorted(shared))}" if shared
                else "no finance account in common"), n
    codes = {c for c, accts in invoiced.items() if a.source_code in accts and b.source_code in accts}
    return (f"both accounts invoice POs raised under {', '.join(sorted(codes))}" if codes
            else "no Corvus supplier code in common"), len(codes)


def match_suppliers(ctx: MatchContext) -> dict:
    records = ctx.df(RECORDS_SQL)
    records["key"] = records.source_system + ":" + records.source_code
    records["normalised_name"] = records.source_name.map(lambda n: normalise(n, ctx.config))
    records["block_key"] = records.normalised_name.str.split().str[0]
    invoiced: dict[str, Counter] = defaultdict(Counter)
    for code, account, pos in ctx.con.execute(INVOICED_SQL).fetchall():
        invoiced[code][account] = pos

    pairs = []
    for block, grp in records.groupby("block_key", sort=True):
        for a, b in itertools.combinations(grp.sort_values("key").itertuples(), 2):
            s, scorer = score(a.normalised_name, b.normalised_name)
            ev, support = evidence(a, b, invoiced)
            pairs.append({
                "pair_id": None, "block_key": block, "left_key": a.key, "left_name": a.source_name,
                "right_key": b.key, "right_name": b.source_name, "left_normalised": a.normalised_name,
                "right_normalised": b.normalised_name, "cross_system": a.source_system != b.source_system,
                "method": f"rapidfuzz.{scorer}", "score": s, "status": ctx.status(s),
                "matched_on": f"normalised names '{a.normalised_name}' vs '{b.normalised_name}'",
                "evidence": ev, "evidence_pos": support})
    pairs = pd.DataFrame(pairs).sort_values(["block_key", "score", "left_key", "right_key"],
                                            ascending=[True, False, True, True]).reset_index(drop=True)
    pairs["pair_id"] = [f"SP{i:05d}" for i in range(1, len(pairs) + 1)]
    pairs["decision"] = pairs.status.map({"auto": "merged", "review": "held for review",
                                          "unmatched": "not merged: below review floor"})

    uf = UnionFind()
    for k in records.key:
        uf.find(k)
    for p in pairs[pairs.status == "auto"].itertuples():
        uf.union(p.left_key, p.right_key)
    records["cluster"] = records.key.map(uf.find)

    golden = []
    for i, (_, grp) in enumerate(sorted(records.groupby("cluster"), key=lambda kv: kv[1].normalised_name.min()), 1):
        fin = grp[grp.source_system == "finance"].sort_values(["documents", "source_code"], ascending=[False, True])
        mrp = grp[grp.source_system == "corvus_mrp"].sort_values(["documents", "source_code"], ascending=[False, True])
        name, rule = ((fin.source_name.iloc[0], "finance master name with most invoices") if len(fin)
                      else (mrp.source_name.iloc[0], "most-used Corvus name (no finance account)"))
        golden.append({"supplier_id": f"SUP{i:04d}", "cluster": grp.cluster.iloc[0], "canonical_name": name,
                       "name_rule": rule, "finance_accounts": ", ".join(fin.source_code),
                       "corvus_codes": ", ".join(sorted(mrp.source_code)), "members": len(grp),
                       "in_finance": len(fin) > 0, "in_corvus": len(mrp) > 0,
                       "duplicate_records": len(grp) - 1})
    golden = pd.DataFrame(golden)
    ids = dict(zip(golden.cluster, golden.supplier_id, strict=True))
    names = dict(zip(golden.cluster, golden.canonical_name, strict=True))
    records["supplier_id"] = records.cluster.map(ids)
    records["canonical_name"] = records.cluster.map(names)

    # Per-record crosswalk: the best counterpart on the other system, and its band.
    xref = []
    for r in records.itertuples():
        mine = pairs[((pairs.left_key == r.key) | (pairs.right_key == r.key)) & pairs.cross_system]
        best = mine.sort_values(["score", "pair_id"], ascending=[False, True]).head(1)
        in_cluster_other = records[(records.cluster == r.cluster) & (records.source_system != r.source_system)]
        if len(in_cluster_other):
            status = "auto"
        elif len(best) and best.status.iloc[0] == "review":
            status = "review"
        else:
            status = "unmatched"
        b = best.iloc[0] if len(best) else None
        other = None if b is None else (b.right_key if b.left_key == r.key else b.left_key)
        xref.append({
            "source_system": r.source_system, "source_code": r.source_code, "source_name": r.source_name,
            "normalised_name": r.normalised_name, "block_key": r.block_key, "documents": r.documents,
            "supplier_id": r.supplier_id, "canonical_name": r.canonical_name,
            "best_counterpart": other, "method": None if b is None else b.method,
            "score": None if b is None else float(b.score), "status": status,
            "matched_on": ("no record on the other system in the same block" if b is None else
                           f"{b.matched_on}; {b.evidence}"),
            "linked_via": ", ".join(sorted(in_cluster_other.key)) or None})
    xref = pd.DataFrame(xref)

    # One review item per pair of entities: approving it settles every record pair between them.
    entity = dict(zip(records.key, records.supplier_id, strict=True))
    members = records.groupby("supplier_id").key.agg(lambda k: ", ".join(sorted(k)))
    held = pairs[pairs.status == "review"].copy()
    held["left_entity"] = held.left_key.map(entity)
    held["right_entity"] = held.right_key.map(entity)
    held = held[held.left_entity != held.right_entity]
    held[["left_entity", "right_entity"]] = pd.DataFrame(
        [sorted(p) for p in zip(held.left_entity, held.right_entity, strict=True)], index=held.index)
    queue = []
    for (le, re_), grp in held.groupby(["left_entity", "right_entity"], sort=True):
        best = grp.sort_values(["evidence_pos", "score"], ascending=False).iloc[0]
        support = int(grp.evidence_pos.max())
        queue.append({"review_id": None, "left_entity": le, "left_members": members[le], "right_entity": re_,
                      "right_members": members[re_], "left_name": best.left_name, "right_name": best.right_name,
                      "score": float(grp.score.max()), "method": best.method, "pairs": ", ".join(grp.pair_id),
                      "matched_on": best.matched_on, "evidence": best.evidence, "evidence_pos": support,
                      "suggested_action": ("approve merge: invoices corroborate" if support > 0
                                           else "check VAT number, address and bank details"),
                      "est_minutes": ctx.minutes("supplier")})
    queue = pd.DataFrame(queue)
    queue["review_id"] = [f"SR{i:03d}" for i in range(1, len(queue) + 1)]

    ctx.write("core.supplier_candidate_pairs", pairs)
    ctx.write("core.supplier_xref", xref)
    ctx.write("core.supplier_golden", golden.drop(columns=["cluster"]), audit=False)
    ctx.write("core.supplier_review_queue", queue)

    mrp = xref[xref.source_system == "corvus_mrp"]
    ctx.lineage(rule_id="MA-03", source_table="purchase_orders, supplier_master",
                source_file="corvus_mrp/purchase_orders.csv, finance/supplier_master.csv",
                target_table="core.supplier_xref", rows=len(xref), affected=int((xref.status == "auto").sum()),
                detail=f"{len(pairs)} pairs scored in {records.block_key.nunique()} blocks; {len(queue)} to review; "
                       f"{len(mrp)} Corvus codes: {int((mrp.status == 'auto').sum())} auto, "
                       f"{int((mrp.status == 'review').sum())} review, {int((mrp.status == 'unmatched').sum())} "
                       f"unmatched; {len(golden)} supplier entities")
    return {"records": records, "pairs": pairs, "xref": xref, "golden": golden, "queue": queue}
