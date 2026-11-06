"""What keeps a long unattended run honest: hooks that speak inside a long turn, a
question nobody is watching, waiting without spending, what a session leaves running,
the machine's floor, the reviewer's own home, the end of a loop, and what a waking
carries."""
import datetime as dt
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import time
import types
import uuid

import pytest

from test_cli import E, completed, git_commit, record_claude, result_json


def hook(curia, cli, estate, monkeypatch, event, seat="warden", **payload):
    monkeypatch.setenv("CURIA_SEAT", seat)
    monkeypatch.setenv("CURIA_ESTATE", str(estate.dir))
    return cli("hook", event, stdin=json.dumps(payload))


def awake_since(curia, estate, seat, hours):
    at = (curia.now() - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    (estate.seat_dir(seat) / "sessions.log").write_text(f"start {at} account=a session=s1 pid={os.getpid()}\n")


# ---------------------------------------------------------------- shift, inside a turn

def test_a_long_turn_hears_the_shift_from_posttooluse(curia, cli, estate, monkeypatch):
    monkeypatch.delenv("CURIA_HEADLESS", raising=False)
    awake_since(curia, estate, "warden", 7)
    rc, out, _ = hook(curia, cli, estate, monkeypatch, "tool-shift", session_id="s1")
    assert rc == 0
    said = json.loads(out)["hookSpecificOutput"]
    assert said["hookEventName"] == "PostToolUse" and "Shift over: this session has been awake 7.0h" in said["additionalContext"]
    assert "shift" in [e[0] for e in curia.session_events(estate.seat_dir("warden"))]
    # told, it is quiet until the reminder is due...
    assert hook(curia, cli, estate, monkeypatch, "tool-shift", session_id="s1")[1] == ""
    told = estate.seat_dir("warden") / "SHIFT-TOLD"
    old = time.time() - 31 * 60
    os.utime(told, (old, old))
    # ...and the Stop hook still has its one word when the turn does end
    rc, out, err = hook(curia, cli, estate, monkeypatch, "shift", session_id="s1")
    assert rc == 2 and "Shift over" in err
    rc, out, _ = hook(curia, cli, estate, monkeypatch, "tool-shift", session_id="s1")
    assert "Shift over" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_the_midturn_check_is_at_most_once_a_minute(curia, cli, estate, monkeypatch):
    monkeypatch.delenv("CURIA_HEADLESS", raising=False)
    awake_since(curia, estate, "warden", 1)
    assert hook(curia, cli, estate, monkeypatch, "tool-shift", session_id="s1")[1] == ""
    awake_since(curia, estate, "warden", 7)
    assert hook(curia, cli, estate, monkeypatch, "tool-shift", session_id="s1")[1] == ""   # asked seconds ago
    old = time.time() - 61
    os.utime(estate.seat_dir("warden") / "SHIFT-CHECKED", (old, old))
    assert "Shift over" in hook(curia, cli, estate, monkeypatch, "tool-shift", session_id="s1")[1]


def test_context_past_an_absolute_number_of_tokens_ends_a_shift(curia, cli, estate, monkeypatch, tmp_path):
    monkeypatch.delenv("CURIA_HEADLESS", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "acct-a"))
    awake_since(curia, estate, "warden", 1)
    # 45% of a million: under context_at, over context_tokens_at
    hook(curia, cli, estate, monkeypatch, "usage", session_id="s1",
         context_window={"used_percentage": 45.0, "context_window_size": 1000000})
    rc, _, err = hook(curia, cli, estate, monkeypatch, "shift", session_id="s1")
    assert rc == 2 and "holds about 450k tokens" in err
    # the same percentage of a small window is nothing
    (estate.seat_dir("warden") / "SHIFT-OVER").unlink()
    hook(curia, cli, estate, monkeypatch, "usage", session_id="s1",
         context_window={"used_percentage": 45.0, "context_window_size": 200000})
    assert hook(curia, cli, estate, monkeypatch, "shift", session_id="s1")[0] == 0


def test_only_an_interactive_session_carries_the_midturn_hooks(curia, estate):
    awake = json.loads(curia.seat_settings(estate))["hooks"]
    assert "hook tool-shift" in json.dumps(awake["PostToolUse"]) and "hook asked" in json.dumps(awake["PreToolUse"])
    headless = json.loads(curia.seat_settings(estate, headless=True))["hooks"]
    assert "PostToolUse" not in headless and "AskUserQuestion" not in json.dumps(headless)


# ---------------------------------------------------------------- a question nobody is watching

def test_a_question_left_standing_reaches_the_principal(curia, cli, estate, monkeypatch):
    monkeypatch.delenv("CURIA_HEADLESS", raising=False)
    started = []
    monkeypatch.setattr(curia.subprocess, "Popen", lambda cmd, **k: started.append((cmd, k)))
    q = {"questions": [{"question": "Promote tonight?"}]}
    rc, out, _ = hook(curia, cli, estate, monkeypatch, "asked", tool_use_id="t-1", tool_input=q)
    assert rc == 0 and out == ""   # it refuses nothing
    marker = estate.seat_dir("warden") / "ASKING-t-1"
    assert marker.exists() and started[0][0][-2:] == ["hook", "asked-wait"]
    assert started[0][1]["start_new_session"] and started[0][1]["env"]["CURIA_ASKING"] == str(marker)
    # it holds none of the hook's pipes, or Claude Code would wait on the sleeper
    assert all(started[0][1][k] == subprocess.DEVNULL for k in ("stdin", "stdout", "stderr"))

    told = []
    monkeypatch.setattr(curia, "notify", lambda est, subject, body, path=None: told.append((subject, body)) or True)
    monkeypatch.setattr(curia.time, "sleep", lambda s: None)
    monkeypatch.setenv("CURIA_ASKING", str(marker))
    hook(curia, cli, estate, monkeypatch, "asked-wait")
    assert told[0][0] == "NEEDS YOU: Warden is waiting on your answer" and "Promote tonight?" in told[0][1]
    hook(curia, cli, estate, monkeypatch, "answered", tool_use_id="t-1")
    assert not marker.exists()


def test_a_question_answered_in_time_tells_nobody(curia, cli, estate, monkeypatch):
    monkeypatch.delenv("CURIA_HEADLESS", raising=False)
    monkeypatch.setattr(curia.subprocess, "Popen", lambda cmd, **k: None)
    hook(curia, cli, estate, monkeypatch, "asked", tool_use_id="t-2", tool_input={"questions": [{"question": "x?"}]})
    marker = estate.seat_dir("warden") / "ASKING-t-2"
    hook(curia, cli, estate, monkeypatch, "answered", tool_use_id="t-2")
    told = []
    monkeypatch.setattr(curia, "notify", lambda *a, **k: told.append(a))
    monkeypatch.setattr(curia.time, "sleep", lambda s: None)
    monkeypatch.setenv("CURIA_ASKING", str(marker))
    hook(curia, cli, estate, monkeypatch, "asked-wait")
    assert told == [] and "answered" not in [e[0] for e in curia.session_events(estate.seat_dir("warden"))]


