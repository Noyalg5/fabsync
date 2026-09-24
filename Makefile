# FabSync build targets. Runs entirely offline; all data is synthetic.
PY      := .venv/bin/python
PIP     := .venv/bin/pip
EXPORT  := export

.PHONY: help venv generate ingest match quality run-all app pack test clean

help:
	@echo "generate  - create synthetic source extracts in data/raw/"
	@echo "ingest    - rebuild the DuckDB warehouse: raw, staging, core, lineage, quarantine, profiling"
	@echo "match     - rebuild crosswalks, golden records and review queues; write the match quality report"
	@echo "quality   - run the declared data quality rules; write the scorecard and exception queue"
	@echo "run-all   - generate, ingest, match, quality, reconcile, kpi"
	@echo "app       - launch the Streamlit demonstrator"
	@echo "pack      - bundle the demo (warehouse, exports, docs) into export/"
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

run-all: generate ingest match quality
	$(PY) -m fabsync.reconcile
	$(PY) -m fabsync.kpi

app: venv
	.venv/bin/streamlit run app/Home.py

pack: run-all
	mkdir -p $(EXPORT)
	tar -czf $(EXPORT)/fabsync-demo.tar.gz data/warehouse docs README.md

test: venv
	$(PY) -m pytest -q

clean:
	rm -rf data/raw/* data/warehouse/* $(EXPORT)/* .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	touch data/raw/.gitkeep data/warehouse/.gitkeep $(EXPORT)/.gitkeep
