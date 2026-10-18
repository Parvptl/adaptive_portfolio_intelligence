"""Pairing decision-time features with the return they earn, without leakage.

A decision taken at the close of ``t`` (using features dated ``t``) is executed at the
close of ``t + L`` and first earns ``r_{t+L+1}``, where ``L`` is the execution lag in
observed sessions (D-048, D-055). With the default ``L = 0`` this is the next return
``r_{t+1}`` (D-043). The arithmetic lives in :mod:`adaptive_portfolio.timing`, shared
with the simulator, so the targets here are exactly the returns the simulator credits.

Near a split boundary, the outcome of a late decision falls in the next partition.
Such pairs are labelled ``boundary`` instead of being given to either partition, so
validation or test outcomes never enter training pairs. The backtest drops exactly
these decisions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from adaptive_portfolio.timing import execution_row, first_earned_row, validate_execution_lag

BOUNDARY = "boundary"


def next_period_targets(
    asset_returns: pd.DataFrame,
    split_labels: pd.Series,
    *,
    execution_lag_sessions: int = 0,
) -> pd.DataFrame:
    """One row per decision date ``t`` that has an earned return in the table.

    With lag ``L`` (``execution_lag_sessions``, observed sessions; default 0 keeps the
    milestone-3 behaviour) the decision rows are all but the last ``L + 1`` return rows.

    Columns:

    * ``execution_date``: date of row ``t + L`` (the trade's close);
    * ``target_date``: date of the first earned return row ``t + L + 1``;
    * ``target_<asset>``: that return, ``r_{t+L+1}``;
    * ``pair_split``: the partition if rows ``t`` to ``t + L + 1`` all share one label,
      otherwise ``boundary``. A shared non-partition label (e.g. ``excluded``) is kept.
    """
    if not asset_returns.index.equals(split_labels.index):
        raise ValueError("returns and split labels must have identical date indexes")
    if not asset_returns.index.is_monotonic_increasing or asset_returns.index.has_duplicates:
        raise ValueError("return dates must be unique and increasing")
    lag = validate_execution_lag(execution_lag_sessions)
    n = len(asset_returns)
    decisions = np.arange(max(n - (lag + 1), 0))
    executed = np.array([execution_row(int(d), lag) for d in decisions], dtype=int)
    earned = np.array([first_earned_row(int(d), lag) for d in decisions], dtype=int)
    labels = split_labels.to_numpy()
    pair = [
        labels[d] if all(labels[d] == labels[k] for k in range(d, e + 1)) else BOUNDARY
        for d, e in zip(decisions, earned, strict=True)
    ]
    frame = pd.DataFrame(
        {
            "execution_date": asset_returns.index[executed],
            "target_date": asset_returns.index[earned],
            **{
                f"target_{asset}": asset_returns[asset].to_numpy()[earned]
                for asset in asset_returns.columns
            },
            "pair_split": np.array(pair, dtype=object),
        },
        index=pd.DatetimeIndex(asset_returns.index[decisions], name="date"),
    )
    return frame
