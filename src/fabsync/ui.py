"""Shared building blocks for the FabSync Streamlit app: data access, formatting, charts, clickable figures.

Design rules applied here so every page follows them:

* one accent colour for interface emphasis; one fixed colour per source system,
  used for that system everywhere it appears
* charts label their data directly rather than through legends, label axes
  with units, and never use 3D, dual axes, or pies
* currency in pounds with thousands separators
* every headline figure is a button that opens the rows behind it, and any row
  that carries a source file and line can be traced to the line as received

All data shown is synthetic.
"""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

from fabsync.palette import ACCENT, GRID, INK, MUTED, RULE, SYSTEM_COLOURS, SYSTEM_LABELS  # noqa: F401

DEFAULT_WAREHOUSE = Path("data/warehouse/fabsync.duckdb")
BANNER = "Demonstration prototype. All data is synthetic."

MONEY_HINTS = ("value", "amount", "cost", "gap", "price", "turnover", "invoiced", "exposure", "expected_invoice",
               "_material", "_labour", "_subcontract", "_plant", "net_adjustment", "sales")
NOT_MONEY_HINTS = ("pct", "accuracy", "ratio", "kg", "hours", "rank", "score", "count", "lines", "rows", "_id")

CSS = f"""
<style>
.fs-banner {{ background: #F5F7FA; border-left: 4px solid {ACCENT}; color: {INK}; padding: 0.45rem 0.9rem;
             font-size: 0.9rem; margin-bottom: 0.6rem; }}
[class*="st-key-hl_"] button p {{ font-size: 1.7rem; font-weight: 600; color: {ACCENT}; }}
[class*="st-key-hl_"] button {{ padding: 0; min-height: 0; }}
[class*="st-key-hlrow_"] button p {{ font-weight: 600; color: {ACCENT}; }}
.fs-system {{ display: inline-block; width: 0.8rem; height: 0.8rem; margin-right: 0.35rem; vertical-align: -0.05rem; }}
</style>
"""


# ---- data ------------------------------------------------------------------------------- #

def warehouse() -> Path:
    """The warehouse the app reads; FABSYNC_WAREHOUSE overrides the default, for tests."""
    return Path(os.environ.get("FABSYNC_WAREHOUSE", DEFAULT_WAREHOUSE))


@st.cache_data(show_spinner=False, max_entries=512)
def _query(sql: str, params: tuple, path: str, mtime: float) -> pd.DataFrame:
    con = duckdb.connect(path, read_only=True)
    try:
        return con.execute(sql, list(params)).df()
    finally:
        con.close()


def q(sql: str, params: list | tuple = ()) -> pd.DataFrame:
    """Run a read-only query, cached until the warehouse file changes."""
    path = warehouse()
    return _query(sql, tuple(params), str(path), path.stat().st_mtime if path.exists() else 0.0)


def scalar(sql: str, params: list | tuple = ()):
    frame = q(sql, params)
    return None if frame.empty else frame.iloc[0, 0]


def has_table(schema: str, table: str) -> bool:
    if not warehouse().exists():
        return False
    return bool(scalar("SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
                       (schema, table)))


def require(schema: str, table: str, command: str) -> None:
    if not has_table(schema, table):
        st.info(f"This page needs results that are not in the warehouse yet. Run `{command}`, or `make run-all`.")
        st.stop()


# ---- formatting ----------------------------------------------------------------------------- #

def gbp(v, dp: int = 0) -> str:
    if v is None or pd.isna(v):
        return "–"
    return f"-£{-v:,.{dp}f}" if v < 0 else f"£{v:,.{dp}f}"


def fmt(v, unit: str) -> str:
    if v is None or pd.isna(v):
        return "no data"
    return {"GBP": gbp(v), "percent": f"{v:.1f}%", "count": f"{int(v):,}", "tonnes": f"{v:,.1f} t",
            "kg": f"{v:,.0f} kg", "hours": f"{v:,.0f} h", "index": f"{v:.1f}"}.get(unit, f"{v:,}")


def system_swatch(system: str) -> str:
    return (f'<span class="fs-system" style="background:{SYSTEM_COLOURS[system]}"></span>'
            f"{SYSTEM_LABELS[system]}")


