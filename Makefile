# FabSync build targets. Runs entirely offline; all data is synthetic.
PY      := .venv/bin/python
PIP     := .venv/bin/pip
EXPORT  := export
# The first interpreter on the PATH that is Python 3.11 or later; override with make PYTHON=/path/to/python3.
PYTHON  ?= $(firstword $(foreach p,python3.13 python3.12 python3.11 python3,$(shell command -v $(p) >/dev/null 2>&1 \
             && $(p) -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null && echo $(p))))
# Dependencies are installed once, and again only when pyproject.toml changes, so later runs need no network.
INSTALLED := .venv/.installed

.PHONY: help venv generate ingest match quality reconcile kpi diagrams run-all app pack audit test coverage clean

help:
	@echo "generate  - create synthetic source extracts in data/raw/"
	@echo "ingest    - rebuild the DuckDB warehouse: raw, staging, core, lineage, quarantine, profiling"
	@echo "match     - rebuild crosswalks, golden records and review queues; write the match quality report"
	@echo "quality   - run the declared data quality rules; write the scorecard and exception queue"
	@echo "reconcile - three-way match, job cost, stock accuracy, material traceability"
	@echo "kpi       - build the documented KPI views in marts; write the data dictionary and KPI report"
	@echo "diagrams  - fill the design diagrams with measured figures; render SVG and PNG"
	@echo "run-all   - generate, ingest, match, quality, reconcile, kpi"
	@echo "app       - launch the Streamlit demonstrator"
	@echo "pack      - from a clean run: the A4 management pack PDF and its charts as 300 dpi PNGs in export/"
	@echo "audit     - build the pack, then trace every number in it and on the Overview page to its source"
	@echo "test      - run the pytest suite"
	@echo "coverage  - run the suite under coverage.py and report line and branch coverage by module"
	@echo "clean     - remove generated data, warehouse and caches"

venv: $(INSTALLED)

$(INSTALLED): pyproject.toml
	@test -n "$(PYTHON)" || { echo "FabSync needs Python 3.11 or later on the PATH (python3.11, python3.12, python3.13" \
		"or python3), or make PYTHON=/path/to/python3." >&2; exit 1; }
	test -d .venv || $(PYTHON) -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -e ".[dev]"
	touch $@

generate: venv
	$(PY) -m fabsync.ingest.generate_sources

# Ingest rebuilds the warehouse from empty on every run. It generates the raw
# extracts first only if they are missing, so it also works from a clean clone.
ingest: venv
	test -f data/raw/defects.json || $(PY) -m fabsync.ingest.generate_sources
	$(PY) -m fabsync.ingest

match: venv
	$(PY) -m fabsync.match

quality: venv
	$(PY) -m fabsync.quality

reconcile: venv
	$(PY) -m fabsync.reconcile

kpi: venv
	$(PY) -m fabsync.kpi

# Documentation build step: fills the diagram templates with measured figures and renders SVG and PNG
# with the Mermaid renderer (mmdc). Not part of run-all; rendered files are committed.
diagrams: venv
	$(PY) -m fabsync.design.render

run-all: generate ingest match quality reconcile kpi

app: venv
	.venv/bin/streamlit run app/app.py

# The management pack: a 16-page A4 PDF, and every chart in it as a 300 dpi PNG in export/figures/ for slides.
# Rebuilds everything from a clean run first, so the pack always matches the data. Byte-identical on rerun.
pack: run-all
	$(PY) export/build_pack.py
	tar -czf $(EXPORT)/fabsync-demo.tar.gz data/warehouse docs README.md $(EXPORT)/fabsync-management-pack.pdf \
		$(EXPORT)/figures

# Traces every number in the pack and on the app's Overview page to its source; fails on any untraced number.
audit: pack
	$(PY) -m fabsync.audit

test: venv
	$(PY) -m pytest -q

coverage: venv
	$(PY) -m coverage erase
	$(PY) -m coverage run -m pytest -q
	$(PY) -m coverage combine -q || true
	$(PY) -m coverage report

clean:
	rm -rf data/raw/* data/warehouse/* $(EXPORT)/figures $(EXPORT)/audit $(EXPORT)/*.pdf $(EXPORT)/*.tar.gz \
		.pytest_cache .ruff_cache .coverage .coverage.*
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	touch data/raw/.gitkeep data/warehouse/.gitkeep $(EXPORT)/.gitkeep
