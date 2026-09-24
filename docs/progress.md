# Progress log

Running mission log. Updated after every mission. Newest entry at the top.

## Mission 7: Streamlit app (2026-09-25)

**Done**
- `make app` runs `app/app.py`, with eight pages in story order: Overview, Source systems, Data
  quality, Master data, Reconciliation, Performance, Governance, Roadmap. The earlier Home,
  Lineage and Reconciliation pages were folded in. Lineage and quarantine is now a tab under
  Governance.
- `src/fabsync/ui.py` holds the shared design system: one accent, fixed source-system colours,
  cached queries, £ formatting, directly labelled Altair charts, clickable headline figures that
  open the rows behind them, and tracing from a row to its source line.
- **Overview:** the problem in plain English, an inline SVG diagram of the three disconnected
  systems, and eight clickable headline findings.
- **Source systems:** each raw extract as received, with its conventions, profiling findings and
  quarantined rows marked line by line.
- **Governance:** the data dictionary, a live ownership matrix, the rule set, and lineage and
  quarantine.
- **Roadmap:** phases, risk register and training plan from the new `config/roadmap.yaml`, sized
  by live figures. KPIs gained a `rows` query so their figures are clickable.
- **Offline:** usage statistics are off, and the server binds to localhost. Without the binding,
  Streamlit fetched the public IP address at startup.
- **Speed:** every page renders in under 0.5 s warm; the first page is about 1 s cold.
- 9 app tests replace the two old page tests; 138 tests in total.

**Not verified**
- No browser is available in this environment, so the visual layout, including the CSS for the
  banner and the large clickable figures, has not been seen rendered. It has been checked only
  through the test harness.

**Next**
- The PDF pack.

## Mission 6: KPI layer (2026-09-25)

**Done**
- `marts` schema: 24 documented objects built from `src/fabsync/kpi/sql/`. Each view's description
  is stored as a warehouse comment, and the build fails if views and definitions disagree.
- Nine KPIs defined in `config/kpis.yaml`, each with definition, formula, sources, owner, refresh,
  target and a mandatory caveat of at least 20 words.
- **Current values:**
  - OTIF 16.7% against 95%
  - labour variance +7.4% against ±10%
  - cut yield 76.2% against 85%
  - stock accuracy 89.6% against 95%
  - three-way exception rate 53.8% against 5%, with £4.32m at risk
  - traceability 68.7% against 100%
  - WIP £714k, 55% of it over 90 days
  - capacity utilisation 86.1% against a 75 to 95% band
  - cost of quality 1.3% of turnover against 2%, with 7.2 NCRs per 100 tonnes
- `docs/data-dictionary.md` (one table ready for the PDF pack) and `docs/kpi-report.md`, where
  every figure appears with its caveat.
- `make kpi` added. `make run-all` now runs end to end from a clean tree.
- 16 new tests; 132 in total. They show each KPI reproduces from source or from the
  reconciliation, and that a KPI without a caveat is refused.

**Changed from earlier missions**
- **Generator headcount recalibrated** from 48 and 34 to 13 and 12 direct staff. The old figures
  implied 26% utilisation, meaning three quarters of the workforce idle. Only available hours in
  the weekly capacity sheet change; every earlier report is unchanged except one distinct count
  in the profiling report.

**Known calibration points to review**
- **OTIF (16.7%)** is what the mission 1 generator implies. Delivery-note promised dates equal the
  internal planned finish and most works orders slip. A real customer promise usually carries a
  buffer. Changing it would shift labour and booking figures across every mission, so it is
  flagged rather than changed.
- **Three-way exception rate (53.8%)** is driven by the generator short-delivering about half of
  all orders by 2 to 10%, and by a strict 2% quantity tolerance.

**Next**
- The Streamlit management views and the PDF pack.

## Mission 5: Reconciliation engines (2026-09-25)

**Done**
- `src/fabsync/reconcile/`: four engines, each returning rows, a summary, an exposure figure and
  headline figures. `make reconcile` publishes them to the `recon` schema and chains into
  `run-all`. Settings are in `config/reconcile.toml`.
- **No unexplainable figures:** all 45 headlines are stored with their value SQL and rows SQL. The
  pipeline recomputes each from its rows before committing and refuses to publish otherwise. The
  Streamlit page Reconciliation drills from headline to rows to raw source line.