def is_money(col: str, series: pd.Series) -> bool:
    name = col.lower()
    return (pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
            and any(h in name for h in MONEY_HINTS) and not any(h in name for h in NOT_MONEY_HINTS))


def table(frame: pd.DataFrame, height: int | None = None, money: tuple[str, ...] = (),
          hide: tuple[str, ...] = ("_run_id", "_loaded_at", "match_run_id", "matched_at")) -> None:
    """A dataframe with money in pounds and run bookkeeping columns hidden."""
    frame = frame[[c for c in frame.columns if c not in hide]]
    config = {}
    for c in frame.columns:
        if c in money or is_money(c, frame[c]):
            config[c] = st.column_config.NumberColumn(c, format="£%,.2f")
        elif pd.api.types.is_float_dtype(frame[c]):
            config[c] = st.column_config.NumberColumn(c, format="%,.2f")
    kwargs = {"height": height} if height else {}
    st.dataframe(frame, hide_index=True, width="stretch", column_config=config, **kwargs)


# ---- page furniture ---------------------------------------------------------------------------- #

def page_setup() -> None:
    """Styles and the persistent banner. Called once per run by the app entry point."""
    st.html(CSS)
    st.html(f'<div class="fs-banner">{BANNER}</div>')


def title(text: str, lead: str | None = None) -> None:
    st.title(text)
    if lead:
        st.markdown(lead)


# ---- clickable figures -------------------------------------------------------------------------- #

@st.dialog("Rows behind this figure", width="large")
def _rows_dialog(label: str, value: str, rows_sql: str, explanation: str | None) -> None:
    rows = q(rows_sql)
    st.markdown(f"**{label}: {value}**")
    if explanation:
        st.caption(explanation)
    st.caption(f"{len(rows):,} rows. Source file and line are shown where the row came from a file.")
    table(rows, height=380)
    with st.expander("Query"):
        st.code(rows_sql, language="sql")
    trace_rows(rows, key="dialog_trace")


def headline(label: str, value: str, rows_sql: str, key: str, note: str | None = None,
             explanation: str | None = None) -> None:
    """A headline figure whose number opens the rows behind it."""
    with st.container(border=True):
        st.caption(label)
        if st.button(value, key=f"hl_{key}", type="tertiary", help="Show the rows behind this figure"):
            _rows_dialog(label, value, rows_sql, explanation)
        if note:
            st.caption(note)


def figure_row(label: str, value: str, rows_sql: str, key: str, explanation: str | None = None) -> None:
    """A compact figure for lists: the label, and the value as a link to its rows."""
    left, right = st.columns([3, 1])
    left.markdown(label)
    if right.button(value, key=f"hlrow_{key}", type="tertiary", help="Show the rows behind this figure"):
        _rows_dialog(label, value, rows_sql, explanation)


def trace_rows(rows: pd.DataFrame, key: str) -> None:
    """Let the viewer pick a row and see the source line it came from, as received."""
    cols = {"source_file", "source_row"} if {"source_file", "source_row"} <= set(rows.columns) else (
        {"_source_file", "_source_row"} if {"_source_file", "_source_row"} <= set(rows.columns) else None)
    if not cols or rows.empty:
        return
    f, n = sorted(cols)
    traceable = rows.dropna(subset=[f, n])
    traceable = traceable[traceable[f].astype(str).str.endswith(".csv")]
    if traceable.empty:
        return
    options = list(range(min(len(traceable), 500)))
    pick = st.selectbox("Trace a row to its source line", options, key=key,
                        format_func=lambda i: f"{traceable.iloc[i][f]} line {int(traceable.iloc[i][n])}")
    src = traceable.iloc[pick]
    system, tbl = str(src[f]).removesuffix(".csv").split("/")
    raw = q(f"SELECT * EXCLUDE (_run_id, _loaded_at) FROM raw.{system}_{tbl} WHERE _source_row = ?",
            (int(src[n]),))
    st.caption(f"As received in {src[f]}, line {int(src[n])}:")
    table(raw)


# ---- charts --------------------------------------------------------------------------------------- #