def with_notify(estate):
    meta = (estate.dir / "estate.toml").read_text()
    assert re.search(r'^notify = .*$', meta, re.M)
    (estate.dir / "estate.toml").write_text(re.sub(r'^notify = .*$', 'notify = "true"', meta, flags=re.M))


def test_tell_reaches_the_principal_and_is_capped(curia, cli, estate, monkeypatch):
    monkeypatch.setenv("CURIA_SEAT", "muse")
    monkeypatch.setenv("CURIA_ESTATE", str(estate.dir))
    rc, _, err = cli("tell", "the disk is nearly full")
    assert rc != 0 and "names no `notify`" in err
    with_notify(estate)
    told = []
    monkeypatch.setattr(curia, "notify", lambda est, subject, body, path=None: told.append(subject) or True)
    for _ in range(6):
        assert cli("tell", "the disk is nearly full")[0] == 0
    assert told[0] == "Muse: the disk is nearly full" and len(told) == 6
    rc, _, err = cli("tell", "again")
    assert rc != 0 and "tell_per_hour is 6" in err and len(told) == 6
    monkeypatch.setattr(curia, "notify", lambda *a, **k: False)
    (estate.seat_dir("muse") / "sessions.log").unlink()
    rc, _, err = cli("tell", "lost")
    assert rc != 0 and "was not told" in err


# ---------------------------------------------------------------- waiting without spending

def test_watch_streams_new_lines_and_can_stop_at_the_first(curia, cli, estate, monkeypatch):
    log = estate.seat_dir("worker") / "assignments.log"
    log.write_text("returned 2026-01-01T00:00:00+00:00 bead=al-0 rc=0\n")
    looks = []

    def later(seconds):
        looks.append(seconds)
        with open(log, "a") as f:
            f.write("dispatch 2026-01-01T01:00:00+00:00 bead=al-1 branch=b\n"
                    "reviewed 2026-01-01T02:00:00+00:00 bead=al-1 by=muse rc=0\n")
    monkeypatch.setattr(curia.time, "sleep", later)
    rc, out, _ = cli(*E(estate), "watch", "--event", "reviewed", "--once")
    assert rc == 0 and out == "reviewed 2026-01-01T02:00:00+00:00 seat=worker bead=al-1 by=muse rc=0\n" and looks


def test_watch_since_resumes_and_narrows(curia, cli, estate, monkeypatch):
    (estate.seat_dir("worker") / "assignments.log").write_text(
        "returned 2026-01-01T00:00:00+00:00 bead=al-0 rc=0\n"
        "returned 2026-01-02T00:00:00+00:00 bead=al-1 rc=0\n"
        "returned 2026-01-03T00:00:00+00:00 bead=al-2 rc=1\n")
    rc, out, _ = cli(*E(estate), "watch", "--since", "2026-01-02T00:00:00+00:00", "--once")
    assert rc == 0 and [x.split()[3] for x in out.splitlines()] == ["bead=al-1", "bead=al-2"]
    rc, out, _ = cli(*E(estate), "watch", "--since", "2026-01-01", "--bead", "al-2", "--once")
    assert "bead=al-2" in out and out.count("\n") == 1
    rc, out, _ = cli(*E(estate), "watch", "--since", "2026-01-01", "--match", "rc=1", "--once")
    assert "bead=al-2" in out and out.count("\n") == 1


def test_watch_gives_up_on_its_timeout_and_with_its_parent(curia, cli, estate, monkeypatch):
    t = [0.0]
    monkeypatch.setattr(curia.time, "monotonic", lambda: t[0])
    monkeypatch.setattr(curia.time, "sleep", lambda s: t.__setitem__(0, t[0] + 100))
    rc, _, err = cli(*E(estate), "watch", "--timeout", "150")
    assert rc == 3 and "nothing more" in err
    ppid = iter([100, 1])
    monkeypatch.setattr(curia.os, "getppid", lambda: next(ppid))
    assert cli(*E(estate), "watch")[0] == 0


def test_bg_records_the_job_and_its_exit(curia, cli, estate, monkeypatch, tmp_path):
    monkeypatch.setenv("CURIA_SEAT", "muse")
    marker = tmp_path / "ran"
    rc, _, err = cli(*E(estate), "bg", "--label", "gate", "--cwd", str(tmp_path), "--", f"touch {marker}; exit 0")
    assert rc == 0, err
    assert marker.exists()
    log = (estate.seat_dir("muse") / "assignments.log").read_text()
    assert "bg " in log and "label=gate" in log and "bg-done" in log and "rc=0" in log
    rc, _, _ = cli(*E(estate), "bg", "--label", "bad", "--", "exit 3")
    assert rc == 1 and "label=bad" in (estate.seat_dir("muse") / "assignments.log").read_text()
    assert "rc=3" in (estate.seat_dir("muse") / "assignments.log").read_text()
    assert curia.open_bg(estate.seat_dir("muse")) == []
    rc, out, _ = cli(*E(estate), "bg", "--list")
    assert rc == 0 and "no background job" in out
    rc, _, err = cli(*E(estate), "bg", "--")
    assert rc != 0 and "nothing to run" in err


def test_bg_needs_a_seat_and_gives_its_children_a_run_of_their_own(curia, cli, estate, monkeypatch, tmp_path):
    monkeypatch.delenv("CURIA_SEAT", raising=False)
    rc, _, err = cli(*E(estate), "bg", "--", "true")
    assert rc != 0 and "a job belongs to a seat" in err
    out = tmp_path / "env"
    monkeypatch.setenv("CURIA_RUN", "the-session-that-asked")
    rc, _, _ = cli(*E(estate), "bg", "--seat", "muse", "--", f'echo "$CURIA_RUN" > {out}')
    assert rc == 0 and out.read_text().startswith("bg-")


MECH_BIN = pathlib.Path(__file__).resolve().parent.parent / "bin" / "curia"


def real_curia(estate, *argv, env=None):
    """The binary itself, in a process of its own, so what it detaches really detaches."""
    e = {k: v for k, v in os.environ.items() if k not in ("CURIA_SEAT", "CURIA_RUN", "CURIA_ESTATE")}
    return subprocess.run([sys.executable, str(MECH_BIN), "--estate", str(estate.dir), *argv], env={**e, **(env or {})},
                          capture_output=True, text=True, timeout=60)


def wait_for(check, seconds=20.0):
    t0 = time.time()
    while time.time() - t0 < seconds:
        if check():
            return True
        time.sleep(0.1)
    return False


def test_bg_outlives_its_caller_writes_exit_and_records_the_end(curia, estate, tmp_path):
    release = tmp_path / "release"
    p = real_curia(estate, "bg", "--seat", "muse", "--label", "gate", "--ignore-floor", "--",
                   f"while [ ! -e {release} ]; do sleep 0.1; done; echo finished; exit 4")
    assert p.returncode == 0, p.stderr   # the caller is gone, the job is not
    sd = estate.seat_dir("muse")
    assert wait_for(lambda: curia.open_bg(sd))
    assert curia.open_bg(sd)[0]["label"] == "gate"
    release.touch()
    assert wait_for(lambda: "bg-done" in curia.read(sd / "assignments.log"))
    log = next((sd / "runs").glob("*bg-gate.log")).read_text()
    assert "finished" in log and log.rstrip().endswith("EXIT=4")
    assert "rc=4" in curia.read(sd / "assignments.log")


