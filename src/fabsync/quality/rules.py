"""Load and validate the declarative rule set in config/dq_rules.yaml.

The engine knows nothing about any particular rule. Everything a rule is (its
business meaning, owner, severity, check and threshold) comes from the file,
and a file that breaks the schema is refused before anything runs.
"""

from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

RULES_PATH = Path("config/dq_rules.yaml")
DIMENSIONS = ("completeness", "validity", "consistency", "uniqueness", "timeliness", "accuracy")
SEVERITIES = ("critical", "high", "medium", "low")
SYSTEMS = ("corvus_mrp", "finance", "shop_floor")
REQUIRED = ("id", "name", "description", "dimension", "severity", "system_of_record", "owner", "threshold",
            "consequence", "corrective_action", "check")
PARAM_RE = re.compile(r"\$\{(\w+)\}")


class RuleError(ValueError):
    """The rule file does not meet the schema."""


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    description: str
    dimension: str
    severity: str
    system_of_record: str
    owner: str
    threshold: float
    consequence: str
    corrective_action: str
    check_type: str  # sql or python
    check: str
    covers_defects: tuple[int, ...] = ()


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[Rule, ...]
    parameters: dict
    weights: dict[str, float]
    roles: tuple[str, ...]
    sha256: str

    def sql(self, rule: Rule) -> str:
        def sub(m: re.Match) -> str:
            if m.group(1) not in self.parameters:
                raise RuleError(f"{rule.id}: unknown parameter ${{{m.group(1)}}}")
            return str(self.parameters[m.group(1)])
        return PARAM_RE.sub(sub, rule.check)


def resolve_callable(path: str):
    module, _, name = path.partition(":")
    return getattr(importlib.import_module(module), name)


def load_rules(path: Path = RULES_PATH) -> RuleSet:
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    weights = {k: float(v) for k, v in doc.get("severity_weights", {}).items()}
    roles = tuple(doc.get("roles", ()))
    problems: list[str] = []
    if set(weights) != set(SEVERITIES):
        problems.append(f"severity_weights must define exactly {', '.join(SEVERITIES)}")
    rules, seen = [], set()
    for i, raw in enumerate(doc.get("rules") or [], start=1):
        where = raw.get("id", f"rule #{i}")
        missing = [f for f in REQUIRED if raw.get(f) in (None, "")]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        if raw["id"] in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(raw["id"])
        if raw["dimension"] not in DIMENSIONS:
            problems.append(f"{where}: dimension '{raw['dimension']}' not one of {', '.join(DIMENSIONS)}")
        if raw["severity"] not in SEVERITIES:
            problems.append(f"{where}: severity '{raw['severity']}' not one of {', '.join(SEVERITIES)}")
        if raw["system_of_record"] not in SYSTEMS:
            problems.append(f"{where}: system_of_record '{raw['system_of_record']}' not one of {', '.join(SYSTEMS)}")
        if roles and raw["owner"] not in roles:
            problems.append(f"{where}: owner '{raw['owner']}' is not a declared role")
        if not 0 < float(raw["threshold"]) <= 1:
            problems.append(f"{where}: threshold must be above 0 and at most 1")
        check = raw["check"]
        kinds = [k for k in ("sql", "python") if k in check]
        if len(kinds) != 1:
            problems.append(f"{where}: check must have exactly one of sql or python")
            continue
        if kinds[0] == "python":
            try:
                resolve_callable(check["python"])
            except (ImportError, AttributeError, ValueError) as exc:
                problems.append(f"{where}: python check {check['python']} not found ({exc})")
        rules.append(Rule(raw["id"], raw["name"], " ".join(raw["description"].split()), raw["dimension"],
                          raw["severity"], raw["system_of_record"], raw["owner"], float(raw["threshold"]),
                          " ".join(raw["consequence"].split()), " ".join(raw["corrective_action"].split()),
                          kinds[0], check[kinds[0]].strip(), tuple(raw.get("covers_defects") or ())))
    if not rules and not problems:
        problems.append("no rules defined")
    if problems:
        raise RuleError(f"{path}: " + "; ".join(problems))
    return RuleSet(tuple(rules), dict(doc.get("parameters") or {}), weights, roles,
                   hashlib.sha256(text.encode("utf-8")).hexdigest())
