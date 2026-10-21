"""Load and validate the YAML configuration files in ``configs/``.

Deliberately small: each config file maps onto a frozen dataclass, and
``from_dict`` constructors perform explicit validation. Unknown keys are
rejected so that typos fail loudly instead of silently falling back to a
default.

Typical usage::

    from adaptive_portfolio.config import load_project_config

    config = load_project_config("configs")
    config.experiment.seed
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from adaptive_portfolio.timing import MAX_EXECUTION_LAG_SESSIONS

ALLOWED_PROVIDERS = frozenset({"csv", "synthetic", "yfinance"})
ALLOWED_FREQUENCIES = ("daily", "weekly", "monthly")  # ordered from finest to coarsest
ALLOWED_WALK_FORWARD_SCHEMES = frozenset({"expanding", "rolling"})
ALLOWED_PRICE_FIELDS = frozenset({"adj_close", "close"})
ALLOWED_CACHE_MODES = frozenset({"use", "refresh", "offline"})
ALLOWED_MISSING_DATA_POLICIES = frozenset({"error", "drop_sessions"})

# Instrument identifiers are also used as file names, so only a conservative
# character set is accepted (letters, digits, '.', '-', '^', '='; e.g. "BRK-B", "^GSPC").
TICKER_PATTERN = re.compile(r"[A-Z0-9^][A-Z0-9.\-^=]{0,19}")

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"
"""``configs/`` in a source checkout. Not available in a non-editable install."""


class ConfigError(ValueError):
    """Raised when a configuration file is missing, malformed, or invalid."""


# --------------------------------------------------------------------------
# Small validation helpers
# --------------------------------------------------------------------------


def _check_keys(
    raw: Mapping[str, Any],
    section: str,
    required: set[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    """Ensure ``raw`` has every required key and no unknown keys."""
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{section}: expected a mapping, got {type(raw).__name__}")
    missing = required - raw.keys()
    if missing:
        raise ConfigError(f"{section}: missing required key(s): {sorted(missing)}")
    unknown = raw.keys() - required - optional
    if unknown:
        raise ConfigError(f"{section}: unknown key(s): {sorted(unknown)}")


def _parse_date(value: Any, field: str) -> dt.date:
    """Accept ISO-8601 strings or YAML-native dates; reject anything else."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ConfigError(f"{field}: invalid ISO date {value!r}") from exc
    raise ConfigError(f"{field}: expected a date, got {type(value).__name__}")


def _as_float(value: Any, field: str) -> float:
    # bool is a subclass of int; treat it as a type error rather than 0/1.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{field}: expected a number, got {value!r}")
    # NaN compares False against every bound, so it would slip past range checks.
    if not math.isfinite(value):
        raise ConfigError(f"{field}: expected a finite number, got {value!r}")
    return float(value)


def _as_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{field}: expected true/false, got {value!r}")
    return value


def _as_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field}: expected a non-empty string, got {value!r}")
    return value


