"""Pairing decision-time features with the *next* period's return, without leakage.

A decision taken at the close of ``t`` (using features dated ``t``) is evaluated with
``r_{t+1}``, the return row dated after ``t``. Near a split boundary, the last training
decision's outcome falls in the validation period. Such pairs are labelled ``boundary``
instead of being given to either partition, so validation or test outcomes never enter
training pairs (decision D-043).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BOUNDARY = "boundary"


def next_period_targets(asset_returns: pd.DataFrame, split_labels: pd.Series) -> pd.DataFrame:
    """One row per decision date ``t`` (all but the last return row).

    Columns: ``target_date`` (date of ``r_{t+1}``), ``target_<asset>`` (``r_{t+1}``), and
    ``pair_split``: the partition if ``t`` and ``t+1`` are in the same partition,
    ``boundary`` if they differ, or the shared label otherwise (e.g. ``excluded``).
    """
    if not asset_returns.index.equals(split_labels.index):
        raise ValueError("returns and split labels must have identical date indexes")
    if not asset_returns.index.is_monotonic_increasing or asset_returns.index.has_duplicates:
        raise ValueError("return dates must be unique and increasing")
    decision = asset_returns.index[:-1]
    labels = split_labels.to_numpy()
    same = labels[:-1] == labels[1:]
    frame = pd.DataFrame(
        {
            "target_date": asset_returns.index[1:],
            **{
                f"target_{asset}": asset_returns[asset].to_numpy()[1:]
                for asset in asset_returns.columns
            },
            "pair_split": np.where(same, labels[:-1], BOUNDARY),
        },
        index=pd.DatetimeIndex(decision, name="date"),
    )
    return frame
