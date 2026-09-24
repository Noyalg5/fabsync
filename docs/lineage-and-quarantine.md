# Warehouse, lineage and quarantine

**All data described here is synthetic.**

`make ingest` rebuilds `data/warehouse/fabsync.duckdb` from empty. It builds into a temporary file
and swaps it in only when every step succeeds, so a failed run leaves the previous warehouse intact.
Running it twice over the same raw files gives the same tables; only run ids and timestamps differ.

## Layers

| Schema | Holds | Rule |
| --- | --- | --- |
| `raw` | One table per source file, e.g. `raw.shop_floor_time_bookings` | Exactly as received: every column text, padding kept, nothing cleaned. Each row carries `_source_file` and `_source_row`, the physical line in the file. |
| `staging` | The same tables, typed | Trimmed, blanks to NULL, dates parsed, numerics coerced. Rows that fail a rule are quarantined, not dropped. |
| `core` | Conformed and joined tables, e.g. `core.time_bookings`, `core.jobs` | Works orders, jobs, sites and operations conformed; children joined to parents with a matched flag. Never gains or loses a row. |
| `governance` | Lineage, quarantine, contracts, rules, profiling, balance, run log, match quality | The evidence. |

Every staging and core row keeps `_source_file` and `_source_row`, so any figure can be traced back
to the line a person would see opening the file.

## Contracts

Each source system declares its schema contract in its own module, separately from the data:
`src/fabsync/ingest/corvus_mrp.py`, `finance.py` and `shop_floor.py`. A contract lists every column
with its type, whether it is required, accepted date formats, allowed values and canonical pattern.
A file whose columns differ from its contract stops the run (RAW-02). The contracts are materialised
in `governance.contract`.

## Rules

Staging applies its rules in a fixed order, and each rule writes one lineage row per table. A row
that fails leaves the flow at that rule, so the rows out of one step are the rows in to the next.

| Rule | What it does |
| --- | --- |
| RAW-01 | Load the file as received, record its SHA-256 and SYNTHETIC DATA header |
| RAW-02 | Columns must match the contract; a ragged row is quarantined |
| ST-01 | Trim whitespace |
| ST-02 | Exact duplicate row: first kept, repeats quarantined |
| ST-03 | Required column must not be blank |
| ST-04 | Date must parse with a declared format |
| ST-05 | Number must coerce; `1,234.50` and `£650` are accepted, `7,5` and `4hrs` are not |
| ST-06 | Integer column must hold a whole number |
| ST-07 | Value must be in the declared domain |
| ST-08 | Natural key unique: first kept, repeats quarantined |
| ST-09 | Cast to declared types; blank text to NULL |
| CO-01 | Works order free text conformed to the five-digit Corvus number |
| CO-02 | Site alias conformed using `config/conformance.toml` |
| CO-03 | Job reference conformed to `J-YY-NNNN`; finance code derived as `YY` + sequence |
| CO-04 | Operation alias conformed using `config/conformance.toml` |
| CO-05 | Join to parent recorded as a matched flag; unmatched rows kept |
| CO-06 | Core table built with no row loss |
| MA-01 | Material codes and descriptions parsed; canonical code emitted |
| MA-02 | Material golden record built by survivorship |
| MA-03 | Supplier fuzzy match: 95+ auto, 80 to 95 review, under 80 never merged |
| MA-04 | Job crosswalk across Corvus, finance and shop floor |
| MA-05 | Works order free text parsed; unknown numbers checked for transpositions |

## Useful queries

Open the warehouse with the DuckDB command line, or from Python with
`duckdb.connect("data/warehouse/fabsync.duckdb", read_only=True)`.

Does every file balance?

```sql
SELECT source_file, data_lines, staged_rows, quarantined_rows, core_rows, balanced
FROM governance.table_balance ORDER BY source_file;
```

What was quarantined, and why?

```sql
SELECT * FROM governance.v_quarantine_summary;
```

The rows themselves, with the values exactly as typed:

```sql
SELECT quarantine_id, source_file, source_row, rule_id, failing_column, failing_value, original_record
FROM governance.quarantine
WHERE rule_id IN ('ST-04', 'ST-05')
ORDER BY source_file, source_row;
```

What happened to the time bookings file, step by step?

```sql
SELECT step_id, rule_id, rows_in, rows_out, rows_rejected, rows_affected, detail
FROM governance.lineage
WHERE source_file = 'shop_floor/time_bookings.csv'
ORDER BY step_id;
```

Trace one line of a file through every layer:

```sql
SELECT 'raw' AS layer, works_order, hours, booking_date, site FROM raw.shop_floor_time_bookings WHERE _source_row = 100
UNION ALL
SELECT 'staging', works_order, CAST(hours AS VARCHAR), CAST(booking_date AS VARCHAR), site
FROM staging.shop_floor_time_bookings WHERE _source_row = 100
UNION ALL
SELECT 'core', CAST(wo_no AS VARCHAR), CAST(hours AS VARCHAR), CAST(booking_date AS VARCHAR), site_code
FROM core.time_bookings WHERE _source_row = 100;
```

Which bookings are on works orders Corvus has never heard of?

```sql
SELECT wo_no, count(*) AS bookings, sum(hours) AS hours
FROM core.time_bookings WHERE NOT wo_matched GROUP BY wo_no ORDER BY wo_no;
```

Which finance job codes have no MRPII job?

```sql
SELECT finance_job_code FROM core.finance_jobs WHERE NOT mrp_matched ORDER BY 1;
```

What did profiling find before anything was cleaned?

```sql
SELECT source_table, column_name, anomaly, affected_values, sample_values
FROM governance.profile_anomaly ORDER BY source_system, source_table, column_name;
```

## Seeing it

`make app` opens the demonstrator. The **Lineage and quarantine** page shows the balance, the rule
chain for any table, a quarantine browser with each row's original values, and a row trace across
layers. `docs/profiling-report.md` is the profiling output as a document; it is regenerated by every
`make ingest` and contains no timestamps, so it only changes when the data does.
