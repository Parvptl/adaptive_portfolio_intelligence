"""Pre-grid hardening (D-075): locks, stale recovery, exclusive finalisation, code provenance.

No RL library and no training: plain files, temporary Git repositories and short-lived child
processes only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from adaptive_portfolio.agents import run_safety as rs

GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]  # fmt: skip
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def _write_lock(path: Path, pid: int, host: str | None = None) -> None:
    info = {"pid": pid, "host": host or socket.gethostname(), "created_at": "x", "purpose": "t"}
    path.write_text(json.dumps(info), encoding="utf-8")


def _all_files(root: Path) -> set[str]:
    return {p.name for p in root.rglob("*") if p.is_file() and p.name != "reason.json"}


def test_process_liveness_and_exclusive_locks(tmp_path: Path) -> None:
    import os

    assert rs.pid_alive(os.getpid()) and not rs.pid_alive(_dead_pid()) and not rs.pid_alive(0)
    lock = tmp_path / "run.lock"
    info = rs.acquire_lock(lock, "test")
    with pytest.raises(rs.LockHeldError) as held:
        rs.acquire_lock(lock, "second")  # exclusive: a second owner is refused
    assert held.value.state == "alive"
    rs.release_lock(lock, {**info, "pid": info["pid"] + 1})  # not ours: left in place
    assert lock.exists()
    rs.release_lock(lock, info)
    assert not lock.exists()
    _write_lock(lock, _dead_pid())
    assert rs.lock_state(lock) == "stale"
    _write_lock(lock, _dead_pid(), host="another-host")  # never auto-recovered
    assert rs.lock_state(lock) == "unknown"
    lock.write_text("not json", encoding="utf-8")
    assert rs.lock_state(lock) == "unknown"


def test_recover_stale_quarantines_only_provably_stale_state(tmp_path: Path) -> None:
    import os

    out = tmp_path / "experiments"
    completed = out / "0123456789abcdef"  # a completed run: never touched
    completed.mkdir(parents=True)
    (completed / "model.zip").write_bytes(b"done")
    stale_lock = out / "aaaaaaaaaaaaaaaa.lock"
    _write_lock(stale_lock, (dead := _dead_pid()))
    (out / f"aaaaaaaaaaaaaaaa.staging-{dead}").mkdir()
    (out / f"aaaaaaaaaaaaaaaa.staging-{dead}" / "monitor.csv").write_text("partial")
    _write_lock(out / "bbbbbbbbbbbbbbbb.lock", os.getpid())  # alive owner
    (out / f"bbbbbbbbbbbbbbbb.staging-{os.getpid()}").mkdir()
    _write_lock(out / "cccccccccccccccc.lock", 4242, host="another-host")  # other host
    orphan = out / f"dddddddddddddddd.staging-{_dead_pid()}"  # orphan, no lock
    orphan.mkdir()
    before = _all_files(out)

    actions = rs.recover_stale(out)

    moved = {a["item"] for a in actions if a["action"] == "quarantined"}
    assert moved == {"aaaaaaaaaaaaaaaa.lock", orphan.name}
    assert (out / "bbbbbbbbbbbbbbbb.lock").exists() and (out / "cccccccccccccccc.lock").exists()
    assert (out / f"bbbbbbbbbbbbbbbb.staging-{os.getpid()}").exists()  # live owner: kept
    assert (completed / "model.zip").read_bytes() == b"done"
    assert not stale_lock.exists() and not list(out.glob("aaaa*")) and not orphan.exists()
    reasons = list((out / rs.QUARANTINE_DIR).glob("*/reason.json"))
    assert len(reasons) == 2
    assert all("running" in r.read_text(encoding="utf-8") for r in reasons)
    assert _all_files(out) == before  # moved, nothing deleted
    again = rs.recover_stale(out)  # idempotent: nothing further is moved
    assert not [a for a in again if a["action"] == "quarantined"]


def test_finalise_never_replaces_an_existing_run(tmp_path: Path) -> None:
    target, staging = tmp_path / "run", tmp_path / "run.staging-1"
    target.mkdir()
    (target / "model.zip").write_bytes(b"completed")
    staging.mkdir()
    (staging / "model.zip").write_bytes(b"newer")
    with pytest.raises(rs.RunSafetyError, match="never replaced"):
        rs.finalise_exclusive(staging, target)
    assert (target / "model.zip").read_bytes() == b"completed" and staging.exists()
    fresh = tmp_path / "fresh"
    rs.finalise_exclusive(staging, fresh)
    assert (fresh / "model.zip").read_bytes() == b"newer" and not staging.exists()


@needs_git
def test_code_provenance_and_policy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run([*GIT, "-C", str(repo), "init", "-q"], check=True)
    (repo / ".gitignore").write_text("data/\n")
    (repo / "code.py").write_text("x = 1\n")
    subprocess.run([*GIT, "-C", str(repo), "add", "-A"], check=True)
    subprocess.run([*GIT, "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    head = subprocess.run([*GIT, "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()  # fmt: skip

    clean = rs.code_provenance(repo)
    assert clean == {"git_available": True, "commit": head, "dirty": False, "changed_paths": 0}
    rs.check_code_policy(clean, "full")  # allowed
    (repo / "data").mkdir()
    (repo / "data" / "big.csv").write_text("ignored")  # ignored files do not count
    assert rs.code_provenance(repo)["dirty"] is False

    (repo / "code.py").write_text("x = 2\n")
    first = rs.code_provenance(repo)
    (repo / "code.py").write_text("x = 3\n")
    second = rs.code_provenance(repo)
    assert first["dirty"] and first["commit"] == head
    assert first["diff_sha256"] != second["diff_sha256"]  # exact uncommitted state
    (repo / "code.py").write_text("x = 1\n")
    (repo / "new.py").write_text("y = 1\n")  # untracked files count
    untracked = rs.code_provenance(repo)
    assert untracked["dirty"] and untracked["changed_paths"] == 1
    with pytest.raises(rs.RunSafetyError, match="clean, committed"):
        rs.check_code_policy(untracked, "full")
    rs.check_code_policy(untracked, "smoke")  # smoke runs are allowed and recorded

    outside = rs.code_provenance(tmp_path / "not_a_repo_dir_is_missing")
    assert outside["git_available"] is False and outside["dirty"] is True
    with pytest.raises(rs.RunSafetyError):
        rs.check_code_policy(outside, "full")


def test_child_process_is_killed_at_the_timeout(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "child.log"
    slow = rs.run_with_timeout(
        [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(60)"],
        2,
        log,
    )
    assert slow.timed_out and slow.returncode is None and slow.seconds < 30
    assert "started" in log.read_text(encoding="utf-8")
    quick = rs.run_with_timeout([sys.executable, "-c", "raise SystemExit(3)"], 30, log)
    assert quick.returncode == 3 and not quick.timed_out


def test_verify_run_dir_detects_incomplete_or_altered_runs(tmp_path: Path) -> None:
    run = tmp_path / "0123456789abcdef"
    run.mkdir()
    for name in ("model.zip", "scaler.json"):
        (run / name).write_bytes(name.encode())
    (run / "run_config.json").write_text(json.dumps({"split": "train"}), encoding="utf-8")
    (run / "monitor.csv").write_text('#{"t_start": 0}\nr,l,t\n1.5,496,1.0\n', encoding="utf-8")
    digest = {n: hashlib.sha256((run / n).read_bytes()).hexdigest()
              for n in ("model.zip", "scaler.json", "run_config.json")}  # fmt: skip
    meta = {"status": "completed", "run_id": run.name, "timesteps_done": 100,
            "files_sha256": digest}  # fmt: skip
    (run / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    assert rs.verify_run_dir(run, run.name, 100) == []
    assert rs.verify_run_dir(run, run.name, 200)  # too few timesteps
    (run / "model.zip").write_bytes(b"altered")
    assert any("sha256" in p for p in rs.verify_run_dir(run, run.name, 100))
    (run / "model.zip").unlink()
    assert rs.verify_run_dir(run, run.name, 100)  # a missing file
