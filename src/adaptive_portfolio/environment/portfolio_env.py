"""Gymnasium environment for weekly portfolio allocation (milestone 5.2; needs the ``rl`` extra).

One episode is one split's evaluation window (D-064, D-065):

* decisions ``d_0 < ... < d_K`` are the weekly rows from the common start ``k0`` (the same rule
  as the baseline backtest, D-058) to ``last_evaluable_decision(e, L)``;
* ``reset()`` returns the observation at ``d_0`` (the portfolio is still cash);
* ``step(action)`` scales the normalised action ``u`` in ``[-1, 1]^8`` to logits ``5u`` and maps
  them to a target (D-072, D-063), advances the simulator row by row with
  :func:`~adaptive_portfolio.evaluation.simulator.step` (D-067; the target executes at
  ``d_k + L``) up to the next decision row, and returns the decision-aligned reward
  ``log(V_{d_{k+1}} / V_{d_k})`` (D-064) with the observation at ``d_{k+1}``;
* the step for ``d_K`` ends at the split's last row ``e`` with ``terminated=True``; its
  observation is formed at ``e`` the same way. ``truncated`` is always False: the split end is
  the episode's natural end, and nothing is bootstrapped past it.

All accounting (drift, costs, cash, constraints) is done by the simulator's ``step``; this
module only sequences calls. Rows after the split's last row ``e`` are never read. ``reset`` is
deterministic: every episode starts at ``k0`` from cash (no random start offsets).

Observations are ``float32`` (the Gymnasium and Stable-Baselines3 convention); accounting stays
in ``float64``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import pandas as pd

from adaptive_portfolio.config import BacktestConfig, ProjectConfig
from adaptive_portfolio.data import cache
from adaptive_portfolio.data.boundaries import assert_training_only
from adaptive_portfolio.environment.actions import (
    POLICY_ACTION_HIGH,
    POLICY_ACTION_LOW,
    ActionError,
    action_proposal,
    policy_action_to_logits,
    project_action,
)
from adaptive_portfolio.environment.observation import (
    FEATURE_CLIP,
    FeatureScaler,
    build_observation,
    fit_feature_scaler,
    regime_one_hot,
)
from adaptive_portfolio.environment.rewards import episode_decisions, log_growth, reward_intervals
from adaptive_portfolio.evaluation.backtest import simulation_settings, split_bounds
from adaptive_portfolio.evaluation.simulator import (
    PortfolioState,
    SimulationSettings,
    StepRecord,
)
from adaptive_portfolio.evaluation.simulator import step as simulator_step
from adaptive_portfolio.features.engineering import FeatureDataError
from adaptive_portfolio.features.pipeline import load_feature_outputs, load_processed_inputs
from adaptive_portfolio.regimes.rules import REGIME_LABELS
from adaptive_portfolio.timing import execution_row


class PortfolioEnvError(ValueError):
    """Raised for inconsistent environment inputs or invalid use of the environment."""


class PortfolioEnv(gym.Env):
    """Weekly long-only allocation over one split, on top of the portfolio simulator."""

    metadata: dict[str, Any] = {"render_modes": []}  # noqa: RUF012 (Gymnasium convention)

    def __init__(
        self,
        returns: pd.DataFrame,
        features: pd.DataFrame,
        regimes: pd.Series,
        split_labels: pd.Series,
        *,
        split: str,
        scaler: FeatureScaler,
        settings: SimulationSettings,
        lag: int,
        required_history: int,
    ) -> None:
        """
        Args:
            returns: asset returns (index: dates, columns: universe order).
            features, regimes, split_labels: feature rows, regime labels (the ``regime``
                column of ``regimes.csv``) and split labels on the same dates.
            split: the split whose window forms the episode.
            scaler: frozen feature scaler fitted on training rows (reused for other splits).
            settings: simulator settings; ``allow_cash`` must be true (D-063).
            lag: execution lag in sessions; the reward needs ``lag >= 1`` (D-071, raises
                ``RewardError`` otherwise).
            required_history: rows needed at the first decision (backtest ``required_history``).
        """
        super().__init__()
        self.render_mode = None
        for name, frame in (("features", features), ("regimes", regimes), ("split", split_labels)):
            if not frame.index.equals(returns.index):
                raise PortfolioEnvError(f"{name} dates differ from the return dates")
        if not settings.constraints.allow_cash:
            raise PortfolioEnvError("the action mapping sends capped weight to cash: allow_cash")
        start, last = split_bounds(split_labels, split)
        first_decision = max(start, required_history - 1)
        self.split = split
        self.dates = returns.index[: last + 1]
        self.assets = tuple(returns.columns)
        self.settings = settings
        self.scaler = scaler
        self.lag = lag
        self.first_decision, self.last_row = first_decision, last
        self.first_execution = execution_row(first_decision, lag)
        self.decisions = episode_decisions(returns.index, first_decision, last, lag)
        reward_intervals(self.decisions, last, lag)  # lag >= 1, no pending order (D-071)

        # Only rows <= e are kept; rows of later splits are never read.
        self._returns = returns.iloc[: last + 1].to_numpy(dtype=np.float64)
        if not np.isfinite(self._returns[self.first_execution :]).all():
            raise PortfolioEnvError("returns in the episode window are not all finite")
        self._scaled, self.clip_counts = scaler.transform(features.iloc[first_decision : last + 1])
        self._regimes = regimes.iloc[: last + 1].to_numpy(dtype=object)
        for row in [*self.decisions, last]:  # fail at construction, not mid-episode
            regime_one_hot(self._regimes[row])

        n_features, n_assets = len(scaler.columns), len(self.assets)
        low = np.r_[np.full(n_features, -FEATURE_CLIP), np.zeros(len(REGIME_LABELS) + n_assets + 1)]
        high = np.r_[np.full(n_features, FEATURE_CLIP), np.ones(len(REGIME_LABELS) + n_assets + 1)]
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32), high=high.astype(np.float32), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=POLICY_ACTION_LOW,
            high=POLICY_ACTION_HIGH,
            shape=(n_assets + 1,),
            dtype=np.float32,
        )
        self._state: PortfolioState | None = None
        self._k = 0
        self._processed_row = self.first_execution - 1
        self.ledger: list[tuple[int, StepRecord]] = []
        self.provenance: dict[str, Any] = {}  # data identity, set by make_training_env

    @property
    def n_steps(self) -> int:
        """Number of decisions (steps) in one episode."""
        return len(self.decisions)

    def _observation(self, row: int) -> np.ndarray:
        assert self._state is not None
        values = build_observation(
            self._scaled[row - self.first_decision], self._regimes[row], self._state.weights
        )
        return values.astype(np.float32)

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        self._state = PortfolioState.initial(self.settings, len(self.assets))
        self._k = 0
        self._processed_row = self.first_execution - 1
        self.ledger = []
        d0 = self.decisions[0]
        info = {
            "decision_index": 0,
            "decision_date": self.dates[d0],
            "value": self._state.value,
        }
        return self._observation(d0), info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._state is None:
            raise PortfolioEnvError("call reset() before step()")
        if self._k >= self.n_steps:
            raise PortfolioEnvError("the episode has terminated; call reset()")
        raw = np.asarray(action, dtype=np.float64).copy()
        if raw.shape != self.action_space.shape:
            raise ActionError(f"action has shape {raw.shape}, expected {self.action_space.shape}")
        logits = policy_action_to_logits(raw)  # 5u (D-072), then the D-063 mapping
        proposal = action_proposal(logits)
        target = project_action(logits, self.settings.constraints.max_weight)
        decision = self.decisions[self._k]
        execution = execution_row(decision, self.lag)
        end = self.decisions[self._k + 1] if self._k + 1 < self.n_steps else self.last_row
        value_start = self._state.value
        state, post_trade, cost_value, rows = self._state, None, 0.0, []
        for t in range(self._processed_row + 1, end + 1):
            order = target if t == execution else None
            state, record = simulator_step(
                state, self._returns[t], order, self.settings, date=self.dates[t]
            )
            rows.append((t, record))
            cost_value += record.cost_value
            if order is not None:
                post_trade = record.weights
        reward = log_growth(value_start, state.value)
        # Commit only after the whole step succeeded, so an error leaves the episode unchanged.
        self.ledger.extend(rows)
        self._state, self._processed_row = state, end
        self._k += 1
        terminated = self._k == self.n_steps
        info = {
            "decision_index": self._k - 1,
            "decision_date": self.dates[decision],
            "execution_date": self.dates[execution],
            "interval_end_date": self.dates[end],
            "action": raw,
            "logits": logits,
            "proposal": proposal,
            "target": np.append(target, 1.0 - target.sum()),
            "post_trade_weights": post_trade,
            "cost_value": cost_value,
            "value": state.value,
        }
        return self._observation(end), reward, terminated, False, info

    def ledger_frame(self) -> pd.DataFrame:
        """Rows processed in the current episode: date, value, costs and end-of-row weights."""
        columns = [*self.assets, "CASH"]
        return pd.DataFrame.from_records(
            [
                {
                    "date": self.dates[t],
                    "gross_return": r.gross_return,
                    "rebalanced": r.rebalanced,
                    "traded_notional": r.traded_notional,
                    "cost_fraction": r.cost_fraction,
                    "net_return": r.net_return,
                    "value": r.value,
                    **{f"weight_{c}": r.weights[i] for i, c in enumerate(columns)},
                }
                for t, r in self.ledger
            ]
        )


def make_training_env(
    config: ProjectConfig, backtest: BacktestConfig, dataset_dir: Path, feature_dir: Path
) -> PortfolioEnv:
    """Training-split environment loaded with ``train_only=True`` (no validation/test values).

    The feature scaler is fitted on rows ``k0`` to the last training decision (D-062) and is
    available as ``env.scaler`` for reuse on other splits. ``env.provenance`` records the
    dataset and feature-set ids and the SHA-256 of the training lines of each file read.
    """
    inputs = load_processed_inputs(Path(dataset_dir), config, train_only=True)
    outputs = load_feature_outputs(Path(feature_dir), Path(dataset_dir), config, train_only=True)
    # Explicit guard on the rows actually held (configured dates and labels), D-076.
    splits = config.experiment.splits
    assert_training_only(inputs.asset_returns.index, inputs.split_labels, splits)
    assert_training_only(outputs.features.index, outputs.split_labels, splits)
    multi = int((inputs.sessions_spanned > 1).sum())
    if multi and not backtest.allow_multi_session_returns:
        raise FeatureDataError(
            f"{multi} return(s) span more than one session; set "
            "backtest.allow_multi_session_returns: true to accept this explicitly"
        )
    lag = backtest.execution_lag_sessions
    start, last = split_bounds(inputs.split_labels, "train")
    first_decision = max(start, backtest.required_history - 1)
    decisions = episode_decisions(inputs.asset_returns.index, first_decision, last, lag)
    scaler = fit_feature_scaler(
        outputs.features, inputs.split_labels, first_decision, decisions[-1]
    )
    env = PortfolioEnv(
        inputs.asset_returns,
        outputs.features,
        outputs.regimes["regime"],
        inputs.split_labels,
        split="train",
        scaler=scaler,
        settings=simulation_settings(config, backtest),
        lag=lag,
        required_history=backtest.required_history,
    )
    n_rows = len(inputs.asset_returns)
    files = {
        "returns.csv": Path(dataset_dir) / "returns.csv",
        "splits.csv": Path(dataset_dir) / "splits.csv",
        "features.csv": Path(feature_dir) / "features.csv",
        "regimes.csv": Path(feature_dir) / "regimes.csv",
    }
    env.provenance = {
        "processed_dataset_id": inputs.metadata.get("processed_dataset_id"),
        "feature_set_id": outputs.metadata.get("feature_set_id"),
        "loaded_rows": n_rows,
        "first_date": inputs.asset_returns.index[0].date().isoformat(),
        "last_date": inputs.asset_returns.index[-1].date().isoformat(),
        # Hashes of the header and the loaded (training) lines only; later rows are not read.
        "train_prefix_sha256": {
            name: cache.head_sha256(path, n_rows) for name, path in files.items()
        },
    }
    return env
