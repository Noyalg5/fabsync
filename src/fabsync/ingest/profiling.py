"""Profile every raw source table against its contract.

Per table: row count, exact duplicate rows, duplicate natural keys. Per column:
blank rate, distinct count, declared type, the type a naive loader would infer,
whether they disagree, and format anomalies with a sample of offending values.

Results go to governance.profile_table, governance.profile_column and
governance.profile_anomaly, and to docs/profiling-report.md. The report holds
no timestamps or run ids so that rebuilding from the same data gives the same
file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import duckdb
import pandas as pd

from fabsync.ingest.contracts import DATE, DECIMAL, INTEGER, TEXT, SourceContract, TableContract
from fabsync.ingest.raw_loader import raw_table_name
from fabsync.ingest.staging import INTEGER_RE, PLAIN_NUMBER_RE, coerce_numeric, parse_dates

ALL_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%b-%y")
FORMAT_LABEL = {"%d/%m/%Y": "DD/MM/YYYY", "%Y-%m-%d": "YYYY-MM-DD", "%d-%b-%y": "DD-Mon-YY"}
COMPATIBLE = {INTEGER: {INTEGER}, DECIMAL: {INTEGER, DECIMAL}, DATE: {DATE}, TEXT: {TEXT, INTEGER, DECIMAL, DATE}}
SAMPLE_SIZE = 5

PROFILE_DDL = """
CREATE TABLE governance.profile_table (
    run_id VARCHAR, source_system VARCHAR, source_table VARCHAR, source_file VARCHAR,
    row_count INTEGER, column_count INTEGER, blank_cells INTEGER, exact_duplicate_rows INTEGER,
    duplicate_key_rows INTEGER, natural_key VARCHAR, type_mismatches INTEGER, anomalies INTEGER
);
CREATE TABLE governance.profile_column (
    run_id VARCHAR, source_system VARCHAR, source_table VARCHAR, ordinal INTEGER, column_name VARCHAR,
    declared_type VARCHAR, inferred_type VARCHAR, type_mismatch BOOLEAN, blank_count INTEGER,
    blank_rate DOUBLE, distinct_count INTEGER, anomaly_count INTEGER
);
CREATE TABLE governance.profile_anomaly (
    run_id VARCHAR, source_system VARCHAR, source_table VARCHAR, column_name VARCHAR, anomaly VARCHAR,
    affected_values INTEGER, sample_values VARCHAR
);
"""


@dataclass
class Anomaly:
    column: str
    anomaly: str
    affected: int
    samples: list[str]


@dataclass
class ColumnProfile:
    ordinal: int
    name: str
    declared: str
    inferred: str
    blank: int
    rows: int
    distinct: int
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def mismatch(self) -> bool:
        return self.inferred not in COMPATIBLE[self.declared]


@dataclass
class TableProfile:
    system: str
    table: str
    file: str
    rows: int
    key: tuple[str, ...]
    exact_duplicates: int
    duplicate_keys: int
    duplicate_sample: list[str]
    columns: list[ColumnProfile]

    @property
    def anomalies(self) -> list[Anomaly]:
        found = [a for c in self.columns for a in c.anomalies]
        if self.exact_duplicates:
            found.insert(0, Anomaly("(row)", "exact duplicate rows", self.exact_duplicates, self.duplicate_sample))
        if self.duplicate_keys:
            found.insert(0 if not self.exact_duplicates else 1,
                         Anomaly("(row)", f"duplicate natural key ({', '.join(self.key)}) with differing values",
                                 self.duplicate_keys, []))
        return found


def quoted(values) -> list[str]:
    """Show values with quotes so padding and blanks are visible."""
    return [json.dumps(v, ensure_ascii=False) for v in values]


def sample(values: pd.Series) -> list[str]:
    return quoted(pd.unique(values)[:SAMPLE_SIZE])


def infer_type(values: pd.Series) -> str:
    """The type a naive loader would infer from the trimmed, non-blank values."""
    v = values[values != ""]
    if v.empty:
        return TEXT
    if v.str.match(INTEGER_RE).all():
        return INTEGER
    if v.str.match(PLAIN_NUMBER_RE).all():
        return DECIMAL
    if parse_dates(v, ALL_DATE_FORMATS).notna().all():
        return DATE
    return TEXT


def profile_column(ordinal: int, col, raw: pd.Series) -> ColumnProfile:
    trimmed = raw.str.strip()
    non_blank = trimmed != ""
    prof = ColumnProfile(ordinal, col.name, col.dtype, infer_type(trimmed), int((~non_blank).sum()), len(raw),
                         int(raw.nunique()))
    add = prof.anomalies.append

    padded = raw[non_blank & (raw != trimmed)]
    if len(padded):
        add(Anomaly(col.name, "leading or trailing whitespace", len(padded), sample(padded)))
    if col.required and prof.blank:
        add(Anomaly(col.name, "blank in required column", prof.blank, []))

    values = trimmed[non_blank]
    if col.dtype == DATE:
        per_format = {FORMAT_LABEL[f]: int(parse_dates(values, (f,)).notna().sum()) for f in ALL_DATE_FORMATS}
        used = {k: n for k, n in per_format.items() if n}
        if len(used) > 1:
            add(Anomaly(col.name, "mixed date formats (" + ", ".join(f"{k} {n:,}" for k, n in used.items())
                        + "); count is values outside the most common format",
                        sum(used.values()) - max(used.values()), []))
        undeclared = values[parse_dates(values, col.formats).isna() & parse_dates(values, ALL_DATE_FORMATS).notna()]
        if len(undeclared):
            add(Anomaly(col.name, "date in a format the contract does not declare", len(undeclared),
                        sample(undeclared)))
        bad = values[parse_dates(values, ALL_DATE_FORMATS).isna()]
        if len(bad):
            add(Anomaly(col.name, "not a valid date", len(bad), sample(bad)))
    elif col.dtype in (DECIMAL, INTEGER):
        coerced = values.map(coerce_numeric)
        as_text = values[coerced.notna() & ~values.str.match(PLAIN_NUMBER_RE)]
        if len(as_text):
            add(Anomaly(col.name, "number stored as text (separators, currency or spaces)", len(as_text),
                        sample(as_text)))
        bad = values[coerced.isna()]
        if len(bad):
            add(Anomaly(col.name, "not a number", len(bad), sample(bad)))
        if col.dtype == INTEGER:
            frac = values[coerced.notna() & ~coerced.fillna("").str.match(INTEGER_RE)]
            if len(frac):
                add(Anomaly(col.name, "not a whole number", len(frac), sample(frac)))
    else:
        folded = values.str.casefold().str.replace(r"\s+", " ", regex=True)
        groups = values.groupby(folded).agg(lambda s: sorted(pd.unique(s)))
        variants = groups[groups.map(len) > 1]
        if len(variants):
            add(Anomaly(col.name, "same value written with different case or spacing",
                        int(values[folded.isin(variants.index)].shape[0]),
                        [" / ".join(quoted(v)) for v in variants.head(3)]))
    if col.domain:
        outside = values[~values.isin(col.domain)]
        if len(outside):
            add(Anomaly(col.name, "outside declared domain", len(outside), sample(outside)))
    if col.pattern:
        off = values[~values.str.match(col.pattern)]
        if len(off):
            add(Anomaly(col.name, "not in canonical form", len(off), sample(off)))
    return prof


def profile_table(con: duckdb.DuckDBPyConnection, source: SourceContract, table: TableContract) -> TableProfile:
    raw = con.execute(
        f"SELECT * FROM raw.{raw_table_name(source.system, table.name)} ORDER BY _source_row").df()
    data = raw[table.column_names]
    exact = data.duplicated(keep="first")
    distinct = data[~exact]
    dup_keys = int(distinct.duplicated(subset=list(table.key), keep="first").sum()) if table.key else 0
    dup_sample = [json.dumps(dict(zip(table.key or table.column_names[:2], r, strict=False)))
                  for r in data[exact][list(table.key or table.column_names[:2])].head(3).itertuples(index=False)]
    columns = [profile_column(i, c, data[c.name]) for i, c in enumerate(table.columns, start=1)]
    return TableProfile(source.system, table.name, table.file, len(data), table.key, int(exact.sum()), dup_keys,
                        dup_sample, columns)


def write_profiles(con: duckdb.DuckDBPyConnection, run_id: str, profiles: list[TableProfile]) -> None:
    con.execute(PROFILE_DDL)
    for p in profiles:
        con.execute("INSERT INTO governance.profile_table VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [run_id, p.system, p.table, p.file, p.rows, len(p.columns), sum(c.blank for c in p.columns),
                     p.exact_duplicates, p.duplicate_keys, ", ".join(p.key), sum(c.mismatch for c in p.columns),
                     len(p.anomalies)])
        con.executemany("INSERT INTO governance.profile_column VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [(run_id, p.system, p.table, c.ordinal, c.name, c.declared, c.inferred, c.mismatch,
                          c.blank, c.blank / c.rows if c.rows else 0.0, c.distinct, len(c.anomalies))
                         for c in p.columns])
        if p.anomalies:
            con.executemany("INSERT INTO governance.profile_anomaly VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [(run_id, p.system, p.table, a.column, a.anomaly, a.affected, "; ".join(a.samples))
                             for a in p.anomalies])


def profile_sources(con: duckdb.DuckDBPyConnection, run_id: str, sources: list[SourceContract]) -> list[TableProfile]:
    profiles = [profile_table(con, s, t) for s in sources for t in s.tables]
    write_profiles(con, run_id, profiles)
    return profiles


# --------------------------------------------------------------------------- #
# Markdown report
# --------------------------------------------------------------------------- #

def md(text: str) -> str:
    return str(text).replace("|", "\\|")


def code(values: list[str]) -> str:
    return ", ".join(f"`{md(v)}`" for v in values)


def render_report(profiles: list[TableProfile], sources: list[SourceContract], balance: pd.DataFrame,
                  quarantine: pd.DataFrame, header_comment: str | None) -> str:
    labels = {s.system: s.label for s in sources}
    out = [
        "# Source profiling report",
        "",
        "**All data profiled here is synthetic.** It is generated for the FabSync demonstrator and represents",
        "no real company, person, supplier or transaction.",
        "",
        "Produced by `make ingest` from the raw layer of the warehouse, before any cleaning. Every figure is also",
        "queryable in `governance.profile_table`, `governance.profile_column` and `governance.profile_anomaly`.",
    ]
    if header_comment:
        out += ["", "Every source file opens with a SYNTHETIC DATA header comment. The raw layer records it, with the",
                "file's SHA-256, in `governance.source_file`."]
    out += [
        "",
        "Inferred type is what a naive loader would guess from the values as received. A mismatch means that",
        "guess disagrees with the contract, so loading without a contract would mistype the column.",
        "",
        "## Summary",
        "",
        "| System | Table | Rows | Blank cells | Exact duplicates | Duplicate keys | Type mismatches | Anomalies |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for p in profiles:
        cells = p.rows * len(p.columns)
        blank = sum(c.blank for c in p.columns)
        out.append(f"| {labels[p.system]} | `{p.table}` | {p.rows:,} | {blank:,} ({blank / cells:.1%}) | "
                   f"{p.exact_duplicates:,} | {p.duplicate_keys:,} | {sum(c.mismatch for c in p.columns)} | "
                   f"{len(p.anomalies)} |")

    out += ["", "## What staging did with it", "",
            "Every row that left the raw layer is either in staging or in quarantine. "
            "`governance.table_balance` holds this table; `governance.quarantine` holds each rejected row with "
            "its original values.", "",
            "| Source file | Raw rows | Staged | Quarantined | Balanced |",
            "| --- | ---: | ---: | ---: | :---: |"]
    for r in balance.itertuples():
        out.append(f"| `{r.source_file}` | {r.raw_rows:,} | {r.staged_rows:,} | {r.quarantined_rows:,} | "
                   f"{'yes' if r.balanced else '**no**'} |")
    if len(quarantine):
        out += ["", "| Source file | Rule | Column | Rows |", "| --- | --- | --- | ---: |"]
        for r in quarantine.itertuples():
            column = r.failing_column if isinstance(r.failing_column, str) else "(whole row)"
            out.append(f"| `{r.source_file}` | {r.rule_id} {md(r.rule_description)} | {column} | {r.rows:,} |")

    for s in sources:
        out += ["", f"## {s.label}", ""]
        out += [f"- {k}: {v}" for k, v in s.conventions]
        for p in [p for p in profiles if p.system == s.system]:
            out += ["", f"### `{p.table}`", "", f"File `{p.file}`, {p.rows:,} rows. "
                    f"Natural key: {', '.join(p.key) or 'none declared'}.", "",
                    "| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |",
                    "| ---: | --- | --- | --- | ---: | ---: | ---: |"]
            for c in p.columns:
                inferred = f"**{c.inferred}**" if c.mismatch else c.inferred
                out.append(f"| {c.ordinal} | `{c.name}` | {c.declared} | {inferred} | {c.blank / c.rows:.1%} | "
                           f"{c.distinct:,} | {len(c.anomalies) or ''} |")
            if p.anomalies:
                out += ["", "| Column | Anomaly | Values | Sample |", "| --- | --- | ---: | --- |"]
                for a in p.anomalies:
                    out.append(f"| `{a.column}` | {md(a.anomaly)} | {a.affected:,} | {code(a.samples)} |")
            else:
                out += ["", "No anomalies."]
    out.append("")
    return "\n".join(out)