def test_stop_ends_a_bg_job_even_when_ps_cannot_see_its_environment(curia, estate, tmp_path):
    # sh and sleep are the binaries macOS hides the environment of: a run id would not find this
    pidfile = tmp_path / "pid"
    p = real_curia(estate, "bg", "--seat", "muse", "--label", "nap", "--ignore-floor", "--", f"echo $$ > {pidfile}; exec sleep 300")
    assert p.returncode == 0, p.stderr
    assert wait_for(pidfile.exists) and wait_for(lambda: pidfile.read_text().strip())
    pid = int(pidfile.read_text())
    assert curia.still_running(pid)
    p = real_curia(estate, "stop", "muse", "--bg", "nap", "--why", "test")
    assert p.returncode == 0 and "background job nap stopped" in p.stdout, p.stdout + p.stderr
    assert wait_for(lambda: not curia.still_running(pid))
    sd = estate.seat_dir("muse")
    assert wait_for(lambda: "bg-done" in curia.read(sd / "assignments.log"))
    assert "EXIT=-15" in next((sd / "runs").glob("*bg-nap.log")).read_text()
    assert "went=yes" in curia.read(sd / "assignments.log") and curia.open_bg(sd) == []


def test_stop_ends_a_headless_run_and_its_launcher_writes_the_record(curia, estate, tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    pidfile = tmp_path / "pid"
    (bindir / "claude").write_text(f"#!/bin/sh\necho $$ > {pidfile}\nexec sleep 300\n")
    (bindir / "claude").chmod(0o755)
    (estate.dir / "prompts" / "b.md").write_text("do\n")
    env = {"PATH": f"{bindir}:{os.environ['PATH']}"}
    p = real_curia(estate, "run", "muse", "--prompt", "b.md", "--detach", "--ignore-floor", env=env)
    assert p.returncode == 0, p.stderr
    assert wait_for(pidfile.exists) and wait_for(lambda: pidfile.read_text().strip())
    pid = int(pidfile.read_text())
    p = real_curia(estate, "stop", "muse", "--why", "superseded")
    assert p.returncode == 0 and "stopped" in p.stdout, p.stdout + p.stderr
    assert wait_for(lambda: not curia.still_running(pid))
    events = curia.session_events(estate.seat_dir("muse"))
    assert "rc=-15" in next(d for ev, _, d in events if ev == "end")
    assert "why=superseded" in next(d for ev, _, d in events if ev == "stopped")


# ---------------------------------------------------------------- what a session leaves running

def test_a_run_that_ended_well_takes_its_group_with_it(curia, tmp_path):
    pidfile = tmp_path / "pid"
    cmd = ["sh", "-c", f"sleep 60 >/dev/null 2>&1 & echo $! > {pidfile}; exit 0"]
    p = curia.invoke_claude(cmd, tmp_path, dict(os.environ), timeout=30, capture=True)
    assert p.returncode == 0
    pid = int(pidfile.read_text())
    time.sleep(0.2)
    assert not curia.pid_alive(pid) or "Z" in subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout


def real_orphan(tmp_path, run, estate_dir):
    """A process in a session of its own carrying a run id: what a group sweep misses."""
    env = dict(os.environ, CURIA_RUN=run, CURIA_ESTATE=str(estate_dir))
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    return p


def test_run_processes_reads_the_environment_not_the_command_line(curia, tmp_path):
    run = "test-" + uuid.uuid4().hex
    p = real_orphan(tmp_path, run, tmp_path)
    decoy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", f"CURIA_RUN={run}x"],
                             env={k: v for k, v in os.environ.items() if k != "CURIA_RUN"}, start_new_session=True)
    time.sleep(0.4)
    try:
        found = [x for x in curia.run_processes() if x["run"] in (run, run + "x")]
        assert [x["pid"] for x in found] == [p.pid] and found[0]["estate"] == str(tmp_path)
    finally:
        p.kill(); decoy.kill(); p.wait(); decoy.wait()


def test_a_session_end_sweeps_what_left_the_group_and_only_that(curia, tmp_path):
    sd = tmp_path / "seat"
    sd.mkdir()
    run = "test-" + uuid.uuid4().hex
    mine, other = real_orphan(tmp_path, run, tmp_path), real_orphan(tmp_path, run + "-other", tmp_path)
    try:
        est = types.SimpleNamespace(meta={})
        assert curia.sweep_run(est, sd, run) == 1
        assert mine.wait(timeout=10) == -signal.SIGTERM and other.poll() is None
        assert f"session={run} killed=1 what=" in (sd / "sessions.log").read_text()
        assert curia.sweep_run(est, sd, run + "-gone") == 0
    finally:
        other.kill(); other.wait()


def test_a_curia_job_started_from_a_session_is_no_leftover(curia):
    assert curia.curia_job("/opt/Python /home/x/.local/bin/curia dispatch hero --bead a")
    assert curia.curia_job("python3 /x/bin/curia --estate /e bg -- true")
    assert not curia.curia_job("/x/bin/curia watch --once")
    assert not curia.curia_job("/x/bin/curia hook asked-wait")
    assert not curia.curia_job("python -m pytest tests/curia")
    assert not curia.curia_job("pytest /x/curia -q")   # an argument that ends in the name is no curia job
    est = types.SimpleNamespace(meta={"sweep_spares": ["mydaemon"]})
    assert curia.leftover(est, "/usr/bin/pytest x") and not curia.leftover(est, "/opt/tmux new -d")
    assert not curia.leftover(est, "/opt/dolt sql-server") and not curia.leftover(est, "mydaemon --serve")


def test_run_sweeps_at_the_end_and_gives_the_session_its_id(curia, cli, estate, monkeypatch):
    swept, seen = [], {}

    def fake(cmd, cwd, env, **kw):
        seen["run"], seen["sid"] = env.get("CURIA_RUN"), cmd[cmd.index("--session-id") + 1]
        return completed(cmd, 0, result_json("ok", session_id=seen["sid"]))
    monkeypatch.setattr(curia, "invoke_claude", fake)
    monkeypatch.setattr(curia, "sweep_run", lambda est, sd, run: swept.append(run))
    (estate.dir / "prompts" / "b.md").write_text("do\n")
    assert cli(*E(estate), "run", "muse", "--prompt", "b.md")[0] == 0
    assert seen["run"] == seen["sid"] and swept == [seen["sid"]]


def start_line(curia, estate, seat, sid, pid=None, headless=True, cwd="/nowhere", run=True):
    curia.log_session(estate.seat_dir(seat), "start", ("headless " if headless else "")
                      + f"account=a cwd={cwd} session={sid} pid={pid or os.getpid()}" + (f" run={sid}" if run else ""))


