"""Dataset-quality report: one JSON document plus a Markdown rendering.

Every number is computed from the data actually processed. The report states
where the data came from (``data_origin``: live, local_csv, synthetic or
in_memory), so fixture or synthetic results are never mistaken for market data.
It is descriptive only: nothing in the report is fed back into processing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from adaptive_portfolio.data.processing import ProcessedPrices
from adaptive_portfolio.data.splits import SplitAssignment
from adaptive_portfolio.data.validation import RawSummary

ORIGIN_WARNINGS = {
    "synthetic": "SYNTHETIC DATA: generated prices for testing; not market data. Do not "
    "draw any empirical conclusion from it.",
    "in_memory": "FIXTURE DATA: in-memory test frames; not market data.",
    "local_csv": "Local CSV data: provenance is whatever produced the files; record it.",
    "live": "Live provider data (unofficial, revisable). Adjusted histories can change "
    "between downloads; the snapshot freezes one retrieval only.",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return pd.Timestamp(value).date().isoformat()


def build_quality_report(
    *,
    manifest: Mapping[str, Any],
    dataset_id: str,
    processed_id: str,
    price_field: str,
    universe: Sequence[str],
    raw_summaries: Mapping[str, RawSummary],
    aligned: pd.DataFrame,
    processed: ProcessedPrices,
    returns: pd.DataFrame,
    assignment: SplitAssignment,
    missing_policy: str,
    max_abs_return_threshold: float,
) -> dict[str, Any]:
    """Assemble the machine-readable report (deterministic for identical inputs)."""
    origin = manifest["provider"]["data_origin"]
    calendar = processed.calendar
    sessions_per_year = calendar.year.value_counts().sort_index()
    calendar_gaps = calendar.to_series().diff().dropna().dt.days

    per_instrument = []
    for instrument in universe:
        raw = raw_summaries[instrument]
        prices = processed.prices[instrument]
        rets = returns[instrument]
        per_instrument.append(
            {
                "instrument": instrument,
                "raw_rows": raw.rows,
                "raw_missing_price_rows": raw.missing_price_rows,
                "first_observation": raw.first_date.isoformat(),
                "last_observation": raw.last_date.isoformat(),
                "missing_cells_on_observed_calendar": int(aligned[instrument].isna().sum()),
                "max_gap_between_observations_days": raw.max_calendar_gap_days,
                "dividend_events_in_raw": raw.dividend_events,
                "split_events_in_raw": raw.split_events,
                "processed_price_min": float(prices.min()),
                "processed_price_max": float(prices.max()),
                "return_min": float(rets.min()),
                "return_max": float(rets.max()),
            }
        )

    abs_returns = returns[list(universe)].abs()
    warnings = [ORIGIN_WARNINGS.get(origin, f"Unknown data origin {origin!r}.")]
    if price_field == "close":
        warnings.append("price_field is 'close': returns exclude dividends (price return only).")
    spanning = int((returns["sessions_spanned"] > 1).sum())
    if spanning:
        warnings.append(
            f"{spanning} return(s) span more than one observed session because sessions "
            "were dropped; see missing_data.dropped_sessions."
        )

    return {
        "report_schema_version": 1,
        "data_origin": origin,
        "warnings": warnings,
        "dataset": {
            "raw_dataset_id": dataset_id,
            "processed_dataset_id": processed_id,
            "provider": manifest["provider"]["name"],
            "provider_version": manifest["provider"]["version"],
            "retrieved_at_utc": manifest["retrieved_at_utc"],
            "request": manifest["request"],
            "price_field": price_field,
        },
        "instruments": {"count": len(universe), "per_instrument": per_instrument},
        "calendar": {
            "definition": "union of dates with at least one observed price",
            "observed_sessions": len(calendar),
            "first_session": _iso(calendar[0]),
            "last_session": _iso(calendar[-1]),
            "max_gap_between_sessions_days": int(calendar_gaps.max()) if len(calendar_gaps) else 0,
            "sessions_per_calendar_year": {str(k): int(v) for k, v in sessions_per_year.items()},
        },
        "integrity": {
            "duplicate_observations": 0,
            "duplicate_rule": "duplicate or unsorted dates raise an error before processing",
            "non_positive_or_infinite_prices": 0,
            "invalid_price_rule": "non-positive or infinite prices raise an error",
        },
        "missing_data": {
            "policy": missing_policy,
            "missing_cells": processed.missing_cells,
            "dropped_sessions": [
                {"date": _iso(d.date), "missing_instruments": list(d.missing_instruments)}
                for d in processed.dropped_sessions
            ],
            "returns_spanning_multiple_sessions": spanning,
            "forward_fill_or_interpolation": "never applied",
        },
        "exclusions": {
            "instruments": [],
            "instrument_rule": "instruments with insufficient coverage raise an error; none "
            "are dropped silently",
            "sessions": len(processed.dropped_sessions),
        },
        "processed": {
            "sessions": len(processed.prices),
            "first_session": _iso(processed.prices.index[0]),
            "last_session": _iso(processed.prices.index[-1]),
        },
        "returns": {
            "definition": "simple return P_t / P_prev - 1 between consecutive retained sessions",
            "rows": len(returns),
            "first_period_end": _iso(returns.index[0]),
            "last_period_end": _iso(returns.index[-1]),
            "max_abs_return_observed": float(abs_returns.to_numpy().max()),
            "max_abs_return_threshold": max_abs_return_threshold,
        },
        "splits": assignment.summary(),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Human-readable version of :func:`build_quality_report` output."""
    ds = report["dataset"]
    cal = report["calendar"]
    miss = report["missing_data"]
    rets = report["returns"]
    lines = [
        "# Dataset quality report",
        "",
        f"**Data origin:** `{report['data_origin']}`",
        "",
        *[f"> {w}" for w in report["warnings"]],
        "",
        "## Dataset",
        "",
        f"- Provider: {ds['provider']} ({ds['provider_version']})",
        f"- Retrieved (UTC): {ds['retrieved_at_utc']}",
        f"- Raw dataset id: `{ds['raw_dataset_id']}`; processed id: `{ds['processed_dataset_id']}`",
        f"- Requested: {ds['request']['start']} to {ds['request']['end']}, "
        f"{ds['request']['frequency']}, price field `{ds['price_field']}`",
        "",
        "## Calendar and coverage",
        "",
        f"- Observed sessions: {cal['observed_sessions']} "
        f"({cal['first_session']} to {cal['last_session']}); "
        f"largest gap {cal['max_gap_between_sessions_days']} day(s)",
        f"- Processed sessions: {report['processed']['sessions']} "
        f"({report['processed']['first_session']} to {report['processed']['last_session']})",
        "",
        "| Instrument | Raw rows | First | Last | Missing cells | Dividends | Splits "
        "| Min return | Max return |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["instruments"]["per_instrument"]:
        lines.append(
            f"| {item['instrument']} | {item['raw_rows']} | {item['first_observation']} "
            f"| {item['last_observation']} | {item['missing_cells_on_observed_calendar']} "
            f"| {item['dividend_events_in_raw']} | {item['split_events_in_raw']} "
            f"| {item['return_min']:+.4f} | {item['return_max']:+.4f} |"
        )
    lines += [
        "",
        "## Missing data and integrity",
        "",
        f"- Policy: `{miss['policy']}`; missing cells: {miss['missing_cells']}; "
        f"dropped sessions: {len(miss['dropped_sessions'])}; returns spanning several "
        f"sessions: {miss['returns_spanning_multiple_sessions']}",
        *[
            f"  - dropped {d['date']}: missing {', '.join(d['missing_instruments'])}"
            for d in miss["dropped_sessions"]
        ],
        f"- Duplicate observations: {report['integrity']['duplicate_observations']} "
        "(duplicates raise an error)",
        f"- Returns: {rets['rows']} rows; max |return| {rets['max_abs_return_observed']:.4f} "
        f"(threshold {rets['max_abs_return_threshold']})",
        "",
        "## Temporal splits",
        "",
        "| Partition | Configured | Observed first | Observed last | Rows |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, part in report["splits"]["partitions"].items():
        lines.append(
            f"| {name} | {part['configured_start']} to {part['configured_end']} "
            f"| {part['first_date']} | {part['last_date']} | {part['count']} |"
        )
    excluded = report["splits"]["excluded"]
    lines += [
        "",
        f"Excluded rows: {excluded['before_train']} before train, "
        f"{excluded['between_partitions']} between partitions, "
        f"{excluded['after_test']} after test.",
        "",
    ]
    return "\n".join(lines)
