"""Schema contracts: what each source file is expected to contain.

A contract is declared in code, separately from the data, and drives raw
loading, profiling and staging. Nothing about a file's shape is inferred at
run time; when a file disagrees with its contract the disagreement is recorded
as lineage or quarantine, never patched over.
"""

from __future__ import annotations

from dataclasses import dataclass

TEXT = "text"
INTEGER = "integer"
DECIMAL = "decimal"
DATE = "date"

STAGING_TYPES = {TEXT: "VARCHAR", INTEGER: "INTEGER", DECIMAL: "DECIMAL(18,4)", DATE: "DATE"}


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str = TEXT
    required: bool = False
    formats: tuple[str, ...] = ()  # date formats accepted, tried in order
    domain: tuple[str, ...] = ()  # allowed values after trimming, if constrained
    pattern: str = ""  # canonical form; deviations are profiled and conformed in core, not rejected
    description: str = ""


@dataclass(frozen=True)
class TableContract:
    name: str
    file: str
    columns: tuple[Column, ...]
    key: tuple[str, ...] = ()  # natural key expected to be unique
    description: str = ""

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(name)


@dataclass(frozen=True)
class SourceContract:
    system: str
    label: str
    conventions: tuple[tuple[str, str], ...]
    tables: tuple[TableContract, ...]


class ContractViolation(Exception):
    """A file does not have the columns its contract declares."""


# Every rule the ingestion layer can apply. Rule ids appear in the lineage and
# quarantine tables, so they are stable identifiers, not implementation detail.
RULES: dict[str, str] = {
    "RAW-01": "Load the file exactly as received: every column text, header comment recorded, no value altered",
    "RAW-02": "File columns must match the declared contract",
    "ST-01": "Trim leading and trailing whitespace from every value",
    "ST-02": "Exact duplicate row: first occurrence kept, repeats quarantined",
    "ST-03": "Required column must not be blank",
    "ST-04": "Date must parse with one of the declared formats",
    "ST-05": "Numeric must coerce after removing thousands separators, currency symbols and spaces",
    "ST-06": "Integer column must hold a whole number",
    "ST-07": "Value must be within the declared domain",
    "ST-08": "Natural key must be unique: first occurrence kept, repeats quarantined",
    "ST-09": "Blank text becomes NULL; typed columns cast to declared staging types",
    "CO-01": "Works order reference conformed: five-digit number extracted from free text",
    "CO-02": "Site alias conformed to site code using config/conformance.toml",
    "CO-03": "Job reference conformed to J-YY-NNNN; finance job code derived as YY + sequence without zeros",
    "CO-04": "Operation alias conformed to routing operation using config/conformance.toml",
    "CO-05": "Join to parent recorded as a matched flag; unmatched rows retained, never dropped",
    "CO-06": "Conformed table built from staging with no row loss",
    "MA-01": "Material code and description parsed into section type, dimensions and grade; canonical code emitted",
    "MA-02": "Material golden record built by the documented survivorship rule",
    "MA-03": "Supplier names fuzzy matched within blocks: >=95 auto-accept, 80-95 review queue, <80 never merged",
    "MA-04": "Job crosswalk across MRPII job_no, finance job_code and shop-floor free-text references",
    "MA-05": "Works order free text parsed to a Corvus wo_no; unknown numbers checked for transposition candidates",
}