def _as_int(value: Any, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{field}: expected an integer, got {value!r}")
    if value < minimum:
        raise ConfigError(f"{field}: must be >= {minimum}, got {value}")
    return value


def _as_relative_or_absolute_path(value: Any, field: str) -> Path:
    path_text = _as_str(value, field)
    if "\x00" in path_text:
        raise ConfigError(f"{field}: path contains a NUL character")
    return Path(path_text)


def _check_choice(value: str, allowed: Any, field: str) -> str:
    if value not in allowed:
        raise ConfigError(f"{field}: {value!r} is not one of {sorted(allowed)}")
    return value


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Read a YAML file whose top level must be a mapping."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        try:
            content = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Could not parse YAML in {path}: {exc}") from exc
    if not isinstance(content, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return content


# --------------------------------------------------------------------------
# Data configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderOptions:
    """Network and source settings for market-data providers."""

    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    input_dir: Path = Path("data/raw/csv_input")  # used by the "csv" provider only

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ProviderOptions:
        section = "data.provider_options"
        _check_keys(
            raw,
            section,
            required=set(),
            optional=frozenset(
                {"timeout_seconds", "max_retries", "retry_delay_seconds", "input_dir"}
            ),
        )
        timeout = _as_float(
            raw.get("timeout_seconds", cls.timeout_seconds), f"{section}.timeout_seconds"
        )
        if not 0 < timeout <= 600:
            raise ConfigError(f"{section}.timeout_seconds must be in (0, 600]")
        delay = _as_float(
            raw.get("retry_delay_seconds", cls.retry_delay_seconds),
            f"{section}.retry_delay_seconds",
        )
        if not 0 <= delay <= 60:
            raise ConfigError(f"{section}.retry_delay_seconds must be in [0, 60]")
        max_retries = _as_int(
            raw.get("max_retries", cls.max_retries), f"{section}.max_retries", minimum=0
        )
        if max_retries > 10:
            raise ConfigError(f"{section}.max_retries must be <= 10")
        return cls(
            timeout_seconds=timeout,
            max_retries=max_retries,
            retry_delay_seconds=delay,
            input_dir=_as_relative_or_absolute_path(
                raw.get("input_dir", str(cls.input_dir)), f"{section}.input_dir"
            ),
        )


@dataclass(frozen=True)
class CacheConfig:
    """How raw provider downloads are reused (see the market-data pipeline)."""

    mode: str = "use"  # use | refresh | offline

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> CacheConfig:
        _check_keys(raw, "data.cache", required=set(), optional=frozenset({"mode"}))
        mode = _as_str(raw.get("mode", cls.mode), "data.cache.mode")
        return cls(mode=_check_choice(mode, ALLOWED_CACHE_MODES, "data.cache.mode"))


@dataclass(frozen=True)
class MissingDataConfig:
    """What to do when an instrument has no price on an observed session."""

    policy: str = "error"  # error | drop_sessions
    max_dropped_sessions: int = 0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> MissingDataConfig:
        section = "data.missing_data"
        _check_keys(
            raw, section, required=set(), optional=frozenset({"policy", "max_dropped_sessions"})
        )
        policy = _check_choice(
            _as_str(raw.get("policy", cls.policy), f"{section}.policy"),
            ALLOWED_MISSING_DATA_POLICIES,
            f"{section}.policy",
        )
        max_dropped = _as_int(
            raw.get("max_dropped_sessions", cls.max_dropped_sessions),
            f"{section}.max_dropped_sessions",
            minimum=0,
        )
        if policy == "error" and max_dropped != 0:
            raise ConfigError(
                f"{section}.max_dropped_sessions only applies to policy 'drop_sessions'; "
                "set it to 0 or change the policy"
            )
        return cls(policy=policy, max_dropped_sessions=max_dropped)


@dataclass(frozen=True)
class DataValidationConfig:
    """Thresholds used to reject implausible or incomplete datasets."""

    min_sessions: int = 1000
    max_abs_return: float = 0.4
    max_calendar_gap_days: int = 7
    max_start_lag_days: int = 7
    max_end_lag_days: int = 7

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> DataValidationConfig:
        section = "data.validation"
        _check_keys(
            raw,
            section,
            required=set(),
            optional=frozenset(
                {
                    "min_sessions",
                    "max_abs_return",
                    "max_calendar_gap_days",
                    "max_start_lag_days",
                    "max_end_lag_days",
                }
            ),
        )
        max_abs_return = _as_float(
            raw.get("max_abs_return", cls.max_abs_return), f"{section}.max_abs_return"
        )
        if not 0 < max_abs_return <= 10:
            raise ConfigError(f"{section}.max_abs_return must be in (0, 10] (decimal return)")
        return cls(
            min_sessions=_as_int(
                raw.get("min_sessions", cls.min_sessions), f"{section}.min_sessions", minimum=2
            ),
            max_abs_return=max_abs_return,
            max_calendar_gap_days=_as_int(
                raw.get("max_calendar_gap_days", cls.max_calendar_gap_days),
                f"{section}.max_calendar_gap_days",
                minimum=1,
            ),
            max_start_lag_days=_as_int(
                raw.get("max_start_lag_days", cls.max_start_lag_days),
                f"{section}.max_start_lag_days",
                minimum=0,
            ),
            max_end_lag_days=_as_int(
                raw.get("max_end_lag_days", cls.max_end_lag_days),
                f"{section}.max_end_lag_days",
                minimum=0,
            ),
        )


def _optional_section(raw: Mapping[str, Any], key: str) -> Any:
    """Return a nested section; a missing key or an empty YAML value (None) means defaults."""
    value = raw.get(key)
    return {} if value is None else value


def _parse_universe(universe_raw: Any) -> tuple[str, ...]:
    if not isinstance(universe_raw, list) or not universe_raw:
        raise ConfigError("data.universe: expected a non-empty list of tickers")
    universe = tuple(_as_str(t, "data.universe[]").strip().upper() for t in universe_raw)
    if len(set(universe)) != len(universe):
        raise ConfigError("data.universe: contains duplicate tickers")
    for ticker in universe:
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ConfigError(
                f"data.universe: invalid identifier {ticker!r}; use 1-20 characters from "
                "A-Z, 0-9, '.', '-', '^', '=' (no spaces or path separators)"
            )
    return universe


@dataclass(frozen=True)
class DataConfig:
    """Data source, asset universe, date range, bar frequency and pipeline policies."""

    provider: str
    raw_data_dir: Path
    processed_data_dir: Path
    universe: tuple[str, ...]
    start_date: dt.date
    end_date: dt.date
    frequency: str
    price_field: str
    provider_options: ProviderOptions = field(default_factory=ProviderOptions)
    cache: CacheConfig = field(default_factory=CacheConfig)
    missing_data: MissingDataConfig = field(default_factory=MissingDataConfig)
    validation: DataValidationConfig = field(default_factory=DataValidationConfig)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> DataConfig:
        _check_keys(
            raw,
            "data",
            required={"provider", "universe", "start_date", "end_date", "frequency"},
            optional=frozenset(
                {
                    "raw_data_dir",
                    "processed_data_dir",
                    "price_field",
                    "provider_options",
                    "cache",
                    "missing_data",
                    "validation",
                }
            ),
        )
        provider = _check_choice(
            _as_str(raw["provider"], "data.provider"), ALLOWED_PROVIDERS, "data.provider"
        )
        universe = _parse_universe(raw["universe"])

        start = _parse_date(raw["start_date"], "data.start_date")
        end = _parse_date(raw["end_date"], "data.end_date")
        if start >= end:
            raise ConfigError("data.start_date must be before data.end_date")

        raw_dir = _as_relative_or_absolute_path(
            raw.get("raw_data_dir", "data/raw"), "data.raw_data_dir"
        )
        processed_dir = _as_relative_or_absolute_path(
            raw.get("processed_data_dir", "data/processed"), "data.processed_data_dir"
        )
        if raw_dir == processed_dir:
            raise ConfigError("data.raw_data_dir and data.processed_data_dir must differ")

        price_field = _check_choice(
            _as_str(raw.get("price_field", "adj_close"), "data.price_field"),
            ALLOWED_PRICE_FIELDS,
            "data.price_field",
        )
        return cls(
            provider=provider,
            raw_data_dir=raw_dir,
            processed_data_dir=processed_dir,
            universe=universe,
            start_date=start,
            end_date=end,
            frequency=_check_choice(
                _as_str(raw["frequency"], "data.frequency"), ALLOWED_FREQUENCIES, "data.frequency"
            ),
            price_field=price_field,
            provider_options=ProviderOptions.from_dict(_optional_section(raw, "provider_options")),
            cache=CacheConfig.from_dict(_optional_section(raw, "cache")),
            missing_data=MissingDataConfig.from_dict(_optional_section(raw, "missing_data")),
            validation=DataValidationConfig.from_dict(_optional_section(raw, "validation")),
        )


# --------------------------------------------------------------------------
# Environment configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstraintsConfig:
    """Portfolio weight and turnover constraints."""

    long_only: bool
    allow_cash: bool
    min_weight: float
    max_weight: float
    max_turnover: float | None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ConstraintsConfig:
        section = "environment.constraints"
        _check_keys(
            raw,
            section,
            required={"long_only", "allow_cash", "min_weight", "max_weight"},
            optional=frozenset({"max_turnover"}),
        )
        long_only = _as_bool(raw["long_only"], f"{section}.long_only")
        min_weight = _as_float(raw["min_weight"], f"{section}.min_weight")
        max_weight = _as_float(raw["max_weight"], f"{section}.max_weight")

        if long_only and min_weight < 0:
            raise ConfigError(f"{section}.min_weight must be >= 0 when long_only is true")
        # Shorting is outside the current research scope; cap it at -100% per asset.
        if min_weight < -1:
            raise ConfigError(f"{section}.min_weight must be >= -1")
        if not 0 < max_weight <= 1:
            raise ConfigError(f"{section}.max_weight must be in (0, 1]")
        if min_weight > max_weight:
            raise ConfigError(f"{section}.min_weight must not exceed max_weight")

        max_turnover_raw = raw.get("max_turnover")
        max_turnover = None
        if max_turnover_raw is not None:
            max_turnover = _as_float(max_turnover_raw, f"{section}.max_turnover")
            # Turnover measured as sum(|w_new - w_old|) is bounded by 2.
            if not 0 < max_turnover <= 2:
                raise ConfigError(f"{section}.max_turnover must be in (0, 2] or null")

        return cls(
            long_only=long_only,
            allow_cash=_as_bool(raw["allow_cash"], f"{section}.allow_cash"),
            min_weight=min_weight,
            max_weight=max_weight,
            max_turnover=max_turnover,
        )


@dataclass(frozen=True)
class EnvironmentConfig:
    """Starting capital, trading costs, rebalancing and constraints."""

    initial_capital: float
    transaction_cost_bps: float
    slippage_bps: float
    rebalance_frequency: str
    constraints: ConstraintsConfig
    risk_free_rate: float

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> EnvironmentConfig:
        _check_keys(
            raw,
            "environment",
            required={
                "initial_capital",
                "transaction_cost_bps",
                "rebalance_frequency",
                "constraints",
            },
            optional=frozenset({"slippage_bps", "risk_free_rate"}),
        )
        initial_capital = _as_float(raw["initial_capital"], "environment.initial_capital")
        if initial_capital <= 0:
            raise ConfigError("environment.initial_capital must be positive")

        cost = _as_float(raw["transaction_cost_bps"], "environment.transaction_cost_bps")
        slippage = _as_float(raw.get("slippage_bps", 0.0), "environment.slippage_bps")
        for name, value in (("transaction_cost_bps", cost), ("slippage_bps", slippage)):
            # 1000 bps = 10% per trade: anything above is almost certainly a unit error.
            if not 0 <= value <= 1000:
                raise ConfigError(f"environment.{name} must be in [0, 1000] basis points")

        risk_free = _as_float(raw.get("risk_free_rate", 0.0), "environment.risk_free_rate")
        if not -0.05 <= risk_free <= 0.25:
            raise ConfigError(
                "environment.risk_free_rate must be an annual decimal rate in [-0.05, 0.25]"
            )

        return cls(
            initial_capital=initial_capital,
            transaction_cost_bps=cost,
            slippage_bps=slippage,
            rebalance_frequency=_check_choice(
                _as_str(raw["rebalance_frequency"], "environment.rebalance_frequency"),
                ALLOWED_FREQUENCIES,
                "environment.rebalance_frequency",
            ),
            constraints=ConstraintsConfig.from_dict(raw["constraints"]),
            risk_free_rate=risk_free,
        )


# --------------------------------------------------------------------------
# Experiment configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SplitPeriod:
    """An inclusive date range."""

    start: dt.date
    end: dt.date

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], section: str) -> SplitPeriod:
        _check_keys(raw, section, required={"start", "end"})
        start = _parse_date(raw["start"], f"{section}.start")
        end = _parse_date(raw["end"], f"{section}.end")
        if start >= end:
            raise ConfigError(f"{section}: start must be before end")
        return cls(start=start, end=end)


@dataclass(frozen=True)
class Splits:
    """Chronological, non-overlapping train / validation / test periods."""

    train: SplitPeriod
    validation: SplitPeriod
    test: SplitPeriod

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Splits:
        section = "experiment.splits"
        _check_keys(raw, section, required={"train", "validation", "test"})
        train = SplitPeriod.from_dict(raw["train"], f"{section}.train")
        validation = SplitPeriod.from_dict(raw["validation"], f"{section}.validation")
        test = SplitPeriod.from_dict(raw["test"], f"{section}.test")

        # Strict ordering prevents overlap and therefore leakage between periods.
        if not train.end < validation.start:
            raise ConfigError(f"{section}: train must end before validation starts")
        if not validation.end < test.start:
            raise ConfigError(f"{section}: validation must end before test starts")
        return cls(train=train, validation=validation, test=test)


@dataclass(frozen=True)
class WalkForwardConfig:
    """Intended walk-forward settings (evaluation not implemented yet)."""

    enabled: bool
    scheme: str
    train_window_years: int
    step_months: int

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> WalkForwardConfig:
        section = "experiment.walk_forward"
        _check_keys(
            raw, section, required={"enabled", "scheme", "train_window_years", "step_months"}
        )
        ints: dict[str, int] = {}
        for key in ("train_window_years", "step_months"):
            value = raw[key]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ConfigError(f"{section}.{key} must be a positive integer")
            ints[key] = value
        return cls(
            enabled=_as_bool(raw["enabled"], f"{section}.enabled"),
            scheme=_check_choice(
                _as_str(raw["scheme"], f"{section}.scheme"),
                ALLOWED_WALK_FORWARD_SCHEMES,
                f"{section}.scheme",
            ),
            **ints,
        )


