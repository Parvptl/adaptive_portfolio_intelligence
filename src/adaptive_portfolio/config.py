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
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

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
