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
| `src/fabsync/ingest/` | Synthetic generator; per-system contracts (`corvus_mrp.py`, `finance.py`, `shop_floor.py`); raw, staging, core, profiling; `pipeline.py` orchestrates |
| `src/fabsync/match/` | Matchers for materials, suppliers, jobs, works orders; `pipeline.py` orchestrates, `report.py` writes the quality report |
| `src/fabsync/quality/` | Declarative data quality engine: `rules.py` loads and validates, `engine.py` runs, `checks.py` holds Python checks, `scorecard.py` reports |
| `src/fabsync/reconcile/` | Four reconciliation engines (three-way match, job cost, stock accuracy, material traceability); `pipeline.py` publishes and verifies |
| `src/fabsync/kpi/` | KPI marts: `sql/` holds the documented views, `build.py` builds and validates, `report.py` writes the data dictionary and KPI report |
| `app/` | Streamlit demonstrator |
| `config/` | `kpis.yaml` KPI definitions and targets; `dq_rules.yaml` the data quality rules; `reconcile.toml` tolerances and targets; `conformance.toml` site and operation aliases; `matching.toml` thresholds, effort assumptions, name standardisation; `section_catalogue.csv` reference masses |
| `data/raw/` | Generated source extracts, one folder per system: `corvus_mrp/`, `finance/`, `shop_floor/`, plus `DEFECTS.md` and `defects.json` (not committed) |
| `data/warehouse/` | `fabsync.duckdb`, rebuilt from empty by `make ingest` (not committed) |
| `docs/` | This brief, progress log, `lineage-and-quarantine.md`, generated `profiling-report.md`, `match-quality-report.md`, `dq-scorecard.md`, `reconciliation-report.md`, `data-dictionary.md` and `kpi-report.md` |
| `tests/` | pytest suite |
| `export/` | Packed demo bundle (not committed) |

Make targets: `generate`, `ingest`, `match`, `quality`, `reconcile`, `kpi`, `run-all`, `app`, `pack`, `test`, `clean`.

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

## Synthetic source generation

`make generate` runs `fabsync.ingest.generate_sources` (seed 1090, 24 months to
2026-08-31) and rebuilds `data/raw/` in about a second. The ten seeded defects
and the exact identifiers they touch are written to `data/raw/defects.json`;
`tests/test_generate_sources.py` asserts each one is present. Later stages must
detect them, and their tests should read the same manifest.

| # | Defect | Where |
| --- | --- | --- |
| 1 | Material code drift, four spellings per section | Corvus BOM, stock, POs, GRNs |
| 2 | Supplier duplicates, three names and three codes | Corvus POs, finance supplier master |
| 3 | Job code mapping gap, ~12% finance-only codes | Finance job costs and sales invoices |
| 4 | UoM conflicts, M / EA / KG for one material | Corvus BOM, stock, POs, GRNs |
| 5 | Three-way match failures | Corvus POs and GRNs, finance purchase invoices |
| 6 | Traceability gaps, ~18% GRNs without heat or cert | Corvus GRNs |
| 7 | Labour variance | Shop-floor time bookings, finance job costs |
| 8 | Stock accuracy, ~15% of lines | Corvus stock |
| 9 | Structural noise | Duplicates, padding, mixed dates, numbers as text |
| 10 | Orphan works orders | Shop-floor time bookings |

## Warehouse, lineage and quarantine

`make ingest` rebuilds the DuckDB warehouse from empty and is idempotent. Full detail, rule catalogue
and example queries: `docs/lineage-and-quarantine.md`.

- **Schemas:** `raw` (as received, all text), `staging` (typed), `core` (conformed and joined),
  `governance` (lineage, quarantine, contracts, rules, profiling, balance, run log).
- **Contracts** are declared per system in code, separately from the data, and materialised in
  `governance.contract`.
- **Lineage is mandatory.** Every transform writes a row to `governance.lineage`: source file,
  rule, rows in, rows out, rows rejected, timestamp, run id. Every staging and core row carries
  `_source_file` and `_source_row`.
- **Quarantine is mandatory.** A row that fails a staging rule goes to `governance.quarantine` with
  the rule, failing column and original values. Nothing is dropped silently or edited in place.
  `governance.table_balance` proves lines in = staged + quarantined for every file.
- **Core never gains or loses rows.** Joins are left joins with a matched flag. Matching of
  materials, suppliers and customers belongs to the match stage, not core.
- Rule ids (RAW-, ST-, CO-) are stable identifiers used in lineage, quarantine and tests.

## Master data matching

`make match` (and `make run-all`) runs four matchers against the warehouse in one transaction. It
writes only its own tables, so it reruns without re-ingesting. Output:
`docs/match-quality-report.md` and `governance.match_quality`.

- **Bands** are set in `config/matching.toml`: 95 or more auto-accept, 80 to 95 human review,
  below 80 never merged.