@dataclass(frozen=True)
class ExperimentConfig:
    """Experiment identity, seed, splits and walk-forward settings."""

    name: str
    description: str
    seed: int
    splits: Splits
    walk_forward: WalkForwardConfig
    output_dir: Path

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ExperimentConfig:
        _check_keys(
            raw,
            "experiment",
            required={"name", "seed", "splits"},
            optional=frozenset({"description", "walk_forward", "output_dir"}),
        )
        seed = raw["seed"]
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
            raise ConfigError("experiment.seed must be an integer in [0, 2**32)")

        walk_forward_raw = raw.get(
            "walk_forward",
            {"enabled": False, "scheme": "expanding", "train_window_years": 5, "step_months": 12},
        )
        return cls(
            name=_as_str(raw["name"], "experiment.name"),
            description=str(raw.get("description", "")),
            seed=seed,
            splits=Splits.from_dict(raw["splits"]),
            walk_forward=WalkForwardConfig.from_dict(walk_forward_raw),
            output_dir=Path(raw.get("output_dir", "reports")),
        )


# --------------------------------------------------------------------------
# Combined project configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectConfig:
    """All configuration sections, validated for mutual consistency."""

    data: DataConfig
    environment: EnvironmentConfig
    experiment: ExperimentConfig

    def __post_init__(self) -> None:
        validate_consistency(self.data, self.environment, self.experiment)


def validate_consistency(
    data: DataConfig, environment: EnvironmentConfig, experiment: ExperimentConfig
) -> None:
    """Checks that span more than one config file."""
    splits = experiment.splits
    if splits.train.start < data.start_date or splits.test.end > data.end_date:
        raise ConfigError(
            "experiment.splits must lie within data.start_date and data.end_date "
            f"({data.start_date} to {data.end_date})"
        )

    if ALLOWED_FREQUENCIES.index(environment.rebalance_frequency) < ALLOWED_FREQUENCIES.index(
        data.frequency
    ):
        raise ConfigError(
            "environment.rebalance_frequency cannot be finer than data.frequency "
            f"({environment.rebalance_frequency!r} vs {data.frequency!r})"
        )

    constraints = environment.constraints
    n_assets = len(data.universe)
    if not constraints.allow_cash and constraints.max_weight * n_assets < 1:
        raise ConfigError(
            "Infeasible constraints: without cash, max_weight * number of assets must be >= 1 "
            f"({constraints.max_weight} * {n_assets})"
        )
    if constraints.min_weight * n_assets > 1:
        raise ConfigError(
            "Infeasible constraints: min_weight * number of assets must be <= 1 "
            f"({constraints.min_weight} * {n_assets})"
        )


def load_data_config(path: str | Path) -> DataConfig:
    return DataConfig.from_dict(load_yaml(path))


def load_environment_config(path: str | Path) -> EnvironmentConfig:
    return EnvironmentConfig.from_dict(load_yaml(path))


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    return ExperimentConfig.from_dict(load_yaml(path))


def load_project_config(config_dir: str | Path = DEFAULT_CONFIG_DIR) -> ProjectConfig:
    """Load ``data.yaml``, ``environment.yaml`` and ``experiment.yaml`` from one directory."""
    config_dir = Path(config_dir)
    return ProjectConfig(
        data=load_data_config(config_dir / "data.yaml"),
        environment=load_environment_config(config_dir / "environment.yaml"),
        experiment=load_experiment_config(config_dir / "experiment.yaml"),
    )


# --------------------------------------------------------------------------
# Feature and regime configuration (milestone 3, configs/features.yaml)
# --------------------------------------------------------------------------

GROUP_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,29}")


def _as_window_list(value: Any, field: str, minimum: int) -> tuple[int, ...]:
    """Non-empty list of distinct integer windows (in return observations), sorted."""
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{field}: expected a non-empty list of integer windows")
    windows = tuple(_as_int(v, f"{field}[]", minimum=minimum) for v in value)
    if len(set(windows)) != len(windows):
        raise ConfigError(f"{field}: contains duplicate windows")
    if max(windows) > 2000:
        raise ConfigError(f"{field}: windows must be <= 2000 observations")
    return tuple(sorted(windows))


def _as_probability(value: Any, field: str) -> float:
    number = _as_float(value, field)
    if not 0 < number < 1:
        raise ConfigError(f"{field}: must be strictly between 0 and 1, got {number}")
    return number


@dataclass(frozen=True)
class FeatureWindows:
    """Rolling-window lengths, counted in return observations (one per session)."""

    asset_momentum: tuple[int, ...] = (63,)
    asset_volatility: tuple[int, ...] = (21,)
    group_momentum: tuple[int, ...] = (21, 63)
    market_volatility: tuple[int, ...] = (21, 63)
    market_downside_volatility: tuple[int, ...] = (63,)
    market_drawdown: int = 126
    average_asset_volatility: int = 21
    correlation: int = 63

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> FeatureWindows:
        section = "features.windows"
        names = (
            "asset_momentum",
            "asset_volatility",
            "group_momentum",
            "market_volatility",
            "market_downside_volatility",
            "market_drawdown",
            "average_asset_volatility",
            "correlation",
        )
        _check_keys(raw, section, required=set(), optional=frozenset(names))
        defaults = cls()

        def windows(name: str, minimum: int) -> tuple[int, ...]:
            value = raw.get(name, list(getattr(defaults, name)))
            return _as_window_list(value, f"{section}.{name}", minimum)

        def single(name: str, minimum: int) -> int:
            value = _as_int(raw.get(name, getattr(defaults, name)), f"{section}.{name}", minimum)
            if value > 2000:
                raise ConfigError(f"{section}.{name}: must be <= 2000 observations")
            return value

        return cls(
            asset_momentum=windows("asset_momentum", 1),
            # A sample standard deviation needs at least 2 observations.
            asset_volatility=windows("asset_volatility", 2),
            group_momentum=windows("group_momentum", 1),
            market_volatility=windows("market_volatility", 2),
            market_downside_volatility=windows("market_downside_volatility", 2),
            market_drawdown=single("market_drawdown", 1),
            average_asset_volatility=single("average_asset_volatility", 2),
            # A correlation from 2 points is always +-1; require at least 3.
            correlation=single("correlation", 3),
        )

    def max_window(self) -> int:
        return max(
            *self.asset_momentum,
            *self.asset_volatility,
            *self.group_momentum,
            *self.market_volatility,
            *self.market_downside_volatility,
            self.market_drawdown,
            self.average_asset_volatility,
            self.correlation,
        )


@dataclass(frozen=True)
class RegimeConfig:
    """Rule-based regime calibration (fitted on the training partition only)."""

    trend_window: int = 63
    volatility_window: int = 21
    trend_neutral_quantile: float = 0.3333
    volatility_quantiles: tuple[float, float] = (0.3333, 0.6667)
    min_calibration_observations: int = 250
    sparse_regime_fraction: float = 0.02
    concentration_warning_fraction: float = 0.5

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> RegimeConfig:
        section = "features.regime"
        _check_keys(
            raw,
            section,
            required=set(),
            optional=frozenset(
                {
                    "trend_window",
                    "volatility_window",
                    "trend_neutral_quantile",
                    "volatility_quantiles",
                    "min_calibration_observations",
                    "sparse_regime_fraction",
                    "concentration_warning_fraction",
                }
            ),
        )
        defaults = cls()
        quantiles_raw = raw.get("volatility_quantiles", list(defaults.volatility_quantiles))
        if not isinstance(quantiles_raw, list) or len(quantiles_raw) != 2:
            raise ConfigError(f"{section}.volatility_quantiles: expected [low, high]")
        low, high = (_as_probability(q, f"{section}.volatility_quantiles[]") for q in quantiles_raw)
        if not low < high:
            raise ConfigError(f"{section}.volatility_quantiles: low must be < high")
        sparse = _as_float(
            raw.get("sparse_regime_fraction", defaults.sparse_regime_fraction),
            f"{section}.sparse_regime_fraction",
        )
        if not 0 < sparse < 0.5:
            raise ConfigError(f"{section}.sparse_regime_fraction must be in (0, 0.5)")
        concentration = _as_float(
            raw.get("concentration_warning_fraction", defaults.concentration_warning_fraction),
            f"{section}.concentration_warning_fraction",
        )
        if not 0 < concentration <= 1:
            raise ConfigError(f"{section}.concentration_warning_fraction must be in (0, 1]")
        return cls(
            trend_window=_as_int(
                raw.get("trend_window", defaults.trend_window), f"{section}.trend_window", 1
            ),
            volatility_window=_as_int(
                raw.get("volatility_window", defaults.volatility_window),
                f"{section}.volatility_window",
                2,
            ),
            trend_neutral_quantile=_as_probability(
                raw.get("trend_neutral_quantile", defaults.trend_neutral_quantile),
                f"{section}.trend_neutral_quantile",
            ),
            volatility_quantiles=(low, high),
            min_calibration_observations=_as_int(
                raw.get("min_calibration_observations", defaults.min_calibration_observations),
                f"{section}.min_calibration_observations",
                10,
            ),
            sparse_regime_fraction=sparse,
            concentration_warning_fraction=concentration,
        )


