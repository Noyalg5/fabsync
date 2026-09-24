"""Staging layer: apply the contract's rules in a fixed order.

Rules run one after another, so every lineage row chains: the rows out of one
rule are the rows in to the next. A row that fails a rule leaves the flow at
that rule and is written to quarantine with the rule id, the failing column,
and the original record as received. The raw table is never touched.

Order: ST-01 trim, ST-02 exact duplicates, ST-03 required, ST-04 dates,
ST-05 numerics, ST-06 integers, ST-07 domain, ST-08 natural key, ST-09 cast.
"""

from __future__ import annotations

import re
from datetime import datetime

import duckdb
import pandas as pd

from fabsync.ingest.contracts import DATE, DECIMAL, INTEGER, STAGING_TYPES, SourceContract, TableContract
from fabsync.ingest.raw_loader import raw_table_name
from fabsync.ingest.warehouse import Recorder, now

# A plain number, or one grouped correctly in thousands. "7,5" and "1,23,456" are rejected
# rather than silently read as 75 and 123456.
NUMERIC_RE = re.compile(r"^[+-]?(\d+|\d{1,3}(,\d{3})+)(\.\d+)?$")
PLAIN_NUMBER_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")
INTEGER_RE = re.compile(r"^[+-]?\d+$")


def coerce_numeric(value: str) -> str | None:
    """Return a plain decimal string, or None if the value cannot be read as a number."""
    candidate = value.replace("£", "").replace(" ", "")
    if NUMERIC_RE.match(candidate):
        return candidate.replace(",", "")
    return None


def parse_dates(values: pd.Series, formats: tuple[str, ...]) -> pd.Series:
    """ISO date strings for values matching any declared format; None elsewhere."""
    def parse(v: str) -> str | None:
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).date().isoformat()
            except ValueError:
                continue
        return None
    return values.map(parse)