def fake_procs(curia, monkeypatch, estate, *runs):
    procs = [{"pid": 900000 + i, "command": "/bin/python x", "run": r, "estate": str(estate.dir)} for i, r in enumerate(runs)]
    monkeypatch.setattr(curia, "run_processes", lambda: procs)
    stopped = []
    monkeypatch.setattr(curia, "stop_processes", lambda ps, *a: stopped.extend(p["run"] for p in ps) or len(ps))
    monkeypatch.setattr(curia, "ask_to_stop", lambda o, *a: True)   # the pid on a fake start line is this test's own
    return stopped


def test_stop_ends_a_seats_headless_run_on_proof_of_whose_it_is(curia, cli, estate, monkeypatch):
    start_line(curia, estate, "muse", "s-1")
    stopped = fake_procs(curia, monkeypatch, estate, "s-1", "s-other")
    monkeypatch.delenv("CURIA_SEAT", raising=False)
    rc, out, _ = cli(*E(estate), "stop", "muse", "--why", "superseded by a newer head")
    assert rc == 0 and stopped == ["s-1"] and "Muse's session s-1 stopped" in out
    assert "stopped" in [e[0] for e in curia.session_events(estate.seat_dir("muse"))]
    assert "why=superseded%20by" in (estate.seat_dir("muse") / "sessions.log").read_text()


def test_stop_authority_several_runs_and_a_person_at_the_keyboard(curia, cli, estate, monkeypatch):
    start_line(curia, estate, "muse", "s-1")
    start_line(curia, estate, "muse", "s-2")
    stopped = fake_procs(curia, monkeypatch, estate, "s-1", "s-2")
    monkeypatch.setenv("CURIA_SEAT", "clerk")
    rc, _, err = cli(*E(estate), "stop", "muse")
    assert rc != 0 and "Clerk may not stop Muse" in err and not stopped
    monkeypatch.setenv("CURIA_SEAT", "warden")   # an office with a fleet
    rc, _, err = cli(*E(estate), "stop", "muse")
    assert rc != 0 and "has 2 runs" in err and not stopped
    rc, _, _ = cli(*E(estate), "stop", "muse", "--session", "s-2")
    assert rc == 0 and stopped == ["s-2"]
    # a keyboard session is no job, even in a directory that says headless
    start_line(curia, estate, "clerk", "s-3", headless=False, cwd="/home/headless work")
    rc, out, _ = cli(*E(estate), "stop", "clerk")
    assert rc == 0 and "no headless run to stop" in out
    rc, _, err = cli(*E(estate), "stop", "clerk", "--session", "s-3")
    assert rc != 0 and "awake with a person" in err


def test_stop_does_nothing_to_a_run_older_than_itself(curia, cli, estate, monkeypatch):
    start_line(curia, estate, "muse", "s-old", run=False)   # its launcher would die and leave the run going
    asked = []
    monkeypatch.setattr(curia, "ask_to_stop", lambda o, *a: asked.append(o) or True)
    monkeypatch.delenv("CURIA_SEAT", raising=False)
    rc, out, _ = cli(*E(estate), "stop", "muse")
    assert rc == 0 and "started before" in out and not asked


def test_a_stop_that_does_not_take_says_so(curia, cli, estate, monkeypatch):
    start_line(curia, estate, "muse", "s-1")
    fake_procs(curia, monkeypatch, estate)
    monkeypatch.setattr(curia, "ask_to_stop", lambda o, *a: False)
    monkeypatch.delenv("CURIA_SEAT", raising=False)
    rc, out, _ = cli(*E(estate), "stop", "muse")
    assert rc == 0 and "is still running" in out and "went=no" in (estate.seat_dir("muse") / "sessions.log").read_text()


def test_stop_a_background_job(curia, cli, estate, monkeypatch):
    sd = estate.seat_dir("muse")
    curia.assignments_log(sd, "bg", f"label=gate run=bg-a pid={os.getpid()} log=/l cwd=/c")
    stopped = fake_procs(curia, monkeypatch, estate, "bg-a")
    monkeypatch.delenv("CURIA_SEAT", raising=False)
    assert [j["label"] for j in curia.open_bg(sd)] == ["gate"]
    rc, _, err = cli(*E(estate), "stop", "muse", "--bg", "nope")
    assert rc != 0 and "no running background job" in err
    assert cli(*E(estate), "stop", "muse", "--bg", "gate")[0] == 0 and stopped == ["bg-a"]


def test_reap_stops_only_what_the_record_proves_finished(curia, cli, estate, monkeypatch):
    sd = estate.seat_dir("muse")
    start_line(curia, estate, "muse", "finished")
    curia.log_session(sd, "end", "rc=0 session=finished")
    start_line(curia, estate, "muse", "alive")
    procs = [{"pid": 900001, "command": "/bin/pytest", "run": "finished", "estate": str(estate.dir)},
             {"pid": 900002, "command": "/bin/server", "run": "alive", "estate": str(estate.dir)},
             {"pid": 900003, "command": "/bin/mystery", "run": "never-recorded", "estate": str(estate.dir)},
             {"pid": 900004, "command": "/bin/theirs", "run": "finished", "estate": "/another/estate"},
             {"pid": 900005, "command": "/x/curia dispatch a", "run": "finished", "estate": str(estate.dir)}]
    monkeypatch.setattr(curia, "run_processes", lambda: procs)
    gone = []
    monkeypatch.setattr(curia, "stop_processes", lambda ps, *a: gone.extend(p["pid"] for p in ps) or len(ps))
    lines = []
    assert curia.reap_orphans(estate, dry=True, say=lines.append) == 1 and not gone and "would stop" in lines[0]
    assert curia.reap_orphans(estate, dry=False, say=lines.append) == 1 and gone == [900001]


def test_a_relaunched_session_does_not_inherit_the_last_ones_shift(curia, cli, estate, monkeypatch):
    sd = estate.seat_dir("warden")
    seen = []

    def invoke(cmd, cwd, env, **kw):
        seen.append({m: (sd / m).exists() for m in ("SHIFT-OVER", "SHIFT-TOLD", "SHIFT-CHECKED")})
        for m in ("SHIFT-OVER", "SHIFT-TOLD", "SHIFT-CHECKED"):
            (sd / m).write_text("told\n")
        if len(seen) == 1:
            (sd / "RESTART").touch()
        return 0
    monkeypatch.setattr(curia, "invoke_claude", invoke)
    assert cli(*E(estate), "launch", "warden", "--loop")[0] == 0
    assert len(seen) == 2 and not any(seen[1].values())


def test_reap_clears_a_limited_marker_with_no_session_awake(curia, cli, estate, monkeypatch):
    marker = estate.seat_dir("worker") / "LIMITED"
    marker.write_text("{}")
    lines = []
    curia.reap(estate, dry=True, say=lines.append)
    assert marker.exists() and any("would clear" in x for x in lines)
    curia.reap(estate, dry=False, say=lines.append)
    assert not marker.exists()
    marker.write_text("{}")
    start_line(curia, estate, "worker", "s-1")
    curia.reap(estate, dry=False, say=lines.append)
    assert marker.exists()