@dataclass(frozen=True)
class FeatureConfig:
    """Causal market features and rule-based regimes (configs/features.yaml)."""

    output_dir: Path
    asset_groups: tuple[tuple[str, tuple[str, ...]], ...]  # ordered (name, members) pairs
    market_group: str
    correlation_groups: tuple[str, str] | None
    allow_multi_session_returns: bool
    windows: FeatureWindows
    regime: RegimeConfig

    def group(self, name: str) -> tuple[str, ...]:
        return dict(self.asset_groups)[name]

    @property
    def trend_feature(self) -> str:
        return f"{self.market_group}_mom_{self.regime.trend_window}"

    @property
    def volatility_feature(self) -> str:
        return f"market_vol_{self.regime.volatility_window}"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> FeatureConfig:
        _check_keys(
            raw,
            "features",
            required={"asset_groups", "market_group"},
            optional=frozenset(
                {
                    "output_dir",
                    "correlation_groups",
                    "allow_multi_session_returns",
                    "windows",
                    "regime",
                }
            ),
        )
        groups_raw = raw["asset_groups"]
        if not isinstance(groups_raw, Mapping) or not groups_raw:
            raise ConfigError("features.asset_groups: expected a non-empty mapping name -> tickers")
        groups: list[tuple[str, tuple[str, ...]]] = []
        seen: dict[str, str] = {}
        for name, members_raw in groups_raw.items():
            if not isinstance(name, str) or not GROUP_NAME_PATTERN.fullmatch(name):
                raise ConfigError(
                    f"features.asset_groups: invalid group name {name!r} (lowercase letters, "
                    "digits, underscore; starting with a letter)"
                )
            if name == "market":
                raise ConfigError("features.asset_groups: 'market' is reserved")
            members = _parse_universe(members_raw)
            for ticker in members:
                if ticker in seen:
                    raise ConfigError(
                        f"features.asset_groups: {ticker} is in both {seen[ticker]!r} and "
                        f"{name!r}; groups must be disjoint"
                    )
                seen[ticker] = name
            groups.append((name, members))
        names = [name for name, _ in groups]

        market_group = _as_str(raw["market_group"], "features.market_group")
        if market_group not in names:
            raise ConfigError(f"features.market_group {market_group!r} is not one of {names}")

        correlation_raw = raw.get("correlation_groups")
        correlation: tuple[str, str] | None = None
        if correlation_raw is not None:
            if (
                not isinstance(correlation_raw, list)
                or len(correlation_raw) != 2
                or correlation_raw[0] == correlation_raw[1]
                or any(g not in names for g in correlation_raw)
            ):
                raise ConfigError(
                    f"features.correlation_groups: expected two different group names from {names}"
                )
            correlation = (correlation_raw[0], correlation_raw[1])

        windows = FeatureWindows.from_dict(_optional_section(raw, "windows"))
        regime = RegimeConfig.from_dict(_optional_section(raw, "regime"))
        if regime.trend_window not in windows.group_momentum:
            raise ConfigError(
                f"features.regime.trend_window={regime.trend_window} must be one of "
                f"features.windows.group_momentum {list(windows.group_momentum)}"
            )
        if regime.volatility_window not in windows.market_volatility:
            raise ConfigError(
                f"features.regime.volatility_window={regime.volatility_window} must be one of "
                f"features.windows.market_volatility {list(windows.market_volatility)}"
            )
        allow_multi = raw.get("allow_multi_session_returns", False)
        return cls(
            output_dir=_as_relative_or_absolute_path(
                raw.get("output_dir", "data/processed/features"), "features.output_dir"
            ),
            asset_groups=tuple(groups),
            market_group=market_group,
            correlation_groups=correlation,
            allow_multi_session_returns=_as_bool(
                allow_multi, "features.allow_multi_session_returns"
            ),
            windows=windows,
            regime=regime,
        )

    def check_universe(self, universe: tuple[str, ...]) -> None:
        """Every grouped instrument must be part of the configured data universe."""
        for name, members in self.asset_groups:
            unknown = [ticker for ticker in members if ticker not in universe]
            if unknown:
                raise ConfigError(
                    f"features.asset_groups.{name}: {unknown} not in data.universe {list(universe)}"
                )


def load_feature_config(path: str | Path) -> FeatureConfig:
    return FeatureConfig.from_dict(load_yaml(path))


# --------------------------------------------------------------------------
# Portfolio simulation and baselines (milestone 4, configs/backtest.yaml)
# --------------------------------------------------------------------------

STRATEGY_TYPES = frozenset({"equal_weight", "inverse_volatility", "fixed_weights"})
REBALANCE_SCHEDULES = ("daily", "weekly", "monthly", "never")  # finest to coarsest
STRATEGY_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,49}")


@dataclass(frozen=True)
class StrategyConfig:
    """One conventional baseline: allocation rule plus rebalancing schedule."""

    name: str
    type: str
    rebalance: str
    lookback: int | None = None
    weights: tuple[tuple[str, float], ...] | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], index: int) -> StrategyConfig:
        section = f"backtest.strategies[{index}]"
        _check_keys(
            raw,
            section,
            required={"name", "type", "rebalance"},
            optional=frozenset({"lookback", "weights"}),
        )
        name = _as_str(raw["name"], f"{section}.name")
        if not STRATEGY_NAME_PATTERN.fullmatch(name):
            raise ConfigError(
                f"{section}.name {name!r}: use lowercase letters, digits and underscores"
            )
        kind = _check_choice(
            _as_str(raw["type"], f"{section}.type"), STRATEGY_TYPES, f"{section}.type"
        )
        rebalance = _check_choice(
            _as_str(raw["rebalance"], f"{section}.rebalance"),
            REBALANCE_SCHEDULES,
            f"{section}.rebalance",
        )
        lookback = None
        if kind == "inverse_volatility":
            if "lookback" not in raw:
                raise ConfigError(f"{section}: inverse_volatility needs 'lookback' (sessions)")
            lookback = _as_int(raw["lookback"], f"{section}.lookback", minimum=2)
            if lookback > 2000:
                raise ConfigError(f"{section}.lookback must be <= 2000")
        elif "lookback" in raw:
            raise ConfigError(f"{section}: 'lookback' only applies to inverse_volatility")

        weights = None
        if kind == "fixed_weights":
            raw_weights = raw.get("weights")
            if not isinstance(raw_weights, Mapping) or not raw_weights:
                raise ConfigError(f"{section}: fixed_weights needs a non-empty 'weights' mapping")
            parsed = []
            for ticker, value in raw_weights.items():
                symbol = _as_str(ticker, f"{section}.weights key").strip().upper()
                if not TICKER_PATTERN.fullmatch(symbol):
                    raise ConfigError(f"{section}.weights: invalid identifier {ticker!r}")
                parsed.append((symbol, _as_float(value, f"{section}.weights.{symbol}")))
            weights = tuple(parsed)
        elif "weights" in raw:
            raise ConfigError(f"{section}: 'weights' only applies to fixed_weights")
        return cls(name=name, type=kind, rebalance=rebalance, lookback=lookback, weights=weights)

    @property
    def min_history(self) -> int:
        """Return rows needed up to and including the decision date."""
        return self.lookback or 1


