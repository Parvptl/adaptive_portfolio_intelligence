"""Safety helpers for training runs: locks, recovery, finalisation, code provenance (D-075).

Pure Python (no RL library), so the core test matrix covers it.

* **Exclusive finalisation:** a completed staging directory is renamed onto its run directory
  only if that directory does not exist. Completed results are never replaced.
* **Locks:** ``<run_id>.lock`` (one per run) and ``runner.lock`` (one per grid) are created with
  ``O_CREAT | O_EXCL`` and hold the owner's pid, host and start time.
* **Recovery after hard termination:** a lock or staging directory is *stale* only when its
  owner is on this host and its process is no longer alive. Stale items are moved to
  ``<output_dir>/_quarantine/<UTC time>-<name>/`` with a ``reason.json``; nothing is deleted.
  Locks held by a live process, by another host, or with unreadable contents are left alone and
  reported, so a human decides.
* **Code provenance:** the Git commit and working-tree state (with a hash of the uncommitted
  changes). Policy: ``full`` runs need a clean committed tree; ``smoke`` runs may use
  uncommitted code, which is recorded.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

RUN_FILES = ("run_config.json", "metadata.json", "scaler.json", "model.zip", "monitor.csv")
QUARANTINE_DIR = "_quarantine"
STAGING_MARK = ".staging-"
LOCK_SUFFIX = ".lock"


class RunSafetyError(RuntimeError):
    """Raised when a run cannot proceed safely (held lock, unsafe tree, existing output...)."""


class LockHeldError(RunSafetyError):
    def __init__(self, path: Path, info: dict[str, Any] | None, state: str) -> None:
        super().__init__(f"{path} is held ({state}): {info}")
        self.path, self.info, self.state = path, info, state


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Process liveness (never signals a process)
# --------------------------------------------------------------------------


def pid_alive(pid: int) -> bool:
    """Whether process ``pid`` exists on this host. Conservative: unknown counts as alive."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # POSIX signal 0: existence check only, nothing is sent
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# --------------------------------------------------------------------------
# Locks
# --------------------------------------------------------------------------


def read_lock(path: Path) -> dict[str, Any] | None:
    try:
        info = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return info if isinstance(info, dict) else None


def lock_state(path: Path) -> str:
    """``alive``, ``stale`` (same host, process gone) or ``unknown`` (never auto-recovered)."""
    info = read_lock(path)
    if not info or not isinstance(info.get("pid"), int) or "host" not in info:
        return "unknown"
    if info["host"] != socket.gethostname():
        return "unknown"
    return "alive" if pid_alive(info["pid"]) else "stale"


def acquire_lock(path: Path, purpose: str) -> dict[str, Any]:
    """Create ``path`` exclusively; raises :class:`LockHeldError` if it exists."""
    info = {"pid": os.getpid(), "host": socket.gethostname(), "created_at": utc_now(),
            "purpose": purpose}  # fmt: skip
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise LockHeldError(path, read_lock(path), lock_state(path)) from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(info, handle)
    return info


def release_lock(path: Path, info: dict[str, Any]) -> None:
    """Remove our own lock file (only if it still records this process)."""
    current = read_lock(path)
    if current and current.get("pid") == info["pid"] and current.get("host") == info["host"]:
        Path(path).unlink()


# --------------------------------------------------------------------------
# Quarantine and stale recovery (moves, never deletes)
# --------------------------------------------------------------------------


def quarantine(output_dir: Path, items: list[Path], label: str, reason: str) -> Path | None:
    """Move ``items`` into ``<output_dir>/_quarantine/<UTC time>-<label>/`` with a reason."""
    items = [Path(p) for p in items if Path(p).exists()]
    if not items:
        return None
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    event = Path(output_dir) / QUARANTINE_DIR / f"{stamp}-{label}"
    event.mkdir(parents=True)
    for item in items:
        item.rename(event / item.name)
    note = {"quarantined_at": utc_now(), "reason": reason, "items": [p.name for p in items],
            "host": socket.gethostname(), "by_pid": os.getpid()}  # fmt: skip
    (event / "reason.json").write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
    return event


def _staging_pid(path: Path) -> int | None:
    try:
        return int(path.name.rsplit(STAGING_MARK, 1)[1])
    except (IndexError, ValueError):
        return None


def recover_stale(output_dir: Path) -> list[dict[str, Any]]:
    """Quarantine stale run locks and staging directories in ``output_dir``; report the rest.

    Only items whose owner process is provably gone on this host are moved. Completed run
    directories, ``_quarantine`` and ``grids`` are never touched.
    """
    output_dir = Path(output_dir)
    actions: list[dict[str, Any]] = []
    if not output_dir.is_dir():
        return actions
    for lock in sorted(output_dir.glob(f"*{LOCK_SUFFIX}")):
        run_id = lock.name[: -len(LOCK_SUFFIX)]
        state = lock_state(lock)
        staging = sorted(output_dir.glob(f"{run_id}{STAGING_MARK}*"))
        if state == "stale":
            info = read_lock(lock)
            event = quarantine(output_dir, [lock, *staging], run_id,
                               f"stale run lock: owner {info} is no longer running")  # fmt: skip
            actions.append({"item": lock.name, "action": "quarantined", "to": str(event)})
        else:
            actions.append({"item": lock.name, "action": "left", "state": state})
    for staging in sorted(output_dir.glob(f"*{STAGING_MARK}*")):
        if not staging.exists() or (output_dir / f"{staging.name.split(STAGING_MARK)[0]}"
                                    f"{LOCK_SUFFIX}").exists():  # fmt: skip
            continue  # handled with its lock above
        pid = _staging_pid(staging)
        if pid is not None and not pid_alive(pid):
            event = quarantine(
                output_dir,
                [staging],
                staging.name.split(STAGING_MARK)[0],
                f"orphan staging directory: process {pid} is not running",
            )
            actions.append({"item": staging.name, "action": "quarantined", "to": str(event)})
        else:
            actions.append({"item": staging.name, "action": "left", "state": "alive or unknown"})
    return actions