# ---------------------------------------------------------------- the machine's floor

def test_past_the_floor_new_jobs_are_refused_and_the_principal_told_hourly(curia, cli, estate, monkeypatch):
    with_notify(estate)
    (estate.dir / "prompts" / "b.md").write_text("do\n")
    told = []
    monkeypatch.setattr(curia, "notify", lambda est, s, b, path=None: told.append(s) or True)
    monkeypatch.setattr(curia, "machine_reading", lambda p: {"disk_free_gb": 1.5, "swap_used_gb": 9.0})
    seen = record_claude(curia, monkeypatch)
    rc, _, err = cli(*E(estate), "run", "muse", "--prompt", "b.md")
    assert rc != 0 and "1.5 GB free on disk (floor_disk_gb is 5)" in err and not seen
    rc, _, err = cli(*E(estate), "dispatch", "worker", "--bead", "al-1", "--repo", "alpha")
    assert rc != 0 and "past its floor" in err and not (estate.root / "worktrees").exists()
    assert told == ["NEEDS YOU: the machine is past its floor"]
    assert "machine-floor" in (estate.dir / "brain" / "fences.log").read_text()
    assert cli(*E(estate), "run", "muse", "--prompt", "b.md", "--ignore-floor")[0] == 0 and seen


def test_the_swap_floor_is_off_until_an_estate_sets_it(curia, cli, estate, monkeypatch):
    monkeypatch.setattr(curia, "machine_reading", lambda p: {"disk_free_gb": 100.0, "swap_used_gb": 40.0})
    assert curia.floor_breaches(estate) == []
    (estate.dir / "estate.toml").write_text("floor_swap_gb = 32\n" + (estate.dir / "estate.toml").read_text())
    est = curia.Estate(estate.dir)
    assert curia.floor_breaches(est) == ["40.0 GB of swap in use (floor_swap_gb is 32)"]
    rc, out, _ = cli(*E(estate), "check")
    assert "past its floor" in out


def test_a_reading_the_machine_cannot_give_is_no_breach(curia, estate, monkeypatch):
    monkeypatch.setattr(curia, "machine_reading", lambda p: {"disk_free_gb": None, "swap_used_gb": None})
    assert curia.floor_breaches(estate) == []


# ---------------------------------------------------------------- the reviewer's home

def git_repo(curia, estate):
    src = estate.root / "alpha"
    subprocess.run(["git", "init", "-q", "-b", "main", str(src)], check=True)
    subprocess.run(["git", "-C", str(src), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(src), "config", "user.name", "t"], check=True)
    (src / "f.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(src), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(src), "commit", "-qm", "base"], check=True)
    subprocess.run(["git", "-C", str(src), "branch", "worker/al-1"], check=True)
    return src


def test_a_second_review_starts_from_what_the_first_pushed_and_a_redispatch_picks_it_up(curia, estate, tmp_path):
    src = git_repo(curia, estate)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "-C", str(src), "remote", "add", "origin", str(origin)], check=True)
    subprocess.run(["git", "-C", str(src), "push", "-q", "origin", "main", "worker/al-1"], check=True)
    def sha(where, ref):
        return subprocess.run(["git", "-C", str(where), "rev-parse", ref], capture_output=True, text=True).stdout.strip()
    # the first review commits in its own home and pushes from a detached HEAD
    home = curia.claim_review_home(estate, "muse", "alpha", "worker/al-1")
    (home / "fix.txt").write_text("fixed\n")
    subprocess.run(["git", "-C", str(home), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(home), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "review: fix"], check=True)
    subprocess.run(["git", "-C", str(home), "push", "-q", "origin", "HEAD:worker/al-1"], check=True)
    pushed = sha(home, "HEAD")
    curia.release_review_home(home)
    assert sha(src, "refs/heads/worker/al-1") != pushed   # the local branch has not moved
    again = curia.claim_review_home(estate, "muse", "alpha", "worker/al-1")
    assert sha(again, "HEAD") == pushed
    curia.release_review_home(again)
    # the worker comes back to the same bead, and has the reviewer's commit
    wt, _ = curia.prepare_worktree(estate, "worker", "alpha", "al-1")
    assert sha(wt, "HEAD") == pushed


def test_the_mechanism_tells_a_reviewer_how_to_work_detached(curia, cli, estate, monkeypatch):
    git_repo(curia, estate)
    prompts = []

    def fake(cmd, cwd, env, **kw):
        prompts.append(cmd[cmd.index("-p") + 1])
        return completed(cmd, 0, result_json("ok", session_id=cmd[cmd.index("--session-id") + 1]))
    monkeypatch.setattr(curia, "invoke_claude", fake)
    (estate.dir / "prompts" / "old-review.md").write_text("An old brief: commit on {branch} and push, in {worktree}.\n")
    rc, _, err = cli(*E(estate), "dispatch", "worker", "--bead", "al-1", "--repo", "alpha", "--review", "muse",
                     "--review-prompt", "old-review.md")
    assert rc == 0, err
    assert "git push origin HEAD:worker/al-1" in prompts[1] and "alpha-review" in prompts[1]
    assert "Stay detached" in prompts[1]


