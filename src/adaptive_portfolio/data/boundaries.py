"""Explicit data-boundary guards (milestone B; D-060 extended by D-076).

The bounded loaders (``train_only`` / ``exclude_test``) already stop reading at a split
boundary. These guards check the rows a caller *actually holds*, so a wrong loader option or
a future code change fails loudly instead of leaking a later period:

* training code may hold only rows dated before ``validation.start``, all labelled ``train``;
* validation evaluation may hold only rows dated before ``test.start``, none labelled ``test``.

Both use the configured dates (``experiment.yaml``) and the labels, not one or the other.
"""

from __future__ import annotations

import pandas as pd

from adaptive_portfolio.config import Splits
from adaptive_portfolio.data.splits import PARTITIONS


class DataBoundaryError(ValueError):
    """Raised when data from a sealed or not-yet-permitted period is held."""


def assert_before_split(
    dates: pd.DatetimeIndex, labels: pd.Series, splits: Splits, split: str, purpose: str
) -> None:
    """Refuse any row dated on or after ``split``'s start, or labelled ``split`` or later."""
    if split not in PARTITIONS[1:]:
        raise ValueError(f"split must be 'validation' or 'test', got {split!r}")
    start = pd.Timestamp(getattr(splits, split).start)
    if len(dates) and dates.max() >= start:
        raise DataBoundaryError(
            f"{purpose}: holds rows dated up to {dates.max().date()}, on or after "
            f"{split}.start {start.date()}; refusing"
        )
    later = set(PARTITIONS[PARTITIONS.index(split) :])
    found = sorted(set(labels.astype(str)) & later)
    if found:
        raise DataBoundaryError(f"{purpose}: holds rows labelled {found}; refusing")


def assert_training_only(dates: pd.DatetimeIndex, labels: pd.Series, splits: Splits) -> None:
    """Training may hold training rows only (warm-up rows before training are labelled train)."""
    assert_before_split(dates, labels, splits, "validation", "training")
    other = sorted(set(labels.astype(str)) - {"train", "excluded"})
    if other:
        raise DataBoundaryError(f"training: holds rows labelled {other}; refusing")