def _base(chart: alt.Chart, height: int) -> alt.Chart:
    return (chart.properties(height=height)
            .configure_view(stroke=None)
            .configure_axis(labelColor=INK, titleColor=INK, gridColor=GRID, domainColor=RULE, tickColor=RULE,
                            labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
            .configure_text(color=INK))


def bar_h(frame: pd.DataFrame, category: str, value: str, x_title: str, label: str | None = None,
          colour: str | None = None, sort: str = "-x", height: int | None = None, colours: dict | None = None,
          target: float | None = None) -> None:
    """Horizontal bars, each labelled with its value at the bar end; no legend."""
    frame = frame.copy()
    label = label or value
    if colours:
        frame["_colour"] = frame[category].map(colours).fillna(MUTED)
        fill = alt.Color("_colour:N", scale=None, legend=None)
    else:
        fill = alt.value(colour or ACCENT)
    y = alt.Y(f"{category}:N", sort=sort, title=None, axis=alt.Axis(labelLimit=260))
    bars = alt.Chart(frame).mark_bar(size=16).encode(
        x=alt.X(f"{value}:Q", title=x_title, axis=alt.Axis(format=",.0f")), y=y, color=fill,
        tooltip=[category, alt.Tooltip(f"{label}:N" if label != value else f"{value}:Q", title=x_title)])
    text = alt.Chart(frame).mark_text(align="left", dx=4, fontSize=12).encode(
        x=f"{value}:Q", y=y, text=f"{label}:N" if label != value else alt.Text(f"{value}:Q", format=",.1f"))
    layers = [bars, text]
    if target is not None:
        layers.append(alt.Chart(pd.DataFrame({"t": [target]})).mark_rule(color=INK, strokeDash=[4, 3])
                      .encode(x="t:Q"))
    h = height or max(120, 26 * len(frame) + 40)
    st.altair_chart(_base(alt.layer(*layers), h), width="stretch")


def line(frame: pd.DataFrame, x: str, y: str, x_title: str, y_title: str, series: str | None = None,
         colours: dict | None = None, target: float | None = None, y_format: str = ",.0f", height: int = 260) -> None:
    """A line chart; with several series, each is labelled at its last point instead of a legend."""
    frame = frame.copy()
    enc = {"x": alt.X(f"{x}:T", title=x_title), "y": alt.Y(f"{y}:Q", title=y_title, axis=alt.Axis(format=y_format))}
    if series:
        palette = colours or {}
        domain = sorted(frame[series].dropna().unique())
        rng = [palette.get(s, ACCENT if i == 0 else MUTED) for i, s in enumerate(domain)]
        colour = alt.Color(f"{series}:N", scale=alt.Scale(domain=domain, range=rng), legend=None)
        lines = alt.Chart(frame).mark_line(strokeWidth=2).encode(**enc, color=colour, tooltip=[x, series, y])
        last = frame.sort_values(x).groupby(series).tail(1)
        labels = alt.Chart(last).mark_text(align="left", dx=6, fontSize=12).encode(
            x=f"{x}:T", y=f"{y}:Q", text=f"{series}:N", color=colour)
        layers = [lines, labels]
    else:
        layers = [alt.Chart(frame).mark_line(strokeWidth=2, color=ACCENT).encode(**enc, tooltip=[x, y])]
    if target is not None:
        layers.append(alt.Chart(pd.DataFrame({"t": [target], "lbl": [f"target {target:g}"]}))
                      .mark_rule(color=INK, strokeDash=[4, 3]).encode(y="t:Q"))
    st.altair_chart(_base(alt.layer(*layers), height), width="stretch")


def columns_chart(frame: pd.DataFrame, x: str, y: str, x_title: str, y_title: str, label: str | None = None,
                  colour: str = ACCENT, sort: list | None = None, height: int = 240, y_format: str = ",.0f") -> None:
    """Vertical bars for ordered categories (age buckets, months), each labelled on top."""
    xenc = alt.X(f"{x}:N" if sort else f"{x}:O", title=x_title, sort=sort, axis=alt.Axis(labelAngle=0))
    bars = alt.Chart(frame).mark_bar(color=colour, size=36).encode(
        x=xenc, y=alt.Y(f"{y}:Q", title=y_title, axis=alt.Axis(format=y_format)), tooltip=[x, y])
    text = alt.Chart(frame).mark_text(dy=-6, fontSize=12).encode(
        x=xenc, y=f"{y}:Q", text=f"{label}:N" if label else alt.Text(f"{y}:Q", format=y_format))
    st.altair_chart(_base(alt.layer(bars, text), height), width="stretch")
