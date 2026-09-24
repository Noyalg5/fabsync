# FabSync project brief

Re-read this file at the start of every session. It is the single source of
project context.

## What FabSync is

FabSync is a systems integration, data governance and management reporting
demonstrator for a UK structural steelwork and architectural metalwork
fabricator. The fictional company fabricates structural steel, telecoms towers
and masts, rail structures and stadium steelwork across two sites. It runs an
ageing MRPII system alongside a separate finance system and shop-floor
operations spreadsheets. The three do not talk to each other, master data has
drifted apart, and management has no single trustworthy view.

The prototype is a two-day demonstration build.

## What it demonstrates, in order

1. **What breaks** when three systems hold overlapping master data.
2. **How to reconcile** them without destroying the originals.
3. **What governance rules** stop it recurring.
4. **What management can finally see** once it is fixed.

## House rules

1. Never mention any AI assistant, AI vendor, CLI tool or model name anywhere:
   not in code, comments, docstrings, documentation, commit messages, file
   names, directory names, or UI text.
2. No co-author or "generated with" trailers in commit messages.
3. All data is synthetic. Every dataset, page and document says so plainly.
4. British English. Use real UK steel fabrication vocabulary: works order,
   goods received note, mill certificate, heat number, EN 1090, section,
   offcut, WIP, OTIF, NCR.
5. Python 3.11+, single repo, runs with one command. Streamlit for the UI,
   DuckDB for the warehouse, pandas for transforms, pytest for tests. No cloud
   services, no API keys, no network calls at runtime.
6. Commit after each mission with a short conventional-commit message.

No file at the repo root is named after an assistant or tool. The single
source of project context is this file.

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/fabsync/generate/` | Synthetic source extracts for the three systems |
| `src/fabsync/ingest/` | Load raw extracts into DuckDB, originals untouched |
| `src/fabsync/match/` | Entity matching across systems |
| `src/fabsync/quality/` | Data quality rules and governance checks |
| `src/fabsync/reconcile/` | Golden records with source lineage |
| `src/fabsync/kpi/` | Management KPIs |
| `app/` | Streamlit demonstrator |
| `config/` | Rules, thresholds, mappings |
| `data/raw/` | Generated source extracts (not committed) |
| `data/warehouse/` | DuckDB file (not committed) |
| `docs/` | This brief, progress log, design notes |
| `tests/` | pytest suite |
| `export/` | Packed demo bundle (not committed) |

Make targets: `generate`, `ingest`, `run-all`, `app`, `pack`, `test`, `clean`.

## The three source systems

| System | Role | Character |
| --- | --- | --- |
| MRPII | Works orders, bills of material, stock, purchasing, routing | Ageing, fixed-width codes, truncated names, its own customer and supplier numbering |
| Finance | Sales ledger, purchase ledger, nominal ledger, invoicing | Separate customer and supplier accounts, different numbering, VAT-driven naming |
| Shop-floor spreadsheets | Daily production logs, weld records, NCRs, despatch notes, per site | Free-text, inconsistent units, copied-and-edited tabs, two sites keeping slightly different layouts |

## Domain glossary

| Term | Meaning |
| --- | --- |
| Works order (WO) | Authorisation to fabricate a defined quantity of assemblies for a contract; the unit of shop-floor planning and costing. |
| Contract | A customer job, typically a building, tower, bridge or stadium package; owns many works orders. |
| Bill of material (BOM) | The list of sections, plate, fittings and consumables needed for an assembly. |
| Section | A rolled steel profile: UB (universal beam), UC (universal column), PFC (parallel flange channel), RHS/SHS/CHS (hollow sections), angle, flat. Specified by designation and mass per metre, e.g. 254x146x31 UB. |
| Plate | Flat steel by thickness and grade, cut to profiles for cleats, baseplates, gussets. |
| Grade | Steel grade to EN 10025, e.g. S275JR, S355J2. |
| Heat number | The steel mill's cast identifier; links a piece of steel to its mill certificate. Must be traceable from stock to finished assembly. |
| Mill certificate | Inspection document (EN 10204 type 3.1) from the mill stating chemistry and mechanical properties for a heat. |
| Goods received note (GRN) | Record that purchased material arrived, was checked and booked to stock, with heat numbers captured. |
| Purchase order (PO) | Order to a stockholder or mill for sections, plate, bolts or consumables. |
| Stockholder | Merchant supplying steel from stock rather than from the mill. |
| Offcut | Usable remainder after cutting a section or plate; should return to stock with its heat number, often does not. |
| Nesting | Arranging cut lengths or plate profiles to minimise offcut and scrap. |
| Assembly mark | Identifier for a fabricated assembly on the erection drawings, e.g. B12, C3A. |
| Piece mark | Identifier for an individual part within an assembly. |
| Drawing revision | Issue level of a fabrication or general arrangement drawing; work to a superseded revision is a classic NCR cause. |
| Fit-up | Positioning and tacking parts before full welding. |
| Weld procedure specification (WPS) | Qualified procedure a welder must follow; welder qualification (EN ISO 9606-1) must match. |
| EN 1090 | Standard for execution of steel and aluminium structures; EN 1090-2 governs structural steel. Factory production control certification is required to UKCA/CE mark structural steelwork. |
| Execution class (EXC) | EXC1 to EXC4 under EN 1090-2; sets inspection and traceability requirements. Telecoms masts and rail structures often sit at EXC3. |
| Inspection and test plan (ITP) | Agreed sequence of inspections and hold points for a contract. |
| Non-conformance report (NCR) | Record of a defect or deviation: wrong revision, missing mill certificate, weld defect, dimensional error. Has a disposition: rework, use-as-is, scrap. |
| Rework | Corrective fabrication after an NCR; consumes hours not planned in the works order. |
| Galvanising | Hot-dip zinc coating, usually subcontracted; a common schedule bottleneck for towers and rail. |
| Shot blast and paint | Surface preparation and coating to a specified system; in-house or subcontract. |
| Work in progress (WIP) | Value of works orders started but not despatched or invoiced; material plus labour plus overhead. |
| Tonnage | Fabricated output by mass; the industry's headline throughput measure. |
| OTIF | On time, in full: proportion of despatches delivered on the agreed date with the full quantity. |
| Despatch note | Record of assemblies loaded and sent to site; links works orders to invoicing. |
| Erection | Site assembly of the fabricated steel, often by a subcontractor. |
| Site | One of the company's two fabrication works. Each keeps its own spreadsheets. |
| Bay | A section of a fabrication shop served by a crane; a scheduling resource. |
| Routing | The sequence of operations (saw, drill, fit, weld, blast, paint) a works order follows. |
| MRPII | Manufacturing resource planning: the legacy system holding works orders, BOMs, stock and purchasing. |
| Nominal ledger | The finance system's general ledger. |
| Sales ledger / purchase ledger | Customer and supplier accounts in the finance system. |
| Application for payment | Interim billing on construction contracts, distinct from a final invoice. |
| Retention | Portion of contract value withheld by the customer until defects period ends. |
| Master data | Reference records shared across systems: customers, suppliers, sections, grades, sites, employees. |
| Golden record | The reconciled, governed version of a master data entity, with lineage back to each source. |
| Lineage | Which source record, field and extract a reconciled value came from. |
| Survivorship | Rules deciding which source wins when values conflict. |
| Data owner / steward | Named accountability for a master data domain and for resolving conflicts. |

## Naming and style

- British English throughout: "programme", "organisation", "centre", "tonne".
- Module and table names are plain English nouns in snake_case.
- Every generated dataset carries a `synthetic = true` marker or equivalent
  note; every UI page and document states that data is synthetic.