- **Three-way match:** £4.32m at risk. That is £3.41m of invoices with no PO (subcontract,
  galvanising, paint, erection and similar), £428k received but not invoiced, £304k ordered but not
  received, £116k in quantity variances and £59k in price variances. Ageing uses 0-30, 31-60,
  61-90, 91-180 and over-180-day buckets.
- **Job cost:** £1.74m gross unexplained gap across 169 jobs, ranked. Of the £1.54m gross material
  gap, £1.43m is steel charged to the wrong job. It cancels out across jobs, and the invoices
  reconcile to finance to the penny. The labour gap flags exactly the 30 seeded jobs. Finance cost
  on jobs Corvus does not hold is £236k.
- **Stock accuracy:** 89.6% against the 95% target. 8 of 20 site and section-type groups miss it.
  The 11 offending lines total £15.3k.
- **Traceability:** 68.7% coverage by weight. 148 despatched jobs for 38 customers carry steel
  without a full chain, 1,103 tonnes in all. Chains break at: heat number missing (651 lines),
  certificate missing (458), grade unconfirmed on receipt (656), no receipt on record (74), and no
  delivery note (21). Corvus has no issue records, so the issue link is reconstructed and labelled
  as such.
- 20 new tests; 116 in total.

**Next**
- Mission 6: management reporting, including KPIs such as OTIF, WIP, NCR cost, tonnage and margin,
  on the reconciled data.

## Mission 4: Data quality engine (2026-09-24)

**Done**
- `config/dq_rules.yaml`: 34 declarative rules covering all six dimensions, four severities and
  four owning roles. 33 are SQL checks and one is a Python check. Every rule states its business
  description, consequence and corrective action. Between them they cover all ten seeded defects,
  plus completeness, referential integrity, UoM validity, date sequence, duplicates, positive
  quantities, orphans, stale counts and timeliness.
- `src/fabsync/quality/`: the rule loader validates the schema and refuses bad files. The engine
  appends results by run id. A rule that errors is recorded and the rest still run, with a
  non-zero exit.
- Scorecards by owning role, source system, dimension and severity, as views and in
  `docs/dq-scorecard.md`.
- Exception queue of the latest run's failing records, with severity, owner and corrective action.
- Headline data quality index, documented in the engine and the scorecard. The current value is
  92.1, with 7 of 34 rules met and 4 critical rules breached: three on EN 1090 traceability and one on invoice overcharging.
- `make ingest` now carries quality history across rebuilds. `make quality` was added and chained
  into `run-all`.
- New dependencies: PyYAML, and pytz, which DuckDB needs to return time-zone-aware timestamps to
  Python.
- 29 new tests. Each seeded defect's exceptions match the manifest exactly. The suite also covers
  the documented formula, three scorecards, the trend, history surviving re-ingest, a broken rule
  that is not fatal, and a rule schema check for each field.

**Next**
- Mission 5: reconciliation. Apply approved matches and survivorship without destroying originals,
  and show what changes.

## Mission 3: Master data matching (2026-09-24)

**Done**
- `src/fabsync/match/`: four matchers, a shared audit context, an orchestrator and a report writer.
  `make match` runs them in one transaction; `make run-all` chains generate, ingest and match.
- **Materials:** parser for UK section designations, handling kind prefix and suffix, long names
  and plate forms. 423 written forms resolve to 47 golden materials. Every BOM line auto-matches.
  Codes without a grade on POs, GRNs and stock go to review rather than being guessed.
- **Material golden record:** survivorship puts identity from the parse, grade from the BOM column
  first, mass from the section catalogue first, and lists every unit of measure seen. The 14
  seeded UoM conflicts are flagged.
- **Suppliers:** rapidfuzz with first-token blocking and abbreviation expansion. 21 of 24 Corvus
  codes auto-matched. 4 review decisions carry invoice evidence. Mersey Tube is correctly not
  merged at 67, and is reported as a likely miss because its invoices corroborate.
- **Jobs:** three-way crosswalk with customer corroboration. The 20 finance-only codes are listed
  as unmatched.
- **Works orders:** 3,473 references parse, none fail. The 6 orphans each get a transposition
  candidate for review, with site and date evidence.
- `docs/match-quality-report.md` and `governance.match_quality` cover auto %, queue size,
  unmatched and effort. The estimate is 9.1 hours for 93 review decisions.
