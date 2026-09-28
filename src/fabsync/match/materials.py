"""Material matching: parse UK section designations and emit a canonical material code.

Corvus writes one material many ways: ``UB203X133X25-S355J2``, ``UB203X133X25``,
``203X133X25UB``, ``UNIV BEAM 203X133X25``, ``PLT12-S355J2``, ``PLATE12``,
``PL12MM``, ``12mm PLATE``. Each distinct way a material is written, in each
table, is parsed from both its code and its description into section type,
dimensions and grade, and mapped to one canonical code in the Corvus house form
(``UB203X133X25-S355J2``, ``PLT12-S355J2``).

Grade is the hard part. A code with no grade on a purchase order cannot say
whether the steel is S275JR or S355J2. On EXC3 work, and for S355 at any execution
class, EN 1090 makes that a traceability question, not a formatting one. Grade is taken, in this order, from: the BOM
grade column, the grade in the code, the grade in the description. Only if all
are silent is it inferred, and then only when the designation is stocked in a
single grade; otherwise the candidates go to the review queue.

Scores:

====  ===============================================  =======
 100  code already canonical                            auto
  98  code parsed, grade in the code                    auto
  97  code parsed, grade from the BOM grade column      auto
  96  code parsed, grade from the description           auto
  95  parsed from the description only                  auto
  90  grade inferred: designation stocked in one grade  review
  85  grade ambiguous: several grades stocked           review
  82  code and description disagree                     review
  70  designation not seen with any grade               unmatched
   0  cannot be parsed                                  unmatched
====  ===============================================  =======

Golden record survivorship (one row per canonical code, built from auto
matches only):

* identity: section type and designation as parsed; grade by the order above
* mass per metre: reference catalogue (config/section_catalogue.csv), else the
  serial mass in the designation (UB, UC, PFC), else the modal BOM unit weight;
  plate is 7.85 kg/m2 per mm of thickness
* description: generated from the structured fields, e.g. ``UB 203x133x25 S355J2``
* base unit: M for sections, KG for plate; every unit seen in any system is listed
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fabsync.match.common import MatchContext

SECTION_CATALOGUE = Path("config/section_catalogue.csv")
KINDS = ("PLATE", "FLAT", "PFC", "SHS", "RHS", "CHS", "UB", "UC", "L")
DIM_PARTS = {"UB": 3, "UC": 3, "PFC": 3, "SHS": 3, "RHS": 3, "L": 3, "CHS": 2, "FLAT": 2, "PLATE": 1}
LONG_NAMES = {
    "PARALLEL FLANGE CHANNEL": "PFC", "PAR FLANGE CHAN": "PFC", "UNIVERSAL BEAM": "UB", "UNIV BEAM": "UB",
    "UNIVERSAL COLUMN": "UC", "UNIV COL": "UC", "SQUARE HOLLOW": "SHS", "SQ HOLLOW": "SHS",
    "RECTANGULAR HOLLOW": "RHS", "RECT HOLLOW": "RHS", "CIRCULAR HOLLOW": "CHS", "CIRC HOLLOW": "CHS",
    "EQUAL ANGLE": "L", "UNEQUAL ANGLE": "L", "ANGLE": "L", "FLAT BAR": "FLAT",
}
NON_SECTION = re.compile(r"^(BOLT|NUT|WASH|WIRE|PAINT|GAS)-")
GRADE_RE = re.compile(r"\bS\s?(235|275|355|420|460)\s?(JR|J0|JO|J2|K2|NL|N|ML|M)?\b")
DIMS = r"(\d+(?:\.\d+)?(?:X\d+(?:\.\d+)?){0,2})"
KIND_ALT = "|".join(k for k in KINDS if k != "PLATE")
PATTERNS = [
    ("kind_prefix", re.compile(rf"^({KIND_ALT})[\s-]*{DIMS}$")),
    ("kind_suffix", re.compile(rf"^{DIMS}[\s-]*({KIND_ALT})$")),
    ("plate_prefix", re.compile(r"^(PLATE|PLT|PL)[\s-]*(\d+(?:\.\d+)?)\s*(?:MM)?$")),
    ("plate_suffix", re.compile(r"^(\d+(?:\.\d+)?)\s*MM\s*(PLATE|PLT|PL)$")),
]


@dataclass(frozen=True)
class Parsed:
    kind: str
    dims: str  # upper-case X, e.g. 203X133X25; plate thickness in mm, e.g. 12
    grade: str | None
    form: str

    @property
    def designation(self) -> str:
        return self.dims.lower() if self.kind != "PLATE" else f"{self.dims}mm"


def normalise_grade(text: str) -> str:
    grade = text.replace(" ", "").upper()
    return grade.replace("JO", "J0")


def parse(text: str | None) -> Parsed | None:
    """Parse a material code or description; None if it is not a recognisable section or plate."""
    if not text:
        return None
    s = text.upper().strip()
    grade = None
    m = GRADE_RE.search(s)
    if m:
        grade = normalise_grade(m.group(0))
        s = (s[:m.start()] + s[m.end():]).strip(" -")
    long_form = False
    for name, code in sorted(LONG_NAMES.items(), key=lambda kv: -len(kv[0])):
        if s.startswith(name):
            s = code + " " + s[len(name):].strip()
            long_form = True
            break
    s = re.sub(r"\s*X\s*", "X", s)
    for form, pattern in PATTERNS:
        m = pattern.match(s)
        if not m:
            continue
        if form == "kind_prefix":
            kind, dims = m.group(1), m.group(2)
        elif form == "kind_suffix":
            dims, kind = m.group(1), m.group(2)
        elif form == "plate_prefix":
            kind, dims = "PLATE", m.group(2)
        else:
            kind, dims = "PLATE", m.group(1)
        if len(dims.split("X")) != DIM_PARTS[kind]:
            return None
        return Parsed(kind, dims, grade, "long_name" if long_form else form)
    return None


def canonical_code(kind: str, dims: str, grade: str) -> str:
    return f"PLT{dims}-{grade}" if kind == "PLATE" else f"{kind}{dims}-{grade}"


def canonical_description(kind: str, dims: str, grade: str) -> str:
    return f"PLATE {dims}mm {grade}" if kind == "PLATE" else f"{kind} {dims.lower()} {grade}"


def load_catalogue(path: Path = SECTION_CATALOGUE) -> dict[tuple[str, str], float]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    return {(r["kind"], r["designation"].upper()): float(r["kg_per_m"]) for r in reader}


SOURCES_SQL = """
SELECT 'bom_lines' AS source_table, material_code AS source_code, description AS source_description,
       grade AS source_grade, section_type AS source_section_type, string_agg(DISTINCT uom, ',' ORDER BY uom) AS uoms,
       count(*) AS row_count, mode(unit_weight_kg) AS modal_unit_weight