@dataclass(frozen=True)
class BacktestConfig:
    """Simulator conventions and the list of baseline strategies."""

    output_dir: Path
    execution_lag_sessions: int
    charge_initial_funding: bool
    periods_per_year: float | None
    allow_multi_session_returns: bool
    strategies: tuple[StrategyConfig, ...]
    # Return rows (including the decision row) every strategy must have available at the
    # first decision of each split, on top of each strategy's own lookback. 1 = no extra
    # requirement (milestone-4 behaviour). Set to the feature warm-up so that baselines and
    # a later feature-based agent share one evaluation window.
    common_start_history_sessions: int = 1

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> BacktestConfig:
        _check_keys(
            raw,
            "backtest",
            required={"strategies", "execution_lag_sessions"},
            optional=frozenset(
                {
                    "output_dir",
                    "charge_initial_funding",
                    "periods_per_year",
                    "allow_multi_session_returns",
                    "common_start_history_sessions",
                }
            ),
        )
        # Required, with no default: the execution lag is a research choice (D-055 proposes
        # 1 as the primary convention and 0 as an idealised sensitivity case).
        lag = _as_int(raw["execution_lag_sessions"], "backtest.execution_lag_sessions", 0)
        if lag > MAX_EXECUTION_LAG_SESSIONS:
            raise ConfigError(
                f"backtest.execution_lag_sessions must be <= {MAX_EXECUTION_LAG_SESSIONS}"
            )
        periods = raw.get("periods_per_year")
        if periods is not None:
            periods = _as_float(periods, "backtest.periods_per_year")
            if not 0 < periods <= 400:
                raise ConfigError("backtest.periods_per_year must be in (0, 400] or null")
        strategies_raw = raw["strategies"]
        if not isinstance(strategies_raw, list) or not strategies_raw:
            raise ConfigError("backtest.strategies: expected a non-empty list")
        strategies = tuple(
            StrategyConfig.from_dict(item, i) for i, item in enumerate(strategies_raw)
        )
        names = [s.name for s in strategies]
        if len(set(names)) != len(names):
            raise ConfigError(f"backtest.strategies: duplicate names in {names}")
        return cls(
            output_dir=_as_relative_or_absolute_path(
                raw.get("output_dir", "data/processed/backtests"), "backtest.output_dir"
            ),
            execution_lag_sessions=lag,
            charge_initial_funding=_as_bool(
                raw.get("charge_initial_funding", True), "backtest.charge_initial_funding"
            ),
            periods_per_year=periods,
            allow_multi_session_returns=_as_bool(
                raw.get("allow_multi_session_returns", False),
                "backtest.allow_multi_session_returns",
            ),
            strategies=strategies,
            common_start_history_sessions=_as_int(
                raw.get("common_start_history_sessions", 1),
                "backtest.common_start_history_sessions",
                1,
            ),
        )

    @property
    def required_history(self) -> int:
        """Return rows needed at the common first decision of a split (all strategies)."""
        return max(self.common_start_history_sessions, *(s.min_history for s in self.strategies))

    def check_feature_warm_up(self, features: FeatureConfig) -> None:
        """Require the common evaluation window to cover the longest feature window."""
        needed = features.windows.max_window()
        if self.common_start_history_sessions < needed:
            raise ConfigError(
                f"backtest.common_start_history_sessions is "
                f"{self.common_start_history_sessions}, but the longest feature window in "
                f"features.yaml is {needed} sessions; set it to at least {needed} so that "
                "baselines and a feature-based agent share one evaluation window"
            )

    def check_against(self, data: DataConfig, environment: EnvironmentConfig) -> None:
        """Cross-checks with the universe, the portfolio constraints and rebalancing limits."""
        constraints = environment.constraints
        if not constraints.long_only:
            raise ConfigError("the simulator supports long-only portfolios only (D-050)")
        n = len(data.universe)
        finest = ALLOWED_FREQUENCIES.index(environment.rebalance_frequency)
        for strategy in self.strategies:
            label = f"backtest strategy {strategy.name!r}"
            if (
                strategy.rebalance != "never"
                and ALLOWED_FREQUENCIES.index(strategy.rebalance) < finest
            ):
                raise ConfigError(
                    f"{label}: rebalance {strategy.rebalance!r} is finer than "
                    f"environment.rebalance_frequency {environment.rebalance_frequency!r}"
                )
            if strategy.type == "equal_weight" and not (
                constraints.min_weight <= 1 / n <= constraints.max_weight
            ):
                raise ConfigError(
                    f"{label}: equal weight 1/{n} violates weight bounds "
                    f"[{constraints.min_weight}, {constraints.max_weight}]"
                )
            if strategy.type == "inverse_volatility" and constraints.max_weight * n < 1:
                raise ConfigError(f"{label}: max_weight * {n} assets < 1; cannot stay invested")
            if strategy.type == "fixed_weights":
                weights = dict(strategy.weights or ())
                unknown = [t for t in weights if t not in data.universe]
                if unknown:
                    raise ConfigError(f"{label}: {unknown} not in data.universe")
                bad = [
                    t
                    for t, w in weights.items()
                    if not constraints.min_weight <= w <= constraints.max_weight
                ]
                if bad:
                    raise ConfigError(f"{label}: weights of {bad} violate the weight bounds")
                total = sum(weights.values())
                if total > 1 + 1e-9 or (not constraints.allow_cash and abs(total - 1) > 1e-9):
                    raise ConfigError(
                        f"{label}: weights sum to {total}; must be <= 1 "
                        "(and exactly 1 when cash is not allowed); no leverage"
                    )


def load_backtest_config(path: str | Path) -> BacktestConfig:
    return BacktestConfig.from_dict(load_yaml(path))


# --------------------------------------------------------------------------
# PPO agent (milestone 5.3, configs/agent.yaml)
# --------------------------------------------------------------------------

AGENT_ACTIVATIONS = ("tanh", "relu")
# Execution policy (D-075). Parallel execution and continue-on-failure need separate approval.
EXECUTION_MODES = ("sequential",)
FAILURE_POLICIES = ("stop",)


@dataclass(frozen=True)
class PPORunSpec:
    """One training run: a grid configuration (index in grid order) and a seed."""

    configuration: int
    learning_rate: float
    n_steps: int
    ent_coef: float
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "configuration": self.configuration,
            "learning_rate": self.learning_rate,
            "n_steps": self.n_steps,
            "ent_coef": self.ent_coef,
            "seed": self.seed,
        }


def _unique_list(raw: Any, field: str) -> list[Any]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError(f"{field}: expected a non-empty list")
    if len(set(raw)) != len(raw):
        raise ConfigError(f"{field}: values must be unique, got {raw}")
    return raw


