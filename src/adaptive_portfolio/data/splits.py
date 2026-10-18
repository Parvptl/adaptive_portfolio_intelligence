"""Chronological train / validation / test assignment without look-ahead.

Boundary semantics (documented in docs/technical_handbook.md):

* Each row is labelled by its own date: the session date for prices, the period-end
  date for returns. A row belongs to the partition whose inclusive
  ``[start, end]`` range (``configs/experiment.yaml``) contains that date.
* Rows outside every range are labelled ``excluded`` and counted.
* The first validation return uses the last training price as its starting price.
  That price was observed *before* the validation period, so this is not
  leakage; no training row ever depends on a price dated after ``train.end``.
* Assignment is a pure function of the dates and the split configuration, so it is
  reproducible. There is no random or shuffled splitting.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from adaptive_portfolio.config import SplitPeriod, Splits

PARTITIONS = ("train", "validation", "test")
EXCLUDED = "excluded"


class SplitError(ValueError):
    """Raised for invalid split specifications or insufficient history."""


@dataclass(frozen=True)
class PartitionSummary:
    name: str
    configured_start: str
    configured_end: str
    first_date: str | None
    last_date: str | None
    count: int


@dataclass(frozen=True)
class SplitAssignment:
    labels: pd.Series  # index: dates; values in PARTITIONS or EXCLUDED
    partitions: tuple[PartitionSummary, ...]
    excluded_before: int
    excluded_between: int
    excluded_after: int

    def summary(self) -> dict[str, object]:
        """JSON-serialisable summary for reports."""
        return {
            "boundary_rule": "row date in inclusive [start, end] of the partition",
            "partitions": {
                p.name: {
                    "configured_start": p.configured_start,
                    "configured_end": p.configured_end,
                    "first_date": p.first_date,
                    "last_date": p.last_date,
                    "count": p.count,
                }
                for p in self.partitions
            },
            "excluded": {
                "before_train": self.excluded_before,
                "between_partitions": self.excluded_between,
                "after_test": self.excluded_after,
            },
        }


def label_dates(dates: pd.DatetimeIndex, splits: Splits) -> pd.Series:
    """Partition label of each date from the configured boundaries alone.

    A date inside ``[start, end]`` of a partition gets its name; any other date is
    ``excluded``. Unlike :func:`assign_temporal_splits`, this needs no observation in any
    partition, so it can check a prefix of the dates (e.g. train and validation only).
    """
    index = pd.DatetimeIndex(dates)
    labels = pd.Series(EXCLUDED, index=index, dtype=object, name="split")
    for name, period in (("train", splits.train), ("validation", splits.validation),
                         ("test", splits.test)):  # fmt: skip
        inside = (index >= pd.Timestamp(period.start)) & (index <= pd.Timestamp(period.end))
        labels[inside] = name
    return labels


def assign_temporal_splits(
    dates: pd.DatetimeIndex, splits: Splits, *, min_observations: int = 1
) -> SplitAssignment:
    """Label each date with its partition; raise :class:`SplitError` on problems."""
    if min_observations < 1:
        raise SplitError("min_observations must be >= 1")
    index = pd.DatetimeIndex(dates)
    if index.has_duplicates:
        raise SplitError("dates contain duplicates")
    if not index.is_monotonic_increasing:
        raise SplitError("dates are not in chronological order")
    periods: Mapping[str, SplitPeriod] = {
        "train": splits.train,
        "validation": splits.validation,
        "test": splits.test,
    }
    if not (
        splits.train.end < splits.validation.start and splits.validation.end < splits.test.start
    ):
        raise SplitError("partitions must be ordered train < validation < test without overlap")

    labels = label_dates(index, splits)
    summaries = []
    for name in PARTITIONS:
        period = periods[name]
        selected = index[(labels == name).to_numpy()]
        if len(selected) < min_observations:
            raise SplitError(
                f"insufficient history: {name} ({period.start}..{period.end}) has "
                f"{len(selected)} observation(s); at least {min_observations} required"
            )
        summaries.append(
            PartitionSummary(
                name=name,
                configured_start=period.start.isoformat(),
                configured_end=period.end.isoformat(),
                first_date=selected[0].date().isoformat(),
                last_date=selected[-1].date().isoformat(),
                count=len(selected),
            )
        )

    excluded = labels == EXCLUDED
    before = excluded & (index < pd.Timestamp(splits.train.start))
    after = excluded & (index > pd.Timestamp(splits.test.end))
    return SplitAssignment(
        labels=labels,
        partitions=tuple(summaries),
        excluded_before=int(before.sum()),
        excluded_between=int((excluded & ~before & ~after).sum()),
        excluded_after=int(after.sum()),
    )


def split_frame(frame: pd.DataFrame, assignment: SplitAssignment) -> dict[str, pd.DataFrame]:
    """Partition a date-indexed frame using a previously computed assignment."""
    if not frame.index.equals(assignment.labels.index):
        raise SplitError("frame index does not match the dates used for the assignment")
    return {name: frame.loc[(assignment.labels == name).to_numpy()] for name in PARTITIONS}
