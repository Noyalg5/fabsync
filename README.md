# FabSync

Systems integration, data governance and management reporting demonstrator for
a fictional UK structural steelwork and architectural metalwork fabricator.

**All data is synthetic.** No real company, contract, person or supplier is
represented.

## Quick start

```sh
make generate  # rebuild the synthetic source extracts in data/raw/
make ingest    # rebuild the DuckDB warehouse with lineage, quarantine and profiling
make match     # match materials, suppliers, jobs and works orders across systems
make quality   # run the declared data quality rules; scorecard and exception queue
make reconcile # three-way match, job cost, stock accuracy, material traceability
make kpi       # build the documented KPI views; data dictionary and KPI report
make run-all   # generate synthetic data, load the warehouse, run every stage
make app       # open the demonstrator at http://localhost:8501 (runs offline)
make test      # run the test suite
```

Requires Python 3.11 or later. Runs entirely offline.

## Documentation

- `docs/project-brief.md`: context, house rules, domain glossary
- `docs/progress.md`: mission log
- `docs/lineage-and-quarantine.md`: warehouse layers, rules and example queries
- `docs/profiling-report.md`: profile of every source file as received
- `docs/match-quality-report.md`: match rates, review queue and effort to clear it
- `docs/dq-scorecard.md`: data quality index and scorecards by owner, system and dimension
- `docs/reconciliation-report.md`: the four reconciliations, each figure with the query behind it
- `docs/data-dictionary.md`: every KPI's definition, formula, sources, owner, refresh and caveat
- `docs/kpi-report.md`: current KPI values, each with its caveat
- `docs/process-maps.md`: AS-IS process maps and TO-BE architecture, with diagrams in `docs/diagrams/`
- `docs/integration-design.md`: interfaces, systems of record, conflict-resolution rules
- `docs/data-ownership.md`: ownership matrix and escalation route
- `docs/rollout-plan.md`: five phases over 18 months, with entry and exit criteria and quarterly reviews
- `docs/risk-register.md`: 23 scored risks, inherent and residual, with owners and early warnings
- `docs/training-plan.md`: training by role, each with a competence check
- `docs/benefits-case.md`: ILLUSTRATIVE benefits by phase; measured baselines, modelled targets