- **Audit trail:** every match record carries `method`, `score`, `matched_on`, `status`,
  `matched_at`, `match_run_id`, and keeps the source value beside the canonical one. Nothing is
  merged destructively.
- **Materials:** `core.material_xref` holds one row per way a material is written per table.
  `core.material_golden` holds one row per canonical code, built by survivorship. Grade comes from
  the BOM grade column, then the code, then the description. It is never guessed when several
  grades are held.
- **Suppliers:** rapidfuzz, blocking on the first normalised token, abbreviations expanded.
  Accepted links are clustered into entities in `core.supplier_golden`. Review items are one per
  pair of entities, with invoice evidence.
- **Jobs:** `core.job_xref` holds every source value, `core.job_crosswalk` one row per job, and
  `core.job_unmatched` the gaps on all three sides.
- **Works orders:** `core.works_order_xref`. Numbers Corvus does not hold get transposition
  candidates in the review queue.
- **Combined review queue:** `core.v_match_review_queue`.

## Data quality and governance

`make quality` runs every rule in `config/dq_rules.yaml`. Rules are never hardcoded, and the engine
refuses a rule file that breaks the schema.

- **What a rule declares:** id, name, business description, dimension, severity, system of record,
  owning role, the check as SQL or `module:function`, pass threshold, business consequence,
  corrective action, and the seeded defects it covers.
- **Check contract:** one row per record checked, with `record_key`, `passed`, `observed`, and
  optionally `source_file` and `source_row`.
- **Results:** `governance.dq_results` gains a row per rule per run and is never overwritten. The
  trend is in `governance.v_dq_trend`, and `make ingest` carries this history across rebuilds.
- **Scorecards:** `governance.v_dq_scorecard_by_owner`, `_by_system`, `_by_dimension`, and
  `docs/dq-scorecard.md`.
- **Exception queue:** `governance.v_dq_exception_queue` holds the latest run's failing records,
  with severity, owner and corrective action.
- **Headline index:** DQI = 100 × Σ(weight × min(1, pass rate / threshold)) / Σ weight. Severity
  weights are critical 8, high 4, medium 2, low 1.
- **Owning roles:** Purchasing Manager, Production Controller, Finance Manager, Quality Manager.

## Reconciliation

`make reconcile` rebuilds the `recon` schema in one transaction. Each engine returns a row-level
result set, a summary, an exposure figure and headline figures.

- **Headline figures:** `recon.headline` stores each figure with the SQL that produces it and the
  SQL that lists its rows. The pipeline recomputes every figure from its rows and refuses to
  publish if any disagrees, so no figure is unexplainable. Every row carries its source file and
  line.
- **Three-way match:** `recon.three_way_lines` puts every PO line in one category: matched,
  quantity variance, price variance, missing GRN, missing invoice, or not yet due. Invoices on
  non-exempt nominals with no PO are a separate category. Each line carries its value at risk,
  age and reason.
- **Job cost:** `recon.job_cost` shows the Corvus, finance and shop-floor views side by side, with
  the gap ranked. `recon.job_cost_detail` holds every contributing row, and `recon.job_material`
  explains the material gap by material. Most of the material gap is steel charged to the wrong
  job.
- **Stock accuracy:** `recon.stock_lines` and `recon.stock_summary` by site and section type,
  against the 95% target.
- **Traceability:** Corvus holds no material issues, so receipts are allocated to BOM lines
  first-in first-out (`recon.trace_allocations`). `recon.trace_lines` records where each chain
  breaks. `recon.trace_jobs` and `recon.trace_customers` show the EN 1090 exposure.
- **Drill-down:** the Streamlit page Reconciliation goes from headline to rows to source line.

## KPIs

`make kpi` rebuilds the `marts` schema from `src/fabsync/kpi/sql/` in one transaction. Nine KPIs:
OTIF, labour variance, material yield, stock accuracy, three-way exception rate, traceability
coverage, WIP and ageing, capacity utilisation, and NCR rate with cost of quality.

- **Definitions:** every KPI is defined in `config/kpis.yaml` with name, one-sentence definition,
  formula, sources, owner, refresh, target and caveat. The build refuses a KPI whose caveat is
  missing or perfunctory.
- **Documented views:** every view carries its description as a warehouse comment. The build fails
  if a view is undocumented, or documented but not built.
- **Outputs:** `marts.kpi_definition`, `marts.kpi_scorecard`, `docs/data-dictionary.md` (one
  table, ready for the PDF pack) and `docs/kpi-report.md`, where every figure appears with its
  caveat.
- **Rule:** never present a KPI without its caveat.

## Naming and style

- British English throughout: "programme", "organisation", "centre", "tonne".
- Module and table names are plain English nouns in snake_case.
- Every generated dataset carries a `synthetic = true` marker or equivalent
  note; every UI page and document states that data is synthetic.