def finalise_exclusive(staging: Path, target: Path) -> None:
    """Rename a complete ``staging`` directory to ``target``; never replaces an existing one."""
    if Path(target).exists():
        raise RunSafetyError(f"{target} already exists; completed results are never replaced")
    Path(staging).rename(
        target
    )  # not .replace(): fails if target appeared meanwhile (Windows) or is non-empty


# --------------------------------------------------------------------------
# Code provenance and policy
# --------------------------------------------------------------------------


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True, timeout=60
    ).stdout


def code_provenance(root: Path) -> dict[str, Any]:
    """Git commit and working-tree state of the repository containing ``root``.

    ``dirty`` covers modified, staged and untracked (non-ignored) files; ``diff_sha256`` hashes
    ``git diff HEAD`` plus the paths and contents of untracked files, so it identifies the
    exact uncommitted code. Without Git (or outside a repository) the state is unavailable and
    treated as not clean.
    """
    try:
        commit = _git(root, "rev-parse", "HEAD").decode().strip()
        status = _git(root, "status", "--porcelain=v1", "--untracked-files=all", "-z")
    except (OSError, subprocess.SubprocessError):
        return {"git_available": False, "commit": None, "dirty": True, "changed_paths": None}
    entries = [e for e in status.decode("utf-8", "replace").split("\0") if e]
    result: dict[str, Any] = {"git_available": True, "commit": commit,
                              "dirty": bool(entries), "changed_paths": len(entries)}  # fmt: skip
    if entries:
        digest = hashlib.sha256(
            _git(root, "diff", "HEAD", "--binary", "--no-color", "--no-ext-diff")
        )
        top = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip())
        for entry in sorted(e for e in entries if e.startswith("?? ")):
            path = entry[3:]
            digest.update(path.encode("utf-8"))
            digest.update(hashlib.sha256((top / path).read_bytes()).digest())
        result["diff_sha256"] = digest.hexdigest()
    return result


def check_code_policy(code: dict[str, Any], run_kind: str) -> None:
    """``full`` runs require a clean, committed working tree; ``smoke`` runs are recorded."""
    if run_kind == "full" and (not code.get("git_available") or code.get("dirty")):
        raise RunSafetyError(
            "full training runs require a clean, committed Git working tree (D-075); found "
            f"{code}. Commit the reviewed code first (no override exists)."
        )


# --------------------------------------------------------------------------
# Verification of a completed run directory
# --------------------------------------------------------------------------


def verify_run_dir(directory: Path, run_id: str, total_timesteps: int) -> list[str]:
    """Problems with a completed run directory (empty list if it is valid)."""
    directory = Path(directory)
    if not directory.is_dir():
        return [f"{directory} does not exist"]
    names = sorted(p.name for p in directory.iterdir())
    if names != sorted(RUN_FILES):
        return [f"files {names} != {sorted(RUN_FILES)}"]
    problems = []
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    config = json.loads((directory / "run_config.json").read_text(encoding="utf-8"))
    if meta.get("status") != "completed":
        problems.append(f"status {meta.get('status')!r}")
    if not (meta.get("run_id") == run_id == directory.name):
        problems.append(f"run id {meta.get('run_id')} / folder {directory.name} != {run_id}")
    if meta.get("timesteps_done", 0) < total_timesteps:
        problems.append(f"timesteps_done {meta.get('timesteps_done')} < {total_timesteps}")
    if config.get("split") != "train":
        problems.append(f"split {config.get('split')!r} is not train")
    for name, digest in (meta.get("files_sha256") or {}).items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            problems.append(f"sha256 mismatch for {name}")
    rewards = pd.read_csv(directory / "monitor.csv", skiprows=1)
    if "r" not in rewards.columns or not np.isfinite(rewards["r"].to_numpy(float)).all():
        problems.append("monitor.csv rewards missing or not finite")
    return problems


# --------------------------------------------------------------------------
# Subprocess execution with a hard timeout
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LaunchOutcome:
    returncode: int | None
    timed_out: bool
    seconds: float


def run_with_timeout(
    command: list[str], timeout_seconds: float, log_path: Path, env: dict[str, str] | None = None
) -> LaunchOutcome:
    """Run ``command``, writing its output to ``log_path``; kill it after ``timeout_seconds``.

    The kill is a hard termination (no cleanup runs in the child); callers must then recover
    stale state with :func:`recover_stale`.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    clock = time.perf_counter()
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            returncode = process.wait(timeout=timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            returncode, timed_out = None, True
        except BaseException:
            process.kill()
            process.wait()
            raise
    return LaunchOutcome(returncode, timed_out, round(time.perf_counter() - clock, 3))