class Stage:
    """The flow of one table through the staging rules."""

    def __init__(self, con: duckdb.DuckDBPyConnection, rec: Recorder, source: SourceContract,
                 table: TableContract) -> None:
        self.con, self.rec, self.source, self.table = con, rec, source, table
        self.cols = table.column_names
        self.originals = con.execute(
            f"SELECT * FROM raw.{raw_table_name(source.system, table.name)} ORDER BY _source_row").df()
        self.work = self.originals[self.cols + ["_source_row"]].copy()
        self.target = f"staging.{raw_table_name(source.system, table.name)}"

    def _lineage(self, rule_id: str, rows_in: int, rejected: int = 0, affected: int = 0, detail: str = "",
                 started=None) -> None:
        self.rec.lineage(layer="staging", source_system=self.source.system, source_table=self.table.name,
                         source_file=self.table.file, target_table=self.target, rule_id=rule_id, rows_in=rows_in,
                         rows_out=rows_in - rejected, rows_rejected=rejected, rows_affected=affected,
                         detail=detail, started_at=started)

    def reject(self, rule_id: str, fail: pd.Series, failing_column: pd.Series | str | None,
               detail: str = "", started=None, affected: int = 0) -> None:
        """Quarantine rows where ``fail`` is true and remove them from the flow."""
        rows_in = len(self.work)
        bad = self.work[fail]
        if len(bad):
            col = failing_column[fail] if isinstance(failing_column, pd.Series) else failing_column
            self.rec.quarantine(layer="staging", source_system=self.source.system, source_table=self.table.name,
                                source_file=self.table.file, rule_id=rule_id, rows=bad, failing_column=col,
                                originals=self.originals, columns=self.cols)
        self.work = self.work[~fail]
        self._lineage(rule_id, rows_in, rejected=len(bad), affected=affected, detail=detail, started=started)

    def column_rule(self, rule_id: str, checks: dict[str, pd.Series], affected: int = 0, note: str = "") -> None:
        """Apply a per-column check; a row fails on the first column (contract order) that fails."""
        started = now()
        fail = pd.Series(False, index=self.work.index)
        failing = pd.Series(None, index=self.work.index, dtype=object)
        counts = {}
        for col in self.cols:
            if col not in checks:
                continue
            col_fail = checks[col].reindex(self.work.index, fill_value=False) & ~fail
            if col_fail.any():
                counts[col] = int(col_fail.sum())
                failing[col_fail] = col
                fail |= col_fail
        detail = (", ".join(f"{c}: {n}" for c, n in counts.items()) or "no failures") + note
        self.reject(rule_id, fail, failing, detail=detail, started=started, affected=affected)

    def run(self) -> int:
        t = self.table

        # ST-01 trim
        started = now()
        before = self.work[self.cols]
        self.work[self.cols] = before.apply(lambda s: s.str.strip())
        changed = int((before != self.work[self.cols]).to_numpy().sum())
        cols_changed = [c for c in self.cols if (before[c] != self.work[c]).any()]
        self._lineage("ST-01", len(self.work), affected=changed,
                      detail=f"{changed:,} values trimmed" + (f" in {', '.join(cols_changed)}" if cols_changed else ""),
                      started=started)

        # ST-02 exact duplicates, compared on trimmed values
        started = now()
        self.reject("ST-02", self.work.duplicated(subset=self.cols, keep="first"), None,
                    detail="repeat of an earlier row in the same file", started=started)

        # ST-03 required columns
        w = self.work
        self.column_rule("ST-03", {c.name: w[c.name] == "" for c in t.columns if c.required})

        # ST-04 dates
        w = self.work
        parsed_dates = {c.name: parse_dates(w[c.name], c.formats) for c in t.columns if c.dtype == DATE}
        self.column_rule("ST-04", {n: (w[n] != "") & parsed_dates[n].isna() for n in parsed_dates})

        # ST-05 numerics (decimal and integer columns)
        w = self.work
        numeric_cols = [c.name for c in t.columns if c.dtype in (DECIMAL, INTEGER)]
        coerced = {n: w[n].map(coerce_numeric) for n in numeric_cols}
        separators = sum(int(((w[n] != "") & (w[n] != coerced[n].fillna(w[n]))).sum()) for n in numeric_cols)
        self.column_rule("ST-05", {n: (w[n] != "") & coerced[n].isna() for n in numeric_cols}, affected=separators,
                         note=f"; {separators:,} values coerced (separators, currency, spaces)" if separators else "")

        # ST-06 integers
        w = self.work
        int_cols = [c.name for c in t.columns if c.dtype == INTEGER]
        self.column_rule("ST-06", {n: (w[n] != "") & ~coerced[n].reindex(w.index).fillna("").str.match(INTEGER_RE)
                                   for n in int_cols})

        # ST-07 domain
        w = self.work
        self.column_rule("ST-07", {c.name: (w[c.name] != "") & ~w[c.name].isin(c.domain)
                                   for c in t.columns if c.domain})

        # ST-08 natural key
        started = now()
        if t.key:
            self.reject("ST-08", self.work.duplicated(subset=list(t.key), keep="first"), t.key[0],
                        detail=f"key ({', '.join(t.key)}); first occurrence kept", started=started)

        # ST-09 cast to declared types; blank text becomes NULL
        started = now()
        out = self.work.copy()
        for c in t.columns:
            if c.dtype == DATE:
                out[c.name] = parsed_dates[c.name].reindex(out.index)
            elif c.dtype in (DECIMAL, INTEGER):
                out[c.name] = coerced[c.name].reindex(out.index)
        blanks = int((self.work[self.cols] == "").to_numpy().sum())
        out = out.astype(object).where(out.astype(str) != "", None)
        out["_source_file"] = t.file
        select = ", ".join(
            f'CAST(NULLIF(CAST("{c.name}" AS VARCHAR), \'\') AS {STAGING_TYPES[c.dtype]}) AS "{c.name}"'
            for c in t.columns)
        self.con.register("_stage_frame", out)
        self.con.execute(f"""CREATE TABLE {self.target} AS SELECT {select}, _source_file,
                             CAST(_source_row AS INTEGER) AS _source_row, '{self.rec.run_id}' AS _run_id
                             FROM _stage_frame ORDER BY _source_row""")
        self.con.unregister("_stage_frame")
        types = ", ".join(f"{c.name} {STAGING_TYPES[c.dtype]}" for c in t.columns if c.dtype != "text")
        self._lineage("ST-09", len(out), affected=blanks, detail=f"{blanks:,} blanks to NULL; {types}",
                      started=started)
        self.rec.flush()
        return len(out)


def stage_table(con: duckdb.DuckDBPyConnection, rec: Recorder, source: SourceContract,
                table: TableContract) -> int:
    return Stage(con, rec, source, table).run()
