# Progress log

Running mission log. Updated after every mission. Newest entry at the top.

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
