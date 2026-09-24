"""Shared machinery for the matchers: configuration, scoring bands, table writing, lineage.

Every match record written by any matcher carries the same audit columns:
``method`` (how the match was made), ``score`` (0-100), ``matched_on`` (the
evidence in words), ``status`` (auto, review or unmatched), ``matched_at`` and
``match_run_id``. Source values always sit alongside the canonical value.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from fabsync.ingest.warehouse import Recorder

MATCHING_CONFIG = Path("config/matching.toml")
AUDIT_COLUMNS = ["method", "score", "matched_on", "status", "matched_at", "match_run_id"]


@dataclass
class MatchContext:
    con: duckdb.DuckDBPyConnection
    rec: Recorder
    config: dict
    run_id: str
    matched_at: datetime
    tables: list[str] = field(default_factory=list)

    @property
    def auto(self) -> float:
        return float(self.config["thresholds"]["auto_accept"])

    @property
    def floor(self) -> float:
        return float(self.config["thresholds"]["review_floor"])

    def status(self, score: float | None) -> str:
        """The band a score falls in. Nothing below the review floor is ever merged."""
        if score is None or pd.isna(score) or score < self.floor:
            return "unmatched"
        return "auto" if score >= self.auto else "review"

    def minutes(self, domain: str) -> float:
        return float(self.config["effort_minutes"][domain])

    def df(self, sql: str, params: list | None = None) -> pd.DataFrame:
        return self.con.execute(sql, params or []).df()

    def write(self, table: str, frame: pd.DataFrame, audit: bool = True) -> int:
        """Create ``table`` from ``frame``; audit columns are stamped with this run."""
        frame = frame.copy()
        if audit:
            frame["matched_at"] = self.matched_at
            frame["match_run_id"] = self.run_id
        self.con.execute(f"DROP TABLE IF EXISTS {table}")
        self.con.register("_match_frame", frame)
        self.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _match_frame")
        self.con.unregister("_match_frame")
        self.tables.append(table)
        return len(frame)

    def lineage(self, *, rule_id: str, source_table: str, source_file: str, target_table: str, rows: int,
                affected: int, detail: str, system: str = "multiple") -> None:
        self.rec.lineage(layer="match", source_system=system, source_table=source_table, source_file=source_file,
                         target_table=target_table, rule_id=rule_id, rows_in=rows, rows_out=rows,
                         rows_affected=affected, detail=detail, started_at=self.matched_at)


def load_config(path: Path = MATCHING_CONFIG) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))
