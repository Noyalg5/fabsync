"""The management pack as an A4 document: sixteen pages that tell the whole story without the app.

Figure first, method second. Every figure comes from the facts gathered from the warehouse and the
committed documents; every technical term is defined the first time it appears; every page carries the
synthetic data statement; and the benefits page is labelled ILLUSTRATIVE throughout.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from PIL import Image as PILImage
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from fabsync.design.figures import money
from fabsync.pack.charts import band
from fabsync.pack.facts import FRAMES as FRAMES_SQL
from fabsync.pack.facts import Facts, strip_md
from fabsync.pack.terms import BY_KEY, Glossary
from fabsync.palette import ACCENT, ACCENT_FILL, GRID, INK, MUTED, PAPER, RULE
from fabsync.provenance import Origin, TracedInt, quote, record, scope, total, trace, word

SYNTHETIC = "Demonstration prototype. All data is synthetic."
SECTION_NAMES = {"L": "Angle", "FLAT": "Flat", "PLATE": "Plate", "CONSUMABLE": "Consumables"}
TITLE = "FabSync management pack"
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 20 * mm, 14 * mm, 17 * mm
FRAME_W = A4[0] - 2 * MARGIN_X
FRAME_H = A4[1] - MARGIN_TOP - MARGIN_BOTTOM

# Terms restated on the one-page summary, so it can be left behind on its own.
LEAVE_BEHIND_TERMS = ["value_at_risk", "dqi", "traceability", "en1090", "corvus", "works_order", "modelled"]

# The contents, in page order: section title, page it starts on.
CONTENTS = [
    ("Executive summary", 2), ("The problem", 3), ("How the work flows today", 4), ("What we found", 6),
    ("The target", 10), ("Who owns the data, and the rules", 11), ("How performance will be measured", 12),
    ("The plan", 13), ("Risks", 14), ("Benefits, illustrative", 15), ("The pack on one page", 16),
]
# The sections in the order they are written; the order matters, since each term is defined where first used.
SECTIONS = ["cover", "executive_summary", "problem", "maps", "findings", "target", "governance", "kpis", "plan",
            "risks", "benefits", "summary"]


def article(n: int) -> str:
    """'an' before a number said with a leading vowel sound: an 8-, 11-, 18- or 80-month plan."""
    return "an" if str(n).startswith(("8", "11", "18")) else "a"


def c(hex_colour: str) -> colors.Color:
    return colors.HexColor(hex_colour)


def register_fonts() -> None:
    ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for name, file in (("Sans", "DejaVuSans.ttf"), ("Sans-Bold", "DejaVuSans-Bold.ttf"),
                       ("Sans-Oblique", "DejaVuSans-Oblique.ttf"), ("Sans-BoldOblique", "DejaVuSans-BoldOblique.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(ttf / file)))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Oblique",
                                  boldItalic="Sans-BoldOblique")


def styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("body", fontName="Sans", fontSize=8.4, leading=11.4, textColor=c(INK), alignment=TA_LEFT,
                          spaceAfter=4)
    s = {"body": base}
    s["lead"] = ParagraphStyle("lead", base, fontSize=9.4, leading=13, spaceAfter=6)
    s["small"] = ParagraphStyle("small", base, fontSize=7.3, leading=9.6, spaceAfter=3)
    s["note"] = ParagraphStyle("note", s["small"], textColor=c(MUTED))
    s["cell"] = ParagraphStyle("cell", base, fontSize=6.9, leading=8.5, spaceAfter=0)
    s["cell_bold"] = ParagraphStyle("cell_bold", s["cell"], fontName="Sans-Bold")
    s["tight"] = ParagraphStyle("tight", s["cell"], fontSize=6.4, leading=7.8)
    s["head"] = ParagraphStyle("head", s["cell"], fontName="Sans-Bold")
    s["kicker"] = ParagraphStyle("kicker", base, fontName="Sans-Bold", fontSize=7.3, textColor=c(ACCENT),
                                 spaceAfter=2)
    s["h1"] = ParagraphStyle("h1", base, fontName="Sans-Bold", fontSize=15, leading=18.5, spaceAfter=6)
    s["h2"] = ParagraphStyle("h2", base, fontName="Sans-Bold", fontSize=9.6, leading=12.5, spaceBefore=5,
                             spaceAfter=3)
    s["number"] = ParagraphStyle("number", base, fontName="Sans-Bold", fontSize=22, leading=25, textColor=c(ACCENT),
                                 spaceAfter=1)
    s["number_small"] = ParagraphStyle("number_small", s["number"], fontSize=15, leading=18)
    s["tile_label"] = ParagraphStyle("tile_label", base, fontName="Sans-Bold", fontSize=7.8, leading=10,
                                     spaceAfter=2)
    s["tile_text"] = ParagraphStyle("tile_text", base, fontSize=7.1, leading=9.2, spaceAfter=0)
    s["cover_title"] = ParagraphStyle("cover_title", base, fontName="Sans-Bold", fontSize=34, leading=40,
                                      spaceAfter=6)
    s["cover_sub"] = ParagraphStyle("cover_sub", base, fontSize=14, leading=19, textColor=c(ACCENT), spaceAfter=14)
    s["banner"] = ParagraphStyle("banner", base, fontName="Sans-Bold", fontSize=8.6, leading=11.5, spaceAfter=0)
    return s


class Rule(Flowable):
    """A thin horizontal line across the frame."""

    def __init__(self, colour: str = RULE, width: float = 0.6, space: float = 4):
        super().__init__()
        self.colour, self.line_width, self.space = colour, width, space

    def wrap(self, avail_w, avail_h):
        self.avail_w = avail_w
        return avail_w, self.space * 2

    def draw(self):
        self.canv.setStrokeColor(c(self.colour))
        self.canv.setLineWidth(self.line_width)
        self.canv.line(0, self.space, self.avail_w, self.space)


class Pack:
    """Builds the pages in order, so the glossary defines each term where it is first used."""

    def __init__(self, facts: Facts, figures: dict[str, Path]):
        self.f, self.fig, self.g, self.s = facts, figures, Glossary(), styles()
        self.page_scopes: list[str] = []
        self.months = facts.months
        road = facts.roadmap
        self.phase_count = TracedInt(len(road["phases"]), Origin("config", "roadmap.yaml number of phases", ""))
        self.risk_count = TracedInt(len(road["risks"]), Origin("config", "roadmap.yaml number of risks", ""))
        first, last = (int(x) for x in re.findall(r"\d+", road["phases"][0]["timing"]))
        self.phase1_months = TracedInt(last - first + 1, Origin("config", "roadmap.yaml phase 1 timing",
                                                                road["phases"][0]["timing"]))

    # ---- helpers ----------------------------------------------------------------------------------------- #

    def p(self, text: str, style: str = "body") -> Paragraph:
        return Paragraph(text, self.s[style])

    def page_head(self, kicker: str, title: str, lead: str | None = None) -> list:
        out = [self.p(escape(kicker), "kicker"), self.p(title, "h1")]
        if lead:
            out.append(self.p(lead, "lead"))
        return out

    def image(self, key: str, max_h: float, max_w: float = FRAME_W) -> Image:
        path = self.fig[key]
        with PILImage.open(path) as im:
            w_px, h_px = im.size
        w, h = w_px / 300 * 72, h_px / 300 * 72
        scale = min(1.0, max_w / w, max_h / h)
        img = Image(str(path), width=w * scale, height=h * scale)
        img.hAlign = "LEFT"
        return img

    def table(self, rows: list[list], widths: list[float], header: bool = True, zebra: bool = False,
              style: str = "cell", valign: str = "TOP", pad: float = 2.2) -> Table:
        cells = [[x if isinstance(x, Flowable) else self.p(str(x), "head" if header and i == 0 else style)
                  for x in row] for i, row in enumerate(rows)]
        t = Table(cells, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        cmds = [("VALIGN", (0, 0), (-1, -1), valign), ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad), ("LINEBELOW", (0, 0), (-1, -1), 0.4, c(GRID))]
        if header:
            cmds += [("BACKGROUND", (0, 0), (-1, 0), c(PAPER)), ("LINEBELOW", (0, 0), (-1, 0), 0.7, c(RULE))]
        if zebra:
            cmds += [("BACKGROUND", (0, r), (-1, r), c(PAPER)) for r in range(2, len(rows), 2)]
        t.setStyle(TableStyle(cmds))
        return t

    def tiles(self, items: list[tuple[str, str, str]], number_style: str = "number") -> Table:
        """Headline figures side by side: label, number, explanation, each tile read as one unit."""
        gap = 4 * mm
        w = (FRAME_W - gap * (len(items) - 1)) / len(items)
        row, widths = [], []
        for i, (label, number, text) in enumerate(items):
            if i:
                row.append("")
                widths.append(gap)
            row.append([self.p(label, "tile_label"), self.p(number, number_style), self.p(text, "tile_text")])
            widths.append(w)
        t = Table([row], colWidths=widths, hAlign="LEFT")
        cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
        for col in range(0, len(row), 2):
            cmds += [("BACKGROUND", (col, 0), (col, 0), c(ACCENT_FILL)),
                     ("LINEBEFORE", (col, 0), (col, 0), 2.2, c(ACCENT))]
        t.setStyle(TableStyle(cmds))
        return t

    def boxed(self, flowables: list, fill: str = PAPER, border: str = RULE) -> Table:
        t = Table([[flowables]], colWidths=[FRAME_W], hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), c(fill)), ("BOX", (0, 0), (-1, -1), 0.7, c(border)),
                               ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        return t

    def caveat(self, text: str) -> Table:
        return self.boxed([self.p(f"<b>Read with care.</b> {escape(text)}", "small")])

    def h(self, engine: str, key: str) -> float:
        return self.f.h(engine, key)

    def cfg(self, text: str, name: str) -> str:
        """Text quoted from config; the numbers in it are recorded as config."""
        return quote(text, "config", name)

    def doc(self, text: str, name: str = "benefits case") -> str:
        """Text quoted from a committed document; the numbers in it are recorded as document."""
        return quote(text, "document", name)

    def date(self) -> str:
        text = f"{self.f.as_of:%-d %B %Y}"
        record(text, Origin("warehouse", "extract date", "SELECT as_of_date FROM marts.parameters"))
        return text

    # ---- pages ------------------------------------------------------------------------------------------- #

    def cover(self) -> list:
        f = self.f
        contents = [[self.p(title, "body"), self.p(str(page), "body")] for title, page in CONTENTS]
        toc = Table(contents, colWidths=[90 * mm, 12 * mm], hAlign="LEFT")
        toc.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("LINEBELOW", (0, 0), (-1, -1), 0.4,
                                                                         c(GRID))]))
        return [
            Spacer(1, 30 * mm), self.p("Management pack", "kicker"), self.p("FabSync", "cover_title"),
            self.p("One version of the truth for a structural steel fabricator", "cover_sub"),
            self.p(f"How {word(f.systems)} systems that do not talk to each other cost a "
                   f"{word(f.source['sites'])}-site steelwork fabricator money and certainty, what it adds up to, and "
                   f"{article(self.months)} {self.months}-month plan to fix it.", "lead"),
            Spacer(1, 8 * mm),
            self.boxed([self.p(f"<b>{SYNTHETIC}</b> The company, its customers, suppliers and jobs, and every "
                               "figure in this pack, are invented for the demonstrator. Each figure is measured by "
                               "the prototype from that invented data, not typed by hand, except where a page says "
                               "a figure is estimated.", "body")], fill=ACCENT_FILL, border=ACCENT),
            Spacer(1, 4 * mm),
            self.p(f"Figures as at {self.date()}, covering {f.source['months']:.0f} months of records.",
                   "note"),
            Spacer(1, 14 * mm), self.p("Contents", "h2"), toc, PageBreak(),
        ]

    def executive_summary(self) -> list:
        f, g = self.f, self.g
        dq = f.dq
        dqi = g.definition("dqi")
        tiles = self.tiles([
            ("Value at risk", money(self.h("three_way", "value_at_risk")),
             f"The purchasing {g.definition('value_at_risk')}."),
            ("Data quality index, out of 100", f"{dq['dq_index']:.1f}",
             f"{dqi[0].upper()}{dqi[1:]}. {dq['rules_met']:.0f} of "
             f"{dq['rules_run']:.0f} rules are met, and {dq['critical_breaches']:.0f} critical rules are broken."),
            ("Tonnes of steel that cannot be traced", f"{self.h('traceability', 'exposed_kg'):,.0f}",
             f"Despatched on {self.h('traceability', 'exposed_jobs'):.0f} jobs for "
             f"{self.h('traceability', 'exposed_customers'):.0f} customers without full "
             f"{g('traceability')}."),
        ])
        worth = [r for r in f.benefits["pounds"] if r[0].startswith("**Total")][0]
        phases = f.roadmap["phases"]
        return self.page_head("Executive summary", "Three numbers that matter", None) + [
            tiles, Spacer(1, 3 * mm),
            self.p(f"Structural steelwork cannot be sold without {g('en1090')} certification, and certification "
                   "rests on traceability. Every tonne in the third figure is an audit finding waiting to happen.",
                   "body"),
            self.p("What is wrong", "h2"),
            self.p(f"The business runs on {word(f.systems)} systems that do not share data: {g('corvus')}, the "
                   "finance system, and spreadsheets kept by the supervisors at each site. Each has drifted from the "
                   "others. The "
                   f"same steel is written {f.match['material_forms']:.0f} different ways for "
                   f"{f.match['golden_materials']:.0f} materials, suppliers sit under more than one account, a job "
                   "has one number in production and another in finance, and hours are booked to jobs that do not "
                   "exist. Nobody can get one trustworthy answer to simple questions: what is this job making, "
                   "what do we owe, and can we trace this steel?"),
            self.p("What it costs", "h2"),
            self.p(f"&bull; {money(self.h('three_way', 'invoice_with_no_PO_value'))} of galvanising, paint, erection "
                   "and other services was bought with no order to check the invoice against.<br/>"
                   f"&bull; {money(self.h('job_cost', 'material_misallocated'))} of steel was charged to the wrong "
                   "job. The totals agree, so nobody notices, but individual job margins are wrong, and prices are "
                   "set from them.<br/>"
                   f"&bull; {money(self.h('three_way', 'missing_invoice_value'))} of steel has been received but "
                   "not invoiced, so it is missing from the month-end accounts.<br/>"
                   f"&bull; {self.h('stock', 'line_accuracy'):.1f}% of counted stock lines agree with the system, "
                   f"against a {f.reconcile['stock']['accuracy_target']:.0%} target, so planning allocates steel "
                   "that is not in the yard."),
            self.p("What we recommend", "h2"),
            self.p(f"{article(self.months).capitalize()} {self.months}-month programme in "
                   f"{word(self.phase_count)} phases, set out on page {dict(CONTENTS)['The plan']}. The first "
                   f"{word(self.phase1_months)} months "
                   "contain the traceability exposure at goods-in and freeze today's figures as the "
                   f"{g('baseline')}. Then the shared records are cleaned, the systems are joined up for reading "
                   "only, and the shop floor moves from spreadsheets to simple forms. Nothing is written back into "
                   "the working systems until the data is clean and the new collection has run reliably for a "
                   "month."),
            self.p("What it is worth", "h2"),
            self.p("The case rests on keeping certification and on figures the business can take decisions from. "
                   "Neither is given a pound value. The benefits that can be priced are modest: about "
                   f"{self.doc(strip_md(worth[4]))} a year in the central case, between "
                   f"{self.doc(strip_md(worth[3]))} and {self.doc(strip_md(worth[5]))}, an illustrative figure that "
                   f"is {g('modelled')}, not measured."),
            self.p("The decision asked for", "h2"),
            self.boxed([self.p(f"Approve phase 1, {phases[0]['phase'].split('. ', 1)[1].lower()} "
                               f"({self.cfg(phases[0]['timing'].lower(), 'roadmap.yaml phase 1 timing')}), and name a "
                               "director as sponsor.", "banner")],
                       fill=ACCENT_FILL, border=ACCENT),
            PageBreak(),
        ]

    def problem(self) -> list:
        f, g = self.f, self.g
        sites = " and ".join(sorted(f.sites.values(), reverse=True))
        return self.page_head(
            "The problem", f"{word(f.systems).capitalize()} systems, no single version of the truth",
            f"The company fabricates structural steel, telecoms towers and masts, rail structures and stadium "
            f"steelwork at {word(f.source['sites'])} sites, {sites}. Its sales in the last 12 months were "
            f"{money(f.turnover_12m)}. "
            f"It runs on {word(f.systems)} systems that were never joined up.") + [
            self.image("three_systems", 72 * mm), Spacer(1, 2 * mm),
            self.p(f"How the {word(f.systems)} drifted apart", "h2"),
            self.p(f"Production is planned in Corvus MRP against {g('works_order', 'works orders')} and their "
                   f"{g('bom', 'bills of material (BOMs)')}. Buyers raise each {g('po')} to a "
                   f"{g('stockholder')} or mill, and goods-in records each delivery on a {g('grn')}. Finance keeps "
                   "its own supplier accounts and job codes, keys every supplier invoice by hand, and bills "
                   f"customers by invoice or {g('app_payment')}. The shop floor books "
                   f"hours, despatches and each {g('ncr')} on spreadsheets, one set per site. Nothing checks that "
                   "the copies agree:"),
            self.p(f"&bull; {f.match['material_forms']:.0f} ways of writing {f.match['golden_materials']:.0f} "
                   f"materials; {f.fig['uom_conflicts']:.0f} materials are held in "
                   f"{word(f.source['max_units_per_material'])} different units.<br/>"
                   f"&bull; {f.fig['supplier_dupes_confirmed']:.0f} suppliers held under more than one record, and "
                   f"{f.fig['supplier_dupes_likely']:.0f} more likely.<br/>"
                   f"&bull; {f.fig['job_finance_only_codes']:.0f} finance job codes with no production job behind "
                   f"them, carrying {money(f.fig['job_finance_only_cost'])} of cost.<br/>"
                   f"&bull; {f.fig['unallocated_hours']:,.0f} hours booked to {f.fig['orphan_wos']:.0f} works "
                   "orders that production never issued."),
            self.image("dq_by_system", 40 * mm),
            self.p("How the prototype worked it out", "h2"),
            self.p(f"It took {f.source['months']:.0f} months of records from all {word(f.systems)} systems exactly "
                   f"as they were kept: {f.source['raw_rows']:,.0f} rows from {f.source['files']:.0f} files. Nothing "
                   f"was edited in place. Every row either passed its checks or went into {g('quarantine')}; "
                   f"{f.source['quarantined']:.0f} did. The {g('lineage')} of every figure is kept, and "
                   f"the shared {g('master_data')} was matched across the systems into a {g('golden')} for each "
                   f"item, keeping every original beside it. Each {g('reconciliation')} in this pack was then "
                   "recomputed from the rows behind it before it was published."),
            PageBreak(),
        ]

    def process_map(self, key: str, title: str, lead: str, page_break: bool = True) -> list:
        out = self.page_head("How the work flows today", title, lead)
        out.append(self.image(key, FRAME_H - 33 * mm))
        return out + ([PageBreak()] if page_break else [])

    def maps(self) -> list:
        from fabsync.pack.diagrams import parse
        breaks = {k: TracedInt(sum(1 for _, shape in parse(self.f.diagrams[k]).nodes.values() if shape == "hex"),
                               Origin("document", f"break points drawn in docs/diagrams/templates/{k}.mmd", ""))
                  for k in ("as-is-order-to-cash", "as-is-procure-to-pay")}
        return self.process_map(
            "order_to_cash", f"Order to cash: {breaks['as-is-order-to-cash']} places where the records stop agreeing",
            "Each column is one system, or paper. Work moves down the page; a line crossing columns is a hand-off, "
            "and the coloured ones are typed again by hand, where mistakes get in and nothing checks the copies "
            "agree. The boxes on the right are break points, each with what it measurably costs.") + self.process_map(
            "procure_to_pay",
            f"Procure to pay: {breaks['as-is-procure-to-pay']} places where the records stop agreeing",
            f"Steel is ordered, delivered with its {self.g('mill_cert')} and {self.g('heat')}, cut, and paid "
            "for. Services such as galvanising are ordered by phone. Nothing records which delivery went into "
            "which job.")

    def finding(self, n: int, title: str, tiles: list, chart: list, meaning: str, method: str, caveat: str,
                chart_h: float, extra: list | None = None) -> list:
        out = self.page_head(f"What we found: {n} of 4", title)
        out += [self.tiles(tiles, "number_small"), Spacer(1, 3 * mm)]
        out += [self.image(k, chart_h) for k in chart] + (extra or [])
        out += [self.p("What it means", "h2"), self.p(meaning), self.p("How it was measured", "h2"),
                self.p(method), self.caveat(caveat), PageBreak()]
        return out

    def findings(self) -> list:
        f, g, h = self.f, self.g, self.h
        tw = f.reconcile["three_way"]
        kcav = f.kpis.set_index("kpi_id").caveat
        pages = self.finding(
            1, f"{money(h('three_way', 'value_at_risk'))} of purchasing does not match",
            [("Value at risk", f"£{h('three_way', 'value_at_risk'):,.0f}", "Across orders, deliveries and invoices"),
             ("Invoices with no order", money(h("three_way", "invoice_with_no_PO_value")),
              f"{h('three_way', 'invoice_with_no_PO_lines'):,.0f} invoices for services"),
             (quote(f.head_label[("three_way", "over_90_days")], "warehouse", "reconciliation headline label",
                    "SELECT label FROM recon.headline WHERE engine = 'three_way' AND key = 'over_90_days'"),
              f"{h('three_way', 'over_90_days'):,.0f}", "still unresolved")],
            ["value_at_risk"],
            f"Most of the money is services bought on the phone: galvanising, paint, erection and plant hire with "
            "no order to check the invoice against. That is a control gap rather than proven overpayment. "
            f"{money(h('three_way', 'missing_invoice_value'))} of steel has arrived but not been invoiced, so it is "
            f"missing from the accounts; {money(h('three_way', 'missing_GRN_value'))} is ordered, overdue and never "
            f"received; and {h('three_way', 'price_variance_lines'):.0f} invoices charged more than the order, "
            f"{money(h('three_way', 'price_variance_value'))} in all.",
            f"A {g('three_way')}. For each of {f.lines_assessed:,.0f} order lines due for delivery and invoice, the "
            "prototype found the deliveries and invoices belonging to it and put the line in exactly one class: "
            "matched, short or over delivered, overcharged, never received, or never invoiced. A delivery matches "
            f"if it is within {tw['qty_tolerance']:.0%} of the order; an invoice matches if it is within the "
            f"{tw['price_tolerance_pct']:.0%} of what was received. "
            "Invoices with no order are counted separately, except on the overheads account.",
            self.cfg(kcav["KPI-05"], "kpis.yaml caveat"), 62 * mm,
            extra=[self.p("How long the exceptions have been open, in lines", "h2"), self.ageing_table()])
        pages += self.finding(
            2, f"{money(h('job_cost', 'gross_gap'))} of job cost does not reconcile",
            [("Gap across jobs", f"£{h('job_cost', 'gross_gap'):,.0f}",
              f"Summed over {f.jobs_reconciled:.0f} jobs, ignoring sign"),
             ("Steel on the wrong job", money(h("job_cost", "material_misallocated")),
              "Charged to one job, used on others"),
             ("Labour gap", money(h("job_cost", "labour_gap_gross")), "Payroll against hours booked")],
            ["job_cost"],
            "The company's totals agree; its individual job costs do not. Finance charges each steel invoice to "
            "one job, but one order often feeds several, so some jobs look expensive and others cheap. The "
            "labour gap is different: payroll hours are allocated to jobs separately from the hours the shop "
            "floor booked. Either way, estimators price the next job from margins that are wrong.",
            f"{word(f.systems).capitalize()} views of every job side by side: production's (the steel on its BOM at "
            f"the average price paid, and its planned hours), finance's job cost ledger, and the shop floor's "
            f"(hours booked at £{f.labour_rate:,.0f} an hour). The gap is finance's cost less the operational cost, "
            "material and labour, job by job. The steel that moves between jobs is the part of the gap that cancels "
            "out when the jobs are added together.",
            f"Because the steel gap cancels out across jobs, the net gap is only "
            f"{'-' if h('job_cost', 'net_gap') < 0 else ''}£{abs(h('job_cost', 'net_gap')):,.0f}. The gross figure "
            "measures how wrong individual job costs are, not money lost. Labour is at a standard rate with no "
            "overhead.", 84 * mm, extra=[self.p("Where the gap comes from", "h2"), self.gap_table()])
        pages += self.finding(
            3, f"{h('stock', 'line_accuracy'):.1f}% of stock lines agree with the book",
            [("Stock line accuracy", f"{h('stock', 'line_accuracy'):.1f}%",
              f"Target {f.reconcile['stock']['accuracy_target']:.0%}"),
             ("Lines that disagree", f"{h('stock', 'inaccurate_lines'):.0f}",
              f"{h('stock', 'abs_error_kg'):,.0f} kg of steel miscounted"),
             ("Value miscounted", f"£{h('stock', 'value_error'):,.0f}", "Counted against book, at unit cost")],
            ["stock"],
            "The money is small; the planning risk is not. When the book disagrees with the rack, planning "
            "allocates steel that is not there and buyers reorder steel that is. "
            f"{f.fig['uom_conflicts']:.0f} materials are bought in kilograms, stocked in bars and issued in metres, "
            "so their book figure cannot be right. "
            f"{h('stock', 'groups_below_target'):.0f} of {f.rows['stock']} groups miss the target, where a group is "
            f"one site and one type of {g('section')}.",
            "Every counted stock line's physical count was compared with the quantity the system holds. A line "
            "is accurate only if the two agree exactly; the difference is valued at the line's unit cost.",
            self.cfg(kcav["KPI-04"], "kpis.yaml caveat"), 118 * mm)
        pages += self.finding(
            4, f"{h('traceability', 'exposed_kg'):,.0f} tonnes of steel have gone out without full traceability",
            [("Traceability coverage", f"{h('traceability', 'coverage'):.1f}%", "Of steel used, by weight"),
             ("Jobs exposed", f"{h('traceability', 'exposed_jobs'):.0f}",
              f"For {h('traceability', 'exposed_customers'):.0f} customers"),
             ("Sales on those jobs", money(h("traceability", "exposed_sales")), "Already despatched")],
            ["trace_breaks", "trace_customers"],
            "Each tonne here is steel on a customer's site whose certificate cannot be produced on request. "
            "Under EN 1090 that is a nonconformity: a surveillance audit can suspend certification, and without "
            "certification the steelwork cannot be sold. Most chains break at goods-in, where the heat number or "
            "certificate was never recorded, so the fix starts there.",
            "Each finished assembly was followed back through its works order and BOM to the delivery that "
            "supplied the steel, and from the delivery to its heat number and certificate. Production records "
            "no issues of steel to works orders, so which delivery went into which job was reconstructed "
            f"{g('first_in')}. The shop's {g('cutting_list', 'cutting lists')} would settle it, but they are not "
            "kept with the records. A chain is complete only if every link has its reference on file.",
            self.cfg(kcav["KPI-06"], "kpis.yaml caveat"), 58 * mm)
        return pages

    def ageing_table(self) -> Table:
        a = self.f.ageing
        buckets = ["0-30 days", "31-60 days", "61-90 days", "91-180 days", "over 180 days"]
        rows = [["What went wrong"] + [self.cfg(b.replace("-", " to "), "reconcile.toml [three_way] ageing_buckets")
                                       for b in buckets] + ["All"]]
        none = trace(0, "warehouse", "ageing: a bucket with no lines, lines", FRAMES_SQL["ageing"])
        for cat in self.f.three_way.category:
            sub = a[a.category == cat].set_index("age_bucket").lines
            rows.append([cat[0].upper() + cat[1:]] + [f"{sub.get(b, none):,.0f}" for b in buckets]
                        + [f"{total(sub, f'ageing: {cat}, all buckets, lines'):,.0f}"])
        t = self.table(rows, [44 * mm] + [21 * mm] * 6, zebra=True)
        t.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
        return t

    def gap_table(self) -> Table:
        h = self.h
        rows = [["Part of the gap", "Amount", "What it is"],
                ["Steel, gross", f"£{h('job_cost', 'material_gap_gross'):,.0f}",
                 "Finance's steel cost against the steel on each job's BOM, summed over jobs ignoring sign"],
                ["of which on the wrong job", f"£{h('job_cost', 'material_misallocated'):,.0f}",
                 "The part that cancels out: steel invoiced to one job but used on another"],
                ["Labour, gross", f"£{h('job_cost', 'labour_gap_gross'):,.0f}",
                 "Payroll hours allocated by finance against the hours the shop floor booked"],
                ["Cost on jobs production does not hold", f"£{h('job_cost', 'finance_only_cost'):,.0f}",
                 "Finance cost on job codes with no production job behind them"],
                ["Hours on works orders never issued", f"{h('job_cost', 'unallocated_hours'):,.0f} hours",
                 "Booked on the shop floor, so charged to no job at all"]]
        t = self.table(rows, [52 * mm, 26 * mm, 92 * mm], zebra=True)
        t.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT")]))
        return t

    def target(self) -> list:
        g = self.g
        return self.page_head(
            "The target", "Keep what works, remove the gaps between systems",
            "Corvus MRP and the finance system stay. The spreadsheets are replaced by simple forms that accept "
            "only real works orders and real dates. New pieces join everything up.") + [
            self.p(f"&bull; The {g('integration')}.<br/>&bull; The {g('mds')}, which issues each golden record "
                   f"and keeps a {g('crosswalk')} back to every system.<br/>&bull; The {g('warehouse')}.<br/>"
                   "&bull; Reporting: the monthly pack, the data quality scorecard and the queues that tell each "
                   "owner what to fix."),
            self.image("architecture", FRAME_H - 70 * mm),
            PageBreak(),
        ]

    def governance(self) -> list:
        f, g = self.f, self.g
        head = ["Entity", "Corvus MRP", "Finance", "Forms", "Master data service", "Warehouse", "Owner"]
        rows = [head] + [[strip_md(r[0])] + [strip_md(x)[0] for x in r[1:6]] + [r[6]] for r in f.ownership]
        matrix = self.table(rows, [56 * mm, 15 * mm, 13 * mm, 12 * mm, 19 * mm, 21 * mm, 34 * mm], zebra=True,
                            pad=1.3)
        matrix.setStyle(TableStyle([("ALIGN", (1, 0), (5, -1), "CENTER")]))
        sev = ["critical", "high", "medium", "low"]
        r = f.rules
        dims = sorted(r.dimension.unique())
        rule_rows = [["Dimension"] + [s.capitalize() for s in sev] + ["Rules", "Met"]]
        for d in dims:
            sub = r[r.dimension == d]
            rule_rows.append([d.capitalize()] + [f"{total(sub[sub.severity == s].rules):.0f}"
                                                 if len(sub[sub.severity == s]) else "" for s in sev]
                             + [f"{total(sub.rules, f'rules: {d} all severities, rules'):.0f}",
                                f"{total(sub.met, f'rules: {d} all severities, met'):.0f}"])
        rule_rows.append(["All"] + [f"{total(r[r.severity == s].rules, f'rules: all {s}, rules'):.0f}" for s in sev]
                         + [f"{total(r.rules, 'rules: all, rules'):.0f}", f"{total(r.met, 'rules: all, met'):.0f}"])
        rules = self.table(rule_rows, [30 * mm] + [16 * mm] * 6, pad=1.3)
        esc = self.table([["Step", "Who", "Time limit"]] + [[self.doc(e[0], "escalation route"),
                                                             self.doc(e[1], "escalation route"),
                                                             self.doc(e[3], "escalation route")] for e in f.escalation],
                         [10 * mm, 95 * mm, 65 * mm], pad=1.3)
        return self.page_head(
            "Who owns the data, and the rules", "Every kind of data has one owner, one home and written rules",
            f"Each {g('data_owner')} is a senior role, not IT. Each {g('steward')} works the "
            f"{g('exception_queue', 'exception queues')} and {g('review_queue', 'review queues')}.") + [
            self.p(f"<b>Ownership.</b> C marks the {g('system_of_record')}. W is a working copy kept in step "
                   "automatically; R is a read-only copy for reporting; a dash means the system does not hold it. "
                   "Forms are the shop-floor forms that replace the spreadsheets.",
                   "small"),
            matrix, Spacer(1, 3 * mm),
            self.p(f"<b>The rules.</b> {f.dq['rules_run']:.0f} rules, each written in business language with an "
                   "owner, a pass threshold, the consequence of failing and the fix. In the index, a rule weighs "
                   + ", ".join(f"{w} if {s}" for s, w in f.severity_weights.items())
                   + f". Today {f.dq['rules_met']:.0f} are met.", "small"),
            rules, Spacer(1, 3 * mm),
            self.p("<b>When a rule cannot settle it.</b> Disagreements go up this route, each step with a time "
                   "limit, so nothing sits in a queue for ever. Safety and payments have fast tracks that skip "
                   "the queue.", "small"),
            esc, Spacer(1, 2 * mm), self.image("dq_by_owner", 38 * mm), PageBreak(),
        ]

    def kpis(self) -> list:
        f, g = self.f, self.g
        rows = [["Measure", "What it measures", "Today", "Target", "Owner", "Read with care"]]
        words = {">= ": "at least ", "<= ": "at most "}
        for k in f.kpis.itertuples():
            target = k.target
            for code, phrase in words.items():
                target = target.replace(code, phrase)
            today = (money(k.value) if k.unit == "GBP" else f"{k.value:.1f}%")
            if isinstance(k.secondary_label, str):
                sec = money(k.secondary_value) if k.secondary_unit == "GBP" else f"{k.secondary_value:.1f}%" \
                    if k.secondary_unit == "percent" else f"{k.secondary_value:,.2f}"
                label = quote(k.secondary_label, "warehouse", "KPI secondary label", FRAMES_SQL["kpis"])
                today += f"<br/>{escape(label)}: {sec}"
            rows.append([self.p(f"<b>{escape(k.name)}</b>", "tight"), escape(self.cfg(k.definition, "kpis.yaml")),
                         today,
                         f"{escape(self.cfg(target, 'kpis.yaml ' + k.kpi_id + ' target'))}<br/>{escape(k.status)}",
                         f"{escape(k.owner)}<br/>{escape(k.refresh)}", escape(self.cfg(k.caveat, "kpis.yaml caveat"))])
        t = self.table(rows, [21 * mm, 31 * mm, 17 * mm, 16 * mm, 20 * mm, 65 * mm], zebra=True, style="tight")
        return self.page_head(
            "How performance will be measured",
            f"{word(f.kpi_count).capitalize()} measures, each with an owner, a target and a caveat",
            f"Each {g('kpi')} is defined once, calculated from the reconciled data and never shown without "
            "the caveat that says what it cannot tell you.") + [
            self.p(f"Terms the measures use: {g('otif')}; {g('yield')}; an {g('offcut')}; {g('nesting')}; "
                   f"{g('wip')}; the {g('cost_of_quality')}.", "small"),
            t, PageBreak(),
        ]

    def plan(self) -> list:
        f, g = self.f, self.g
        phase_rows = [["Phase", "Months", "Objective"]] + [
            [self.p(f"<b>{escape(p['phase'])}</b>", "cell"), self.cfg(p["timing"].replace("Months ", ""),
                                                                     "roadmap.yaml timing"),
             escape(self.cfg(p["objective"], "roadmap.yaml objective"))] for p in f.roadmap["phases"]]
        reviews = [["Review", "Month", "Decisions"]] + [[str(r["review"]), str(r["month"]),
                                                         escape(self.cfg(r["decisions"], "roadmap.yaml decisions"))]
                                                        for r in f.roadmap["reviews"]]
        return self.page_head(
            "The plan", f"{word(self.phase_count).capitalize()} phases over {self.months} months, with "
            "a management committee review every quarter",
            f"Each phase ends at a review by the {g('committee')}. The order matters. Today's figures are "
            f"frozen first as the {g('baseline')}. Nothing is written "
            f"back until the data is clean and read-only collection has run reliably: {g('write_back')} comes in "
            f"phase 4, after {g('dual', 'dual running')} has proven the new pack. The shop floor changes last, "
            "when there are clean works orders for its forms.") + [
            self.image("timeline", 64 * mm),
            self.table(phase_rows, [46 * mm, 14 * mm, 110 * mm], zebra=True), Spacer(1, 3 * mm),
            self.p("The committee approves each phase exit against written criteria, never against a date; a "
                   "phase that cannot meet them pauses at its gate.", "small"),
            self.table(reviews, [14 * mm, 12 * mm, 144 * mm], zebra=True), PageBreak(),
        ]

    def risks(self) -> list:
        f, g = self.f, self.g
        risks = sorted(f.roadmap["risks"], key=lambda r: (-r["inherent"], r["id"]))
        rows = [["ID", "Risk", "Category", "Owner", "Before", "After"]] + [
            [r["id"], escape(self.cfg(r["risk"], "roadmap.yaml risk")), r["category"], r["owner"], str(r["inherent"]),
             str(r["residual"])]
            for r in risks]
        t = self.table(rows, [10 * mm, 82 * mm, 19 * mm, 31 * mm, 14 * mm, 14 * mm], zebra=True)
        t.setStyle(TableStyle([("ALIGN", (4, 0), (5, -1), "CENTER")]))
        high = [r for r in f.roadmap["risks"] if band(r["residual"])[0] in ("high", "very high")]
        stay_high = TracedInt(len(high), Origin("config", "roadmap.yaml risks whose residual score is high", ""))
        return self.page_head(
            "Risks", f"{self.risk_count} risks; {stay_high} stay high after mitigation",
            f"Each risk has an owner, a specific mitigation and two scores: the {g('inherent')} and the "
            f"{g('residual')}.") + [
            self.image("risk_heat_map", 72 * mm), t, Spacer(1, 2 * mm),
            self.p(f"<b>The {word(stay_high)} that stay high.</b> " + " ".join(
                f"{escape(self.cfg(r['risk'], 'roadmap.yaml risk'))} ({r['id']}): "
                f"{escape(self.cfg(r['mitigation'].split('. ')[0], 'roadmap.yaml mitigation'))}." for r in high),
                "small"),
            NextPageTemplate("illustrative"), PageBreak(),
        ]

    def benefits(self) -> list:
        f, g = self.f, self.g
        caption = "ILLUSTRATIVE. Today's figures are measured on synthetic data; every target is modelled."
        summary = [["Measure", "Today, measured (synthetic)", "Standard", f"Target at month {self.months}, modelled",
                    "Moved by"]]
        summary += [[escape(r[1]), escape(self.doc(r[2])), escape(self.doc(r[4])), escape(self.doc(r[5])),
                     escape(self.doc(r[6]))] for r in f.benefits["summary"]]
        pounds = [["Benefit", "Measured input (synthetic)", "Low", "Central", "High", "Confidence"]]
        pounds += [[self.p(f"<b>{escape(strip_md(r[0]))}</b>", "cell") if r[0].startswith("**") else escape(r[0]),
                    escape(self.doc(r[1]))] + [self.p(f"<b>{self.doc(strip_md(x))}</b>", "cell") if x.startswith("**")
                                               else self.doc(x) for x in r[3:6]] + [r[6]] for r in f.benefits["pounds"]]
        assumed = {a[0]: a for a in f.benefits["assumptions"]}
        used = [assumed[k] for k in ("A2", "A3", "A4", "A7")]
        not_claimed = [["Measured figure (synthetic)", "Value", "Why no saving is claimed"]]
        not_claimed += [[escape(self.doc(r[0])), escape(self.doc(r[1])), escape(self.doc(r[2]))]
                        for r in f.benefits["not_claimed"][:5]]
        return self.page_head("Benefits, illustrative", "Benefits case (ILLUSTRATIVE)") + [
            self.boxed([self.p("ILLUSTRATIVE. This whole page is illustrative and is not a forecast for any real "
                               "business. Today's figures are measured by the prototype on synthetic data. Every "
                               "target and every pound value is modelled from them and from stated assumptions. "
                               f"The real {g('baseline')} is taken in phase 1 and replaces every figure here.",
                               "banner")], fill=ACCENT_FILL, border=ACCENT),
            Spacer(1, 3 * mm), self.p(f"<i>{caption}</i>", "note"),
            self.table(summary, [44 * mm, 26 * mm, 22 * mm, 50 * mm, 28 * mm], zebra=True), Spacer(1, 3 * mm),
            self.p("<i>ILLUSTRATIVE. Inputs measured on synthetic data; every pound value modelled, per year.</i>",
                   "note"),
            self.table(pounds, [40 * mm, 68 * mm, 13 * mm, 15 * mm, 14 * mm, 20 * mm], zebra=True),
            Spacer(1, 1.5 * mm),
            self.p("Assumptions behind the pound values, each to be replaced by a measurement: " + "; ".join(
                f"{escape(a[1][0].lower() + a[1][1:])}, {escape(self.doc(a[2]))}" for a in used) + ".", "note"),
            Spacer(1, 1 * mm),
            self.p("<i>ILLUSTRATIVE. Large measured figures that are deliberately not counted as savings.</i>",
                   "note"),
            self.table(not_claimed, [44 * mm, 18 * mm, 108 * mm], zebra=True), Spacer(1, 2 * mm),
            self.p("<b>Some figures will look worse before they look better.</b> Better data raises some "
                   "measures at first: costing every NCR raises the cost of quality, and capturing every hour can "
                   "raise labour variance. Without a baseline, that reads as failure.", "small"),
            NextPageTemplate("body"), PageBreak(),
        ]

    def summary(self) -> list:
        f = self.f
        phases = f.roadmap["phases"]
        worth = [r for r in f.benefits["pounds"] if r[0].startswith("**Total")][0]
        high = [r for r in f.roadmap["risks"] if r["residual"] >= 10]
        found = [
            ("Purchasing", f"{money(self.h('three_way', 'value_at_risk'))} value at risk; "
                           f"{money(self.h('three_way', 'invoice_with_no_PO_value'))} of it services with no order."),
            ("Job cost", f"{money(self.h('job_cost', 'gross_gap'))} does not reconcile; "
                         f"{money(self.h('job_cost', 'material_misallocated'))} is steel on the wrong job."),
            ("Stock", f"{self.h('stock', 'line_accuracy'):.1f}% of counted lines agree with the book, against "
                      f"{f.reconcile['stock']['accuracy_target']:.0%}."),
            ("Traceability", f"{self.h('traceability', 'exposed_kg'):,.0f} tonnes on "
                             f"{self.h('traceability', 'exposed_jobs'):.0f} jobs cannot be traced to certificate."),
        ]
        return self.page_head("The pack on one page", "FabSync on one page",
                              f"<b>{SYNTHETIC}</b> Figures as at {self.date()}.") + [
            self.tiles([
                ("Value at risk", money(self.h("three_way", "value_at_risk")), "Purchasing that does not match"),
                ("Data quality index", f"{f.dq['dq_index']:.1f} / 100",
                 f"{f.dq['critical_breaches']:.0f} critical rules broken"),
                ("Untraceable steel", f"{self.h('traceability', 'exposed_kg'):,.0f} t",
                 "Already on customers' sites"),
            ], "number_small"), Spacer(1, 2 * mm),
            self.p("The problem", "h2"),
            self.p("Corvus MRP, the finance system and the shop-floor spreadsheets do not share data and have "
                   "drifted apart, so management has no single trustworthy view of jobs, money or steel.", "small"),
            self.p("What we found", "h2"),
            self.table([["Area", "Finding"]] + [[a, b] for a, b in found], [30 * mm, 140 * mm]),
            self.p("What we recommend", "h2"),
            self.table([["Phase", "Months", "Objective"]] + [
                [p["phase"], self.cfg(p["timing"].replace("Months ", ""), "roadmap.yaml timing"),
                 escape(self.cfg(p["objective"].split(". ")[0], "roadmap.yaml objective")) + "."]
                for p in phases], [48 * mm, 14 * mm, 108 * mm]),
            self.p("What it is worth", "h2"),
            self.p("Keeping EN 1090 certification, and figures the business can decide from. Priced benefits are "
                   f"ILLUSTRATIVE and modelled: about {self.doc(strip_md(worth[4]))} a year, between "
                   f"{self.doc(strip_md(worth[3]))} and {self.doc(strip_md(worth[5]))}.", "small"),
            self.p("The risks to watch", "h2"),
            self.p(" ".join(f"{escape(r['risk'])} ({r['owner']})." for r in high), "small"),
            self.boxed([self.p(f"<b>The decision asked for:</b> approve phase 1, "
                               f"{phases[0]['phase'].split('. ', 1)[1].lower()} "
                               f"({self.cfg(phases[0]['timing'].lower(), 'roadmap.yaml phase 1 timing')}), "
                               "and name a director as sponsor.", "banner")], fill=ACCENT_FILL, border=ACCENT),
            Spacer(1, 4 * mm), self.p("Terms on this page", "h2"),
            self.p("<br/>".join(f"<b>{escape(BY_KEY[k].phrase[0].upper() + BY_KEY[k].phrase[1:])}</b>: "
                                f"{escape(BY_KEY[k].definition)}." for k in LEAVE_BEHIND_TERMS), "small"),
        ]

    def story(self) -> list:
        """The pack, section by section. Each section's numbers are recorded under its own provenance scope, and
        the pages it fills are noted in `page_scopes`, so an audit can tell which section printed each page."""
        out = []
        for name in SECTIONS:
            with scope(name):
                flowables = getattr(self, name)()
            # Every section ends on a page break except the last, which fills one page.
            self.page_scopes += [name] * max(1, sum(isinstance(x, PageBreak) for x in flowables))
            out += flowables
        return out


def _footer(canvas, doc, illustrative: bool = False) -> None:
    canvas.saveState()
    canvas.setFont("Sans", 6.8)
    canvas.setFillColor(c(MUTED))
    canvas.drawString(MARGIN_X, 9 * mm, f"{TITLE}   ·   {SYNTHETIC}")
    canvas.drawRightString(A4[0] - MARGIN_X, 9 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(c(RULE))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, 12 * mm, A4[0] - MARGIN_X, 12 * mm)
    if illustrative:
        canvas.setFont("Sans-Bold", 7.5)
        canvas.setFillColor(c(ACCENT))
        canvas.drawRightString(A4[0] - MARGIN_X, A4[1] - 9 * mm, "ILLUSTRATIVE: modelled figures, not results")
    canvas.restoreState()


def build_pdf(facts: Facts, figures: dict[str, Path], out: Path, page_scopes: list[str] | None = None) -> Path:
    """Write the pack. If `page_scopes` is given, it receives the section that printed each page, in order."""
    register_fonts()
    rl_config.invariant = 1
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, FRAME_W, FRAME_H, leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0, id="body")
    doc = BaseDocTemplate(str(out), pagesize=A4, title=TITLE, author="FabSync demonstrator",
                          subject=SYNTHETIC, creator="FabSync", invariant=1,
                          leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_TOP,
                          bottomMargin=MARGIN_BOTTOM)
    doc.addPageTemplates([PageTemplate("body", [frame], onPage=_footer),
                          PageTemplate("illustrative", [frame], onPage=lambda cv, d: _footer(cv, d, True))])
    pack = Pack(facts, figures)
    doc.build(pack.story())
    if page_scopes is not None:
        page_scopes += pack.page_scopes
    return out
