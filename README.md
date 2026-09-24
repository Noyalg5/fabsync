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
make run-all   # generate synthetic data, load the warehouse, run every stage
make app       # open the Streamlit demonstrator
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
