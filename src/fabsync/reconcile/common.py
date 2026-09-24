"""Shared structure for the reconciliation engines.

Every engine returns an :class:`EngineResult`: a row-level result set, a
summary, one exposure figure, and a list of :class:`Headline` figures. A
headline is never a free-standing number. It names the table and filter its
rows live in and the aggregate that produces it, so the same definition gives
both the figure and the rows behind it. The pipeline recomputes every headline
from its rows before it finishes, and refuses to publish one that does not
reproduce.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

RECONCILE_CONFIG = Path("config/reconcile.toml")
SCHEMA = "recon"


@dataclass(frozen=True)
class Headline:
    engine: str
    key: str
    label: str
    value: float
    unit: str  # GBP, count, percent, kg, tonnes, hours
    table: str  # recon.<table> holding the rows
    where: str  # filter selecting the rows behind the figure
    aggregate: str  # SQL aggregate over those rows that gives the figure
    explanation: str

    @property
    def value_sql(self) -> str:
        return f"SELECT {self.aggregate} FROM {self.table} WHERE {self.where}"

    @property
    def rows_sql(self) -> str:
        return f"SELECT * FROM {self.table} WHERE {self.where}"


@dataclass
class EngineResult:
    engine: str
    rows: pd.DataFrame
    summary: pd.DataFrame
    exposure: float
    exposure_label: str
    headlines: list[Headline] = field(default_factory=list)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)  # everything to write to recon


def load_config(path: Path = RECONCILE_CONFIG) -> dict:
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    config["as_of"] = date.fromisoformat(config["as_of_date"])
    return config


def age_bucket(days: float | None, buckets: list[int]) -> str | None:
    if days is None or pd.isna(days):
        return None
    lower = 0
    for upper in buckets:
        if days <= upper:
            return f"{lower}-{upper} days"
        lower = upper + 1
    return f"over {buckets[-1]} days"


def bucket_order(buckets: list[int]) -> list[str]:
    labels, lower = [], 0
    for upper in buckets:
        labels.append(f"{lower}-{upper} days")
        lower = upper + 1
    return labels + [f"over {buckets[-1]} days"]