def test_a_reviewer_gets_a_home_of_its_own_and_concurrent_reviews_two(curia, estate):
    git_repo(curia, estate)
    one = curia.claim_review_home(estate, "muse", "alpha", "worker/al-1")
    two = curia.claim_review_home(estate, "muse", "alpha", "worker/al-1")
    assert one == estate.root / "worktrees" / "muse" / "alpha-review" or one.name == "alpha-review"
    assert two.name == "alpha-review-2"
    head = subprocess.run(["git", "-C", str(one), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert head == "HEAD"   # detached, so the branch stays free to check out in the worker's home
    curia.release_review_home(one)
    again = curia.claim_review_home(estate, "muse", "alpha", "worker/al-1")
    assert again == one   # reused, and what it has provisioned with it
    curia.release_review_home(again)
    (one / "uncommitted.txt").write_text("someone's\n")
    assert curia.claim_review_home(estate, "muse", "alpha", "worker/al-1").name == "alpha-review-3"


def test_a_home_held_by_another_seat_refuses_a_dispatch_unless_shared(curia, cli, estate, monkeypatch):
    git_repo(curia, estate)
    seen = record_claude(curia, monkeypatch)
    home = estate.root / "worktrees" / "worker" / "alpha"
    start_line(curia, estate, "muse", "s-held", cwd=str(home))
    rc, _, err = cli(*E(estate), "dispatch", "worker", "--bead", "al-2", "--repo", "alpha")
    assert rc != 0 and "is in use: Muse" in err and "session s-held" in err and not seen
    # a stale start, its launcher gone, holds nothing
    (estate.seat_dir("muse") / "sessions.log").unlink()
    start_line(curia, estate, "muse", "s-dead", pid=999999, cwd=str(home))
    assert curia.home_holders(estate, home) == []
    start_line(curia, estate, "muse", "s-held-2", cwd=str(home))
    assert [k for k, _ in curia.home_holders(estate, home)] == ["muse"]
    rc, _, err = cli(*E(estate), "dispatch", "worker", "--bead", "al-2", "--repo", "alpha", "--share")
    assert rc == 0, err


def test_the_worker_is_free_while_its_review_runs(curia, cli, estate, monkeypatch):
    git_repo(curia, estate)
    seen = []

    def fake(cmd, cwd, env, **kw):
        seen.append(cwd)
        if env["CURIA_SEAT"] == "muse":   # the review is running: the worker can be dispatched again
            assert not curia.seat_at_work(estate, "worker")
            log = (estate.seat_dir("worker") / "assignments.log").read_text()
            assert "reviewing " in log and "reviewed " not in log
        return completed(cmd, 0, result_json("ok", session_id=cmd[cmd.index("--session-id") + 1]))
    monkeypatch.setattr(curia, "invoke_claude", fake)
    rc, _, err = cli(*E(estate), "dispatch", "worker", "--bead", "al-1", "--repo", "alpha", "--review", "muse")
    assert rc == 0, err
    assert seen[0].name == "alpha" and seen[1].name == "alpha-review"
    assert not (seen[1].parent / ".held-alpha-review").exists()   # given back


# ---------------------------------------------------------------- the end of a loop

def bead(id, status="open", **kw):
    return {"id": id, "status": status, "issue_type": kw.pop("type", "task"), "created_by": "ann", "owner": "ann@x",
            "dependencies": [], **kw}


def child_of(parent):
    return [{"depends_on_id": parent, "type": "parent-child"}]


def test_an_epic_with_nothing_workable_beneath_it_is_not_work(curia, estate):
    issues = [bead("e1", type="epic"), bead("a", labels=["needs-principal"], dependencies=child_of("e1")),
              bead("e2", type="epic"), bead("b", dependencies=child_of("e2")),
              bead("e3", type="epic"), bead("e4", type="epic", dependencies=child_of("e3")),
              bead("c", dependencies=child_of("e4")),
              bead("e5", type="epic"),
              bead("e6", "in_progress", type="epic"), bead("d", labels=["needs-principal"], dependencies=child_of("e6"))]
    b = curia.sort_board(estate, issues)
    assert {i["id"] for i in b["ready"]} == {"e2", "b", "e3", "e4", "c"}
    assert {i["id"] for i in b["epics"]} == {"e1", "e5", "e6"} and {i["id"] for i in b["human"]} == {"a", "d"}
    assert curia.board_counts(b)["workable"] == 5 and b["working"] == []


def test_a_board_of_folders_is_clear(curia, estate):
    issues = [bead("e1", type="epic"), bead("a", labels=["needs-principal"], dependencies=child_of("e1"))]
    assert curia.board_counts(curia.sort_board(estate, issues))["workable"] == 0


def test_epics_outside_a_by_nights_scope_hold_nothing(curia, estate):
    issues = [bead("e1", type="epic"), {**bead("x", dependencies=child_of("e1")), "created_by": "bob", "owner": "bob@x"}]
    assert curia.board_counts(curia.sort_board(estate, issues, ["ann"]))["workable"] == 0


def test_a_bead_handed_to_someone_else_is_theirs_on_a_by_night(curia, estate):
    issues = [bead("mine"), bead("handed", assignee="Bob"), bead("to-a-seat", assignee="Worker"),
              bead("to-me", assignee="ANN"), bead("to-a-key", assignee="muse")]
    b = curia.sort_board(estate, issues, ["ann"])
    assert {i["id"] for i in b["ready"]} == {"mine", "to-a-seat", "to-me", "to-a-key"}
    # a filer's own name, a principal's and this machine's git identity are claims, never hand-offs
    actor = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip() or "ann"
    kept = [{**bead("self", assignee="Ann Full"), "created_by": "Ann Full", "owner": "ann"},
            bead("boss", assignee="Nobody Inparticular"), bead("claimed", "in_progress", assignee=actor)]
    b2 = curia.sort_board(estate, kept, ["ann"])
    assert {i["id"] for i in b2["ready"] + b2["working"]} == {"self", "boss", "claimed"} and b2["others"] == []
    assert [i["id"] for i in b["others"]] == ["handed"] and "Bob 1" in curia.by_others(b)
    assert {i["id"] for i in curia.sort_board(estate, issues)["ready"]} == {i["id"] for i in issues}   # no --by: unchanged


def test_the_orders_say_the_loop_stops_itself_and_where_the_waiting_list_is(curia, estate):
    orders = curia.everything_orders("alpha", curia.sort_board(estate, [bead("a"), bead("e", type="epic")]))
    assert "The loop stops itself" in orders and "two wakings in a row" in orders and "nobody needs asking" in orders
    assert "curia waiting alpha" in orders and "what would unblock" not in orders
    assert "1 epics hold nothing workable" in orders and "curia watch" in orders and "curia bg" in orders


def night_estate(curia, cli, estate, monkeypatch, boards, invoke):
    """A loop on scripted boards. Returns what the principal was told."""
    (estate.dir / "estate.toml").write_text((estate.dir / "estate.toml").read_text().replace("settle_minutes = 0 ", "settle_minutes = 90 "))
    told = []
    monkeypatch.setattr(curia, "notify", lambda est, s, b, path=None: told.append((s, b)) or True)
    reads = iter(boards)
    last = {}

    def fake_board(est, repo, by=None):
        last["b"] = next(reads, last.get("b"))
        return last["b"]
    monkeypatch.setattr(curia, "board", fake_board)
    monkeypatch.setattr(curia, "invoke_claude", invoke)
    return told


def clear_board():
    return {"ready": [], "working": [], "blocked": [], "human": [], "epics": [], "closed": 3, "others": [],
            "source": "origin", "fresh": True, "issues": []}


def working_board():
    return {**clear_board(), "ready": [bead("a")], "closed": 2}


def waking(calls):
    def invoke(cmd, cwd, env, **kw):
        calls.append(cmd[-1] if "-p" not in cmd else cmd)
        return 0
    return invoke


def test_a_clear_board_waits_on_the_run_and_a_green_one_goes_in_the_notice(curia, cli, estate, monkeypatch):
    calls = []
    told = night_estate(curia, cli, estate, monkeypatch, [clear_board()], waking(calls))
    looks = iter([[{"status": "in_progress", "workflowName": "ci", "createdAt": "2026-01-01T00:00:00Z", "url": "u"}],
                  [{"status": "completed", "conclusion": "success", "workflowName": "ci", "createdAt": "2026-01-01T00:00:00Z", "url": "u"}]])
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: next(looks))
    slept = []
    monkeypatch.setattr(curia.time, "sleep", slept.append)
    rc, _, err = cli(*E(estate), "launch", "warden", "--repo", "alpha", "--everything")
    assert rc == 0, err
    assert slept and calls == []   # waited, and spent nothing
    assert told[-1][0] == "Warden: board clear in alpha" and "integration run is green" in told[-1][1] and len(told) == 1
    assert "settled" in [e[0] for e in curia.session_events(estate.seat_dir("warden"))]


def test_a_red_run_earns_one_waking_then_the_launcher_stops(curia, cli, estate, monkeypatch):
    calls = []
    told = night_estate(curia, cli, estate, monkeypatch, [clear_board()], waking(calls))
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: [
        {"status": "completed", "conclusion": "failure", "workflowName": "ci", "createdAt": "2026-01-01T00:00:00Z", "url": "http://run/1"}])
    rc, _, err = cli(*E(estate), "launch", "warden", "--repo", "alpha", "--everything")
    assert rc == 0, err
    assert len(calls) == 1 and "http://run/1" in calls[0] and "One waking" in calls[0]
    assert told[0][0] == "NEEDS YOU: Warden: board clear in alpha" and "went red: ci" in told[0][1]
    assert "did not answer the red run" in told[-1][0]   # the fake wrote no handoff


