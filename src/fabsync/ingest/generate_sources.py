"""Synthetic source data generator for the FabSync demonstrator.

Produces three mutually inconsistent exports under data/raw/:

* ``corvus_mrp/``  Corvus MRP (MRPII, installed 2006). UPPERCASE text, dates
  DD/MM/YYYY, fixed-width padding that leaves trailing whitespace, supplier
  names embedded in transactions with no clean supplier master, UoM EA/M/KG.
* ``finance/``     Finance system. Title Case, dates YYYY-MM-DD, some amounts
  stored as text with thousands separators, job codes in a different format
  from the MRPII job number ("J-24-0871" becomes "24871").
* ``shop_floor/``  Supervisor spreadsheets. Mixed case, typos, blank cells,
  three date formats in one column, duplicate rows, works orders written as
  "WO 12345", "wo-12345", "12345" or "12345 (rev B)".

Every file starts with a SYNTHETIC DATA header comment. The seeded defects are
written to DEFECTS.md (narrative) and defects.json (machine-readable) in the
output directory so the test suite can assert each is present and, later,
detected.

Output is deterministic for a given seed: the same seed always produces
byte-identical files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

DEFAULT_SEED = 1090
DEFAULT_OUT = Path("data/raw")
START = date(2024, 9, 1)
AS_OF = date(2026, 8, 31)
LABOUR_RATE = 38.0  # pounds per hour charged to jobs by finance
VAT_RATE = 0.20
BAR_LENGTH_M = 12.0  # stock bar length assumed when counting sections in EA

# --------------------------------------------------------------------------- #
# Reference data. Every name below is fictional.
# --------------------------------------------------------------------------- #

SITES = [("WKF", "Wakefield"), ("TEE", "Teesside")]
SITE_HEADCOUNT = {"WKF": 13, "TEE": 12}  # direct shop-floor staff; agency operators cover peaks
OPS_SITE_FORMS = {
    "WKF": ["Wakefield", "wakefield", "WKF", "Wakefield works", "Wkfd"],
    "TEE": ["Teesside", "teesside", "TEE", "Teesside works", "Tees"],
}
STOCK_LOCATIONS = ["RACK A1", "RACK A3", "RACK B2", "BAY 2", "BAY 4", "YARD", "PLATE STORE"]

LONG_KIND = {
    "UB": "UNIV BEAM",
    "UC": "UNIV COL",
    "PFC": "PAR FLANGE CHAN",
    "SHS": "SQ HOLLOW",
    "RHS": "RECT HOLLOW",
    "CHS": "CIRC HOLLOW",
    "L": "ANGLE",
    "FLAT": "FLAT BAR",
    "PLATE": "PLATE",
}

# kind, designation, kg/m (kg/m2 for plate), grades stocked
SECTION_CATALOGUE = [
    ("UB", "203x133x25", 25.1, ["S275JR", "S355J2"]),
    ("UB", "254x146x31", 31.1, ["S275JR", "S355J2"]),
    ("UB", "305x165x40", 40.3, ["S275JR", "S355J2"]),
    ("UB", "356x171x51", 51.0, ["S355J2"]),
    ("UB", "406x178x60", 60.1, ["S355J2"]),
    ("UB", "457x191x82", 82.0, ["S355J2"]),
    ("UB", "533x210x101", 101.0, ["S355J2"]),
    ("UB", "610x229x125", 125.1, ["S355J2"]),
    ("UC", "152x152x23", 23.0, ["S275JR", "S355J2"]),
    ("UC", "203x203x46", 46.1, ["S275JR", "S355J2"]),
    ("UC", "254x254x73", 73.1, ["S355J2"]),
    ("UC", "305x305x97", 96.9, ["S355J2"]),
    ("PFC", "100x50x10", 10.2, ["S275JR"]),
    ("PFC", "150x75x18", 17.9, ["S275JR"]),
    ("PFC", "200x75x23", 23.4, ["S355J0"]),
    ("PFC", "260x75x28", 27.6, ["S355J0"]),
    ("SHS", "50x50x3", 4.35, ["S355J2"]),
    ("SHS", "80x80x5", 11.7, ["S355J2"]),
    ("SHS", "100x100x6.3", 18.4, ["S355J2"]),
    ("SHS", "150x150x8", 35.4, ["S355J2"]),
    ("RHS", "100x50x4", 8.49, ["S355J2"]),
    ("RHS", "150x100x6.3", 23.1, ["S355J2"]),
    ("RHS", "200x100x8", 35.1, ["S355J2"]),
    ("CHS", "60.3x3.2", 4.51, ["S355J2"]),
    ("CHS", "114.3x5", 13.5, ["S355J2"]),
    ("CHS", "168.3x6.3", 25.2, ["S355J2"]),
    ("CHS", "219.1x8", 41.6, ["S355J2"]),
    ("L", "50x50x6", 4.47, ["S275JR"]),
    ("L", "75x75x8", 8.99, ["S275JR", "S355J0"]),
    ("L", "100x100x10", 15.0, ["S355J0"]),
    ("L", "150x90x12", 21.6, ["S355J0"]),
    ("FLAT", "50x8", 3.14, ["S275JR"]),
    ("FLAT", "100x10", 7.85, ["S275JR"]),
    ("FLAT", "150x12", 14.1, ["S355J0"]),
    ("PLATE", "8", 62.8, ["S275JR", "S355J2"]),
    ("PLATE", "10", 78.5, ["S355J2"]),
    ("PLATE", "12", 94.2, ["S355J2"]),
    ("PLATE", "15", 117.8, ["S355J2"]),
    ("PLATE", "20", 157.0, ["S355J2"]),
    ("PLATE", "25", 196.3, ["S355J2"]),
]
GRADE_PRICE_PER_TONNE = {"S275JR": 940.0, "S355J0": 1000.0, "S355J2": 1040.0}

CONSUMABLES = [
    ("BOLT-M20X60-88-HDG", "BOLT M20X60 GR 8.8 HDG", "EA", 1.85),
    ("BOLT-M24X80-88-HDG", "BOLT M24X80 GR 8.8 HDG", "EA", 3.40),
    ("NUT-M20-8-HDG", "NUT M20 GR 8 HDG", "EA", 0.42),
    ("WASH-M20-HDG", "WASHER M20 FORM A HDG", "EA", 0.11),
    ("WIRE-MIG-12", "MIG WIRE 1.2MM G3SI1 15KG", "EA", 38.50),
    ("PAINT-ZP-20L", "ZINC PHOSPHATE PRIMER 20L", "EA", 96.00),
    ("GAS-ARGOSHIELD", "ARGON/CO2 SHIELD GAS", "EA", 61.00),
]

STEEL_SUPPLIERS = [
    ("Tyne Steel Stockholders Ltd", "stockholder"),
    ("Humber Steels", "stockholder"),
    ("Aire Valley Steel Stock", "stockholder"),
    ("Calder Metals Ltd", "stockholder"),
    ("Pennine Steel Supplies", "stockholder"),
    ("Ouse Steel Services Ltd", "stockholder"),
    ("Wharfedale Sections", "stockholder"),
    ("Ribble Steel Stock Ltd", "stockholder"),
    ("Trent Plate & Sections", "stockholder"),
    ("Derwent Steels Ltd", "stockholder"),
    ("Tees Plate Ltd", "stockholder"),
    ("Northern Hollow Sections", "hollow"),
    ("Mersey Tube & Section Ltd", "hollow"),
    ("Lune Steel Co", "stockholder"),
    ("Swale Stockholding Ltd", "stockholder"),
    ("Northgate Steelworks", "mill"),
    ("Caledonian Long Products", "mill"),
    ("Sherwood Rolling Mills", "mill"),
    ("Cumbria Plate Mill Ltd", "mill"),
]
OTHER_SUPPLIERS = [
    ("Humber Fasteners Ltd", "consumables"),
    ("Pennine Bolt & Nut", "consumables"),
    ("Kirkstall Fixings", "consumables"),
    ("Yorkshire Welding Supplies", "consumables"),
    ("Northern Gas & Weld", "consumables"),
    ("Tees Abrasives Ltd", "consumables"),
    ("Dales Industrial Supplies", "consumables"),
    ("Ouse Coatings Ltd", "paint"),
    ("Pennine Protective Coatings", "paint"),
    ("Northshield Paints", "paint"),
    ("Beacon Coatings Ltd", "paint"),
    ("Calder Galvanising", "galvanising"),
    ("Humber Galvanizers Ltd", "galvanising"),
    ("Aire Valley Galv Ltd", "galvanising"),
    ("Tees Hot Dip Ltd", "galvanising"),
    ("Trent Galvanising", "galvanising"),
    ("Denton Steel Erectors", "erection"),
    ("Ridings Site Services", "erection"),
    ("Northern Erection Services", "erection"),
    ("Pennine NDT Ltd", "inspection"),
    ("Kestrel Profiling Ltd", "profiling"),
    ("Lune Laser Cutting", "profiling"),
    ("Wharfe Fabrications", "subcontract"),
    ("Craven Crane Hire", "plant"),
    ("Dales Plant Hire Ltd", "plant"),
    ("Aire Access Platforms", "plant"),
    ("Ouse Lifting Ltd", "plant"),
    ("Tees Plant Ltd", "plant"),
    ("Ridings Haulage", "transport"),
    ("Pennine Transport Ltd", "transport"),
    ("Humber Heavy Haulage", "transport"),
    ("Calder Logistics", "transport"),
    ("Northern Freight Ltd", "transport"),
    ("Kingsmead Office Supplies", "overhead"),
    ("Wharfe Valley Facilities", "overhead"),
    ("Brackley Insurance Brokers", "overhead"),
    ("Holbeck IT Services", "overhead"),
    ("Greyfriars Training Ltd", "overhead"),
    ("Lindsey Waste Management", "overhead"),
    ("Thornbury Utilities", "overhead"),
    ("Ellesmere Vehicle Leasing", "overhead"),
]
# Steel suppliers that exist under three names across the two systems.
# "mrp" entries become separate supplier codes in Corvus; "finance" entries
# become separate supplier accounts in the finance system.
DUPLICATE_SUPPLIERS = {
    "Tyne Steel Stockholders Ltd": {
        "mrp": ["TYNE STEEL STOCKHOLDERS LTD", "TYNE STEEL STOCK"],
        "finance": ["Tyne Steel Stockholders Limited"],
    },
    "Humber Steels": {
        "mrp": ["HUMBER STEELS"],
        "finance": ["Humber Steels Ltd", "Humber Steel Ltd"],
    },
    "Aire Valley Steel Stock": {
        "mrp": ["AIRE VALLEY STEEL STOCK", "AIRE VALLEY STEELS"],
        "finance": ["Aire Valley Steel Stock Ltd"],
    },
    "Northern Hollow Sections": {
        "mrp": ["NORTHERN HOLLOW SECTIONS", "NTH HOLLOW SECT"],
        "finance": ["Northern Hollow Sections Ltd"],
    },
    "Trent Plate & Sections": {
        "mrp": ["TRENT PLATE & SECTIONS"],
        "finance": ["Trent Plate and Sections Ltd", "Trent Plate & Sections"],
    },
    "Calder Metals Ltd": {
        "mrp": ["CALDER METALS LTD", "CALDER METALS"],
        "finance": ["Calder Metals Limited"],
    },
    "Mersey Tube & Section Ltd": {
        "mrp": ["MERSEY TUBE & SECTION LTD", "MERSEY TUBE"],
        "finance": ["Mersey Tube and Section Ltd"],
    },
    "Northgate Steelworks": {
        "mrp": ["NORTHGATE STEELWORKS"],
        "finance": ["Northgate Steelworks Ltd", "Northgate Steel Works"],
    },
}

CUSTOMERS = [
    ("Northgate Telecom Infrastructure Ltd", "telecoms"),
    ("Skyreach Networks Ltd", "telecoms"),
    ("Beacon Mast Services Ltd", "telecoms"),
    ("Aerial Sites UK Ltd", "telecoms"),
    ("Fenwick Communications plc", "telecoms"),
    ("Highland Mast & Tower Ltd", "telecoms"),
    ("Orbital Wireless Infrastructure", "telecoms"),
    ("Pendle Networks Ltd", "telecoms"),
    ("Meridian Telecom Build Ltd", "telecoms"),
    ("Pennine Rail Alliance", "rail"),
    ("Trent Valley Infrastructure Ltd", "rail"),
    ("Northern Route Partners", "rail"),
    ("Caledonian Rail Engineering Ltd", "rail"),
    ("Severn Rail Projects Ltd", "rail"),
    ("Eastway Civils Ltd", "rail"),
    ("Midland Track & Structures", "rail"),
    ("Westgate Rail Ltd", "rail"),
    ("Meridian Construction plc", "stadium"),
    ("Ashcroft Build Ltd", "stadium"),
    ("Harland & Cole Construction", "stadium"),
    ("Kestrel Main Contractors Ltd", "stadium"),
    ("Bramhall Group plc", "stadium"),
    ("Lowther Construction Ltd", "structural"),
    ("Oakridge Developments", "structural"),
    ("Stanmore Build Ltd", "structural"),
    ("Calder Engineering Ltd", "structural"),
    ("Ridley Structures", "structural"),
    ("Harborough Industrial Ltd", "structural"),
    ("Whitmore Warehousing plc", "structural"),
    ("Brackley Logistics Parks", "structural"),
    ("Denton Steel Erectors", "structural"),
    ("Thornbury Estates Ltd", "structural"),
    ("Lindsey Energy Services", "structural"),
    ("Kingsmead Retail Developments", "structural"),
    ("Fairfield Architectural Ltd", "architectural"),
    ("Marlow Facades Ltd", "architectural"),
    ("Greyfriars Property Group", "architectural"),
    ("Holbeck Developments Ltd", "architectural"),
    ("Wharfe Valley Homes", "architectural"),
    ("Ellesmere Interiors Ltd", "architectural"),
]

PLACES = [
    "Skipton", "Otley", "Hexham", "Penrith", "Kendal", "Barnsley", "Goole", "Selby",
    "Malton", "Whitby", "Ripon", "Thirsk", "Consett", "Alnwick", "Morpeth", "Buxton",
    "Matlock", "Louth", "Grantham", "Newark", "Retford", "Worksop", "Ilkley", "Keighley",
    "Settle", "Brough", "Beverley", "Driffield", "Pocklington", "Tadcaster", "Wetherby",
    "Harrogate", "Knaresborough", "Pickering", "Helmsley", "Richmond", "Bedale", "Leyburn",
    "Northallerton", "Guisborough", "Saltburn", "Redcar", "Stokesley", "Yarm", "Barnard Castle",
]

SECTORS = {
    "telecoms": {
        "projects": ["{p} 30m lattice tower", "{p} 25m monopole", "{p} rooftop headframe",
                     "{p} 45m guyed mast", "{p} shared site tower replacement"],
        "kinds": ["L", "L", "CHS", "SHS", "PLATE", "FLAT", "RHS"],
        "marks": ["LEG-1", "LEG-2", "LEG-3", "BRACE-A", "BRACE-B", "HEADFRAME", "LADDER",
                  "PLATFORM-1", "ANT-MOUNT", "BASE-GRILLAGE", "CLIMB-RAIL"],
        "wos": (3, 8), "rate_per_t": (3600, 4800),
    },
    "rail": {
        "projects": ["{p} station footbridge", "{p} platform canopy", "{p} OLE gantry portals",
                     "{p} underbridge strengthening", "{p} lift shaft steelwork"],
        "kinds": ["UB", "UB", "UC", "PFC", "PLATE", "SHS", "CHS"],
        "marks": ["TRUSS-01", "TRUSS-02", "DECK-1", "DECK-2", "STAIR-N", "STAIR-S", "CANOPY-COL",
                  "CANOPY-RAFTER", "PARAPET", "LIFT-FRAME", "LANDING"],
        "wos": (4, 10), "rate_per_t": (3800, 5200),
    },
    "stadium": {
        "projects": ["{p} Community Stadium east stand", "{p} Arena north terrace roof",
                     "{p} Park west stand trusses", "{p} training ground grandstand"],
        "kinds": ["UB", "CHS", "CHS", "RHS", "PLATE", "UC", "SHS"],
        "marks": ["TRUSS-A", "TRUSS-B", "TRUSS-C", "RAKER-1", "RAKER-2", "RAKER-3", "PURLIN-RUN",
                  "CRUSH-BARRIER", "VOMITORY", "ROOF-TIE", "GABLE-FRAME", "FLOODLIGHT-MAST"],
        "wos": (6, 14), "rate_per_t": (3200, 4200),
    },
    "structural": {
        "projects": ["{p} distribution centre portal frames", "{p} mezzanine floor",
                     "{p} industrial unit phase 2", "{p} boiler house steelwork",
                     "{p} substation gantries", "{p} car park deck"],
        "kinds": ["UB", "UB", "UC", "PFC", "PLATE", "RHS", "L"],
        "marks": ["B01", "B02", "B03", "B04", "C01", "C02", "C03", "MEZZ-BEAM", "PURLIN-RUN",
                  "STAIR-1", "BRACING-GRID-A", "CRANE-BEAM"],
        "wos": (3, 9), "rate_per_t": (2600, 3400),
    },
    "architectural": {
        "projects": ["{p} feature staircase", "{p} atrium balustrade", "{p} entrance canopy",
                     "{p} brise soleil frames"],
        "kinds": ["SHS", "RHS", "FLAT", "PLATE", "CHS", "PFC"],
        "marks": ["STAIR-1", "STAIR-2", "BALUSTRADE", "HANDRAIL", "CANOPY", "LANDING", "SCREEN"],
        "wos": (2, 5), "rate_per_t": (5500, 8000),
    },
}
SECTOR_WEIGHTS = [("structural", 35), ("telecoms", 25), ("rail", 15), ("architectural", 15),
                  ("stadium", 10)]

WO_DESCRIPTIONS = ["MAIN MEMBER {m}", "{m} ASSEMBLY", "{m} FABRICATION", "{m} C/W CLEATS",
                   "{m} GALV FINISH", "{m} PAINTED FINISH", "{m} AS DRG REV {r}"]

OPERATIONS = ["SAW", "DRILL", "FIT", "WELD", "BLAST", "PAINT", "LOAD"]
OPERATION_SHARE = {"SAW": 8, "DRILL": 6, "FIT": 22, "WELD": 38, "BLAST": 6, "PAINT": 12, "LOAD": 8}
OPS_OPERATION_FORMS = {
    "SAW": ["Saw", "saw", "Cutting", "SAW", "sawing"],
    "DRILL": ["Drill", "drilling", "DRILL", "Drill"],
    "FIT": ["Fit", "fit-up", "Fitting", "FIT", "Fiting"],
    "WELD": ["Weld", "welding", "WELD", "Welding", "Weldng"],
    "BLAST": ["Blast", "shot blast", "BLAST", "Blasting"],
    "PAINT": ["Paint", "painting", "PAINT", "Painting"],
    "LOAD": ["Load", "loading", "Despatch", "LOAD"],
}
OPERATORS = {
    "WKF": ["D Ackroyd", "S Barraclough", "M Kowalski", "J Firth", "A Hussain", "P Sugden",
            "R Illingworth", "K Nowak", "L Ambler", "T Pickles", "G Haigh", "C Brook",
            "N Dyson", "W Lumb", "B Crowther", "F Oduya", "H Speight", "E Rhodes"],
    "TEE": ["J Dobson", "A Mahmood", "P Robson", "S Wilkinson", "M Nowicki", "C Hutton",
            "L Gibson", "R Peacock", "D Coulson", "K Armstrong", "T Bainbridge", "G Elliott",
            "B Ridley", "N Fenwick", "H Lowes", "O Adeyemi", "W Hepple", "E Storey"],
}
OPS_WO_FORMS = ["WO {n}", "wo-{n}", "{n}", "{n} (rev B)", "WO{n}", "{n}"]
NCR_CATEGORIES = [
    ("Wrong drawing revision", 18, "Fabricated to rev {r} drawing, rev {r2} issued"),
    ("Missing mill certificate", 14, "No 3.1 cert traceable for heat on {mark}"),
    ("Weld defect", 22, "Undercut / porosity on {mark} fillet welds, MPI fail"),
    ("Dimensional error", 20, "{mark} hole pitch out by {mm}mm, does not fit"),
    ("Damage in transit", 6, "{mark} flange bent on unloading"),
    ("Galvanising defect", 10, "Bare patches / dross on {mark} after galv"),
    ("Missing fittings", 10, "Bolts / cleats not supplied with {mark}"),
]
VEHICLE_FORMS = ["{reg}", "{reg}", "{reg}", "artic", "rigid", "Ridings artic", "{reg} (Pennine)"]


# --------------------------------------------------------------------------- #
# Formatting helpers for each system's conventions
# --------------------------------------------------------------------------- #

def fmt_mrp(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def fmt_fin(d: date | None) -> str:
    return d.isoformat() if d else ""


OPS_DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%b-%y"]
BOOKING_COLUMNS = ["booking_id", "operator", "works_order", "operation", "hours", "booking_date", "site"]


def fmt_ops(rng: random.Random, d: date | None) -> str:
    if d is None:
        return ""
    return d.strftime(rng.choice(OPS_DATE_FORMATS))


def pad(text: str, width: int) -> str:
    """Corvus exports fixed-width fields, so text carries trailing spaces."""
    return text.ljust(width)


def fin_amount(rng: random.Random, value: float, text_share: float = 0.3) -> str:
    """Finance exports some amounts as text with thousands separators."""
    if rng.random() < text_share:
        return f"{value:,.2f}"
    return f"{value:.2f}"


def ops_hours(rng: random.Random, hours: float) -> str:
    form = rng.random()
    if form < 0.6:
        return f"{hours:g}"
    if form < 0.85:
        return f"{hours:.2f}"
    if form < 0.95:
        return f"{hours:.1f} "
    return f" {hours:g}"


def rand_date(rng: random.Random, a: date, b: date) -> date:
    if b < a:
        b = a
    return a + timedelta(days=rng.randint(0, (b - a).days))


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def customer_ops_forms(name: str) -> list[str]:
    stripped = name
    for suffix in (" Ltd", " plc", " Group", " Limited"):
        stripped = stripped.replace(suffix, "")
    words = stripped.split()
    return [name, stripped, " ".join(words[:2]), words[0].upper(), stripped.lower()]


def job_ops_form(rng: random.Random, job_no: str) -> str:
    """Ops writes J-24-0871 as J-24-0871, J24-0871, 24-0871, j-24-0871 or J-24-871."""
    _, yy, seq = job_no.split("-")
    return rng.choice([job_no, job_no, f"J{yy}-{seq}", f"{yy}-{seq}", job_no.lower(),
                       f"J-{yy}-{int(seq)}"])


def finance_job_code(job_no: str) -> str:
    """Finance stores J-24-0871 as 24871: two-digit year plus the sequence without zeros."""
    _, yy, seq = job_no.split("-")
    return f"{yy}{int(seq)}"


# --------------------------------------------------------------------------- #
# Entities
# --------------------------------------------------------------------------- #

@dataclass
class Material:
    kind: str
    desig: str
    grade: str
    unit_weight: float  # kg/m for sections, kg/m2 for plate
    price_per_tonne: float
    drift: bool = False
    uom_conflict: bool = False

    @property
    def is_plate(self) -> bool:
        return self.kind == "PLATE"

    @property
    def code(self) -> str:
        if self.is_plate:
            return f"PLT{self.desig}-{self.grade}"
        return f"{self.kind}{self.desig.upper()}-{self.grade}"

    def code_variants(self) -> list[str]:
        if self.is_plate:
            return [self.code, f"PLATE{self.desig}", f"PL{self.desig}MM"]
        return [self.code, f"{self.kind}{self.desig.upper()}", f"{self.desig.upper()}{self.kind}"]

    def desc_variants(self) -> list[str]:
        k, d, g = self.kind, self.desig, self.grade
        if self.is_plate:
            return [f"PLATE {d}mm {g}", f"PLT{d}", f"{d}mm PLATE", f"PLATE {d}MM {g}"]
        return [f"{k} {d} {g}", f"{k}{d.upper()}", f"{d}{k}", f"{LONG_KIND[k]} {d.upper()}"]

    @property
    def mrp_description(self) -> str:
        return self.desc_variants()[0].upper()

    def uom_for(self, context: str) -> str:
        if self.is_plate:
            return "KG"
        if self.uom_conflict:
            return {"bom": "M", "stock": "EA", "po": "KG", "grn": "KG"}[context]
        return "M"

    def convert(self, qty_base: float, uom: str) -> float:
        """Convert a base quantity (metres, or kg for plate) to the given UoM."""
        if self.is_plate or uom == "M":
            return qty_base
        if uom == "KG":
            return qty_base * self.unit_weight
        if uom == "EA":
            return float(math.ceil(qty_base / BAR_LENGTH_M))
        raise ValueError(uom)

    def price_per(self, uom: str) -> float:
        per_kg = self.price_per_tonne / 1000.0
        if uom == "KG":
            return per_kg
        if uom == "M":
            return per_kg * self.unit_weight
        if uom == "EA":
            return per_kg * self.unit_weight * BAR_LENGTH_M
        raise ValueError(uom)


@dataclass
class Supplier:
    name: str
    category: str
    mrp_codes: list[tuple[str, str]] = field(default_factory=list)  # (code, name as typed)
    fin_accounts: list[tuple[str, str]] = field(default_factory=list)  # (account, name)
    invoice_style: str = "INV-{n:05d}"
    invoice_counter: int = 0

    @property
    def is_steel(self) -> bool:
        return self.category in ("stockholder", "hollow", "mill")


@dataclass
class Customer:
    name: str
    sector: str
    account: str
    ref_style: str


@dataclass
class Job:
    job_no: str
    customer: Customer
    sector: str
    project: str
    site: str
    start: date
    end: date
    customer_ref: str
    finance_only: bool = False
    labour_factor: float = 1.0
    wos: list[WorksOrder] = field(default_factory=list)

    @property
    def finance_code(self) -> str:
        return finance_job_code(self.job_no)

    @property
    def tonnage(self) -> float:
        return sum(w.tonnage for w in self.wos)


@dataclass
class WorksOrder:
    wo_no: int
    job: Job
    part_code: str
    description: str
    qty: int
    planned_hours: float
    planned_start: date
    planned_finish: date
    actual_finish: date | None
    status: str
    site: str
    lines: list[BomLine] = field(default_factory=list)
    actual_hours: float = 0.0

    @property
    def tonnage(self) -> float:
        return sum(line.weight_kg for line in self.lines) / 1000.0


@dataclass
class BomLine:
    wo: WorksOrder
    line_no: int
    material: Material
    code_as_written: str
    desc_as_written: str
    length_mm: int
    qty: float  # in the BOM UoM
    uom: str
    qty_base: float  # metres, or kg for plate

    @property
    def weight_kg(self) -> float:
        if self.material.is_plate:
            return self.qty_base
        return self.qty_base * self.material.unit_weight


@dataclass
class PurchaseOrder:
    po_no: str
    supplier: Supplier
    mrp_code: str
    mrp_name: str
    material: Material
    code_as_written: str
    qty_base: float
    uom: str
    qty: float
    unit_price: float
    order_date: date
    promised_date: date
    job: Job

    @property
    def value(self) -> float:
        return self.qty * self.unit_price


@dataclass
class GoodsReceipt:
    grn_no: str
    po: PurchaseOrder
    qty_base: float
    uom: str
    qty: float
    received_date: date
    heat_number: str
    mill_cert_ref: str


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #

class SourceGenerator:
    """Builds the three source exports from one seeded random stream."""

    def __init__(self, seed: int = DEFAULT_SEED) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.manifest: dict = {"seed": seed, "as_of": AS_OF.isoformat(),
                               "history_start": START.isoformat(), "defects": {}}
        self.counts: dict[str, int] = {}

    # ---- reference data ------------------------------------------------- #

    def build_materials(self) -> list[Material]:
        rng = self.rng
        materials: list[Material] = []
        for kind, desig, weight, grades in SECTION_CATALOGUE:
            for grade in grades:
                base = GRADE_PRICE_PER_TONNE[grade]
                if kind in ("SHS", "RHS", "CHS"):
                    base += 160
                if kind == "PLATE":
                    base -= 90
                materials.append(Material(kind, desig, grade, weight,
                                          round(base * rng.uniform(0.93, 1.08), 2)))
        structural = [m for m in materials if not m.is_plate]
        for m in rng.sample(structural, 16) + rng.sample([m for m in materials if m.is_plate], 2):
            m.drift = True
        for m in rng.sample(structural, 14):
            m.uom_conflict = True
        return materials

    def build_suppliers(self) -> list[Supplier]:
        rng = self.rng
        suppliers: list[Supplier] = []
        mrp_code_no = 7
        used_accounts: dict[str, int] = defaultdict(int)

        def next_account(name: str) -> str:
            stem = "".join(ch for ch in name.upper() if ch.isalpha())[:3]
            used_accounts[stem] += 1
            return f"{stem}{used_accounts[stem]:03d}"

        for index, (name, category) in enumerate(STEEL_SUPPLIERS + OTHER_SUPPLIERS):
            s = Supplier(name, category)
            s.invoice_style = rng.choice(["INV-{n:05d}", "{n:06d}", "SI{n:06d}", "{n:05d}/A"])
            # Each supplier numbers its own invoices; ranges are kept apart so the
            # number alone identifies an invoice in the finance export.
            s.invoice_counter = 100_000 * (index + 1) + rng.randint(0, 20_000)
            variants = DUPLICATE_SUPPLIERS.get(name)
            mrp_names = variants["mrp"] if variants else [name.upper()]
            fin_names = variants["finance"] if variants else [name]
            if s.is_steel:
                for typed in mrp_names:
                    mrp_code_no += rng.randint(1, 9)
                    s.mrp_codes.append((f"S{mrp_code_no:04d}", typed))
            for fin_name in fin_names:
                s.fin_accounts.append((next_account(fin_name), fin_name))
            suppliers.append(s)
        return suppliers

    def build_customers(self) -> list[Customer]:
        rng = self.rng
        customers = []
        used: dict[str, int] = defaultdict(int)
        for name, sector in CUSTOMERS:
            stem = "".join(ch for ch in name.upper() if ch.isalpha())[:3]
            used[stem] += 1
            style = rng.choice(["PO{n:06d}", "{stem}/{yy}/{n:03d}", "ORD-{n:05d}", "{n:07d}"])
            customers.append(Customer(name, sector, f"{stem}{used[stem]:03d}", style))
        return customers

    # ---- jobs and works orders ----------------------------------------- #

    def build_jobs(self, customers: list[Customer]) -> list[Job]:
        rng = self.rng
        jobs: list[Job] = []
        by_sector: dict[str, list[Customer]] = defaultdict(list)
        for c in customers:
            by_sector[c.sector].append(c)
        sectors = [s for s, w in SECTOR_WEIGHTS for _ in range(w)]
        starts = sorted(rand_date(rng, START, AS_OF - timedelta(days=75)) for _ in range(150))
        counters = {2024: 850, 2025: 100, 2026: 100}
        for start in starts:
            sector = rng.choice(sectors)
            customer = rng.choice(by_sector[sector])
            counters[start.year] += 1
            job_no = f"J-{start.year % 100:02d}-{counters[start.year]:04d}"
            stem = "".join(ch for ch in customer.name.upper() if ch.isalpha())[:3]
            ref = customer.ref_style.format(n=rng.randint(100, 999999), stem=stem,
                                            yy=start.year % 100)
            end = start + timedelta(days=rng.randint(60, 240))
            jobs.append(Job(job_no, customer, sector,
                            rng.choice(SECTORS[sector]["projects"]).format(p=rng.choice(PLACES)),
                            rng.choice(SITES)[0], start, end, ref))
        # Legacy jobs that only finance still knows about: closed in the MRPII
        # archive but still carrying retention releases and late invoices.
        for _ in range(20):
            yy = rng.choice([23, 23, 24])
            seq = rng.randint(620, 849) if yy == 24 else rng.randint(700, 990)
            customer = rng.choice(customers)
            start = rand_date(rng, START, AS_OF - timedelta(days=120))
            jobs.append(Job(f"J-{yy}-{seq:04d}", customer, customer.sector,
                            rng.choice(SECTORS[customer.sector]["projects"]).format(
                                p=rng.choice(PLACES)),
                            rng.choice(SITES)[0], start, start + timedelta(days=150),
                            "", finance_only=True))
        return jobs

    def build_works_orders(self, jobs: list[Job], materials: list[Material]) -> list[WorksOrder]:
        rng = self.rng
        wos: list[WorksOrder] = []
        wo_no = 10000
        by_kind: dict[str, list[Material]] = defaultdict(list)
        for m in materials:
            by_kind[m.kind].append(m)
        for job in sorted((j for j in jobs if not j.finance_only), key=lambda j: j.start):
            spec = SECTORS[job.sector]
            marks = list(spec["marks"])
            rng.shuffle(marks)
            n = rng.randint(*spec["wos"])
            for i in range(n):
                wo_no += 1
                mark = marks[i % len(marks)] + ("" if i < len(marks) else f"-{i // len(marks) + 1}")
                p_start = job.start + timedelta(days=int((job.end - job.start).days * rng.uniform(0, 0.7)))
                p_finish = min(p_start + timedelta(days=rng.randint(7, 45)), job.end)
                wo = WorksOrder(
                    wo_no, job, mark,
                    rng.choice(WO_DESCRIPTIONS).format(m=mark, r=rng.choice("ABCD")),
                    rng.choice([1, 1, 1, 1, 2, 2, 3, 4, 6]), 0.0, p_start, p_finish, None, "", job.site)
                wo.lines = self.build_bom(wo, spec["kinds"], by_kind)
                hours_per_tonne = rng.uniform(10, 22)
                if job.sector == "architectural":
                    hours_per_tonne *= 1.8
                elif job.sector == "telecoms":
                    hours_per_tonne *= 1.4
                wo.planned_hours = round(max(8.0, wo.tonnage * hours_per_tonne), 1)
                self.assign_status(wo)
                job.wos.append(wo)
                wos.append(wo)
        return wos

    def assign_status(self, wo: WorksOrder) -> None:
        rng = self.rng
        if wo.planned_start > AS_OF:
            wo.status = "PLANNED"
            return
        if rng.random() < 0.02:
            wo.status = "CANCELLED"
            return
        if wo.planned_finish + timedelta(days=30) < AS_OF:
            roll = rng.random()
            if roll < 0.9:
                slip = rng.choice([-4, -2, 0, 0, 1, 3, 5, 8, 12, 20, 28])
                wo.actual_finish = min(wo.planned_finish + timedelta(days=slip), AS_OF)
                wo.status = "CLOSED" if rng.random() < 0.8 else "COMPLETE"
            else:
                wo.status = "OPEN"  # overdue and never closed off
        else:
            if wo.planned_finish <= AS_OF and rng.random() < 0.5:
                wo.actual_finish = wo.planned_finish + timedelta(days=rng.randint(0, 6))
                wo.status = "COMPLETE"
            else:
                wo.status = "RELEASED" if wo.planned_start <= AS_OF else "OPEN"

    def build_bom(self, wo: WorksOrder, kinds: list[str],
                  by_kind: dict[str, list[Material]]) -> list[BomLine]:
        rng = self.rng
        lines: list[BomLine] = []
        n = rng.randint(3, 11)
        for line_no in range(1, n + 1):
            material = rng.choice(by_kind[rng.choice(kinds)])
            uom = material.uom_for("bom")
            if material.is_plate:
                length = rng.choice([1500, 2000, 2500, 3000, 6000])
                qty_base = round(rng.uniform(15, 250) * wo.qty, 1)
                qty = qty_base
            else:
                length = rng.choice([1200, 2400, 3000, 4500, 6000, 7500, 9000, 12000])
                pieces = rng.randint(1, 3) * wo.qty
                qty_base = round(length / 1000.0 * pieces, 2)
                qty = qty_base
            code, desc = material.code, material.mrp_description
            if material.drift and rng.random() < 0.45:
                code = rng.choice(material.code_variants()[1:])
                desc = rng.choice(material.desc_variants())
            lines.append(BomLine(wo, line_no, material, code, desc, length, qty, uom, qty_base))
        return lines

    # ---- purchasing ----------------------------------------------------- #

    def build_purchasing(self, wos: list[WorksOrder], materials: list[Material],
                         suppliers: list[Supplier]) -> tuple[list[PurchaseOrder], list[GoodsReceipt]]:
        rng = self.rng
        demand: dict[tuple[str, str], list[BomLine]] = defaultdict(list)
        for wo in wos:
            if wo.status == "CANCELLED":
                continue
            for line in wo.lines:
                demand[(month_key(wo.planned_start), line.material.code)].append(line)
        stockholders = [s for s in suppliers if s.category == "stockholder"]
        hollow = [s for s in suppliers if s.category == "hollow"]
        mills = [s for s in suppliers if s.category == "mill"]
        by_code = {m.code: m for m in materials}
        pos: list[PurchaseOrder] = []
        po_no = 402_113
        for (month, code), lines in sorted(demand.items()):
            material = by_code[code]
            qty_base = sum(line.qty_base for line in lines) * rng.uniform(1.05, 1.3)
            if material.kind in ("SHS", "RHS", "CHS") and rng.random() < 0.7:
                supplier = rng.choice(hollow)
            elif qty_base > 800 and rng.random() < 0.4:
                supplier = rng.choice(mills)
            else:
                supplier = rng.choice(stockholders)
            mrp_code, mrp_name = rng.choice(supplier.mrp_codes)
            uom = material.uom_for("po")
            qty = round(material.convert(qty_base, uom), 1)
            price = round(material.price_per(uom) * rng.uniform(0.96, 1.06), 2)
            month_start = date(int(month[:4]), int(month[5:]), 1)
            order_date = month_start - timedelta(days=rng.randint(10, 35))
            promised = order_date + timedelta(days=rng.randint(12, 35))
            # Attribute the PO to the job that drives most of the demand.
            job_demand: dict[str, float] = defaultdict(float)
            job_lookup = {}
            for line in lines:
                job_demand[line.wo.job.job_no] += line.qty_base
                job_lookup[line.wo.job.job_no] = line.wo.job
            top_job = job_lookup[max(sorted(job_demand), key=lambda j: job_demand[j])]
            po_no += rng.randint(1, 4)
            written = material.code
            if material.drift and rng.random() < 0.35:
                written = rng.choice(material.code_variants()[1:])
            pos.append(PurchaseOrder(f"PO{po_no}", supplier, mrp_code, mrp_name, material, written,
                                     qty_base, uom, qty, price, order_date, promised, top_job))

        grns: list[GoodsReceipt] = []
        grn_no = 88_410
        po_without_grn: list[str] = []
        for po in pos:
            if po.promised_date > AS_OF - timedelta(days=5):
                continue  # not yet due, legitimately no receipt
            if rng.random() < 0.07:
                po_without_grn.append(po.po_no)
                continue
            uom = po.material.uom_for("grn")
            received_base = po.qty_base * rng.choice([1.0, 1.0, 1.0, 0.98, 0.95, 0.9])
            qty = round(po.material.convert(received_base, uom), 1)
            received = po.promised_date + timedelta(days=rng.choice([-3, -1, 0, 0, 1, 2, 4, 7, 12]))
            grn_no += rng.randint(1, 3)
            heat = rng.choice([f"H{rng.randint(100000, 999999)}", f"{rng.randint(24, 26)}A{rng.randint(1000, 9999)}",
                               f"{rng.randint(300000, 899999)}"])
            cert = f"MC/{received.year}/{rng.randint(1000, 99999):05d}"
            grns.append(GoodsReceipt(f"GRN{grn_no}", po, received_base, uom, qty, received, heat, cert))
        # Traceability gaps: about 18% of receipts lack a heat number or mill certificate.
        gaps = rng.sample(grns, int(round(len(grns) * 0.18)))
        gap_ids = []
        for g in gaps:
            roll = rng.random()
            if roll < 0.45:
                g.heat_number = ""
            elif roll < 0.85:
                g.mill_cert_ref = ""
            else:
                g.heat_number = ""
                g.mill_cert_ref = ""
            gap_ids.append(g.grn_no)
        self.manifest["defects"]["6_traceability_gaps"] = {
            "file": "corvus_mrp/goods_received.csv",
            "grn_missing_heat_or_cert": sorted(gap_ids),
            "count": len(gap_ids), "total_grns": len(grns),
            "share": round(len(gap_ids) / len(grns), 3),
        }
        self.manifest["defects"]["5_three_way_match"] = {
            "po_without_grn": po_without_grn,
        }
        return pos, grns

    # ---- shop floor ----------------------------------------------------- #

    def build_bookings(self, wos: list[WorksOrder]) -> tuple[list[dict], list[int]]:
        rng = self.rng
        bookings: list[dict] = []
        ops_pool = [op for op, w in OPERATION_SHARE.items() for _ in range(w)]
        booking_id = 500_000
        for wo in wos:
            if wo.status in ("PLANNED", "CANCELLED") or wo.planned_start > AS_OF:
                continue
            if wo.status == "OPEN" and wo.actual_finish is None and rng.random() < 0.3:
                continue
            factor = rng.choice([0.78, 0.85, 0.92, 1.0, 1.0, 1.05, 1.12, 1.2, 1.3, 1.45])
            total = wo.planned_hours * factor
            wo.actual_hours = round(total, 1)
            window_end = wo.actual_finish or min(wo.planned_finish + timedelta(days=14), AS_OF)
            remaining = total
            while remaining > 0.4:
                hours = min(remaining, round(rng.choice([2, 3.5, 4, 5, 6, 7.5, 7.5, 8, 8, 9.5]), 2))
                remaining -= hours
                booking_id += 1
                bookings.append({
                    "booking_id": booking_id, "wo": wo.wo_no, "site": wo.site,
                    "operator": rng.choice(OPERATORS[wo.site]),
                    "operation": rng.choice(ops_pool), "hours": hours,
                    "date": rand_date(rng, wo.planned_start, window_end),
                    "job": wo.job,
                })
        # Orphans: works orders in the bookings that Corvus has never heard of.
        # Realistically these are transposed digits of genuine numbers.
        existing = {wo.wo_no for wo in wos}
        orphans: list[int] = []
        candidates = sorted(existing)
        while len(orphans) < 6:
            real = str(rng.choice(candidates))
            i = rng.randint(1, 3)
            swapped = int(real[:i] + real[i + 1] + real[i] + real[i + 2:])
            if swapped not in existing and swapped not in orphans:
                orphans.append(swapped)
        for orphan in orphans:
            site = rng.choice(SITES)[0]
            day = rand_date(rng, START + timedelta(days=30), AS_OF - timedelta(days=30))
            for _ in range(rng.randint(5, 11)):
                booking_id += 1
                bookings.append({
                    "booking_id": booking_id, "wo": orphan, "site": site,
                    "operator": rng.choice(OPERATORS[site]),
                    "operation": rng.choice(ops_pool),
                    "hours": rng.choice([3.5, 4, 6, 7.5, 8]),
                    "date": day + timedelta(days=rng.randint(0, 20)), "job": None,
                })
        bookings.sort(key=lambda b: (b["date"], b["booking_id"]))
        self.manifest["defects"]["10_orphans"] = {
            "file": "shop_floor/time_bookings.csv",
            "works_orders_in_bookings_not_in_mrp": sorted(orphans),
            "count": len(orphans),
        }
        return bookings, orphans

    # ---- writers ---------------------------------------------------------- #

    def write_csv(self, path: Path, system: str, columns: list[str], rows: list[list]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            f.write(f"# SYNTHETIC DATA. {system} export generated for the FabSync demonstrator "
                    f"(seed {self.seed}). No real company, person or transaction is represented.\n")
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(columns)
            writer.writerows(rows)
        self.counts[str(path.relative_to(path.parents[1]))] = len(rows)

    def duplicate_rows(self, rows: list[list], share: float) -> int:
        """Copy-and-paste duplicates: a few rows appear twice, back to back."""
        rng = self.rng
        n = max(1, int(round(len(rows) * share)))
        for idx in sorted(rng.sample(range(len(rows)), n), reverse=True):
            rows.insert(idx + 1, list(rows[idx]))
        return n

    def inject_entry_errors(self, booking_rows: list[list], dn_rows: list[list],
                            ncr_rows: list[list]) -> list[dict]:
        """Seed hand-typed values that no parser should accept.

        Uses its own random stream so the rest of the output is unchanged by it.
        Each fault is recorded with the file, the row key and the value typed so
        tests can assert the staging layer quarantines exactly these rows.
        """
        rng = random.Random(self.seed * 7919 + 9)
        faults: list[dict] = []
        next_id = max(int(r[0]) for r in booking_rows) + 1

        def new_booking(column: int, value: str, fault: str) -> None:
            nonlocal next_id
            template = list(rng.choice(booking_rows))
            template[0] = next_id
            template[column] = value
            booking_rows.insert(rng.randrange(len(booking_rows)), template)
            faults.append({"file": "shop_floor/time_bookings.csv", "key_column": "booking_id",
                           "key": str(next_id), "column": BOOKING_COLUMNS[column], "value": value,
                           "fault": fault})
            next_id += 1

        for value in ["7,5", "4hrs", "half day", "7.5.", "8 hrs", "3,25"]:
            new_booking(4, value, "unparseable_number")
        for value in ["31/02/2025", "TBC", "w/c 03/03", "2025-13-02", "30-Feb-25"]:
            new_booking(5, value, "invalid_date")
        for _ in range(4):
            new_booking(2, "", "blank_required")
        # Key collisions: a row copied and edited, so the booking id is reused
        # with different hours. The edited copy sits straight after the original.
        seen: set = set()
        for _ in range(3):
            idx = rng.randrange(len(booking_rows) - 1)
            original = booking_rows[idx]
            if original[0] in seen or not str(original[4]).strip():
                continue
            seen.add(original[0])
            edited = list(original)
            edited[4] = f"{float(str(original[4]).strip()) + rng.choice([1, 2, 3.5]):g}"
            booking_rows.insert(idx + 1, edited)
            faults.append({"file": "shop_floor/time_bookings.csv", "key_column": "booking_id",
                           "key": str(original[0]), "column": "booking_id", "value": str(original[0]),
                           "fault": "key_collision"})

        def unique_rows(rows: list[list], column: int) -> list[list]:
            counts: dict = defaultdict(int)
            for r in rows:
                counts[r[0]] += 1
            return [r for r in rows if counts[r[0]] == 1 and str(r[column]).strip()]

        for value in ["ASAP", "TBC", "end of week"]:
            row = rng.choice(unique_rows(dn_rows, 4))
            row[4] = value
            faults.append({"file": "shop_floor/delivery_notes.csv", "key_column": "dn_no", "key": row[0],
                           "column": "promised_date", "value": value, "fault": "invalid_date"})
        for value in ["2.4t", "approx 3"]:
            row = rng.choice(unique_rows(dn_rows, 5))
            row[5] = value
            faults.append({"file": "shop_floor/delivery_notes.csv", "key_column": "dn_no", "key": row[0],
                           "column": "tonnage", "value": value, "fault": "unparseable_number"})
        for value in ["tbc", "n/a", "see QA"]:
            row = rng.choice(unique_rows(ncr_rows, 2))
            row[5] = value
            faults.append({"file": "shop_floor/ncr_log.csv", "key_column": "ncr_no", "key": row[0],
                           "column": "cost_impact", "value": value, "fault": "unparseable_number"})
        row = rng.choice(unique_rows(ncr_rows, 2))
        row[2] = "?"
        faults.append({"file": "shop_floor/ncr_log.csv", "key_column": "ncr_no", "key": row[0],
                       "column": "raised_date", "value": "?", "fault": "invalid_date"})
        return faults

    # ---- main ------------------------------------------------------------- #

    def run(self, out_dir: Path) -> dict:
        rng = self.rng
        materials = self.build_materials()
        suppliers = self.build_suppliers()
        customers = self.build_customers()
        jobs = self.build_jobs(customers)
        wos = self.build_works_orders(jobs, materials)
        pos, grns = self.build_purchasing(wos, materials, suppliers)
        bookings, orphans = self.build_bookings(wos)
        mrp_jobs = [j for j in jobs if not j.finance_only]

        # Labour variance: finance labour cost drifts from booked hours on some jobs.
        variance_jobs = rng.sample(mrp_jobs, 30)
        for job in variance_jobs:
            job.labour_factor = round(rng.choice([rng.uniform(0.5, 0.82), rng.uniform(1.18, 1.65)]), 3)
        for job in mrp_jobs:
            if job.labour_factor == 1.0:
                job.labour_factor = round(rng.uniform(0.985, 1.015), 3)

        mrp_dir, fin_dir, ops_dir = out_dir / "corvus_mrp", out_dir / "finance", out_dir / "shop_floor"

        # ---------------- Corvus MRP ---------------- #
        self.write_csv(mrp_dir / "works_orders.csv", "Corvus MRP",
                       ["wo_no", "job_no", "customer_ref", "part_code", "description", "qty", "uom",
                        "planned_hours", "planned_start", "planned_finish", "actual_finish", "status",
                        "site"],
                       [[wo.wo_no, wo.job.job_no, pad(wo.job.customer_ref, 15), pad(wo.part_code, 15),
                         pad(wo.description, 30), wo.qty, "EA", f"{wo.planned_hours:.1f}",
                         fmt_mrp(wo.planned_start), fmt_mrp(wo.planned_finish),
                         fmt_mrp(wo.actual_finish), pad(wo.status, 10), wo.site] for wo in wos])

        bom_rows = []
        for wo in wos:
            for line in wo.lines:
                bom_rows.append([wo.wo_no, line.line_no, pad(line.code_as_written, 20),
                                 pad(line.desc_as_written, 30), line.material.kind, line.material.grade,
                                 line.length_mm, f"{line.qty:g}", line.uom,
                                 f"{line.material.unit_weight:.2f}"])
        self.write_csv(mrp_dir / "bom_lines.csv", "Corvus MRP",
                       ["wo_no", "line_no", "material_code", "description", "section_type", "grade",
                        "length_mm", "qty", "uom", "unit_weight_kg"], bom_rows)

        stock_rows = []
        stock_variance: list[dict] = []
        stock_legacy: list[dict] = []
        counted_lines: list[tuple] = []
        for m in materials:
            sites = rng.sample([s for s, _ in SITES], rng.choice([1, 2, 2]))
            for site in sites:
                location = "PLATE STORE" if m.is_plate else rng.choice(STOCK_LOCATIONS[:-1])
                uom = m.uom_for("stock")
                on_hand = round(m.convert(rng.uniform(40, 900), uom), 0 if uom == "EA" else 1)
                count_date = rand_date(rng, AS_OF - timedelta(days=120), AS_OF - timedelta(days=3))
                row = [pad(m.code, 20), pad(m.mrp_description, 30), pad(location, 12), site,
                       f"{on_hand:g}", uom, f"{m.price_per(uom):.2f}", fmt_mrp(count_date), f"{on_hand:g}"]
                stock_rows.append(row)
                counted_lines.append((row, on_hand, uom, m.code, site, location))
            if m.drift:
                # A legacy stock record under an old code, migrated in 2006 and never merged.
                legacy_code = m.code_variants()[rng.choice([1, 2])]
                legacy_desc = m.desc_variants()[rng.choice([2, 3])]
                site = sites[0]
                uom = "EA" if not m.is_plate else "KG"
                on_hand = float(rng.randint(1, 14)) if uom == "EA" else round(rng.uniform(80, 600), 1)
                stock_rows.append([pad(legacy_code, 20), pad(legacy_desc, 30), pad("YARD", 12), site,
                                   f"{on_hand:g}", uom, f"{m.price_per(uom):.2f}",
                                   fmt_mrp(rand_date(rng, START, START + timedelta(days=400))),
                                   f"{on_hand:g}"])
                stock_legacy.append({"canonical": m.code, "legacy_code": legacy_code, "site": site})
        # Stock accuracy: the last count disagrees with the book quantity on about 15% of lines.
        for row, on_hand, uom, code, site, location in rng.sample(counted_lines, round(len(counted_lines) * 0.15)):
            delta = max(1.0, on_hand * rng.uniform(0.03, 0.25)) * rng.choice([-1, 1])
            row[8] = f"{max(0.0, round(on_hand + delta, 0 if uom == 'EA' else 1)):g}"
            stock_variance.append({"material_code": code, "site": site, "location": location})
        for code, desc, uom, price in CONSUMABLES:
            for site, _ in SITES:
                on_hand = float(rng.randint(20, 4000))
                stock_rows.append([pad(code, 20), pad(desc, 30), pad("STORES", 12), site, f"{on_hand:g}",
                                   uom, f"{price:.2f}",
                                   fmt_mrp(rand_date(rng, AS_OF - timedelta(days=90), AS_OF)), f"{on_hand:g}"])
        self.write_csv(mrp_dir / "stock.csv", "Corvus MRP",
                       ["material_code", "description", "location", "site", "qty_on_hand", "uom",
                        "unit_cost", "last_count_date", "counted_qty"], stock_rows)

        self.write_csv(mrp_dir / "purchase_orders.csv", "Corvus MRP",
                       ["po_no", "supplier_code", "supplier_name", "material_code", "qty", "uom",
                        "unit_price", "order_date", "promised_date"],
                       [[po.po_no, po.mrp_code, pad(po.mrp_name, 30), pad(po.code_as_written, 20),
                         f"{po.qty:g}", po.uom, f"{po.unit_price:.2f}", fmt_mrp(po.order_date),
                         fmt_mrp(po.promised_date)] for po in pos])

        self.write_csv(mrp_dir / "goods_received.csv", "Corvus MRP",
                       ["grn_no", "po_no", "material_code", "qty_received", "uom", "received_date",
                        "heat_number", "mill_cert_ref"],
                       [[g.grn_no, g.po.po_no, pad(g.po.code_as_written, 20), f"{g.qty:g}", g.uom,
                         fmt_mrp(g.received_date), pad(g.heat_number, 10), pad(g.mill_cert_ref, 14)]
                        for g in grns])

        # ---------------- Finance ---------------- #
        supplier_rows = []
        for s in suppliers:
            for account, name in s.fin_accounts:
                supplier_rows.append([account, name, rng.choice(["30 Days", "30 Days EOM", "60 Days", "45 Days"]),
                                      "EUR" if s.category == "mill" and rng.random() < 0.3 else "GBP"])
        self.write_csv(fin_dir / "supplier_master.csv", "Finance system",
                       ["supplier_account", "supplier_name", "payment_terms", "currency"], supplier_rows)

        purchase_invoices: list[list] = []
        material_cost: dict[tuple[str, str], float] = defaultdict(float)
        subcontract_cost: dict[tuple[str, str], float] = defaultdict(float)
        plant_cost: dict[tuple[str, str], float] = defaultdict(float)
        grn_without_invoice: list[str] = []
        invoice_over_po: list[dict] = []

        def next_invoice(s: Supplier) -> str:
            s.invoice_counter += rng.randint(1, 40)
            return s.invoice_style.format(n=s.invoice_counter)

        for g in grns:
            if rng.random() < 0.08:
                grn_without_invoice.append(g.grn_no)
                continue
            po = g.po
            received_in_po_uom = po.material.convert(g.qty_base, po.uom)
            net = received_in_po_uom * po.unit_price * rng.uniform(0.985, 1.02)
            if rng.random() < 0.05:
                net = po.value * rng.uniform(1.06, 1.28)
            inv_no = next_invoice(po.supplier)
            if net > po.value * 1.05:
                invoice_over_po.append({"invoice_no": inv_no, "po_no": po.po_no,
                                        "po_value": round(po.value, 2), "net_amount": round(net, 2)})
            account, name = rng.choice(po.supplier.fin_accounts)
            inv_date = g.received_date + timedelta(days=rng.randint(3, 30))
            vat = net * VAT_RATE
            purchase_invoices.append([inv_no, account, name, po.po_no, fin_amount(rng, net),
                                      fin_amount(rng, vat), fin_amount(rng, net + vat), fmt_fin(inv_date),
                                      "5000", po.job.finance_code])
            material_cost[(po.job.finance_code, month_key(inv_date))] += net

        subcontractors = [s for s in suppliers if s.category in ("galvanising", "paint", "erection",
                                                                  "profiling", "inspection", "subcontract")]
        plant = [s for s in suppliers if s.category in ("plant", "transport")]
        consumables = [s for s in suppliers if s.category == "consumables"]
        overhead = [s for s in suppliers if s.category == "overhead"]
        nominal_for = {"galvanising": "5100", "paint": "5110", "erection": "5120", "profiling": "5130",
                       "inspection": "5140", "subcontract": "5150", "plant": "5200", "transport": "5300",
                       "consumables": "5010", "overhead": "7000"}
        for job in jobs:
            tonnage = job.tonnage if not job.finance_only else rng.uniform(8, 60)
            window_end = min(job.end + timedelta(days=45), AS_OF)
            for _ in range(rng.randint(1, 4) if not job.finance_only else rng.randint(0, 2)):
                s = rng.choice(subcontractors)
                net = tonnage * rng.uniform(120, 420)
                inv_date = rand_date(rng, job.start + timedelta(days=20), window_end)
                account, name = rng.choice(s.fin_accounts)
                purchase_invoices.append([next_invoice(s), account, name, "", fin_amount(rng, net),
                                          fin_amount(rng, net * VAT_RATE), fin_amount(rng, net * (1 + VAT_RATE)),
                                          fmt_fin(inv_date), nominal_for[s.category], job.finance_code])
                subcontract_cost[(job.finance_code, month_key(inv_date))] += net
            for _ in range(rng.randint(0, 3)):
                s = rng.choice(plant)
                net = rng.uniform(180, 2600)
                inv_date = rand_date(rng, job.start + timedelta(days=10), window_end)
                account, name = rng.choice(s.fin_accounts)
                purchase_invoices.append([next_invoice(s), account, name, "", fin_amount(rng, net),
                                          fin_amount(rng, net * VAT_RATE), fin_amount(rng, net * (1 + VAT_RATE)),
                                          fmt_fin(inv_date), nominal_for[s.category], job.finance_code])
                plant_cost[(job.finance_code, month_key(inv_date))] += net
        for _ in range(260):
            s = rng.choice(consumables + overhead)
            net = rng.uniform(60, 3200)
            inv_date = rand_date(rng, START, AS_OF)
            account, name = rng.choice(s.fin_accounts)
            purchase_invoices.append([next_invoice(s), account, name, "", fin_amount(rng, net),
                                      fin_amount(rng, net * VAT_RATE), fin_amount(rng, net * (1 + VAT_RATE)),
                                      fmt_fin(inv_date), nominal_for[s.category], ""])
        purchase_invoices.sort(key=lambda r: (r[7], r[0]))
        self.write_csv(fin_dir / "purchase_invoices.csv", "Finance system",
                       ["invoice_no", "supplier_account", "supplier_name", "po_reference", "net_amount",
                        "vat", "gross", "invoice_date", "nominal_code", "job_code"], purchase_invoices)

        sales_rows = []
        si_no = 30_150
        for job in jobs:
            if job.finance_only:
                value = rng.uniform(15_000, 180_000)
                n_apps = rng.randint(1, 2)
            else:
                lo, hi = SECTORS[job.sector]["rate_per_t"]
                value = max(job.tonnage, 0.5) * rng.uniform(lo, hi)
                n_apps = rng.randint(2, 5)
            if value < 1:
                continue
            shares = [rng.uniform(0.5, 1.5) for _ in range(n_apps)]
            total_share = sum(shares)
            window_end = min(job.end + timedelta(days=60), AS_OF)
            for i, share in enumerate(shares):
                inv_date = rand_date(rng, job.start + timedelta(days=14 + i * 20), window_end)
                if inv_date > AS_OF:
                    continue
                si_no += rng.randint(1, 3)
                sales_rows.append([job.customer.account, job.customer.name, job.finance_code,
                                   fin_amount(rng, value * share / total_share * 0.95), fmt_fin(inv_date),
                                   f"SI{si_no}"])
        sales_rows.sort(key=lambda r: (r[4], r[5]))
        self.write_csv(fin_dir / "sales_invoices.csv", "Finance system",
                       ["customer_account", "customer_name", "job_code", "net_amount", "invoice_date",
                        "invoice_no"], sales_rows)

        labour_hours: dict[tuple[str, str], float] = defaultdict(float)
        for b in bookings:
            if b["job"] is not None:
                labour_hours[(b["job"].finance_code, month_key(b["date"]))] += b["hours"]
        labour_cost: dict[tuple[str, str], float] = {}
        job_by_code = {j.finance_code: j for j in jobs}
        for key, hours in labour_hours.items():
            labour_cost[key] = hours * LABOUR_RATE * job_by_code[key[0]].labour_factor
        for job in jobs:
            if job.finance_only:
                for _ in range(rng.randint(0, 2)):
                    labour_cost[(job.finance_code, month_key(rand_date(rng, job.start, min(job.end, AS_OF))))] = \
                        rng.uniform(300, 4000)
        cost_rows = []
        for cost_type, table in (("material", material_cost), ("labour", labour_cost),
                                 ("subcontract", subcontract_cost), ("plant", plant_cost)):
            for (code, period), amount in table.items():
                cost_rows.append([code, cost_type, period, fin_amount(rng, amount, 0.35)])
        cost_rows.sort(key=lambda r: (r[0], r[2], r[1]))
        self.write_csv(fin_dir / "job_costs.csv", "Finance system",
                       ["job_code", "cost_type", "period", "amount"], cost_rows)

        # ---------------- Shop floor ---------------- #
        booking_rows = []
        for b in bookings:
            n = b["wo"]
            booking_rows.append([b["booking_id"], b["operator"] if rng.random() > 0.02 else "",
                                 rng.choice(OPS_WO_FORMS).format(n=n),
                                 rng.choice(OPS_OPERATION_FORMS[b["operation"]]) if rng.random() > 0.03 else "",
                                 ops_hours(rng, b["hours"]), fmt_ops(rng, b["date"]),
                                 rng.choice(OPS_SITE_FORMS[b["site"]])])
        dup_bookings = self.duplicate_rows(booking_rows, 0.012)

        dn_rows = []
        dn_no = 7_200
        despatched = [wo for wo in wos if wo.actual_finish is not None]
        for wo in despatched:
            dn_no += rng.randint(1, 2)
            despatch = wo.actual_finish + timedelta(days=rng.choice([0, 0, 1, 2, 3, 5]))
            if despatch > AS_OF:
                continue
            reg = f"{rng.choice('ABCDEFGHKLMNOPRSTVWY')}{rng.choice('ABCDEFGHKLMNOPRSTVWY')}{rng.randint(20, 26)} " \
                  f"{''.join(rng.choice('ABCDEFGHJKLMNOPRSTUVWXYZ') for _ in range(3))}"
            dn_rows.append([f"DN{dn_no}", job_ops_form(rng, wo.job.job_no),
                            rng.choice(customer_ops_forms(wo.job.customer.name)),
                            fmt_ops(rng, despatch), fmt_ops(rng, wo.planned_finish) if rng.random() > 0.04 else "",
                            f"{wo.tonnage:.2f}" if rng.random() > 0.03 else "",
                            rng.choice(VEHICLE_FORMS).format(reg=reg) if rng.random() > 0.05 else ""])
        dup_dns = self.duplicate_rows(dn_rows, 0.01)

        ncr_rows = []
        ncr_pool = [wo for wo in wos if wo.actual_hours > 0]
        cats = [c for c in NCR_CATEGORIES for _ in range(c[1])]
        ncr_no = 1_040
        for _ in range(250):
            wo = rng.choice(ncr_pool)
            name, _, template = rng.choice(cats)
            raised = rand_date(rng, wo.planned_start, (wo.actual_finish or wo.planned_finish) + timedelta(days=10))
            if raised > AS_OF:
                raised = AS_OF
            closed = raised + timedelta(days=rng.randint(2, 60)) if rng.random() > 0.25 else None
            if closed and closed > AS_OF:
                closed = None
            cost = rng.choice([50, 120, 180, 250, 400, 650, 900, 1400, 2200, 4800]) * rng.uniform(0.8, 1.3)
            cost_text = rng.choice([f"{cost:.0f}", f"{cost:.2f}", f"£{cost:,.0f}", f"{cost:.0f}", ""])
            ncr_no += rng.randint(1, 2)
            ncr_rows.append([f"NCR-{ncr_no}", rng.choice(OPS_WO_FORMS).format(n=wo.wo_no), fmt_ops(rng, raised),
                             name if rng.random() > 0.08 else name.lower(),
                             template.format(r=rng.choice("ABC"), r2=rng.choice("CDE"), mark=wo.part_code,
                                             mm=rng.choice([3, 5, 8, 12, 20])),
                             cost_text, fmt_ops(rng, closed)])
        ncr_rows.sort(key=lambda r: r[0])
        dup_ncrs = self.duplicate_rows(ncr_rows, 0.016)
        entry_errors = self.inject_entry_errors(booking_rows, dn_rows, ncr_rows)
        self.write_csv(ops_dir / "time_bookings.csv", "Shop-floor spreadsheet", BOOKING_COLUMNS, booking_rows)
        self.write_csv(ops_dir / "delivery_notes.csv", "Shop-floor spreadsheet",
                       ["dn_no", "job", "customer", "despatch_date", "promised_date", "tonnage", "vehicle"],
                       dn_rows)
        self.write_csv(ops_dir / "ncr_log.csv", "Shop-floor spreadsheet",
                       ["ncr_no", "works_order", "raised_date", "category", "description", "cost_impact",
                        "closed_date"], ncr_rows)

        booked_by_week: dict[tuple[str, date], float] = defaultdict(float)
        for b in bookings:
            booked_by_week[(b["site"], monday_of(b["date"]))] += b["hours"]
        cap_rows = []
        week = monday_of(START)
        while week <= AS_OF:
            for site, _ in SITES:
                available = SITE_HEADCOUNT[site] * 37.5 * rng.uniform(0.82, 0.97)
                if week.month == 12 and week.day >= 20 or (week.month == 1 and week.day <= 3):
                    available *= 0.35
                booked = booked_by_week.get((site, week), 0.0) * rng.uniform(0.97, 1.03)
                cap_rows.append([fmt_ops(rng, week), rng.choice(OPS_SITE_FORMS[site]), f"{available:.1f}",
                                 f"{booked:.1f}" if rng.random() > 0.03 else ""])
            week += timedelta(days=7)
        self.write_csv(ops_dir / "weekly_capacity.csv", "Shop-floor spreadsheet",
                       ["week_commencing", "site", "available_hours", "booked_hours"], cap_rows)

        # ---------------- Defect manifest ---------------- #
        defects = self.manifest["defects"]
        defects["1_material_code_drift"] = {
            "files": ["corvus_mrp/bom_lines.csv", "corvus_mrp/stock.csv", "corvus_mrp/purchase_orders.csv",
                      "corvus_mrp/goods_received.csv"],
            "materials": {m.code: {"code_variants": m.code_variants(), "description_variants": m.desc_variants()}
                          for m in materials if m.drift},
            "legacy_stock_records": stock_legacy,
            "count": sum(1 for m in materials if m.drift),
        }
        defects["2_supplier_duplicates"] = {
            "files": ["corvus_mrp/purchase_orders.csv", "finance/supplier_master.csv"],
            "suppliers": [{"canonical": s.name,
                           "mrp": [{"code": c, "name": n} for c, n in s.mrp_codes],
                           "finance": [{"account": a, "name": n} for a, n in s.fin_accounts]}
                          for s in suppliers if s.name in DUPLICATE_SUPPLIERS],
            "count": len(DUPLICATE_SUPPLIERS),
        }
        finance_only = sorted(j.finance_code for j in jobs if j.finance_only)
        defects["3_job_code_mapping_gap"] = {
            "files": ["finance/job_costs.csv", "finance/sales_invoices.csv", "corvus_mrp/works_orders.csv"],
            "finance_only_job_codes": finance_only,
            "count": len(finance_only), "total_finance_job_codes": len(jobs),
            "share": round(len(finance_only) / len(jobs), 3),
            "mapping_rule": "finance job_code = two-digit year + MRPII sequence without leading zeros "
                            "(J-24-0871 -> 24871)",
        }
        defects["4_uom_conflicts"] = {
            "files": ["corvus_mrp/bom_lines.csv", "corvus_mrp/stock.csv", "corvus_mrp/purchase_orders.csv",
                      "corvus_mrp/goods_received.csv"],
            "materials": {m.code: {"bom": "M", "stock": "EA", "po": "KG", "grn": "KG",
                                   "bar_length_m": BAR_LENGTH_M, "kg_per_m": m.unit_weight}
                          for m in materials if m.uom_conflict},
            "count": sum(1 for m in materials if m.uom_conflict),
        }
        defects["5_three_way_match"].update({
            "files": ["corvus_mrp/purchase_orders.csv", "corvus_mrp/goods_received.csv",
                      "finance/purchase_invoices.csv"],
            "grn_without_invoice": grn_without_invoice,
            "invoice_over_po_by_more_than_5pct": invoice_over_po,
            "counts": {"po_without_grn": len(defects["5_three_way_match"]["po_without_grn"]),
                       "grn_without_invoice": len(grn_without_invoice),
                       "invoice_over_po": len(invoice_over_po)},
        })
        defects["7_labour_variance"] = {
            "files": ["shop_floor/time_bookings.csv", "finance/job_costs.csv"],
            "labour_rate_per_hour": LABOUR_RATE,
            "jobs": {j.job_no: {"finance_code": j.finance_code, "factor": j.labour_factor}
                     for j in variance_jobs},
            "count": len(variance_jobs),
            "note": "finance labour = booked hours x rate x factor; unlisted jobs sit within 1.5%",
        }
        defects["8_stock_accuracy"] = {
            "file": "corvus_mrp/stock.csv",
            "lines_with_count_variance": stock_variance,
            "count": len(stock_variance),
            "total_counted_lines": len(stock_rows) - len(stock_legacy) - len(CONSUMABLES) * len(SITES),
        }
        defects["9_structural_noise"] = {
            "duplicate_rows": {"shop_floor/time_bookings.csv": dup_bookings,
                               "shop_floor/delivery_notes.csv": dup_dns,
                               "shop_floor/ncr_log.csv": dup_ncrs},
            "trailing_whitespace": "corvus_mrp text fields are space-padded to fixed width",
            "mixed_date_formats": {"shop_floor/*": OPS_DATE_FORMATS},
            "numeric_as_text": {"finance/*": "about 30% of amounts carry thousands separators",
                                "shop_floor/ncr_log.csv": "cost_impact mixes plain numbers, pound signs and blanks",
                                "shop_floor/time_bookings.csv": "hours carry stray spaces and mixed precision"},
            "blank_cells": "shop_floor operator, operation, promised_date, tonnage, vehicle, closed_date",
            "entry_errors": entry_errors,
            "entry_error_count": len(entry_errors),
        }
        self.manifest["row_counts"] = dict(self.counts)
        self.manifest["volumes"] = {
            "jobs_mrp": len(mrp_jobs), "jobs_finance_only": len(finance_only), "works_orders": len(wos),
            "bom_lines": len(bom_rows), "suppliers": len(suppliers), "customers": len(customers),
            "purchase_orders": len(pos), "goods_receipts": len(grns), "time_bookings": len(bookings),
        }
        (out_dir / "defects.json").write_text(json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
                                              encoding="utf-8")
        (out_dir / "DEFECTS.md").write_text(render_defects_md(self.manifest), encoding="utf-8")
        return self.manifest


# --------------------------------------------------------------------------- #
# Narrative defect register
# --------------------------------------------------------------------------- #

def render_defects_md(m: dict) -> str:
    d = m["defects"]
    drift = d["1_material_code_drift"]
    example_code = next(iter(drift["materials"]))
    example = drift["materials"][example_code]
    dup = d["2_supplier_duplicates"]["suppliers"][0]
    twm = d["5_three_way_match"]
    lines = [
        "# Seeded defects register",
        "",
        "**All data in this directory is synthetic.** No real company, person, supplier or",
        "transaction is represented. Generated by `fabsync.ingest.generate_sources` with seed",
        f"`{m['seed']}`; history runs {m['history_start']} to {m['as_of']}.",
        "",
        "Machine-readable detail for every defect, including the exact identifiers affected, is in",
        "`defects.json`. The test suite uses that file to assert each defect is present in the raw",
        "data and, later, that each is detected by the quality and reconciliation stages.",
        "",
        "## Source systems",
        "",
        "| Directory | System | Conventions |",
        "| --- | --- | --- |",
        "| `corvus_mrp/` | Corvus MRP (MRPII, installed 2006) | UPPERCASE, DD/MM/YYYY, fixed-width padding "
        "leaves trailing whitespace, supplier names embedded in POs with no supplier master, UoM EA/M/KG |",
        "| `finance/` | Finance system | Title Case, YYYY-MM-DD, some amounts as text with thousands "
        "separators, job codes as `24871` where MRPII has `J-24-0871` |",
        "| `shop_floor/` | Supervisor spreadsheets | Mixed case, typos, blank cells, three date formats per "
        "column, duplicate rows, works orders as `WO 12345` / `wo-12345` / `12345` / `12345 (rev B)` |",
        "",
        "## Volumes",
        "",
        "| File | Rows |",
        "| --- | --- |",
    ]
    for path, n in sorted(m["row_counts"].items()):
        lines.append(f"| `{path}` | {n:,} |")
    lines += [
        "",
        "## Defects",
        "",
        "### 1. Material code drift",
        "",
        f"{drift['count']} materials are written several ways. Example, {example_code}:",
        "",
        f"- codes: {', '.join('`' + c + '`' for c in example['code_variants'])}",
        f"- descriptions: {', '.join('`' + c + '`' for c in example['description_variants'])}",
        "",
        "About 45% of BOM lines and 35% of POs for these materials use a non-canonical code, and",
        f"{len(drift['legacy_stock_records'])} legacy stock records sit under an old code in the YARD location.",
        "Detect by: normalising kind, dimensions and grade from both code and description, then",
        "counting distinct raw codes per normalised material.",
        "",
        "### 2. Supplier duplicates",
        "",
        f"{d['2_supplier_duplicates']['count']} steel suppliers exist under three name variants and three account",
        f"codes across Corvus purchase orders and the finance supplier master. Example, {dup['canonical']}:",
        "",
    ]
    for entry in dup["mrp"]:
        lines.append(f"- Corvus `{entry['code']}` \"{entry['name']}\"")
    for entry in dup["finance"]:
        lines.append(f"- Finance `{entry['account']}` \"{entry['name']}\"")
    gap = d["3_job_code_mapping_gap"]
    uom = d["4_uom_conflicts"]
    trace = d["6_traceability_gaps"]
    lab = d["7_labour_variance"]
    stock = d["8_stock_accuracy"]
    noise = d["9_structural_noise"]
    orphans = d["10_orphans"]
    lines += [
        "",
        "Detect by: fuzzy matching on normalised names (strip Ltd/Limited/Co, and/&, whitespace).",
        "",
        "### 3. Job code mapping gap",
        "",
        f"{gap['count']} of {gap['total_finance_job_codes']} finance job codes ({gap['share']:.0%}) have no MRPII",
        "job. They are legacy jobs archived out of Corvus but still carrying retention releases and",
        f"late invoices. Mapping rule: {gap['mapping_rule']}.",
        "",
        "### 4. Unit of measure conflicts",
        "",
        f"{uom['count']} sections are transacted in M on BOM lines, EA (12 m bars) in stock, and KG on",
        "purchase orders and goods received. Quantities are consistent once converted with the",
        "kg/m in `defects.json`; naive summing across tables is wrong.",
        "",
        "### 5. Three-way match failures",
        "",
        f"- POs with no goods receipt (past promised date): {twm['counts']['po_without_grn']}",
        f"- Goods receipts with no purchase invoice: {twm['counts']['grn_without_invoice']}",
        f"- Invoices exceeding PO value by more than 5%: {twm['counts']['invoice_over_po']}",
        "",
        "Subcontract, plant and overhead invoices carry no PO reference and are outside the match.",
        "",
        "### 6. Traceability gaps",
        "",
        f"{trace['count']} of {trace['total_grns']} goods receipts ({trace['share']:.0%}) are missing a heat number,",
        "a mill certificate reference, or both. Under EN 1090-2 factory production control every",
        "structural steel receipt must trace to a 3.1 certificate; this is an audit exposure.",
        "",
        "### 7. Labour variance",
        "",
        f"Finance labour cost is booked hours x GBP {lab['labour_rate_per_hour']:.0f}/hour. On {lab['count']} jobs the",
        "finance figure is scaled by a factor between 0.5 and 1.65 and does not reconcile to the",
        "shop-floor time bookings. All other jobs reconcile within 1.5%.",
        "",
        "### 8. Stock accuracy",
        "",
        f"`counted_qty` differs from `qty_on_hand` on {stock['count']} of {stock['total_counted_lines']} "
        "counted stock lines.",
        "",
        "### 9. Structural noise",
        "",
        f"- Duplicate rows: {noise['duplicate_rows']}",
        f"- Trailing whitespace: {noise['trailing_whitespace']}",
        f"- Mixed date formats in shop-floor files: {', '.join(noise['mixed_date_formats']['shop_floor/*'])}",
        f"- Numeric fields stored as text: {noise['numeric_as_text']['finance/*']}",
        f"- Blank cells: {noise['blank_cells']}",
        f"- Hand-typed values no parser should accept: {noise['entry_error_count']} "
        "(unparseable hours, tonnage and costs such as `7,5` and `4hrs`; impossible or placeholder dates such "
        "as `31/02/2025` and `TBC`; blank works orders; booking ids reused on an edited copy). Listed "
        "row by row in `defects.json`; the staging layer must quarantine every one.",
        "",
        "### 10. Orphan works orders",
        "",
        f"{orphans['count']} works orders appear in time bookings but not in Corvus: "
        + ", ".join(str(n) for n in orphans["works_orders_in_bookings_not_in_mrp"]) + ".",
        "They are transposed digits of genuine works order numbers.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def generate(out_dir: Path = DEFAULT_OUT, seed: int = DEFAULT_SEED) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    return SourceGenerator(seed).run(out_dir)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic source system exports.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (data/raw)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    manifest = generate(args.out, args.seed)
    for path, n in sorted(manifest["row_counts"].items()):
        print(f"{n:>8,}  {path}")
    print(f"Defect register: {args.out / 'DEFECTS.md'}")


if __name__ == "__main__":
    main()
