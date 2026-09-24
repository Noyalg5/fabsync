# Progress log

Running mission log. Updated after every mission. Newest entry at the top.

## Mission 0: Scaffold (2026-09-24)

**Done**
- Repository structure: `src/fabsync/{generate,ingest,match,quality,reconcile,kpi}`, `app/`, `config/`, `data/raw/`, `data/warehouse/`, `docs/`, `tests/`, `export/`.
- `pyproject.toml` with pinned dependencies; `Makefile` with `generate`, `ingest`, `run-all`, `app`, `pack`, `test`, `clean`.
- `docs/project-brief.md`: context, house rules, layout, source systems, glossary.
- `.gitignore` and commit-msg hook made tool-agnostic.
- Package stubs only. No logic written.

**Next**
- Mission 1: synthetic source generation for MRPII, finance and shop-floor spreadsheets, with deliberate master data drift.