- 67 tests pass. They check precision and recall against the seeded manifest, no source change,
  bands, no merge below the floor, idempotent rerun, and thresholds read from config.

**Next**
- Mission 4: data quality rules and governance: named rules, owners, and the controls that stop
  each defect recurring.

## Mission 2: Ingestion layer and warehouse (2026-09-24)

**Done**
- Schema contracts declared per system in `src/fabsync/ingest/corvus_mrp.py`, `finance.py` and
  `shop_floor.py`: columns, types, required flags, date formats, domains, canonical patterns.
- DuckDB warehouse with four schemas: `raw` (as received, all text, physical line numbers),
  `staging` (typed via nine ordered rules), `core` (conformed and joined, left joins with matched
  flags), `governance`.
- Lineage: 163 steps per run in `governance.lineage`; each rule's rows in equals the previous rule's
  rows out. Row-level lineage via `_source_file` and `_source_row` on every staging and core row.
- Quarantine: 189 rows in `governance.quarantine` with rule, column and original values. That is
  162 exact duplicates plus all 27 seeded entry errors, each under its expected rule.
  `governance.table_balance` shows every file balances.
- Profiling: `governance.profile_table`, `profile_column`, `profile_anomaly` and
  `docs/profiling-report.md`, covering blank rates, distinct counts, declared versus inferred types,
  format anomalies, duplicates and samples.
- `make ingest` rebuilds from empty, generating raw data first if missing, and is idempotent. The
  build goes to a temporary file that is swapped in only on success.
- Streamlit page **Lineage and quarantine**: balance, rule chain per table, quarantine browser,
  row trace across layers, rules and contracts.
- `docs/lineage-and-quarantine.md` with the rule catalogue and example queries, each verified.
- 37 tests pass.

**Changed from mission 1**
- The generator now seeds 27 hand-typed entry errors in the shop-floor files, such as `7,5` hours,
  `31/02/2025` and `TBC` dates, blank works orders and reused booking ids. Without them the
  quarantine would show only duplicates. They use a separate random stream, so mission 1 figures
  are unchanged, and they are listed in `defects.json`.

**Next**
- Mission 3: matching across systems: materials (defect 1), suppliers (defect 2), job codes
  (defect 3), with UoM normalisation (defect 4).

## Mission 1: Synthetic source generator (2026-09-24)

**Done**
- `src/fabsync/ingest/generate_sources.py`: seeded, reproducible generator for the three source
  systems, writing `data/raw/corvus_mrp/`, `data/raw/finance/`, `data/raw/shop_floor/`.
- Each system keeps its own conventions: Corvus UPPERCASE, DD/MM/YYYY, fixed-width padding, UoM
  EA/M/KG; finance Title Case, ISO dates, amounts as text with separators, `24871` job codes;
  shop floor mixed case, typos, blanks, three date formats, duplicate rows, free-form WO references.
- Volumes: 150 MRPII jobs plus 20 finance-only, 860 works orders, 5,933 BOM lines, 60 suppliers,
  40 customers, 1,104 POs, 989 GRNs, 12,563 time bookings, 24 months of history. Runs in ~1.3 s.
- All ten seeded defects are written to `data/raw/DEFECTS.md` and `data/raw/defects.json` with
  the exact identifiers affected.
- `tests/test_generate_sources.py`: byte-identical reproducibility, synthetic header on every
  file, and one test per defect asserting it is present in the raw data.
- `make generate` wired to the generator.

**Next**
- Mission 2: ingest the raw extracts into DuckDB without altering the originals, with a
  lineage column per row and the header comment handled.

## Mission 0: Scaffold (2026-09-24)

**Done**
- Repository structure: `src/fabsync/{generate,ingest,match,quality,reconcile,kpi}`, `app/`, `config/`, `data/raw/`, `data/warehouse/`, `docs/`, `tests/`, `export/`.
- `pyproject.toml` with pinned dependencies; `Makefile` with `generate`, `ingest`, `run-all`, `app`, `pack`, `test`, `clean`.
- `docs/project-brief.md`: context, house rules, layout, source systems, glossary.
- `.gitignore` and commit-msg hook made tool-agnostic.
- Package stubs only. No logic written.

**Next**
- Mission 1: synthetic source generation for MRPII, finance and shop-floor spreadsheets, with deliberate master data drift.
