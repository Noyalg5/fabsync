"""Where each printed number came from.

During a traceability audit every figure the pack and the app print is a `Traced` value: a number that knows its
source (a warehouse query, a config setting or a document) and writes itself to a ledger each time it is formatted.
Arithmetic keeps the source, so a figure shown as £4.31m or 53.8% still traces to the query behind it. Outside an
audit the ledger is off and a `Traced` value behaves exactly like the number it wraps.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from dataclasses import dataclass

ENV = "FABSYNC_PROVENANCE"
# A number as the pack prints it: thousands in groups of three, an optional pound sign, decimals, m, k or percent.
NUMBER = re.compile(r"(?<![\w.£-])-?£?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:m|k)?%?(?![\w])")


@dataclass(frozen=True)
class Origin:
    kind: str       # warehouse, config or document
    name: str       # what the value is
    detail: str     # the SQL, or the file and key


_LEDGER: list[tuple[str, Origin, str]] | None = None
_SCOPE = ""


def active() -> bool:
    return _LEDGER is not None or os.environ.get(ENV) == "1"


def record(text: str, origin: Origin) -> None:
    if _LEDGER is not None:
        _LEDGER.append((text, origin, _SCOPE))


@contextmanager
def scope(name: str):
    """Tag every entry recorded inside the block with where it is printed, such as one chart of the pack."""
    global _SCOPE
    outer, _SCOPE = _SCOPE, name
    try:
        yield
    finally:
        _SCOPE = outer


@contextmanager
def ledger():
    """Collect every traced number formatted inside the block."""
    global _LEDGER
    outer, _LEDGER = _LEDGER, []
    try:
        yield _LEDGER
    finally:
        _LEDGER = outer if outer is None else outer + _LEDGER


class Traced(float):
    """A number that remembers where it came from, and records itself whenever it is formatted."""

    def __new__(cls, value, origin: Origin):
        obj = super().__new__(cls, value)
        obj.origin = origin
        return obj

    def __format__(self, spec: str) -> str:
        text = float(self).__format__(spec)
        record(text, self.origin)
        return text

    def __reduce__(self):
        return (Traced, (float(self), self.origin))

    def _same(self, value) -> Traced:
        return Traced(value, self.origin)

    def __truediv__(self, other):
        return self._same(float(self) / float(other))

    def __rtruediv__(self, other):
        return self._same(float(other) / float(self))

    def __mul__(self, other):
        return self._same(float(self) * float(other))

    __rmul__ = __mul__

    def __add__(self, other):
        return self._same(float(self) + float(other))

    __radd__ = __add__

    def __sub__(self, other):
        return self._same(float(self) - float(other))

    def __rsub__(self, other):
        return self._same(float(other) - float(self))

    def __neg__(self):
        return self._same(-float(self))

    def __abs__(self):
        return self._same(abs(float(self)))

    def __round__(self, n=None):
        return self._same(round(float(self), n or 0))


class TracedInt(int):
    """A whole number from config or a count, recorded whenever it is formatted."""

    def __new__(cls, value, origin: Origin):
        obj = super().__new__(cls, int(value))
        obj.origin = origin
        return obj

    def __format__(self, spec: str) -> str:
        text = int(self).__format__(spec)
        record(text, self.origin)
        return text

    def __str__(self) -> str:
        return self.__format__("")

    def __reduce__(self):
        return (TracedInt, (int(self), self.origin))

    def __add__(self, other):
        if isinstance(other, float):
            return Traced(int(self) + other, self.origin)
        return TracedInt(int(self) + int(other), self.origin)

    __radd__ = __add__

    def __sub__(self, other):
        return TracedInt(int(self) - int(other), self.origin)


WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
         11: "eleven", 12: "twelve", 13: "thirteen"}


def total(values, name: str | None = None, empty=0):
    """Sum that keeps the source: starts from the first value, not from a plain zero. Given a name, the sum is
    recorded under it, from the same query, rather than under the name of its first value."""
    values = list(values)
    if not values:
        return empty
    out = values[0]
    for v in values[1:]:
        out = out + v
    if name and hasattr(out, "origin"):
        out = type(out)(out, Origin(out.origin.kind, name, out.origin.detail))
    return out


def word(n) -> str:
    """A count written as a word, recorded with the source of the count."""
    text = WORDS[int(n)]
    if hasattr(n, "origin"):
        record(text, n.origin)
    return text


def trace(value, kind: str, name: str, detail: str = ""):
    """Wrap a value with its origin: whole numbers as TracedInt, anything else numeric as Traced."""
    origin = Origin(kind, name, detail)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return TracedInt(value, origin)
    try:
        return Traced(float(value), origin)
    except (TypeError, ValueError):
        return value


def trace_frame(frame, name: str, sql: str):
    """Every numeric cell of a frame as a Traced value naming its row and column, kept in an object column.

    A row is named by its leading text columns, up to two, such as a job number or a site and section type;
    a frame that starts with a number names its rows by position.
    """
    import pandas as pd
    out = frame.copy()
    labels = []
    for col in frame.columns[:2]:
        if frame[col].dtype.kind in "iuf":
            break
        labels.append(col)
    if labels:
        rows = [" ".join(str(v) for v in values) + ", " for values in zip(*(frame[c] for c in labels), strict=True)]
    else:
        rows = [f"row {i}, " for i in range(1, len(frame) + 1)] if len(frame) > 1 else [""] * len(frame)
    for col in frame.columns:
        if frame[col].dtype.kind in "iuf":
            values = [trace(v.item() if hasattr(v, "item") else v, "warehouse", f"{name}: {row}{col}", sql)
                      for v, row in zip(frame[col], rows, strict=True)]
            out[col] = pd.Series(values, index=frame.index, dtype=object)  # a list would be converted back to float
    return out


NUMBER_WORD = re.compile(r"\b(" + "|".join(WORDS.values()) + r")\b", re.I)


def numbers(text: str) -> list[str]:
    """Every number in a piece of text, figures and number words alike, in reading order."""
    found = [(m.start(), m.group(0)) for m in NUMBER.finditer(str(text))]
    found += [(m.start(), m.group(1).lower()) for m in NUMBER_WORD.finditer(str(text))]
    return [token for _, token in sorted(found)]


def quote(text: str, kind: str, name: str, detail: str = "") -> str:
    """Text quoted from config or a document: every number in it is recorded with that source."""
    for token in numbers(text):
        record(token, Origin(kind, name, detail))
    return text