FROM staging.corvus_mrp_bom_lines GROUP BY ALL
UNION ALL
SELECT 'stock', material_code, description, NULL, NULL, string_agg(DISTINCT uom, ',' ORDER BY uom), count(*), NULL
FROM staging.corvus_mrp_stock GROUP BY ALL
UNION ALL
SELECT 'purchase_orders', material_code, NULL, NULL, NULL, string_agg(DISTINCT uom, ',' ORDER BY uom), count(*), NULL
FROM staging.corvus_mrp_purchase_orders GROUP BY ALL
UNION ALL
SELECT 'goods_received', material_code, NULL, NULL, NULL, string_agg(DISTINCT uom, ',' ORDER BY uom), count(*), NULL
FROM staging.corvus_mrp_goods_received GROUP BY ALL
"""


def resolve(row, grades_by_design: dict[tuple[str, str], set[str]], catalogue: dict) -> dict:
    code, desc = row.source_code, row.source_description
    out = {"section_type": None, "designation": None, "grade": None, "canonical_code": None, "proposed_code": None,
           "candidates": None, "method": "unparsed", "score": 0.0, "matched_on": ""}
    pc = parse(code)
    pdsc = parse(desc) if isinstance(desc, str) else None
    if pc is None and NON_SECTION.match(code or ""):
        out.update(canonical_code=code, method="non_section_passthrough", score=100.0,
                   matched_on=f"'{code}' is a consumable; its Corvus code is already its identity")
        return out
    base = pc or pdsc
    if base is None:
        out["matched_on"] = f"neither code '{code}' nor description '{desc}' is a recognisable section or plate"
        return out
    kind, dims = base.kind, base.dims
    out.update(section_type=kind, designation=base.designation)
    notes = [f"code '{code}' parsed as {kind} {base.designation} ({base.form})" if pc else
             f"code '{code}' not parseable; description '{desc}' parsed as {kind} {base.designation} ({base.form})"]

    conflict = pc is not None and pdsc is not None and (pc.kind, pc.dims) != (pdsc.kind, pdsc.dims)
    st = row.source_section_type if isinstance(row.source_section_type, str) else None
    if st and st != kind:
        conflict = True
        notes.append(f"BOM section_type says {st}")

    grade_sources = []
    if isinstance(row.source_grade, str) and row.source_grade:
        grade_sources.append(("BOM grade column", normalise_grade(row.source_grade)))
    if pc and pc.grade:
        grade_sources.append(("code", pc.grade))
    if pdsc and pdsc.grade:
        grade_sources.append(("description", pdsc.grade))
    grades = sorted({g for _, g in grade_sources})

    if conflict or len(grades) > 1:
        cands = [canonical_code(kind, dims, g) for g in grades] or None
        out.update(method="source_conflict", score=82.0, candidates=", ".join(cands) if cands else None,
                   matched_on="; ".join(notes + [f"grades seen: {', '.join(grades) or 'none'}"]))
        return out

    if grades:
        grade = grades[0]
        where = grade_sources[0][0]
        code_out = canonical_code(kind, dims, grade)
        if pc and code.strip() == code_out:
            method, score = "canonical_code", 100.0
        elif pc and pc.grade:
            method, score = "parsed_code", 98.0
        elif pc and where == "BOM grade column":
            method, score = "parsed_code+grade_column", 97.0
        elif pc:
            method, score = "parsed_code+grade_in_description", 96.0
        else:
            method, score = "parsed_description", 95.0
        if kind != "PLATE" and (kind, dims) not in catalogue:
            method, score = method + "+not_in_catalogue", min(score, 90.0)
            notes.append("designation not in the section catalogue")
        out.update(grade=grade, canonical_code=code_out if score >= 95 else None,
                   proposed_code=code_out if score < 95 else None, method=method, score=score,
                   matched_on="; ".join(notes + [f"grade {grade} from {where}"]))
        return out

    stocked = sorted(grades_by_design.get((kind, dims), set()))
    if len(stocked) == 1:
        code_out = canonical_code(kind, dims, stocked[0])
        out.update(grade=stocked[0], proposed_code=code_out, candidates=code_out,
                   method="grade_inferred_single_stocked_grade", score=90.0,
                   matched_on="; ".join(notes + [f"no grade written; {kind} {base.designation} is only held in "
                                                 f"{stocked[0]}; confirm from the mill certificate"]))
    elif stocked:
        cands = ", ".join(canonical_code(kind, dims, g) for g in stocked)
        out.update(candidates=cands, method="grade_ambiguous", score=85.0,
                   matched_on="; ".join(notes + [f"no grade written; {kind} {base.designation} is held in "
                                                 f"{', '.join(stocked)}; the mill certificate decides"]))
    else:
        out.update(method="designation_without_grade", score=70.0,
                   matched_on="; ".join(notes + ["no grade written and the designation is not held in any grade"]))
    return out


def match_materials(ctx: MatchContext) -> dict:
    catalogue = load_catalogue()
    sources = ctx.df(SOURCES_SQL + " ORDER BY source_table, source_code, source_description NULLS FIRST, "
                                   "source_grade NULLS FIRST, source_section_type NULLS FIRST")

    # First pass: every designation seen with an explicit grade anywhere.
    grades_by_design: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in sources.itertuples():
        pc, pdsc = parse(r.source_code), parse(r.source_description if isinstance(r.source_description, str) else None)
        base = pc or pdsc
        if not base:
            continue
        explicit = (r.source_grade if isinstance(r.source_grade, str) and r.source_grade else None) or \
            (pc.grade if pc else None) or (pdsc.grade if pdsc else None)
        if explicit:
            grades_by_design[(base.kind, base.dims)].add(normalise_grade(explicit))

    resolved = pd.DataFrame([resolve(r, grades_by_design, catalogue) for r in sources.itertuples()])
    xref = pd.concat([sources.reset_index(drop=True), resolved], axis=1)
    xref.insert(0, "xref_id", [f"MX{i:05d}" for i in range(1, len(xref) + 1)])
    xref.insert(1, "source_system", "corvus_mrp")
    xref["status"] = xref["score"].map(ctx.status)
    xref["est_minutes"] = xref["status"].map(lambda s: ctx.minutes("material") if s == "review" else 0.0)
    ctx.write("core.material_xref", xref.drop(columns=["modal_unit_weight"]))

    golden = build_golden(xref, catalogue, ctx)
    ctx.write("core.material_golden", golden, audit=False)

    queue = xref[xref.status == "review"][["xref_id", "source_table", "source_code", "source_description",
                                           "row_count", "proposed_code", "candidates", "method", "score",
                                           "matched_on", "est_minutes"]]
    ctx.write("core.material_review_queue", queue)

    n, auto = len(xref), int((xref.status == "auto").sum())
    ctx.lineage(rule_id="MA-01", system="corvus_mrp", source_table="bom_lines, stock, purchase_orders, goods_received",
                source_file="corvus_mrp/*.csv", target_table="core.material_xref", rows=n, affected=auto,
                detail=f"{n} distinct ways materials are written; {auto} auto, "
                       f"{int((xref.status == 'review').sum())} review, {int((xref.status == 'unmatched').sum())} "
                       f"unmatched")
    ctx.lineage(rule_id="MA-02", system="corvus_mrp", source_table="material_xref", source_file="core.material_xref",
                target_table="core.material_golden", rows=len(golden), affected=int(golden.uom_conflict.sum()),
                detail=f"{len(golden)} golden materials; {int(golden.uom_conflict.sum())} transacted in more than "
                       f"one unit of measure; {int(golden.mass_deviation.sum())} with BOM mass off reference")
    return {"xref": xref, "golden": golden, "queue": queue}


SURVIVORSHIP = ("identity: parsed type + designation, grade from BOM column > code > description; "
                "mass: section catalogue > serial mass in designation > modal BOM unit weight; "
                "description: generated; base unit: M (plate KG)")


def build_golden(xref: pd.DataFrame, catalogue: dict, ctx: MatchContext) -> pd.DataFrame:
    tolerance = float(ctx.config["material"]["mass_tolerance"])
    bar = float(ctx.config["material"]["stock_bar_length_m"])
    auto = xref[(xref.status == "auto") & (xref.method != "non_section_passthrough")]
    pending = Counter()
    for r in xref[xref.status == "review"].itertuples():
        listed = r.candidates if isinstance(r.candidates, str) else r.proposed_code
        for c in (listed if isinstance(listed, str) else "").split(", "):
            if c:
                pending[c] += int(r.row_count)
    rows = []
    for code, grp in auto.groupby("canonical_code", sort=True):
        kind = grp.section_type.iloc[0]
        dims = code.split("-")[0].removeprefix("PLT") if kind == "PLATE" else code.split("-")[0][len(kind):]
        grade = grp.grade.iloc[0]
        observed = grp.modal_unit_weight.dropna()
        modal = float(observed.mode().iloc[0]) if len(observed) else None
        if kind == "PLATE":
            mass, source, basis = round(7.85 * float(dims), 2), "plate: 7.85 kg/m2 per mm", "kg/m2"
        elif (kind, dims) in catalogue:
            mass, source, basis = catalogue[(kind, dims)], "section catalogue", "kg/m"
        elif kind in ("UB", "UC", "PFC"):
            mass, source, basis = float(dims.split("X")[-1]), "serial mass in designation", "kg/m"
        else:
            mass, source, basis = modal, "modal BOM unit weight", "kg/m"
        uoms = sorted({u for s in grp.uoms.dropna() for u in s.split(",")})
        rows.append({
            "canonical_code": code, "section_type": kind,
            "designation": dims.lower() if kind != "PLATE" else f"{dims}mm", "grade": grade,
            "description": canonical_description(kind, dims, grade), "mass": mass, "mass_basis": basis,
            "mass_source": source, "bom_modal_unit_weight": modal,
            "mass_deviation": bool(modal and mass and abs(modal - mass) / mass > tolerance),
            "base_uom": "KG" if kind == "PLATE" else "M",
            "kg_per_ea": round(mass * bar, 2) if kind != "PLATE" and mass else None,
            "observed_uoms": ", ".join(uoms), "uom_conflict": len(uoms) > 1,
            "source_codes": ", ".join(sorted(grp.source_code.str.strip().unique())),
            "source_tables": ", ".join(sorted(grp.source_table.unique())),
            "xref_values": len(grp), "source_rows": int(grp.row_count.sum()),
            "pending_review_rows": pending.get(code, 0), "survivorship_rule": SURVIVORSHIP,
        })
    return pd.DataFrame(rows)