@dataclass(frozen=True)
class AgentConfig:
    """PPO grid, seeds and training budget (D-066) plus pinned Stable-Baselines3 settings."""

    algorithm: str
    policy: str
    seeds: tuple[int, ...]
    total_timesteps: int
    learning_rates: tuple[float, ...]
    n_steps: tuple[int, ...]
    ent_coefs: tuple[float, ...]
    batch_size: int
    n_epochs: int
    gamma: float
    gae_lambda: float
    clip_range: float
    vf_coef: float
    max_grad_norm: float
    net_arch: tuple[int, ...]
    activation: str
    log_std_init: float
    device: str
    torch_num_threads: int
    output_dir: Path
    # Execution policy (not part of a run's identity; does not change results).
    execution_mode: str = "sequential"
    run_timeout_seconds: int = 900
    on_failure: str = "stop"

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> AgentConfig:
        keys = {
            "algorithm", "policy", "seeds", "total_timesteps", "grid", "batch_size", "fixed",
            "device", "torch_num_threads", "output_dir", "execution",
        }  # fmt: skip
        _check_keys(raw, "agent", required=keys)
        if raw["algorithm"] != "ppo":
            raise ConfigError("agent.algorithm: only 'ppo' is implemented")
        if raw["policy"] != "MlpPolicy":
            raise ConfigError("agent.policy: only 'MlpPolicy' is implemented")
        if raw["device"] != "cpu":
            raise ConfigError("agent.device: only 'cpu' is supported (CPU-only PyTorch)")
        seeds = []
        for value in _unique_list(raw["seeds"], "agent.seeds"):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**32:
                raise ConfigError(f"agent.seeds: {value!r} is not an integer in [0, 2**32)")
            seeds.append(value)

        grid = raw["grid"]
        _check_keys(grid, "agent.grid", required={"learning_rate", "n_steps", "ent_coef"})
        rates = [_as_float(v, "agent.grid.learning_rate") for v in
                 _unique_list(grid["learning_rate"], "agent.grid.learning_rate")]  # fmt: skip
        if any(r <= 0 or r >= 1 for r in rates):
            raise ConfigError("agent.grid.learning_rate values must be in (0, 1)")
        batch_size = _as_int(raw["batch_size"], "agent.batch_size", minimum=2)
        steps = [_as_int(v, "agent.grid.n_steps", minimum=2) for v in
                 _unique_list(grid["n_steps"], "agent.grid.n_steps")]  # fmt: skip
        if any(n % batch_size for n in steps):
            raise ConfigError(
                f"agent.grid.n_steps {steps} must be multiples of agent.batch_size {batch_size}"
            )
        entropy = [_as_float(v, "agent.grid.ent_coef") for v in
                   _unique_list(grid["ent_coef"], "agent.grid.ent_coef")]  # fmt: skip
        if any(c < 0 for c in entropy):
            raise ConfigError("agent.grid.ent_coef values must be >= 0")

        fixed = raw["fixed"]
        names = {
            "n_epochs", "gamma", "gae_lambda", "clip_range", "vf_coef", "max_grad_norm",
            "net_arch", "activation", "log_std_init",
        }  # fmt: skip
        _check_keys(fixed, "agent.fixed", required=names)
        unit = {k: _as_float(fixed[k], f"agent.fixed.{k}") for k in ("gamma", "gae_lambda")}
        if any(not 0 < v <= 1 for v in unit.values()):
            raise ConfigError("agent.fixed.gamma and gae_lambda must be in (0, 1]")
        positive = {
            k: _as_float(fixed[k], f"agent.fixed.{k}")
            for k in ("clip_range", "vf_coef", "max_grad_norm")
        }
        if any(v <= 0 for v in positive.values()):
            raise ConfigError("agent.fixed.clip_range, vf_coef and max_grad_norm must be > 0")
        layers = fixed["net_arch"]
        if not isinstance(layers, list) or not layers:
            raise ConfigError("agent.fixed.net_arch: expected a non-empty list of layer sizes")
        net_arch = tuple(_as_int(v, "agent.fixed.net_arch", minimum=1) for v in layers)
        return cls(
            algorithm="ppo",
            policy="MlpPolicy",
            seeds=tuple(seeds),
            total_timesteps=_as_int(raw["total_timesteps"], "agent.total_timesteps", minimum=1),
            learning_rates=tuple(rates),
            n_steps=tuple(steps),
            ent_coefs=tuple(entropy),
            batch_size=batch_size,
            n_epochs=_as_int(fixed["n_epochs"], "agent.fixed.n_epochs", minimum=1),
            gamma=unit["gamma"],
            gae_lambda=unit["gae_lambda"],
            clip_range=positive["clip_range"],
            vf_coef=positive["vf_coef"],
            max_grad_norm=positive["max_grad_norm"],
            net_arch=net_arch,
            activation=_check_choice(
                _as_str(fixed["activation"], "agent.fixed.activation"),
                AGENT_ACTIVATIONS,
                "agent.fixed.activation",
            ),
            log_std_init=_as_float(fixed["log_std_init"], "agent.fixed.log_std_init"),
            device="cpu",
            torch_num_threads=_as_int(
                raw["torch_num_threads"], "agent.torch_num_threads", minimum=1
            ),
            output_dir=_as_relative_or_absolute_path(raw["output_dir"], "agent.output_dir"),
            **_execution_policy(raw["execution"]),
        )

    def run_specs(self) -> tuple[PPORunSpec, ...]:
        """Every (configuration, seed) pair: configurations in grid order, then seeds."""
        configurations = [
            (rate, steps, entropy)
            for rate in self.learning_rates
            for steps in self.n_steps
            for entropy in self.ent_coefs
        ]
        return tuple(
            PPORunSpec(index, rate, steps, entropy, seed)
            for index, (rate, steps, entropy) in enumerate(configurations)
            for seed in self.seeds
        )

    def fixed_hyperparameters(self) -> dict[str, Any]:
        """Settings shared by every run (recorded with each run)."""
        return {
            "algorithm": self.algorithm,
            "policy": self.policy,
            "batch_size": self.batch_size,
            "n_epochs": self.n_epochs,
            "gamma": self.gamma,
            "gae_lambda": self.gae_lambda,
            "clip_range": self.clip_range,
            "vf_coef": self.vf_coef,
            "max_grad_norm": self.max_grad_norm,
            "net_arch": list(self.net_arch),
            "activation": self.activation,
            "log_std_init": self.log_std_init,
            "device": self.device,
            "torch_num_threads": self.torch_num_threads,
        }


def _execution_policy(raw: Any) -> dict[str, Any]:
    _check_keys(raw, "agent.execution", required={"mode", "run_timeout_seconds", "on_failure"})
    mode = _as_str(raw["mode"], "agent.execution.mode")
    if mode not in EXECUTION_MODES:
        raise ConfigError(
            f"agent.execution.mode {mode!r}: only 'sequential' is allowed; parallel execution "
            "needs separate approval (D-075)"
        )
    on_failure = _as_str(raw["on_failure"], "agent.execution.on_failure")
    if on_failure not in FAILURE_POLICIES:
        raise ConfigError(f"agent.execution.on_failure {on_failure!r}: only 'stop' is allowed")
    timeout = _as_int(raw["run_timeout_seconds"], "agent.execution.run_timeout_seconds", 60)
    if timeout > 24 * 3600:
        raise ConfigError("agent.execution.run_timeout_seconds must be <= 86400")
    return {"execution_mode": mode, "run_timeout_seconds": timeout, "on_failure": on_failure}


def load_agent_config(path: str | Path) -> AgentConfig:
    return AgentConfig.from_dict(load_yaml(path))


# --------------------------------------------------------------------------
# PPO validation evaluation protocol (milestone B, configs/evaluation.yaml; D-076 accepted)
# --------------------------------------------------------------------------

EVALUATION_POLICY_ACTIONS = ("deterministic",)  # sampled actions need separate approval
EVALUATION_SELECTION_METRICS = ("net_sharpe_annualised",)
EVALUATION_SEED_AGGREGATIONS = ("median",)
EVALUATION_TIE_BREAK = ("lower_learning_rate", "smaller_n_steps", "lower_ent_coef")
EVALUATION_UNDEFINED_METRIC = ("fail",)


