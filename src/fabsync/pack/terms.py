"""Every technical term the management pack uses, with the plain-English definition given at its first use.

The pack is written for a reader who has never seen the app, so each term is defined the first time it
appears. The document builder asks the glossary for a term as it writes; the first request returns the term
with its definition, later ones the term alone. A test reads the finished PDF and checks that the first
appearance of every term is followed by its definition.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    key: str
    pattern: str        # regular expression matching any use of the term in running text
    phrase: str         # how the term is written where it is defined
    definition: str


TERMS = [
    Term("value_at_risk", r"(?i)\bvalue at risk\b", "value at risk",
         "money tied up where orders, deliveries and invoices disagree, plus spend with no order behind it; "
         "money exposed, not money lost"),
    Term("dqi", r"(?i)data quality index", "data quality index",
         "a score out of 100 for how well the data meets its written rules, weighted so that rules about safety "
         "and money count most"),
    Term("traceability", r"(?i)traceab", "traceability",
         "being able to follow every piece of steel in a finished assembly back to the certificate the "
         "steelmaker issued for it"),
    Term("en1090", r"EN 1090", "EN 1090",
         "the standard structural steelwork is made to; a fabricator must be certified against it to CE or UKCA "
         "mark, and so sell, its steelwork"),
    Term("modelled", r"(?i)\bmodelled\b", "modelled",
         "calculated from measured figures and stated assumptions; an estimate or an aim, never a result"),
    Term("corvus", r"Corvus", "Corvus MRP",
         "the manufacturing system, installed in 2006, that plans production, material, stock and purchasing"),
    Term("works_order", r"(?i)works orders?", "works order",
         "the instruction to fabricate a set of assemblies for a contract, which the shop floor books its time "
         "against"),
    Term("bom", r"\bBOMs?\b|(?i:bills? of material)", "bill of material (BOM)",
         "the list of steel and fittings each assembly needs"),
    Term("ncr", r"\bNCRs?\b|(?i:non-conformance)", "non-conformance report (NCR)",
         "the record of a defect and what putting it right cost"),
    Term("po", r"\bPOs?\b|(?i:purchase orders?)", "purchase order (PO)", "the order sent to a supplier"),
    Term("grn", r"\bGRNs?\b|(?i:goods received)", "goods received note (GRN)",
         "the record that ordered goods arrived and were checked in"),
    Term("stockholder", r"(?i)stockholders?", "stockholder", "a merchant who sells steel from stock"),
    Term("mill_cert", r"(?i)mill certificates?", "mill certificate",
         "the steelmaker's certificate of a batch of steel's chemistry and strength"),
    Term("heat", r"(?i)heat numbers?", "heat number",
         "the steelmaker's number for the batch, or cast, the steel came from, printed on the steel and on its "
         "mill certificate"),
    Term("master_data", r"(?i)\bmaster data\b(?! service)", "master data",
         "the reference records every system shares: materials, suppliers, customers and jobs"),
    Term("golden", r"(?i)golden records?", "golden record",
         "the one agreed version of a material, supplier or job, built from every system's copy by written rules"),
    Term("quarantine", r"(?i)quarantin", "quarantine",
         "holding a record that fails a check, with its original values untouched, until someone corrects it "
         "at source"),
    Term("lineage", r"(?i)lineage", "lineage", "the record of which file and line every figure came from"),
    Term("reconciliation", r"(?i)reconcil", "reconciliation",
         "comparing two systems' records of the same thing line by line and explaining every difference"),
    Term("three_way", r"(?i)three-way match", "three-way match",
         "checking that the purchase order, the goods received note and the invoice agree"),
    Term("section", r"(?i)\bsections?\b", "section", "a rolled steel profile such as a beam, column or angle"),
    Term("first_in", r"(?i)first-in first-out", "first-in first-out",
         "each works order is assumed to have used the oldest delivery still in stock"),
    Term("kpi", r"\bKPIs?\b", "key performance indicator (KPI)",
         "one of the nine measures management runs the business on"),
    Term("otif", r"\bOTIF\b", "OTIF", "on time, in full: deliveries made by the promised date with everything "
                                      "on the lorry"),
    Term("wip", r"\bWIP\b", "work in progress (WIP)", "work started on the shop floor but not yet delivered"),
    Term("yield", r"(?i)\byield\b", "yield", "the share of the steel bought that ends up in finished parts"),
    Term("offcut", r"(?i)offcuts?", "offcut", "the part of a bar left over after cutting"),
    Term("cost_of_quality", r"(?i)cost of quality", "cost of quality",
         "what putting defects right costs, as a share of sales"),
    Term("integration", r"(?i)integration layer", "integration layer",
         "scheduled jobs that collect data from every system each night, check it and record where every row "
         "went"),
    Term("mds", r"(?i)master data service", "master data service",
         "the one place that decides what each material, supplier, customer and job is called"),
    Term("warehouse", r"(?i)\bwarehouse\b", "data warehouse",
         "a separate database holding a copy of everything, organised for reporting"),
    Term("crosswalk", r"(?i)crosswalk", "crosswalk",
         "a translation table listing every way a thing is written in each system"),
    Term("system_of_record", r"(?i)system of record", "system of record",
         "the one system where a kind of data is created and corrected; every other system holds a copy"),
    Term("data_owner", r"(?i)data owners?", "data owner", "the manager answerable for one kind of data being right"),
    Term("steward", r"(?i)\bstewards?\b", "data steward", "the person who works that data's queues day to day"),
    Term("exception_queue", r"(?i)exception queues?", "exception queue",
         "the list of records that break a rule, each with its owner and the fix"),
    Term("review_queue", r"(?i)review queues?", "review queue",
         "the list of uncertain matches waiting for a person to decide"),
    Term("nesting", r"(?i)\bnesting\b", "nesting",
         "arranging the lengths cut from each bar so that as little as possible is wasted"),
    Term("cutting_list", r"(?i)cutting lists?", "cutting list",
         "the saw operator's list of what to cut, and from which bars"),
    Term("app_payment", r"(?i)applications? for payment", "application for payment",
         "an interim bill on a construction contract"),
    Term("baseline", r"(?i)\bbaselines?\b", "baseline",
         "the measures taken before anything changes; every benefit is measured against them"),
    Term("write_back", r"(?i)write-back", "write-back",
         "sending approved changes back into Corvus MRP and the finance system"),
    Term("dual", r"(?i)dual running|parallel run", "dual running",
         "doing a job the old way and the new way at once until the new way is proven"),
    Term("committee", r"(?i)management committee", "management committee",
         "the Managing Director, the programme sponsor and the four data owners, meeting at the end of each "
         "quarter"),
    Term("inherent", r"(?i)\binherent\b", "inherent score",
         "likelihood times impact, each scored from 1 to 5, before any mitigation"),
    Term("residual", r"(?i)\bresidual\b", "residual score", "the same score once the mitigation is working"),
]
BY_KEY = {t.key: t for t in TERMS}


class Glossary:
    """Hands out terms in document order: defined the first time, plain after that."""

    def __init__(self) -> None:
        self.defined: list[str] = []

    def __call__(self, key: str, text: str | None = None) -> str:
        term = BY_KEY[key]
        if key in self.defined:
            return text or term.phrase
        self.defined.append(key)
        return f"<b>{text or term.phrase}</b> ({term.definition})"

    def definition(self, key: str) -> str:
        """The definition alone, for layouts that set the term apart from it, such as a headline tile."""
        self.defined.append(key)
        return BY_KEY[key].definition

    def plain(self, key: str) -> str:
        if key not in self.defined:
            raise KeyError(f"{key} used before it is defined")
        return BY_KEY[key].phrase
