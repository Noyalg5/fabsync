# Progress log

Running mission log. Updated after every mission. Newest entry at the top.

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
