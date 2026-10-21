"""Milestone D (core): paired block bootstrap, multiple-comparison adjustment, risk measures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from adaptive_portfolio.evaluation import risk
from adaptive_portfolio.evaluation import uncertainty as u
from adaptive_portfolio.evaluation.bootstrap_reference import (
    reference_moving_block_draws,
)
from adaptive_portfolio.evaluation.metrics import sharpe_ratio


@pytest.mark.parametrize("method", u.METHODS)
def test_indices_stay_in_range_and_are_reproducible(method: str) -> None:
    one = u.bootstrap_indices(50, 5, 40, method, np.random.default_rng(1))
    two = u.bootstrap_indices(50, 5, 40, method, np.random.default_rng(1))
    assert one.shape == (40, 50) and one.min() >= 0 and one.max() < 50
    assert np.array_equal(one, two)


def test_stationary_blocks_have_the_expected_mean_length_and_wrap() -> None:
    rng = np.random.default_rng(0)
    index = u.bootstrap_indices(400, 10, 300, "stationary_block_bootstrap", rng)
    continues = (index[:, 1:] == (index[:, :-1] + 1) % 400).mean()
    assert continues == pytest.approx(1 - 1 / 10, abs=0.01)  # new block with probability 1/L


def test_circular_blocks_are_contiguous_with_fixed_length() -> None:
    index = u.bootstrap_indices(23, 5, 10, "circular_block_bootstrap", np.random.default_rng(3))
    for row in index:
        for start in range(0, 23, 5):
            block = row[start : start + 5]
            assert np.array_equal(block, (block[0] + np.arange(len(block))) % 23)


def test_sharpe_matches_the_project_metric_and_pairing_is_joint() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0.0004, 0.01, size=(300, 3))
    assert u.annualised_sharpe(x)[1] == pytest.approx(
        sharpe_ratio(x[:, 1], 252, annual_risk_free_rate=0.0), rel=1e-12
    )
    same = np.column_stack([x[:, 0], x[:, 0], x[:, 0]])  # policies == baseline column
    point, draws = u.paired_bootstrap(same, 2, method="stationary_block_bootstrap",
                                      block_length=5, resamples=200, seed=1)  # fmt: skip
    assert point == pytest.approx([0.0]) and np.allclose(draws, 0.0, atol=1e-12)


def test_bootstrap_is_deterministic_in_its_seed() -> None:
    x = np.random.default_rng(2).normal(0.0005, 0.01, size=(120, 4))
    kw = {"method": "stationary_block_bootstrap", "block_length": 7, "resamples": 1200}
    a = u.paired_bootstrap(x, 2, seed=11, **kw)[1]
    b = u.paired_bootstrap(x, 2, seed=11, **kw)[1]
    c = u.paired_bootstrap(x, 2, seed=12, **kw)[1]
    assert np.array_equal(a, b) and not np.array_equal(a, c) and a.shape == (1200, 2)


def test_median_and_mean_aggregation() -> None:
    x = np.random.default_rng(4).normal(0.001, 0.01, size=(80, 4))
    sr = u.annualised_sharpe(x)
    med = u.sharpe_differences(x, 3, "median")
    mean = u.sharpe_differences(x, 3, "mean")
    assert med == pytest.approx([np.median(sr[:3]) - sr[3]])
    assert mean == pytest.approx([sr[:3].mean() - sr[3]])
    with pytest.raises(u.UncertaintyError):
        u.sharpe_differences(x, 3, "max")


def test_p_values_and_adjustments_on_known_inputs() -> None:
    draws = np.array([[1.0], [2.0], [-1.0], [3.0]])
    assert u.bootstrap_p_values(draws) == pytest.approx([(2 * 1 + 1) / 5])
    adjusted = u.adjust_p_values([0.01, 0.04, 0.03], "holm")
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])
    assert u.adjust_p_values([0.01, 0.4], "bonferroni") == pytest.approx([0.02, 0.8])
    assert u.adjust_p_values([0.2], "none") == pytest.approx([0.2])


def test_outcomes_distinguish_higher_lower_and_inconclusive() -> None:
    draws = np.column_stack([np.full(999, 0.5), np.full(999, -0.5),
                             np.linspace(-1, 1, 999)])  # fmt: skip
    table = u.summarise_comparisons(np.array([0.5, -0.5, 0.0]), draws, ["a", "b", "c"],
                                    confidence_level=0.95, adjustment="holm",
                                    familywise_alpha=0.05).set_index("baseline")  # fmt: skip
    assert list(table["outcome"]) == ["higher", "lower", "inconclusive"]
    assert table.loc["c", "ci_low"] < 0 < table.loc["c", "ci_high"]
    small = u.summarise_comparisons(np.array([0.5]), draws[:, :1], ["a"], confidence_level=0.9,
                                    adjustment="none", familywise_alpha=0.05,
                                    minimum_difference=1.0)  # fmt: skip
    assert small["outcome"].iloc[0] == "inconclusive"  # significant but below the minimum


def test_invalid_bootstrap_inputs_are_refused() -> None:
    with pytest.raises(u.UncertaintyError, match="finite"):
        u.paired_bootstrap(np.array([[np.nan, 1.0], [0.0, 1.0]]), 1, method=u.METHODS[0],
                           block_length=2, resamples=10, seed=0)  # fmt: skip
    with pytest.raises(u.UncertaintyError, match="policy and one baseline"):
        u.paired_bootstrap(np.zeros((5, 2)), 2, method=u.METHODS[0], block_length=2,
                           resamples=10, seed=0)  # fmt: skip
    with pytest.raises(u.UncertaintyError, match="undefined"):
        u.paired_bootstrap(np.zeros((5, 2)), 1, method=u.METHODS[0], block_length=2,
                           resamples=10, seed=0)  # fmt: skip
    with pytest.raises(u.UncertaintyError, match="unknown method"):
        u.bootstrap_indices(5, 2, 1, "jackknife", np.random.default_rng(0))


def _ledger() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.bdate_range("2024-01-01", periods=5),
        "gross_return": [0.0, 0.01, -0.02, 0.03, 0.0],
        "net_return": [-0.001, 0.01, -0.02, 0.03, 0.0],
        "value": [99.9, 100.899, 98.88102, 101.8474506, 101.8474506],
        "weight_A": [0.4, 0.4, 0.5, 0.0, 0.0],
        "weight_B": [0.4, 0.2, 0.5, 0.0, 0.0],
        "weight_CASH": [0.2, 0.4, 0.0, 1.0, 1.0],
    })  # fmt: skip


def test_concentration_uses_the_risky_sleeve_and_reports_cash_separately() -> None:
    executions = pd.DataFrame({"target_A": [0.4, 0.1], "target_B": [0.4, 0.2]})
    c = risk.concentration(_ledger(), executions, max_weight=0.4)
    # sleeves: (0.5,0.5)->0.5, (2/3,1/3)->5/9, (0.5,0.5)->0.5, cash-only rows undefined
    assert c["mean_risky_hhi"] == pytest.approx((0.5 + 5 / 9 + 0.5) / 3)
    assert c["max_risky_hhi"] == pytest.approx(5 / 9)
    assert c["mean_cash"] == pytest.approx(0.52)
    assert c["share_executions_at_cap"] == pytest.approx(0.5)
    assert c["max_held_etf_weight"] == pytest.approx(0.5)


def test_window_metrics_measure_losses_inside_the_window_only() -> None:
    m = risk.window_metrics(_ledger(), "2024-01-02", "2024-01-04")
    assert m["sessions"] == 3
    assert m["net_return"] == pytest.approx(1.01 * 0.98 * 1.03 - 1)
    assert m["max_drawdown"] == pytest.approx(0.98 - 1.0)
    with pytest.raises(risk.RiskError, match="not inside"):
        risk.window_metrics(_ledger(), "2024-01-01", "2024-01-03")  # starts on the funding row
    with pytest.raises(risk.RiskError, match="fewer than 2"):
        risk.window_metrics(_ledger(), "2024-01-05", "2024-01-05")
    assert risk.gross_sharpe(_ledger()) == sharpe_ratio(
        np.array([0.01, -0.02, 0.03, 0.0]), 252, annual_risk_free_rate=0.0
    )


# --------------------------------------------------------------- moving-block bootstrap (D-083)


def test_moving_block_indices_obey_the_declared_rule() -> None:
    n, block = 50, 7
    index = u.bootstrap_indices(n, block, 300, "moving_block_bootstrap",
                                np.random.default_rng(20261021))  # fmt: skip
    assert index.shape == (300, n)  # exactly the original length
    assert index.min() >= 0 and index.max() <= n - 1
    blocks = -(-n // block)
    for row in index:
        for k in range(blocks):
            segment = row[k * block : (k + 1) * block]
            assert 0 <= segment[0] <= n - block  # declared start bounds
            assert np.array_equal(segment, segment[0] + np.arange(len(segment)))  # contiguous,
            # never wrapping: consecutive within a block and never past the last row
    again = u.bootstrap_indices(n, block, 300, "moving_block_bootstrap",
                                np.random.default_rng(20261021))  # fmt: skip
    assert np.array_equal(index, again)


def test_moving_block_indices_from_hand_written_starts() -> None:
    # n = 5, L = 2: ceil(5 / 2) = 3 blocks; starts 3, 0, 1 -> 3 4 | 0 1 | 1 (2 truncated)
    assert u.moving_block_indices_from_starts(np.array([[3, 0, 1]]), 5, 2).tolist() == [
        [3, 4, 0, 1, 1]
    ]
    with pytest.raises(u.UncertaintyError, match="block starts"):
        u.moving_block_indices_from_starts(np.array([[4, 0, 1]]), 5, 2)  # 4 > n - L
    with pytest.raises(u.UncertaintyError, match="ceil"):
        u.moving_block_indices_from_starts(np.array([[0, 1]]), 5, 2)


def test_hand_calculated_miniature_statistic() -> None:
    # Three policy seeds and one comparator over 4 sessions; replicate starts (1, 1), L = 2,
    # so the replicate uses rows 1, 2, 1, 2 of every series (paired).
    data = np.array([[0.01, 0.00, 0.03, 0.00],
                     [0.02, 0.01, 0.01, 0.01],
                     [0.03, 0.02, 0.05, -0.01],
                     [0.04, 0.03, 0.00, 0.02]])  # fmt: skip
    index = u.moving_block_indices_from_starts(np.array([[1, 1]]), 4, 2)[0]
    assert index.tolist() == [1, 2, 1, 2]
    # By hand: seed 1 -> 0.02, 0.03, 0.02, 0.03 (mean 0.025, std sqrt(4 * 0.005^2 / 3))
    #          seed 2 -> 0.01, 0.02, 0.01, 0.02 (mean 0.015, same std)
    #          seed 3 -> 0.01, 0.05, 0.01, 0.05 (mean 0.03, std sqrt(4 * 0.02^2 / 3))
    #          comparator -> 0.01, -0.01, 0.01, -0.01 (mean 0 -> Sharpe 0)
    root252 = 252**0.5
    sr1 = root252 * 0.025 / (4 * 0.005**2 / 3) ** 0.5
    sr2 = root252 * 0.015 / (4 * 0.005**2 / 3) ** 0.5
    sr3 = root252 * 0.03 / (4 * 0.02**2 / 3) ** 0.5
    median = sorted([sr1, sr2, sr3])[1]
    got = u.sharpe_differences(data[index], 3, "median")
    assert got == pytest.approx([median - 0.0], rel=1e-12)
    assert median == pytest.approx(sr2)


def test_reference_path_reproduces_the_main_implementation() -> None:
    x = np.random.default_rng(11).normal(0.0004, 0.01, size=(83, 6))
    _, draws = u.paired_bootstrap(x, 5, method="moving_block_bootstrap", block_length=21,
                                  resamples=1100, seed=20261021)  # fmt: skip
    reference = reference_moving_block_draws(x[:, :5].T, x[:, 5], block_length=21,
                                             resamples=1100, seed=20261021)  # fmt: skip
    assert np.allclose(draws[:, 0], reference, rtol=1e-12, atol=1e-12)


def test_moving_block_pairing_is_shared_across_series() -> None:
    x = np.random.default_rng(7).normal(0.0005, 0.01, size=(60, 1))
    same = np.hstack([x, 2 * x, 3 * x, x])  # identical Sharpe in every replicate if paired
    point, draws = u.paired_bootstrap(same, 3, method="moving_block_bootstrap", block_length=5,
                                      resamples=300, seed=20261021)  # fmt: skip
    assert point == pytest.approx([0.0], abs=1e-12) and np.allclose(draws, 0.0, atol=1e-10)


def test_percentile_interval_and_invalid_inputs() -> None:
    draws = np.arange(1.0, 102.0)  # 1..101
    interval = u.percentile_interval(50.0, draws, 0.95)
    assert interval["ci_low"] == pytest.approx(np.quantile(draws, 0.025))
    assert interval["ci_high"] == pytest.approx(np.quantile(draws, 0.975))
    assert "p_value" not in interval and interval["replicates"] == 101
    for bad, message in (((np.nan, draws, 0.95), "point estimate"),
                         ((1.0, draws[:1], 0.95), "at least two"),
                         ((1.0, np.r_[draws, np.nan], 0.95), "finite"),
                         ((1.0, draws, 0.4), "confidence_level")):  # fmt: skip
        with pytest.raises(u.UncertaintyError, match=message):
            u.percentile_interval(*bad)
    with pytest.raises(u.UncertaintyError, match="block_length <= n"):
        u.bootstrap_indices(5, 6, 1, "moving_block_bootstrap", np.random.default_rng(0))
    with pytest.raises(u.UncertaintyError, match="undefined"):
        u.paired_bootstrap(np.zeros((30, 2)), 1, method="moving_block_bootstrap",
                           block_length=5, resamples=10, seed=0)  # fmt: skip


# --------------------------------------------------------------- stress windows and allocations


def _window_ledger() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=6)
    net = np.array([-0.001, 0.01, -0.05, 0.02, -0.03, 0.04])
    return pd.DataFrame({"date": dates, "net_return": net, "value": 100 * np.cumprod(1 + net)})


def test_stress_window_uses_peak_close_exclusive_trough_close_inclusive() -> None:
    ledger = _window_ledger()
    peak, trough = "2024-01-02", "2024-01-05"  # sessions 01-03, 01-04, 01-05
    m = risk.stress_window(ledger, peak, trough, expected_sessions=3)
    assert m["status"] == "computed" and m["realised_sessions"] == 3
    assert m["first_session"] == "2024-01-03" and m["last_session"] == "2024-01-05"
    path = np.cumprod([0.95, 1.02, 0.97])  # from the value at the peak close
    assert m["net_return"] == pytest.approx(path[-1] - 1)
    assert m["max_drawdown"] == pytest.approx(min(path / np.maximum.accumulate(
        np.r_[1.0, path])[1:]) - 1)  # fmt: skip
    mismatch = risk.stress_window(ledger, peak, trough, expected_sessions=4)
    assert mismatch["status"].startswith("not computed: 3 sessions")
    missing = risk.stress_window(ledger, "2024-01-06", "2024-01-08", expected_sessions=1)
    assert "never moved" in missing["status"]
    with pytest.raises(risk.RiskError, match="must be after"):
        risk.stress_window(ledger, trough, peak, expected_sessions=3)


def test_allocation_summary_and_undefined_values_are_explicit() -> None:
    ledger = _ledger()
    executions = pd.DataFrame({"target_A": [0.4, 0.1], "target_B": [0.4, 0.2]})
    a = risk.allocation_summary(ledger, executions)
    assert (a["executions_total"], a["executions_recurring"]) == (2, 1)
    assert a["mean_risky_exposure"] == pytest.approx(1 - 0.52)
    assert a["max_weight_A"] == pytest.approx(0.5) and a["mean_target_B"] == pytest.approx(0.3)
    c = risk.concentration(ledger, executions, max_weight=0.4)
    assert c["rows_without_risky_exposure"] == 2  # HHI undefined on the all-cash rows
    flat = _ledger().assign(gross_return=0.0)
    assert np.isnan(risk.gross_sharpe(flat))  # undefined: reported, not coerced