def test_a_red_run_wakes_nothing_if_the_seat_was_launched_meanwhile(curia, cli, estate, monkeypatch):
    calls = []
    told = night_estate(curia, cli, estate, monkeypatch, [clear_board()], waking(calls))

    def runs(*a, **k):
        start_line(curia, estate, "warden", "meanwhile", pid=os.getppid(), headless=False)
        return [{"status": "completed", "conclusion": "failure", "workflowName": "ci", "createdAt": "2026-01-01T00:00:00Z", "url": "u"}]
    monkeypatch.setattr(curia, "integration_runs", runs)
    assert cli(*E(estate), "launch", "warden", "--repo", "alpha", "--everything")[0] == 0
    assert calls == [] and "went red" in told[-1][1]


def test_a_later_green_puts_a_red_right_and_the_wait_is_bounded(curia, estate, monkeypatch):
    since = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: [
        {"status": "completed", "conclusion": "failure", "workflowName": "ci", "createdAt": "2026-01-01T01:00:00Z", "url": "old"},
        {"status": "completed", "conclusion": "success", "workflowName": "ci", "createdAt": "2026-01-01T02:00:00Z", "url": "new"}])
    assert curia.settle_board(estate, "alpha", since, 90)["state"] == "green"
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: [
        {"status": "in_progress", "workflowName": "ci", "createdAt": "2026-01-01T01:00:00Z", "url": "u"}])
    t = [0.0]
    monkeypatch.setattr(curia.time, "monotonic", lambda: t[0])
    monkeypatch.setattr(curia.time, "sleep", lambda s: t.__setitem__(0, t[0] + s))
    out = curia.settle_board(estate, "alpha", since, 5)
    assert out["state"] == "unfinished" and "after 5 minutes" in out["line"]
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: [])
    assert curia.settle_board(estate, "alpha", since, 90)["state"] == "none"
    # gh failing is not "nothing to wait on", and a cancelled run is not green
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: None)
    out = curia.settle_board(estate, "alpha", since, 90)
    assert out["state"] == "unfinished" and "gh could not say" in out["line"]
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: [
        {"status": "completed", "conclusion": "cancelled", "workflowName": "ci", "createdAt": "2026-01-01T01:00:00Z", "url": "u"}])
    out = curia.settle_board(estate, "alpha", since, 90)
    assert out["state"] == "unfinished" and "ended cancelled" in out["line"]
    # a repo with no gate has nothing to wait on
    assert curia.settle_board(estate, "nested", since, 90)["state"] == "none"


def test_settle_minutes_zero_does_not_look(curia, cli, estate, monkeypatch):
    calls = []
    told = night_estate(curia, cli, estate, monkeypatch, [clear_board()], waking(calls))
    meta = (estate.dir / "estate.toml").read_text().replace("settle_minutes = 90 ", "settle_minutes = 0 ")
    (estate.dir / "estate.toml").write_text(meta)
    monkeypatch.setattr(curia, "integration_runs", lambda *a, **k: pytest.fail("it looked"))
    assert cli(*E(estate), "launch", "warden", "--repo", "alpha", "--everything")[0] == 0
    assert told[-1][0] == "Warden: board clear in alpha"


def test_one_wait_covers_every_board_and_stops_at_the_deadline(curia, cli, estate, monkeypatch):
    calls = []
    told = night_estate(curia, cli, estate, monkeypatch, [clear_board(), clear_board()], waking(calls))
    looks = []

    def runs(*a, **k):
        looks.append(a[0])
        return [{"status": "in_progress", "workflowName": "ci", "createdAt": "2026-01-01T00:00:00Z", "url": "u"}]
    monkeypatch.setattr(curia, "integration_runs", runs)
    t = [0.0]
    monkeypatch.setattr(curia.time, "monotonic", lambda: t[0])
    monkeypatch.setattr(curia.time, "sleep", lambda s: t.__setitem__(0, t[0] + s))
    target = (estate.dir / "repos.toml").read_text().replace('path = "alpha/sub"\nforge = "other"', 'path = "alpha/sub"\nforge = "github"\nremote = "https://github.com/org/nested"')
    (estate.dir / "repos.toml").write_text(target)
    assert cli(*E(estate), "launch", "warden", "--repo", "alpha", "--repo", "nested", "--everything")[0] == 0
    assert t[0] <= 91 * 60   # not 90 minutes a board
    assert "still going" in told[-1][1]


def test_integration_runs_ask_only_where_there_is_something_to_ask(curia, estate, monkeypatch):
    since = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    runs = [{"status": "completed", "createdAt": "2026-01-01T00:00:00Z"}, {"status": "completed", "createdAt": "2026-01-03T00:00:00Z"}]
    monkeypatch.setattr(curia, "gh_json", lambda args: runs)
    assert curia.integration_target(estate, "alpha") == ("org/alpha", "main")
    assert curia.integration_runs("org/alpha", "main", since) == runs[1:]
    assert curia.integration_target(estate, "nested") is None   # no forge to ask
    monkeypatch.setattr(curia, "gh_json", lambda args: None)
    assert curia.integration_runs("org/alpha", "main", since) is None


# ---------------------------------------------------------------- who the board waits on

def test_waiting_groups_by_person_and_ranks_by_what_each_unblocks(curia, cli, estate):
    meta = (estate.dir / "estate.toml").read_text()
    (estate.dir / "estate.toml").write_text('human_labels = ["ada-question", "bob-question"]\n'
                                            + meta.replace('human_labels = ["needs-principal", "needs-human", "blocked-by-human"]\n', ""))
    rows = [bead("q1", labels=["ada-question"], title="What density?"),
            bead("q2", labels=["bob-question"], title="Which site?"),
            bead("w1", dependencies=[{"depends_on_id": "q2", "type": "blocks"}]),
            bead("w2", dependencies=[{"depends_on_id": "w1", "type": "blocks"}]),
            bead("later", "deferred", defer_until="2099-01-01T00:00:00Z")]
    (estate.root / "alpha" / ".beads" / "issues.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    rc, out, err = cli(*E(estate), "waiting", "alpha")
    assert rc == 0, err
    assert "5 bead(s) waiting on a person" in out
    assert out.index("bob: 1 bead(s), unblocking 2") < out.index("ada: 1 bead(s), unblocking 0")
    assert "q2" in out and "unblocks 2" in out and "deferred, until its date" in out
    assert "blocked by what waits on someone: 2 bead(s)" in out


# ---------------------------------------------------------------- what a waking carries

def ruling(estate):
    rd = estate.dir / "brain" / "rulings"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "2026-01-02-tests-first.md").write_text("status: enforced\nenforced by: a very long account of a program\n")


