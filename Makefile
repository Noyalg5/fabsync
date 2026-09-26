# FabSync build targets. Runs entirely offline; all data is synthetic.
PY      := .venv/bin/python
PIP     := .venv/bin/pip
EXPORT  := export

.PHONY: help venv generate ingest match quality reconcile kpi diagrams run-all app pack test clean

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
	@echo "test      - run the pytest suite"
	@echo "clean     - remove generated data, warehouse and caches"

venv:
	test -d .venv || python3 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -e ".[dev]"

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

test: venv
	$(PY) -m pytest -q

clean:
	rm -rf data/raw/* data/warehouse/* $(EXPORT)/figures $(EXPORT)/*.pdf $(EXPORT)/*.tar.gz .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	touch data/raw/.gitkeep data/warehouse/.gitkeep $(EXPORT)/.gitkeep