@dataclass(frozen=True)
class EvaluationConfig:
    """Frozen parameters of the PPO validation evaluation (every value fixed by D-076)."""

    protocol_version: int
    grid_id: str
    split: str
    policy_actions: str
    selection_metric: str
    seed_aggregation: str
    tie_tolerance: float
    tie_break: tuple[str, ...]
    undefined_metric: str
    output_dir: Path

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> EvaluationConfig:
        keys = {"protocol_version", "grid_id", "split", "policy_actions", "selection",
                "baselines", "output_dir"}  # fmt: skip
        _check_keys(raw, "evaluation", required=keys)
        grid_id = _as_str(raw["grid_id"], "evaluation.grid_id")
        if not re.fullmatch(r"[0-9a-f]{16}", grid_id):
            raise ConfigError("evaluation.grid_id must be a 16-hex-digit grid id")
        if raw["split"] != "validation":
            raise ConfigError("evaluation.split: only 'validation' is allowed (the test split "
                              "is sealed until Gate 3)")  # fmt: skip
        if raw["baselines"] != "from_backtest_config":
            raise ConfigError("evaluation.baselines: only 'from_backtest_config' is allowed")
        selection = raw["selection"]
        _check_keys(selection, "evaluation.selection",
                    required={"metric", "seed_aggregation", "tie_tolerance", "tie_break",
                              "undefined_metric"})  # fmt: skip
        choices = {
            "policy_actions": (raw["policy_actions"], EVALUATION_POLICY_ACTIONS),
            "selection.metric": (selection["metric"], EVALUATION_SELECTION_METRICS),
            "selection.seed_aggregation": (selection["seed_aggregation"],
                                           EVALUATION_SEED_AGGREGATIONS),
            "selection.undefined_metric": (selection["undefined_metric"],
                                           EVALUATION_UNDEFINED_METRIC),
        }  # fmt: skip
        for name, (value, allowed) in choices.items():
            _check_choice(_as_str(value, f"evaluation.{name}"), allowed, f"evaluation.{name}")
        tolerance = _as_float(selection["tie_tolerance"], "evaluation.selection.tie_tolerance")
        if not 0 <= tolerance <= 1e-3:
            raise ConfigError("evaluation.selection.tie_tolerance must be in [0, 1e-3]")
        if tuple(selection["tie_break"] or ()) != EVALUATION_TIE_BREAK:
            raise ConfigError(
                f"evaluation.selection.tie_break must be exactly {list(EVALUATION_TIE_BREAK)} "
                "(the D-066 order)"
            )
        return cls(
            protocol_version=_as_int(raw["protocol_version"], "evaluation.protocol_version", 1),
            grid_id=grid_id,
            split="validation",
            policy_actions=raw["policy_actions"],
            selection_metric=selection["metric"],
            seed_aggregation=selection["seed_aggregation"],
            tie_tolerance=tolerance,
            tie_break=EVALUATION_TIE_BREAK,
            undefined_metric=selection["undefined_metric"],
            output_dir=_as_relative_or_absolute_path(raw["output_dir"], "evaluation.output_dir"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "grid_id": self.grid_id,
            "split": self.split,
            "policy_actions": self.policy_actions,
            "selection_metric": self.selection_metric,
            "seed_aggregation": self.seed_aggregation,
            "tie_tolerance": self.tie_tolerance,
            "tie_break": list(self.tie_break),
            "undefined_metric": self.undefined_metric,
            "baselines": "from_backtest_config",
        }

    def protocol_hash(self) -> str:
        """16-hex SHA-256 prefix of the normalised protocol settings (``to_dict``, canonical JSON).

        Independent of YAML formatting, key order and numeric spelling; it changes whenever a
        protocol setting changes. ``output_dir`` is not a protocol setting and is excluded.
        """
        from adaptive_portfolio.data.cache import short_hash  # local: avoids an import cycle

        return short_hash(self.to_dict())


def load_evaluation_config(path: str | Path) -> EvaluationConfig:
    return EvaluationConfig.from_dict(load_yaml(path))


# ---------------------------------------------------------------- workflow (milestone F) ----
# Artifacts that hold test-period results and must never be read (research_protocol.md §12).
FORBIDDEN_ARTIFACT_IDS = ("ac2d6b163d4f5e4b",)
WORKFLOW_PATH_KEYS = (
    "dataset_dir", "feature_dir", "baseline_backtest_dir", "validation_evaluation_dir",
    "explainability_root", "dashboard_dir",
)  # fmt: skip


@dataclass(frozen=True)
class WorkflowConfig:
    """The saved artifacts the workflow and dashboard read (milestone F; no results here).

    Every path names an existing, recorded artifact (dataset, baseline backtest, validation
    evaluation) or an output root. Artifacts holding test-period results are refused.
    """

    dataset_dir: Path
    feature_dir: Path
    baseline_backtest_dir: Path
    validation_evaluation_dir: Path
    explainability_root: Path
    dashboard_dir: Path

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> WorkflowConfig:
        _check_keys(raw, "workflow", required=set(WORKFLOW_PATH_KEYS))
        paths = {k: _as_relative_or_absolute_path(raw[k], f"workflow.{k}")
                 for k in WORKFLOW_PATH_KEYS}  # fmt: skip
        for key, path in paths.items():
            if any(part in FORBIDDEN_ARTIFACT_IDS for part in path.parts):
                raise ConfigError(f"workflow.{key} points at an artifact with test-period "
                                  "results; it must never be read")  # fmt: skip
        return cls(**paths)


def load_workflow_config(path: str | Path) -> WorkflowConfig:
    return WorkflowConfig.from_dict(load_yaml(path))


# ------------------------------------------------------- test pre-registration (milestone D) ----
# Gate 3 items of docs/approval_checklist.md (G3-1 to G3-27) in machine-readable form. A DRAFT may
# hold OPEN items and proposed values; only a FROZEN file (every item ACCEPTED, with a record of
# where the acceptance is written) can drive the test evaluator, and only with its exact hash.
PREREGISTRATION_ITEMS = (
    "candidate", "primary_endpoint", "secondary_metrics", "baselines", "uncertainty",
    "multiple_comparisons", "success_criteria", "stress_windows", "regimes", "cost_sensitivity",
    "lag_sensitivity", "constraint_sensitivity", "concentration", "walk_forward", "embargo",
    "sortino", "reporting", "outputs",
)  # fmt: skip
PREREGISTRATION_SECONDARY = (
    "net_cumulative_return", "gross_cumulative_return", "net_annualised_return",
    "net_annualised_volatility", "net_max_drawdown", "gross_max_drawdown", "cost_drag",
    "annualised_traded_notional", "total_two_way_turnover", "gross_sharpe_annualised",
    "allocation", "trade_counts",
)  # fmt: skip
_HEX16 = re.compile(r"[0-9a-f]{16}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class PreregistrationConfig:
    """A Gate 3 test pre-registration (milestone D). Values are data, not approvals."""

    version: int
    status: str  # "draft" | "frozen"
    items: Mapping[str, Mapping[str, Any]]  # item -> {decision, record, ...normalised values}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> PreregistrationConfig:
        required = {"preregistration_version", "status", *PREREGISTRATION_ITEMS}
        _check_keys(raw, "preregistration", required=required)
        status = _check_choice(
            _as_str(raw["status"], "preregistration.status"), ("draft", "frozen"),
            "preregistration.status",
        )  # fmt: skip
        items = {name: _prereg_item(name, raw[name]) for name in PREREGISTRATION_ITEMS}
        version = _as_int(raw["preregistration_version"], "preregistration_version", 1)
        config = cls(version, status, MappingProxyType(items))
        statistic = items["uncertainty"]["statistic"]
        aggregation = items["primary_endpoint"]["seed_aggregation"]
        if statistic.startswith("median_") and aggregation != "median":
            raise ConfigError("the bootstrap statistic must use the primary aggregation")
        if status == "frozen" and (problems := config.open_items()):
            raise ConfigError(f"a frozen pre-registration cannot have open items: {problems}")
        return config

    def open_items(self) -> list[str]:
        """Items that block execution (OPEN, or stress windows without sources or counts)."""
        problems = [n for n, item in self.items.items() if item["decision"] != "ACCEPTED"]
        windows = self.items["stress_windows"]
        if windows["include"]:
            if not windows["sources"]:
                problems.append("stress_windows (no cited sources)")
            if not windows["windows"]:
                problems.append("stress_windows (no windows)")
            if any(w["expected_sessions"] is None for w in windows["windows"]):
                problems.append("stress_windows (missing expected session counts)")
        return problems

    def value(self, item: str, key: str) -> Any:
        return self.items[item][key]

    def to_dict(self) -> dict[str, Any]:
        return {
            "preregistration_version": self.version,
            "status": self.status,
            **{name: dict(item) for name, item in self.items.items()},
        }

    def sha256(self) -> str:
        """Full SHA-256 of the canonical content (sorted-key JSON): the pre-registration hash."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def protocol_hash(self) -> str:
        """16-hex hash of the protocol values only (no status, decisions or records)."""
        from adaptive_portfolio.data.cache import short_hash  # local: avoids an import cycle

        values = {
            name: {k: v for k, v in item.items() if k not in ("decision", "record")}
            for name, item in self.items.items()
        }
        return short_hash({"preregistration_version": self.version, **values})


def _prereg_item(name: str, raw: Any) -> dict[str, Any]:
    where = f"preregistration.{name}"
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{where}: expected a mapping")
    decision = _check_choice(
        _as_str(raw.get("decision"), f"{where}.decision"), ("OPEN", "ACCEPTED"),
        f"{where}.decision",
    )  # fmt: skip
    record = raw.get("record")
    if decision == "ACCEPTED" and not (isinstance(record, str) and record.strip()):
        raise ConfigError(f"{where}: an ACCEPTED item needs a record (where it was approved)")
    values = {k: v for k, v in raw.items() if k not in ("decision", "record")}
    return {"decision": decision, "record": record, **_PREREG_VALIDATORS[name](values, where)}


def _prereg_candidate(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    _check_keys(
        v, where, required={"configuration", "grid_id", "validation_evaluation_id", "checkpoints"}
    )
    for key in ("grid_id", "validation_evaluation_id"):
        if not _HEX16.fullmatch(_as_str(v[key], f"{where}.{key}")):
            raise ConfigError(f"{where}.{key} must be a 16-hex id")
    checkpoints = []
    for i, c in enumerate(v["checkpoints"] or []):
        _check_keys(c, f"{where}.checkpoints[{i}]", required={"seed", "run_id", "model_sha256"})
        if not _HEX16.fullmatch(str(c["run_id"])) or not _HEX64.fullmatch(str(c["model_sha256"])):
            raise ConfigError(f"{where}.checkpoints[{i}]: run_id 16-hex, model_sha256 64-hex")
        seed = _as_int(c["seed"], f"{where}.checkpoints[{i}].seed", 0)
        checkpoints.append({"seed": seed, "run_id": c["run_id"], "model_sha256": c["model_sha256"]})
    seeds = [c["seed"] for c in checkpoints]
    if not checkpoints or len(set(seeds)) != len(seeds):
        raise ConfigError(f"{where}.checkpoints: at least one, with unique seeds")
    return {
        "configuration": _as_int(v["configuration"], f"{where}.configuration", 0),
        "grid_id": v["grid_id"],
        "validation_evaluation_id": v["validation_evaluation_id"],
        "checkpoints": sorted(checkpoints, key=lambda c: c["seed"]),
    }


def _prereg_primary(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    _check_keys(v, where, required={"metric", "seed_aggregation", "primary_baseline"})
    _check_choice(v["metric"], ("net_sharpe_annualised",), f"{where}.metric")
    _check_choice(v["seed_aggregation"], ("median", "mean"), f"{where}.seed_aggregation")
    baseline = _as_str(v["primary_baseline"], f"{where}.primary_baseline")
    if not baseline.strip():
        raise ConfigError(f"{where}.primary_baseline must name a baseline strategy")
    return {
        "metric": v["metric"],
        "seed_aggregation": v["seed_aggregation"],
        "primary_baseline": baseline,
    }


def _prereg_secondary(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    _check_keys(v, where, required={"metrics"})
    metrics = list(v["metrics"] or [])
    unknown = sorted(set(metrics) - set(PREREGISTRATION_SECONDARY))
    if unknown:
        raise ConfigError(f"{where}.metrics: unknown {unknown}")
    return {"metrics": metrics}


def _prereg_baselines(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    _check_keys(v, where, required={"source", "same_run"})
    _check_choice(v["source"], ("from_backtest_config",), f"{where}.source")
    if v["same_run"] is not True:
        raise ConfigError(f"{where}.same_run must be true (no separate test access)")
    return {"source": v["source"], "same_run": True}


def _prereg_uncertainty(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    keys = {"include", "method", "mean_block_length", "sensitivity_block_lengths", "resamples",
            "seed", "confidence_level", "statistic", "interval", "p_values"}  # fmt: skip
    _check_keys(v, where, required=keys)
    methods = ("stationary_block_bootstrap", "circular_block_bootstrap", "moving_block_bootstrap")
    _check_choice(v["method"], methods, f"{where}.method")
    statistics = ("median_seed_sharpe_minus_primary_baseline_sharpe",)
    _check_choice(v["statistic"], statistics, f"{where}.statistic")
    _check_choice(v["interval"], ("percentile",), f"{where}.interval")
    _check_choice(v["p_values"], ("not_reported",), f"{where}.p_values")  # D-083
    level = _as_float(v["confidence_level"], f"{where}.confidence_level")
    if not 0.5 < level < 1:
        raise ConfigError(f"{where}.confidence_level must be in (0.5, 1)")
    resamples = _as_int(v["resamples"], f"{where}.resamples", 100)
    if resamples > 1_000_000:
        raise ConfigError(f"{where}.resamples must be <= 1,000,000")
    return {
        "include": _as_bool(v["include"], f"{where}.include"),
        "method": v["method"],
        "mean_block_length": _as_int(v["mean_block_length"], f"{where}.mean_block_length", 1),
        "sensitivity_block_lengths": [
            _as_int(b, f"{where}.sensitivity_block_lengths", 1)
            for b in v["sensitivity_block_lengths"] or []
        ],
        "resamples": resamples,
        "seed": _as_int(v["seed"], f"{where}.seed", 0),
        "confidence_level": level,
        "statistic": v["statistic"],
        "interval": v["interval"],
        "p_values": v["p_values"],
    }


def _prereg_comparisons(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    # D-083: one inferential comparison (the primary baseline); the other baselines get
    # descriptive point differences. More inferential comparisons need a new decision.
    _check_keys(v, where, required={"method", "other_baselines"})
    _check_choice(v["method"], ("none",), f"{where}.method")
    others = ("descriptive_point_differences",)
    _check_choice(v["other_baselines"], others, f"{where}.other_baselines")
    return {"method": v["method"], "other_baselines": v["other_baselines"]}


def _prereg_success(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    # D-083: effect sizes with uncertainty; no pass/fail threshold.
    _check_keys(v, where, required={"minimum_difference", "reporting"})
    if v["minimum_difference"] is not None:
        raise ConfigError(f"{where}.minimum_difference must be null (no threshold, D-083)")
    _check_choice(v["reporting"], ("effect_size_with_interval",), f"{where}.reporting")
    return {"minimum_difference": None, "reporting": v["reporting"]}


def _prereg_stress(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    keys = {"include", "rule", "boundary", "expected_sessions_basis", "sources", "windows"}
    _check_keys(v, where, required=keys)
    boundaries = ("peak_close_exclusive_trough_close_inclusive",)
    _check_choice(v["boundary"], boundaries, f"{where}.boundary")
    sources = []
    for i, s in enumerate(v["sources"] or []):
        _check_keys(s, f"{where}.sources[{i}]", required={"citation", "url"})
        citation = _as_str(s["citation"], f"{where}.sources[{i}].citation")
        url = _as_str(s["url"], f"{where}.sources[{i}].url")
        if not citation.strip() or not url.startswith("https://"):
            raise ConfigError(f"{where}.sources[{i}]: a citation and an https URL are needed")
        sources.append({"citation": citation, "url": url})
    windows = []
    for i, w in enumerate(v["windows"] or []):
        at = f"{where}.windows[{i}]"
        _check_keys(w, at, required={"name", "peak_close", "trough_close", "expected_sessions"})
        peak = _parse_date(w["peak_close"], f"{at}.peak_close")
        trough = _parse_date(w["trough_close"], f"{at}.trough_close")
        if trough <= peak:
            raise ConfigError(f"{at}: the trough close must be after the peak close")
        count = w["expected_sessions"]
        count = None if count is None else _as_int(count, f"{at}.expected_sessions", 1)
        windows.append(
            {
                "name": _as_str(w["name"], f"{at}.name"),
                "peak_close": peak.isoformat(),
                "trough_close": trough.isoformat(),
                "expected_sessions": count,
            }
        )
    return {
        "include": _as_bool(v["include"], f"{where}.include"),
        "rule": v["rule"],
        "boundary": v["boundary"],
        "expected_sessions_basis": v["expected_sessions_basis"],
        "sources": sources,
        "windows": windows,
    }


def _prereg_regimes(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    keys = {"include", "taxonomy", "thresholds_sha256", "min_sessions", "label_convention"}
    _check_keys(v, where, required=keys)
    if not _HEX64.fullmatch(_as_str(v["thresholds_sha256"], f"{where}.thresholds_sha256")):
        raise ConfigError(f"{where}.thresholds_sha256 must be a 64-hex SHA-256")
    _check_choice(v["label_convention"], ("t_minus_lag",), f"{where}.label_convention")
    return {
        "include": _as_bool(v["include"], f"{where}.include"),
        "taxonomy": v["taxonomy"],
        "thresholds_sha256": v["thresholds_sha256"],
        "min_sessions": _as_int(v["min_sessions"], f"{where}.min_sessions", 1),
        "label_convention": v["label_convention"],
    }


def _prereg_costs(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    _check_keys(v, where, required={"total_bps", "mode"})
    # D-083: the primary run's decided targets are replayed; the policy does not adapt.
    _check_choice(v["mode"], ("fixed_action_accounting",), f"{where}.mode")
    levels = [_as_float(b, f"{where}.total_bps") for b in v["total_bps"] or []]
    if any(not 0 <= b < 1000 for b in levels):
        raise ConfigError(f"{where}.total_bps must be in [0, 1000)")
    return {"total_bps": levels, "mode": v["mode"]}


def _prereg_lags(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    _check_keys(v, where, required={"lags"})
    lags = [_as_int(lag, f"{where}.lags", 0) for lag in v["lags"] or []]
    if 0 in lags:
        raise ConfigError(
            f"{where}: lag 0 is not supported for PPO (D-071: the environment needs lag >= 1)"
        )
    return {"lags": lags}


def _prereg_constraints(v: Mapping[str, Any], where: str) -> dict[str, Any]:
    _check_keys(v, where, required={"baseline_max_weights", "policy"})
    caps = [_as_float(w, f"{where}.baseline_max_weights") for w in v["baseline_max_weights"] or []]
    if any(not 0 < w <= 1 for w in caps):
        raise ConfigError(f"{where}.baseline_max_weights must be in (0, 1]")
    _check_choice(v["policy"], ("none",), f"{where}.policy")  # the trained PPO cap stays fixed
    return {"baseline_max_weights": caps, "policy": "none"}


def _prereg_choice(key: str, allowed: tuple[str, ...]):
    def validate(v: Mapping[str, Any], where: str) -> dict[str, Any]:
        _check_keys(v, where, required={key})
        _check_choice(v[key], allowed, f"{where}.{key}")
        return {key: v[key]}

    return validate


_PREREG_VALIDATORS = {
    "candidate": _prereg_candidate,
    "primary_endpoint": _prereg_primary,
    "secondary_metrics": _prereg_secondary,
    "baselines": _prereg_baselines,
    "uncertainty": _prereg_uncertainty,
    "multiple_comparisons": _prereg_comparisons,
    "success_criteria": _prereg_success,
    "stress_windows": _prereg_stress,
    "regimes": _prereg_regimes,
    "cost_sensitivity": _prereg_costs,
    "lag_sensitivity": _prereg_lags,
    "constraint_sensitivity": _prereg_constraints,
    "concentration": _prereg_choice("cash_convention", ("risky_sleeve_rescaled_cash_separate",)),
    "walk_forward": _prereg_choice(
        "value", ("not_feasible", "scheduled_separately", "excluded_from_this_protocol")
    ),
    "embargo": _prereg_choice("value", ("none", "gap_required", "not_applied")),
    "sortino": _prereg_choice("value", ("exclude",)),  # including it needs an implementation
    "reporting": _prereg_choice("policy", ("report_all_preregistered",)),
    "outputs": _prereg_choice("root", ("data/processed/test_evaluations",)),
}


def load_preregistration(path: str | Path) -> PreregistrationConfig:
    return PreregistrationConfig.from_dict(load_yaml(path))
