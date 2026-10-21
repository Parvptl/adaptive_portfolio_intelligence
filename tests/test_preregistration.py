"""Milestone D (core): the Gate 3 pre-registration schema and the repository's DRAFT file."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from adaptive_portfolio.config import (
    PREREGISTRATION_ITEMS,
    ConfigError,
    PreregistrationConfig,
    load_evaluation_config,
    load_preregistration,
)
from conftest import CONFIG_DIR


def _draft() -> dict:
    return yaml.safe_load((CONFIG_DIR / "preregistration.yaml").read_text(encoding="utf-8"))


def frozen(raw: dict) -> dict:
    out = copy.deepcopy(raw)
    out["status"] = "frozen"
    for name in PREREGISTRATION_ITEMS:
        out[name]["decision"], out[name]["record"] = "ACCEPTED", "synthetic test record"
    return out


def test_repository_draft_records_the_d083_statuses_and_values() -> None:
    prereg = load_preregistration(CONFIG_DIR / "preregistration.yaml")
    assert prereg.status == "draft"  # never frozen in this task
    still_open = {"uncertainty", "stress_windows"}  # human review; run-time calendar check
    assert {n for n, i in prereg.items.items() if i["decision"] == "OPEN"} == still_open
    assert prereg.open_items() == ["uncertainty", "stress_windows"]
    for name, item in prereg.items.items():
        if name not in still_open:
            assert item["decision"] == "ACCEPTED" and "D-083" in item["record"]
    assert prereg.value("primary_endpoint", "primary_baseline") == "inverse_volatility_monthly"
    assert prereg.value("primary_endpoint", "seed_aggregation") == "median"
    u = prereg.items["uncertainty"]
    assert (u["method"], u["mean_block_length"], u["resamples"], u["seed"]) == (
        "moving_block_bootstrap",
        21,
        10000,
        20261021,
    )
    assert (u["confidence_level"], u["interval"], u["p_values"]) == (
        0.95,
        "percentile",
        "not_reported",
    )
    assert u["sensitivity_block_lengths"] == []
    assert prereg.value("cost_sensitivity", "total_bps") == [0.0, 15.0, 30.0]
    assert prereg.value("cost_sensitivity", "mode") == "fixed_action_accounting"
    assert prereg.value("lag_sensitivity", "lags") == []
    assert prereg.value("constraint_sensitivity", "baseline_max_weights") == []
    assert prereg.value("walk_forward", "value") == "excluded_from_this_protocol"
    assert prereg.value("embargo", "value") == "not_applied"
    assert prereg.value("multiple_comparisons", "other_baselines") == (
        "descriptive_point_differences"
    )
    s = prereg.items["stress_windows"]
    assert [(w["peak_close"], w["trough_close"], w["expected_sessions"]) for w in s["windows"]] == [
        ("2020-02-19", "2020-03-23", 23),
        ("2022-01-03", "2022-10-12", 195),
    ]
    assert len(s["sources"]) >= 3 and all(x["url"].startswith("https://") for x in s["sources"])
    assert prereg.value("regimes", "thresholds_sha256").startswith("5fc00522f02ce767")


def test_repository_draft_candidate_matches_the_validation_selection() -> None:
    meta_path = CONFIG_DIR.parent / "data/processed/evaluations/1ce9c490ed03c8c9/metadata.json"
    if not meta_path.is_file():
        pytest.skip("EXP-006 outputs are not available (git-ignored)")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    recorded = sorted(({"seed": c["seed"], "run_id": c["run_id"], "model_sha256": c["model_sha256"]}
                       for c in meta["checkpoints"] if c["configuration"] == 4),
                      key=lambda c: c["seed"])  # fmt: skip
    prereg = load_preregistration(CONFIG_DIR / "preregistration.yaml")
    assert list(prereg.value("candidate", "checkpoints")) == recorded


def test_frozen_requires_every_item_accepted_with_a_record() -> None:
    PreregistrationConfig.from_dict(frozen(_draft()))
    bad = frozen(_draft())
    bad["regimes"]["decision"] = "OPEN"
    with pytest.raises(ConfigError, match="cannot have open items"):
        PreregistrationConfig.from_dict(bad)
    bad = frozen(_draft())
    bad["regimes"]["record"] = " "
    with pytest.raises(ConfigError, match="needs a record"):
        PreregistrationConfig.from_dict(bad)
    for change, message in (
        ({"sources": []}, "no cited sources"),
        ({"windows": []}, "no windows"),
        ({"windows": [{"name": "w", "peak_close": "2020-02-19", "trough_close": "2020-03-23",
                       "expected_sessions": None}]}, "missing expected session counts"),
    ):  # fmt: skip
        bad = frozen(_draft())
        bad["stress_windows"].update(change)
        with pytest.raises(ConfigError, match=message):
            PreregistrationConfig.from_dict(bad)


@pytest.mark.parametrize(("item", "key", "value", "message"), [
    ("lag_sensitivity", "lags", [0, 2], "lag 0 is not supported"),
    ("constraint_sensitivity", "policy", "cap_0.3", "constraint_sensitivity.policy"),
    ("sortino", "value", "include", "sortino.value"),
    ("baselines", "same_run", False, "same_run must be true"),
    ("uncertainty", "confidence_level", 1.0, "confidence_level"),
    ("uncertainty", "p_values", "reported", "p_values"),
    ("uncertainty", "interval", "bca", "uncertainty.interval"),
    ("uncertainty", "method", "jackknife", "uncertainty.method"),
    ("multiple_comparisons", "method", "holm", "multiple_comparisons.method"),
    ("multiple_comparisons", "other_baselines", "bootstrap", "other_baselines"),
    ("success_criteria", "minimum_difference", 0.2, "no threshold"),
    ("cost_sensitivity", "mode", "resimulated", "cost_sensitivity.mode"),
    ("primary_endpoint", "primary_baseline", " ", "primary_baseline"),
    ("stress_windows", "boundary", "closed", "stress_windows.boundary"),
    ("candidate", "grid_id", "xyz", "16-hex"),
    ("regimes", "thresholds_sha256", "abc", "64-hex"),
    ("outputs", "root", "data/processed/evaluations", "outputs.root"),
])  # fmt: skip
def test_invalid_or_unsupported_values_are_refused(item, key, value, message) -> None:
    raw = _draft()
    raw[item][key] = value
    with pytest.raises(ConfigError, match=message):
        PreregistrationConfig.from_dict(raw)


def test_stress_windows_and_sources_are_validated() -> None:
    raw = _draft()
    raw["stress_windows"]["windows"] = [
        {
            "name": "w",
            "peak_close": "2020-03-23",
            "trough_close": "2020-02-19",
            "expected_sessions": 23,
        }
    ]
    with pytest.raises(ConfigError, match="trough close must be after the peak close"):
        PreregistrationConfig.from_dict(raw)
    raw = _draft()
    raw["stress_windows"]["windows"][0]["expected_sessions"] = 0
    with pytest.raises(ConfigError, match="expected_sessions"):
        PreregistrationConfig.from_dict(raw)
    raw = _draft()
    raw["stress_windows"]["sources"][0]["url"] = "http://insecure.example"
    with pytest.raises(ConfigError, match="https URL"):
        PreregistrationConfig.from_dict(raw)


def test_missing_baseline_and_inconsistent_statistic_are_refused() -> None:
    raw = _draft()
    del raw["primary_endpoint"]["primary_baseline"]
    with pytest.raises(ConfigError, match="missing"):
        PreregistrationConfig.from_dict(raw)
    raw = _draft()
    raw["primary_endpoint"]["seed_aggregation"] = "mean"
    with pytest.raises(ConfigError, match="primary aggregation"):
        PreregistrationConfig.from_dict(raw)


def test_hashes_are_canonical_and_protocol_hash_ignores_decisions() -> None:
    raw = _draft()
    one = PreregistrationConfig.from_dict(raw)
    reordered = dict(reversed(list(raw.items())))
    assert PreregistrationConfig.from_dict(reordered).sha256() == one.sha256()
    changed = copy.deepcopy(raw)
    changed["uncertainty"]["resamples"] = 9999
    assert PreregistrationConfig.from_dict(changed).sha256() != one.sha256()
    assert PreregistrationConfig.from_dict(changed).protocol_hash() != one.protocol_hash()
    accepted = frozen(raw)
    accepted["status"] = "draft"
    two = PreregistrationConfig.from_dict(accepted)
    assert two.protocol_hash() == one.protocol_hash() and two.sha256() != one.sha256()
    assert len(one.sha256()) == 64 and len(one.protocol_hash()) == 16


def test_the_d076_validation_protocol_hash_is_unchanged() -> None:
    assert load_evaluation_config(CONFIG_DIR / "evaluation.yaml").protocol_hash() == (
        "e652adec1095c95a"
    )


def test_unknown_or_missing_items_are_refused(tmp_path: Path) -> None:
    raw = _draft()
    del raw["embargo"]
    with pytest.raises(ConfigError, match="missing"):
        PreregistrationConfig.from_dict(raw)
    raw = _draft()
    raw["test_rows"] = {}
    with pytest.raises(ConfigError, match="unknown"):
        PreregistrationConfig.from_dict(raw)
