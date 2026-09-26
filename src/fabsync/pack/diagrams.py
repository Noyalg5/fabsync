"""Diagrams for the management pack: the three disconnected systems, the AS-IS process maps and the target
architecture.

The process maps and the architecture are drawn from the committed diagram sources, the same ones behind the
design documents, so the pack and the documents always show the same steps, break points and measured
figures. They are laid out afresh for an A4 page: each process map becomes a swimlane with one lane per
system, so every hand-off between systems is visible as a line crossing lanes.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field

from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

from fabsync.pack.charts import STYLE, SYNTHETIC, WIDTH
from fabsync.palette import ACCENT, ACCENT_FILL, INK, MUTED, PAPER, RULE, SYSTEM_COLOURS, SYSTEM_LABELS

MM = 1 / 25.4
PAGE_W = 170.0                         # mm


# ---- parsing -------------------------------------------------------------------------------------- #

@dataclass
class Flowchart:
    groups: list[tuple[str, str, list[str]]] = field(default_factory=list)   # id, title, member node ids
    nodes: dict[str, tuple[list[str], str]] = field(default_factory=dict)    # id -> (lines, shape)
    edges: list[tuple[str, str, str, str]] = field(default_factory=list)     # source, target, label, style
    classes: dict[str, str] = field(default_factory=dict)                   # node id -> class name
    borders: dict[str, str] = field(default_factory=dict)                   # node id -> border colour


NODE = re.compile(r'^\s*(\w+)(?:\[/"(?P<sheet>.*)"/\]|\["(?P<box>.*)"\]|\{\{"(?P<hex>.*)"\}\})\s*$')
EDGE = re.compile(r'^\s*(\w+)\s*(?:--\s*"(?P<l1>[^"]*)"\s*-->|(?P<plain>-->)|-\.\s*"(?P<l2>[^"]*)"\s*\.->|'
                  r'(?P<dot>-\.-)|(?P<inv>~~~))\s*(\w+)\s*$')


def parse(source: str) -> Flowchart:
    chart, group = Flowchart(), None
    for line in source.splitlines():
        if line.lstrip().startswith("%%"):
            continue
        if m := re.match(r'^\s*subgraph (\w+)\["([^"]+)"\]', line):
            group = (m.group(1), m.group(2), [])
            chart.groups.append(group)
        elif line.strip() == "end":
            group = None
        elif m := NODE.match(line):
            shape = next(k for k in ("sheet", "box", "hex") if m.group(k) is not None)
            chart.nodes[m.group(1)] = (m.group(shape).split("<br/>"), shape)
            if group:
                group[2].append(m.group(1))
        elif m := EDGE.match(line):
            dotted = m.group("l2") is not None or m.group("dot")
            style = "dotted" if dotted else "hidden" if m.group("inv") else "solid"
            chart.edges.append((m.group(1), m.group(7), m.group("l1") or m.group("l2") or "", style))
        elif m := re.match(r"^\s*class ([\w,]+) (\w+)\s*$", line):
            chart.classes.update(dict.fromkeys(m.group(1).split(","), m.group(2)))
        elif m := re.match(r"^\s*style (\w+) stroke:(#[0-9A-Fa-f]{6})", line):
            chart.borders[m.group(1)] = m.group(2)
    return chart


# ---- drawing helpers ------------------------------------------------------------------------------ #

def wrap(text: str, width_mm: float, size: float) -> list[str]:
    chars = max(8, int(width_mm / (size * 0.3528 * 0.57)))
    return textwrap.wrap(text, chars, break_on_hyphens=False) or [""]


def line_h(size: float) -> float:
    return size * 0.3528 * 1.22


def canvas(height_mm: float, title: str | None = None) -> tuple[Figure, object]:
    fig = plt.figure(figsize=(WIDTH, height_mm * MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PAGE_W)
    ax.set_ylim(height_mm, 0)
    ax.axis("off")
    if title:
        ax.text(2.5, 2.5, title, fontsize=8.5, fontweight="bold", va="top", color=INK)
    ax.text(2.5, height_mm - 1.5, SYNTHETIC, fontsize=5.5, color=MUTED, va="bottom")
    return fig, ax


def text_block(ax, x: float, y: float, lines: list[str], size: float, colour: str = INK, bold_first: bool = False,
               ha: str = "center") -> None:
    for i, text in enumerate(lines):
        ax.text(x, y + line_h(size) * (i + 0.5), text, fontsize=size, color=colour, ha=ha, va="center",
                fontweight="bold" if bold_first and i == 0 else "normal")


def rect(ax, x, y, w, h, edge, fill="white", lw=0.8, dashed=False, rounded=False) -> None:
    style = "round,pad=0,rounding_size=1.2" if rounded else "square,pad=0"
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, facecolor=fill, edgecolor=edge, linewidth=lw,
                                linestyle=(0, (3, 2)) if dashed else "solid"))


def arrow(ax, points: list[tuple[float, float]], colour: str, lw: float = 0.7, dotted: bool = False) -> None:
    xs, ys = zip(*points, strict=True)
    ax.plot(xs, ys, color=colour, linewidth=lw, linestyle=(0, (1.5, 1.5)) if dotted else "solid",
            solid_capstyle="butt")
    (x0, y0), (x1, y1) = points[-2], points[-1]
    ax.annotate("", xy=(x1, y1), xytext=(x1 - (x1 - x0) * 0.01, y1 - (y1 - y0) * 0.01),
                arrowprops={"arrowstyle": "-|>,head_length=0.35,head_width=0.18", "color": colour, "lw": lw,
                            "shrinkA": 0, "shrinkB": 0})


def label(ax, x: float, y: float, text: str, colour: str = INK, size: float = 5.6, bold: bool = False,
          rotation: float = 0) -> None:
    ax.text(x, y, text, fontsize=size, color=colour, ha="center", va="center", rotation=rotation,
            fontweight="bold" if bold else "normal",
            bbox={"boxstyle": "square,pad=0.15", "facecolor": "white", "edgecolor": "none"})


# ---- three disconnected systems ----------------------------------------------------------------------- #

def three_systems(title: str, gaps: dict[str, str], job_code: str) -> Figure:
    """The three systems as the business runs them today, with the gaps between them labelled.

    `job_code` is the finance system's code for the example job J-24-0871, looked up in the warehouse.
    """
    contents = {
        "corvus_mrp": ["Works orders, bills of material, stock", "Purchase orders, goods received",
                       "Installed 2006; UPPERCASE codes", "No supplier list"],
        "finance": ["Ledgers, invoices, payments", "Job costs and supplier accounts",
                    f"Its own job numbering, like {job_code}", "Invoices keyed by hand"],
        "shop_floor": ["Time bookings, delivery notes, NCRs", "Weekly capacity, one set per site",
                       "Free text, mixed date formats", "Works orders typed by hand"],
    }
    with plt.rc_context(STYLE):
        h, w, bh = 74.0, 54.0, 6.2 + 4 * line_h(6.4) + 3.4
        fig, ax = canvas(h, title)
        spots = {"corvus_mrp": (4, 11), "finance": (PAGE_W - 4 - w, 11), "shop_floor": ((PAGE_W - w) / 2, 44)}
        for system, (x, y) in spots.items():
            colour = SYSTEM_COLOURS[system]
            rect(ax, x, y, w, bh, colour, lw=1.4)
            ax.add_patch(Rectangle((x, y), w, 6.2, facecolor=colour, edgecolor=colour, linewidth=1.4))
            ax.text(x + 2.5, y + 3.1, SYSTEM_LABELS[system], fontsize=7.5, fontweight="bold", color="white",
                    va="center")
            text_block(ax, x + 2.5, y + 8, contents[system], 6.4, ha="left")
        c, f, s_ = spots["corvus_mrp"], spots["finance"], spots["shop_floor"]
        dashes = {"color": MUTED, "linewidth": 1.1, "linestyle": (0, (3, 3))}
        ax.plot([c[0] + w, f[0]], [c[1] + bh / 2 + 3, f[1] + bh / 2 + 3], **dashes)
        ax.plot([c[0] + w * 0.5, s_[0]], [c[1] + bh, s_[1] + bh / 2], **dashes)
        ax.plot([f[0] + w * 0.5, s_[0] + w], [f[1] + bh, s_[1] + bh / 2], **dashes)
        label(ax, PAGE_W / 2, c[1] + bh / 2 - 2, gaps["corvus_finance_1"], size=6.2)
        label(ax, PAGE_W / 2, c[1] + bh / 2 + 8, gaps["corvus_finance_2"], size=6.2)
        for key, x in (("corvus_shop", 26), ("finance_shop", PAGE_W - 26)):
            label(ax, x, 50, "\n".join(textwrap.wrap(gaps[key], 30)), size=6.2)
        ax.text(PAGE_W / 2, 38.5, "No link between them", fontsize=8, fontweight="bold", color=ACCENT, ha="center",
                va="center")
        return fig


# ---- swimlane process maps ---------------------------------------------------------------------------- #

LANES = [("customer", "Customer", MUTED), ("paper", "Paper, phone and email", MUTED),
         ("corvus_mrp", "Corvus MRP", SYSTEM_COLOURS["corvus_mrp"]),
         ("shop_floor", "Shop-floor and yard sheets", SYSTEM_COLOURS["shop_floor"]),
         ("finance", "Finance system", SYSTEM_COLOURS["finance"])]
REKEY = re.compile(r"re-key|typed", re.I)


def lane_of(group_title: str) -> str:
    t = group_title.lower()
    if t == "customer":
        return "customer"
    if t.startswith("paper"):
        return "paper"
    if t == "corvus mrp":
        return "corvus_mrp"
    if t == "finance system":
        return "finance"
    if t in ("shop-floor spreadsheets", "yard"):
        return "shop_floor"
    raise ValueError(f"no swimlane for {group_title!r}")


def swimlane(title: str, source: str) -> Figure:
    """A process map as swimlanes: steps top to bottom, one lane per system, break points on the right.

    Rows are sized by the steps alone. Each break point sits level with its step where there is room, and
    otherwise just below the one before it, joined to its step by a dotted line.
    """
    chart = parse(source)
    lane = {node: lane_of(t) for _, t, members in chart.groups for node in members}
    steps = [n for _, _, members in chart.groups for n in members if chart.nodes[n][1] != "hex"]
    lanes = [entry for entry in LANES if entry[0] in set(lane.values())]
    colour_of = {key: colour for key, _, colour in LANES}
    breaks: dict[str, list[str]] = {}
    for a, b, _, style in chart.edges:
        if style == "dotted" and chart.nodes[b][1] == "hex":
            breaks.setdefault(a, []).append(b)

    size, csize = 5.8, 5.7
    top, head, callout_w, gap = 10.0, 8.5, 52.0, 4.2
    lane_w = (PAGE_W - callout_w - 7) / len(lanes)
    x_of = {key: 2 + i * lane_w for i, (key, _, _) in enumerate(lanes)}
    callout_x = PAGE_W - callout_w - 2

    rows, y = {}, top + head + 3
    for step in steps:
        lines = wrap(chart.nodes[step][0][0], lane_w - 5, size)
        box_h = len(lines) * line_h(size) + 2.2
        rows[step] = (y, box_h, lines)
        y += box_h + gap
    callouts, floor = [], top + head + 3
    for step in steps:
        y0, box_h, _ = rows[step]
        for b in breaks.get(step, []):
            head_line, *rest = chart.nodes[b][0]
            bold = wrap(head_line, callout_w - 4, csize * 1.08)
            text = bold + [piece for r in rest for piece in wrap(r, callout_w - 4, csize * 1.04)]
            ch = len(text) * line_h(csize) + 2.4
            cy = max(y0 + box_h / 2 - ch / 2, floor)
            callouts.append((step, cy, ch, text, len(bold)))
            floor = cy + ch + 1.6
    height = max(y, floor) + 4

    with plt.rc_context(STYLE):
        fig, ax = canvas(height, title)
        for key, name, colour in lanes:
            x = x_of[key]
            system = key not in ("customer", "paper")
            ax.add_patch(Rectangle((x, top), lane_w - 1, height - top - 4.5, facecolor="white" if system else PAPER,
                                   edgecolor=RULE, linewidth=0.5))
            ax.add_patch(Rectangle((x, top), lane_w - 1, head, facecolor=colour if system else RULE,
                                   edgecolor="none"))
            name_lines = wrap(name, lane_w - 3, 6.8)
            for i, t in enumerate(name_lines):
                ax.text(x + (lane_w - 1) / 2, top + head / 2 + line_h(6.2) * (i - (len(name_lines) - 1) / 2), t,
                        fontsize=6.2, fontweight="bold", color="white" if system else INK, ha="center", va="center")
        ax.add_patch(Rectangle((callout_x, top), callout_w, head, facecolor=ACCENT, edgecolor="none"))
        ax.text(callout_x + callout_w / 2, top + head / 2, "Break points and what they cost", fontsize=6.2,
                color="white", fontweight="bold", ha="center", va="center")

        box_at = {}
        for step in steps:
            y0, box_h, lines = rows[step]
            x, bw = x_of[lane[step]] + 2, lane_w - 5
            colour = colour_of[lane[step]]
            if chart.nodes[step][1] == "sheet":
                ax.add_patch(Polygon([(x + 1.2, y0), (x + bw, y0), (x + bw - 1.2, y0 + box_h), (x, y0 + box_h)],
                                     closed=True, facecolor="white", edgecolor=colour, linewidth=0.9))
            else:
                rect(ax, x, y0, bw, box_h, colour, lw=0.9)
            text_block(ax, x + bw / 2, y0 + 1.1, lines, size)
            box_at[step] = (x + bw / 2, y0, y0 + box_h, x + bw)
        for step, cy, ch, text, bold_lines in callouts:
            _, y0, y1, right = box_at[step]
            rect(ax, callout_x, cy, callout_w, ch, ACCENT, fill=ACCENT_FILL, lw=0.8, rounded=True)
            for i, t in enumerate(text):
                ax.text(callout_x + 2, cy + 1.2 + line_h(csize) * (i + 0.5), t, fontsize=csize, color=INK,
                        va="center", fontweight="bold" if i < bold_lines else "normal")
            ax.plot([right, callout_x], [(y0 + y1) / 2, cy + ch / 2], color=ACCENT, linewidth=0.6,
                    linestyle=(0, (1, 1.5)))

        for a, b, text, style in chart.edges:
            if style != "solid" or a not in box_at or b not in box_at:
                continue
            ax_, _, a_bottom, _ = box_at[a]
            bx, b_top, _, _ = box_at[b]
            emphasis = bool(REKEY.search(text))
            colour = ACCENT if emphasis else INK
            if abs(ax_ - bx) < 0.1:
                arrow(ax, [(ax_, a_bottom), (bx, b_top)], colour)
                if text:
                    label(ax, ax_, (a_bottom + b_top) / 2, text, colour, bold=emphasis)
            else:
                mid = a_bottom + gap / 2
                arrow(ax, [(ax_, a_bottom), (ax_, mid), (bx, mid), (bx, b_top)], colour)
                if text:
                    label(ax, (ax_ + bx) / 2, mid, text, colour, bold=emphasis)
        return fig


# ---- target architecture ------------------------------------------------------------------------------ #

def phrases(lines: list[str]) -> list[str]:
    """Rejoin source lines that were broken mid-phrase, so they can be wrapped again for the page."""
    out: list[str] = []
    for line in lines:
        if out and not line.startswith("(") and (out[-1].endswith(",") or out[-1].endswith(" and")):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def architecture(title: str, source: str) -> Figure:
    """The target: where data is entered, how it is collected and checked, and who acts on it."""
    chart = parse(source)
    edge_label = {(a, b): t for a, b, t, _ in chart.edges}

    def style_of(node: str) -> tuple[str, str, bool]:
        cls = chart.classes.get(node, "stays")
        border = chart.borders.get(node, ACCENT if cls == "new" else MUTED if cls == "retired" else INK)
        return border, ACCENT_FILL if cls == "new" else "white", cls == "retired"

    def lines_of(node: str, w: float, size: float) -> tuple[list[str], int]:
        first, *rest = phrases(chart.nodes[node][0])
        head_lines = wrap(first, w - 4, size * 1.08)
        return head_lines + [piece for r in rest for piece in wrap(r, w - 4, size)], len(head_lines)

    def height(node: str, w: float, size: float) -> float:
        return len(lines_of(node, w, size)[0]) * line_h(size) + 3

    def box(ax, node: str, x: float, y: float, w: float, size: float, h: float | None = None) -> float:
        lines, bold = lines_of(node, w, size)
        h = h or height(node, w, size)
        border, fill, dashed = style_of(node)
        rect(ax, x, y, w, h, border, fill=fill, lw=0.7 if dashed else 1.3, dashed=dashed)
        y0 = y + (h - len(lines) * line_h(size)) / 2
        for i, t in enumerate(lines):
            ax.text(x + w / 2, y0 + line_h(size) * (i + 0.5), t, fontsize=size, ha="center", va="center",
                    color=MUTED if dashed else INK, fontweight="bold" if i < bold and not dashed else "normal")
        return h

    entry = next(g for g in chart.groups if g[0] == "ENTRY")
    retired = next(g for g in chart.groups if g[0] == "RETIRED")
    key = next(g for g in chart.groups if g[0] == "KEY")
    size, inner = 6.2, PAGE_W - 14
    ew = (inner - 4 * 3) / 3
    col_gap = 16.0
    half = (inner - 6 - col_gap) / 2
    x_left, x_right = 5, 5 + half + col_gap
    rw = (inner - 5 * 3) / 4

    y_entry = 10.0
    h_entry = max(height(n, ew, size) for n in entry[2])
    band_bottom = y_entry + 7 + h_entry + 3
    y_int = band_bottom + 11
    h_int = height("INT", inner - 6, size)
    y_mid = y_int + h_int + 11
    h_mid = max(height("WH", half, size), height("MDS", half, size))
    y_low = y_mid + h_mid + 11
    h_low = max(height("REP", half, size), height("OWN", half, size))
    y_ret = y_low + h_low + 9
    h_ret = max(height(n, rw, 5.8) for n in retired[2])
    y_key = y_ret + 7 + h_ret + 9
    total = y_key + 13

    with plt.rc_context(STYLE):
        fig, ax = canvas(total, title)
        rect(ax, 2, y_entry, inner + 2, band_bottom - y_entry, RULE, lw=0.6)
        ax.text(5, y_entry + 3.2, entry[1], fontsize=6.5, color=INK, fontweight="bold", va="center")
        centres = {}
        for i, node in enumerate(entry[2]):
            x = 5 + i * (ew + 3)
            box(ax, node, x, y_entry + 7, ew, size, h_entry)
            centres[node] = x + ew / 2
        for node, cx in centres.items():
            arrow(ax, [(cx, y_entry + 7 + h_entry), (cx, y_int)], INK)
            label(ax, cx, (band_bottom + y_int) / 2, edge_label[(node, "INT")])
        box(ax, "INT", 5, y_int, inner - 6, size, h_int)

        box(ax, "WH", x_left, y_mid, half, size, h_mid)
        box(ax, "MDS", x_right, y_mid, half, size, h_mid)
        for x, node in ((x_left, "WH"), (x_right, "MDS")):
            arrow(ax, [(x + half / 2, y_int + h_int), (x + half / 2, y_mid)], INK)
            label(ax, x + half / 2, (y_int + h_int + y_mid) / 2, edge_label[("INT", node)])
        arrow(ax, [(x_right, y_mid + h_mid / 2), (x_left + half, y_mid + h_mid / 2)], INK)
        label(ax, (x_left + half + x_right) / 2, y_mid + h_mid / 2 - 4.2,
              "\n".join(textwrap.wrap(edge_label[("MDS", "WH")], 12)))

        box(ax, "REP", x_left, y_low, half, size, h_low)
        box(ax, "OWN", x_right, y_low, half, size, h_low)
        arrow(ax, [(x_left + half / 2, y_mid + h_mid), (x_left + half / 2, y_low)], INK)
        arrow(ax, [(x_left + half, y_low + h_low / 2), (x_right, y_low + h_low / 2)], INK)
        label(ax, (x_left + half + x_right) / 2, y_low + h_low / 2 - 5,
              "\n".join(textwrap.wrap(edge_label[("REP", "OWN")], 12)))
        arrow(ax, [(x_right + half * 0.75, y_low), (x_right + half * 0.75, y_mid + h_mid)], INK)
        label(ax, x_right + half * 0.75, (y_mid + h_mid + y_low) / 2, edge_label[("OWN", "MDS")])

        back = next(t for a, b, t, s in chart.edges if a == "MDS" and b == "ENTRY")
        rx, band_right = PAGE_W - 4, 2 + inner + 2
        arrow(ax, [(x_right + half, y_mid + h_mid / 2), (rx, y_mid + h_mid / 2), (rx, y_entry + 5),
                   (band_right, y_entry + 5)], ACCENT, dotted=True)
        ax.text(rx - 1.7, (y_mid + h_mid / 2 + y_entry + 5) / 2, back, fontsize=5.6, color=ACCENT, rotation=90,
                ha="center", va="center",
                bbox={"boxstyle": "square,pad=0.15", "facecolor": "white", "edgecolor": "none"})

        rect(ax, 2, y_ret, inner + 2, h_ret + 10, RULE, lw=0.6, dashed=True)
        ax.text(5, y_ret + 3.2, retired[1], fontsize=6.5, color=MUTED, fontweight="bold", va="center")
        for i, node in enumerate(retired[2]):
            box(ax, node, 5 + i * (rw + 3), y_ret + 7, rw, 5.8, h_ret)

        kx = 5.0
        ax.text(kx, y_key + 3, "Key", fontsize=6.3, fontweight="bold", va="center")
        kx += 8
        for node in key[2]:
            border, fill, dashed = style_of(node)
            rect(ax, kx, y_key, 7, 6, border, fill=fill, lw=0.7 if dashed else 1.3, dashed=dashed)
            ax.text(kx + 9, y_key + 3, chart.nodes[node][0][0], fontsize=6.3, va="center",
                    color=MUTED if dashed else INK)
            kx += 33
        for system in ("corvus_mrp", "finance", "shop_floor"):
            ax.add_patch(Rectangle((kx, y_key + 1.5), 3, 3, facecolor=SYSTEM_COLOURS[system], linewidth=0))
            kx += 4.2
        ax.text(kx + 0.8, y_key + 3, "Border shows the system", fontsize=6.3, va="center")
        return fig