def test_check_never_names_another_estate(curia, cli, estate, tmp_path):
    with open(curia.ESTATES_FILE, "a") as f:
        f.write(f'\n[estates.another_client]\npath = "{tmp_path / "nowhere"}"\n')
    rc, out, _ = cli(*E(estate), "check")
    assert "absent from this machine" in out and "another_client" not in out and "nowhere" not in out


def test_a_hook_this_binary_does_not_know_blocks_nothing(curia, cli, estate, monkeypatch):
    rc, _, err = hook(curia, cli, estate, monkeypatch, "from-a-newer-binary")
    assert rc == 1 and "no hook" in err   # exit 2 would refuse the tool


def test_the_authority_section_is_names_and_statuses(curia, estate):
    ruling(estate)
    prime = curia.build_prime(estate, "muse")
    auth = prime.split("## Your authority", 1)[1]
    assert "2026-01-02-tests-first: enforced" in auth and "a very long account" not in auth
    assert "Refused by the harness's permission classifier" in auth and "reading production systems" in auth
    assert "curia watch" in auth and "curia bg" in auth and "curia tell" in auth and "curia stop" in auth


def test_an_estate_says_what_the_classifier_refuses(curia, estate):
    (estate.dir / "estate.toml").write_text('refused_classes = ["only this"]\n' + (estate.dir / "estate.toml").read_text())
    auth = curia.build_prime(curia.Estate(estate.dir), "muse").split("## Your authority", 1)[1]
    assert "only this" in auth and "reading production systems" not in auth


def test_the_fences_line_reads_with_and_without_an_estates_own(curia, estate):
    (estate.dir / "hooks.json").unlink(missing_ok=True)
    auth = curia.build_prime(estate, "muse")
    assert "Fences (programs that refuse, in every seat session): the mechanism's own: a manual /compact" in auth
    (estate.dir / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": "curia hook release-guard"}]}]}}))
    auth = curia.build_prime(estate, "muse")
    assert re.search(r"release-guard \([^)]*\)\. The mechanism's own: a manual /compact", auth)


def test_the_prime_of_a_fleet_manager_says_what_the_fleet_is_doing(curia, estate):
    sd = estate.seat_dir("worker")
    at = (curia.now() - dt.timedelta(minutes=30)).isoformat(timespec="seconds")
    later = (curia.now() - dt.timedelta(minutes=10)).isoformat(timespec="seconds")
    (sd / "assignments.log").write_text(f"dispatch {at} bead=al-1 repo=alpha branch=b worktree=/w review=muse by=W\n"
                                        f"returned {later} bead=al-1 rc=0 session=s\n"
                                        f"reviewing {later} bead=al-1 by=muse home=/h\n")
    prime = curia.build_prime(estate, "warden")
    assert "## Fleet" in prime and "Worker: free; al-1 returned rc=0" in prime and "al-1 under review by muse" in prime
    assert "500 GB free on disk" in prime
    assert "## Fleet" not in curia.build_prime(estate, "muse")
    curia.log_session(sd, "start", f"headless account=a cwd=/w session=s2 pid={os.getpid()}")
    assert "Worker: building al-1" in curia.build_prime(estate, "warden")
    with open(sd / "assignments.log", "a") as f:
        f.write(f"reviewed {curia.now().isoformat(timespec='seconds')} bead=al-1 by=muse rc=0\n")
    assert "under review" not in curia.build_prime(estate, "warden")


def test_a_next_waking_hears_of_its_background_job(curia, estate):
    curia.assignments_log(estate.seat_dir("muse"), "bg", f"label=gate run=bg-a pid={os.getpid()} log=/the/log cwd=/c")
    assert "Your background job gate: running" in curia.build_prime(estate, "muse") and "/the/log" in curia.build_prime(estate, "muse")


def test_check_says_a_heavy_prime_once_and_weight_says_why(curia, cli, estate, tmp_path):
    (estate.seat_dir("muse") / "charter.md").write_text("# Charter\n" + ("law " * 9000))
    (estate.seat_dir("clerk") / "charter.md").write_text("# Charter\n" + ("rule " * 9000))
    rc, out, _ = cli(*E(estate), "check")
    assert "2 active seat(s) wake with a prime over prime_max_kb (32)" in out and "heaviest clerk" in out
    assert out.count("wake with a prime") == 1 and "Your charter 43 KB" in out and "curia weight" in out
    (estate.root / "alpha" / "CLAUDE.md").write_text("law\n" * 2000)
    (estate.root / "CLAUDE.md").write_text("parent\n" * 2000)
    (estate.root / "alpha" / ".claude").mkdir()
    (estate.root / "alpha" / ".claude" / "settings.json").write_text(json.dumps(
        {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "tracker prime"}]}]}}))
    rc, out, err = cli(*E(estate), "weight", "muse", "--repo", "alpha")
    assert rc == 0, err
    assert "Your charter" in out and str(estate.root / "alpha" / "CLAUDE.md") in out and str(estate.root / "CLAUDE.md") in out
    assert "tracker prime" in out and "connectors = false" in out and "roughly" in out


def test_connectors_and_the_classifier_are_told_from_the_estate(curia, estate):
    settings = json.loads(curia.seat_settings(estate, seat="muse"))
    assert "disableClaudeAiConnectors" not in settings
    env = settings["autoMode"]["environment"]
    assert env[0] == "$defaults" and any("the seat Muse (crew)" in x for x in env)
    assert any(str(estate.seat_dir("muse")) in x for x in env) and any("the one concern" in x for x in env)
    assert set(settings["autoMode"]) == {"environment"}   # context only: never an allow rule
    (estate.dir / "estate.toml").write_text('connectors = false\nauto_mode_environment = ["Source control: x/y"]\n'
                                            + (estate.dir / "estate.toml").read_text())
    settings = json.loads(curia.seat_settings(curia.Estate(estate.dir), seat="muse"))
    assert settings["disableClaudeAiConnectors"] is True and "Source control: x/y" in settings["autoMode"]["environment"]


def test_connectors_can_go_for_one_seat_and_stay_for_another(curia, estate):
    roster = (estate.dir / "roster.toml").read_text()
    (estate.dir / "roster.toml").write_text(roster.replace('[seats.worker]\n', '[seats.worker]\nconnectors = false\n'))
    est = curia.Estate(estate.dir)
    assert json.loads(curia.seat_settings(est, seat="worker"))["disableClaudeAiConnectors"] is True
    assert "disableClaudeAiConnectors" not in json.loads(curia.seat_settings(est, seat="muse"))
