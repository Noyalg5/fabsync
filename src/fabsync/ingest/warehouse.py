"""The DuckDB warehouse: schemas, governance tables and the lineage and quarantine recorders.

Four schemas:

* ``raw``         every source file exactly as received, all columns text
* ``staging``     typed, trimmed, dates parsed, numerics coerced
* ``core``        conformed and joined
* ``governance``  lineage, quarantine, contracts, rules, profiling, run log

Lineage and quarantine are first-class tables, not logs. Every transform writes
one lineage row per rule it applies. Every row a rule rejects is written to
quarantine with the rule, the failing column and the original values as
received; the raw table keeps the original row too. Nothing is dropped
silently and nothing is edited in place.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from fabsync.ingest.contracts import RULES, SourceContract

WAREHOUSE_PATH = Path("data/warehouse/fabsync.duckdb")
SCHEMAS = ("raw", "staging", "core", "governance")

GOVERNANCE_DDL = """
CREATE TABLE governance.run (
    run_id VARCHAR PRIMARY KEY,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    status VARCHAR,
    raw_dir VARCHAR,
    source_files INTEGER,
    rows_raw INTEGER,
    rows_staged INTEGER,
    rows_quarantined INTEGER,
    note VARCHAR
);
CREATE TABLE governance.rule (
    rule_id VARCHAR PRIMARY KEY,
    layer VARCHAR,
    description VARCHAR
);
CREATE TABLE governance.contract (
    source_system VARCHAR,
    source_table VARCHAR,
    source_file VARCHAR,
    ordinal INTEGER,
    column_name VARCHAR,
    declared_type VARCHAR,
    required BOOLEAN,
    is_key BOOLEAN,
    formats VARCHAR,
    domain VARCHAR,
    pattern VARCHAR,
    description VARCHAR
);
CREATE TABLE governance.source_file (
    run_id VARCHAR,
    source_system VARCHAR,
    source_table VARCHAR,
    source_file VARCHAR,
    sha256 VARCHAR,
    bytes BIGINT,
    header_comment VARCHAR,
    data_lines INTEGER,
    loaded_at TIMESTAMPTZ
);
CREATE TABLE governance.lineage (
    run_id VARCHAR,
    step_id INTEGER,
    layer VARCHAR,
    source_system VARCHAR,
    source_table VARCHAR,
    source_file VARCHAR,
    target_table VARCHAR,
    rule_id VARCHAR,
    rule_description VARCHAR,
    rows_in INTEGER,
    rows_out INTEGER,
    rows_rejected INTEGER,
    rows_affected INTEGER,
    detail VARCHAR,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE TABLE governance.quarantine (
    run_id VARCHAR,
    quarantine_id VARCHAR,
    layer VARCHAR,
    source_system VARCHAR,
    source_table VARCHAR,
    source_file VARCHAR,
    source_row INTEGER,
    rule_id VARCHAR,
    rule_description VARCHAR,
    failing_column VARCHAR,
    failing_value VARCHAR,
    original_record JSON,
    status VARCHAR,
    quarantined_at TIMESTAMPTZ
);
CREATE TABLE governance.table_balance (
    run_id VARCHAR,
    source_system VARCHAR,
    source_table VARCHAR,
    source_file VARCHAR,
    data_lines INTEGER,
    raw_rows INTEGER,
    staged_rows INTEGER,
    core_rows INTEGER,
    quarantined_rows INTEGER,
    balanced BOOLEAN
);
"""

GOVERNANCE_VIEWS = """
CREATE VIEW governance.v_quarantine_summary AS
SELECT source_system, source_table, rule_id, rule_description, failing_column,
       count(*) AS rows_quarantined
FROM governance.quarantine
GROUP BY ALL
ORDER BY source_system, source_table, rule_id, failing_column;

CREATE VIEW governance.v_lineage_flow AS
SELECT step_id, layer, source_file, target_table, rule_id, rule_description,
       rows_in, rows_out, rows_rejected, rows_affected, detail
FROM governance.lineage
ORDER BY step_id;
"""


def new_run_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"


def now() -> datetime:
    return datetime.now(UTC)


def rule_layer(rule_id: str) -> str:
    return {"RAW": "raw", "ST": "staging", "CO": "core", "MA": "match", "RC": "reconcile"}[rule_id.split("-")[0]]


def create_warehouse(con: duckdb.DuckDBPyConnection, sources: list[SourceContract]) -> None:
    for schema in SCHEMAS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    con.execute(GOVERNANCE_DDL)
    con.execute(GOVERNANCE_VIEWS)
    con.executemany("INSERT INTO governance.rule VALUES (?, ?, ?)",
                    [(rid, rule_layer(rid), desc) for rid, desc in RULES.items()])
    rows = []
    for src in sources:
        for t in src.tables:
            for i, c in enumerate(t.columns, start=1):
                rows.append((src.system, t.name, t.file, i, c.name, c.dtype, c.required, c.name in t.key,
                             ", ".join(c.formats), ", ".join(c.domain), c.pattern, c.description))
    con.executemany("INSERT INTO governance.contract VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


@dataclass
class Recorder:
    """Writes lineage and quarantine rows for one run."""

    con: duckdb.DuckDBPyConnection
    run_id: str
    step: int = 0
    quarantine_seq: int = 0
    _pending: list[tuple] = field(default_factory=list)

    def lineage(self, *, layer: str, source_system: str, source_table: str, source_file: str,
                target_table: str, rule_id: str, rows_in: int, rows_out: int, rows_rejected: int = 0,
                rows_affected: int = 0, detail: str = "", started_at: datetime | None = None) -> None:
        if rows_in != rows_out + rows_rejected:
            raise AssertionError(
                f"{rule_id} on {target_table}: rows_in {rows_in} != rows_out {rows_out} + rejected {rows_rejected}")
        self.step += 1
        self.con.execute(
            "INSERT INTO governance.lineage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [self.run_id, self.step, layer, source_system, source_table, source_file, target_table, rule_id,
             RULES[rule_id], rows_in, rows_out, rows_rejected, rows_affected, detail,
             started_at or now(), now()])

    def quarantine(self, *, layer: str, source_system: str, source_table: str, source_file: str,
                   rule_id: str, rows: pd.DataFrame, failing_column: pd.Series | str | None,
                   originals: pd.DataFrame, columns: list[str]) -> None:
        """Queue rejected rows. ``originals`` holds the as-received values indexed like ``rows``."""
        stamp = now()
        for idx in rows.index:
            col = failing_column.loc[idx] if isinstance(failing_column, pd.Series) else failing_column
            original = {c: originals.at[idx, c] for c in columns}
            self.quarantine_seq += 1
            self._pending.append((
                self.run_id, f"Q{self.quarantine_seq:06d}", layer, source_system, source_table, source_file,
                int(originals.at[idx, "_source_row"]), rule_id, RULES[rule_id], col,
                original.get(col) if col else None, json.dumps(original, ensure_ascii=False), "open", stamp))

    def flush(self) -> None:
        if self._pending:
            self.con.executemany(
                "INSERT INTO governance.quarantine VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._pending)
            self._pending.clear()
