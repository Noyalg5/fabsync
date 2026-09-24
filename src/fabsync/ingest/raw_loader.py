"""Raw layer: load each source file exactly as received.

Every value is stored as text with its whitespace intact. Each row carries the
file it came from and its physical line number, so any later row can be traced
back to the line a person would see opening the file in an editor. The
SYNTHETIC DATA header comment and a SHA-256 of the file are recorded in
governance.source_file.
"""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

import duckdb
import pandas as pd

from fabsync.ingest.contracts import ContractViolation, SourceContract, TableContract
from fabsync.ingest.warehouse import Recorder, now


def raw_table_name(system: str, table: str) -> str:
    return f"{system}_{table}"


def read_source_file(path: Path) -> tuple[str, str | None, list[str], list[tuple[int, list[str]]], int]:
    """Return sha256, header comment, column header, (line number, fields) per data row, byte size."""
    data = path.read_bytes()
    text = data.decode("utf-8")
    comment = None
    offset = 0
    if text.startswith("#"):
        comment, _, text = text.partition("\n")
        offset = 1
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader)
    rows = [(reader.line_num + offset, rec) for rec in reader]
    return hashlib.sha256(data).hexdigest(), comment, header, rows, len(data)


def load_raw_table(con: duckdb.DuckDBPyConnection, rec: Recorder, raw_dir: Path, source: SourceContract,
                   table: TableContract) -> int:
    started = now()
    path = raw_dir / table.file
    sha, comment, header, rows, size = read_source_file(path)
    if header != table.column_names:
        raise ContractViolation(
            f"{table.file}: columns {header} do not match contract {table.column_names} (RAW-02)")

    good = [(line, fields) for line, fields in rows if len(fields) == len(header)]
    ragged = [(line, fields) for line, fields in rows if len(fields) != len(header)]
    frame = pd.DataFrame([fields for _, fields in good], columns=header, dtype=str)
    frame["_source_file"] = table.file
    frame["_source_row"] = [line for line, _ in good]
    frame["_run_id"] = rec.run_id
    frame["_loaded_at"] = started

    name = raw_table_name(source.system, table.name)
    select = ", ".join(f'CAST("{c}" AS VARCHAR) AS "{c}"' for c in header)
    con.register("_raw_frame", frame)
    con.execute(f"""CREATE TABLE raw.{name} AS SELECT {select}, _source_file, CAST(_source_row AS INTEGER)
                    AS _source_row, _run_id, _loaded_at FROM _raw_frame""")
    con.unregister("_raw_frame")

    if ragged:
        bad = pd.DataFrame({"_source_row": [line for line, _ in ragged],
                            "_raw_line": [",".join(fields) for _, fields in ragged]})
        rec.quarantine(layer="raw", source_system=source.system, source_table=table.name, source_file=table.file,
                       rule_id="RAW-02", rows=bad, failing_column=None, originals=bad, columns=["_raw_line"])
        rec.flush()

    con.execute("INSERT INTO governance.source_file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [rec.run_id, source.system, table.name, table.file, sha, size, comment, len(rows), started])
    rec.lineage(layer="raw", source_system=source.system, source_table=table.name, source_file=table.file,
                target_table=f"raw.{name}", rule_id="RAW-01", rows_in=len(rows), rows_out=len(good),
                rows_rejected=len(ragged), detail=f"sha256 {sha[:12]}, {size:,} bytes, all columns text",
                started_at=started)
    return len(good)
