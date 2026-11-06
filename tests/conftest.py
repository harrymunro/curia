"""Fixtures: the mechanism loaded as a module, an in-process CLI runner, and a
scratch estate built the way `curia init` builds one. Nothing here touches a
live estate, the registry in ~/.config, or a real claude: `invoke_claude` is
the one place claude starts, and tests replace it."""
import contextlib
import importlib.machinery
import importlib.util
import io
import pathlib
import sys

import pytest

MECH = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def curia():
    loader = importlib.machinery.SourceFileLoader("curia_cli", str(MECH / "bin" / "curia"))
    spec = importlib.util.spec_from_loader("curia_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["curia_cli"] = mod   # dataclasses resolve annotations through sys.modules
    loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def no_network(curia, monkeypatch):
    """A judgment a test forgot to fake never reaches the network, and no key
    rides in from the shell. The module is session-scoped, so its error is reset."""
    def refuse(req, timeout):
        raise AssertionError("a test reached jev_open: fake curia.jev or curia.jev_open")
    monkeypatch.setattr(curia, "jev_open", refuse)
    monkeypatch.setattr(curia, "JEV_ERROR", "")
    monkeypatch.delenv("CURIA_JEV_KEY", raising=False)


@pytest.fixture
def cli(curia, monkeypatch):
    """cli("--estate", path, "roster") -> (rc, stdout, stderr), run in-process."""
    def run(*argv: str, stdin: str = ""):
        out, err = io.StringIO(), io.StringIO()
        monkeypatch.setattr(sys, "argv", ["curia", *argv])
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        rc = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                curia.main()
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        return rc, out.getvalue(), err.getvalue()
    return run


ROSTER = '''
[seats.warden]
title = "Warden"
role = "censor"
kind = "office"
model = "model-x"
account = "a"
home = "estate"
tools = ["Bash", "Read"]

[seats.clerk]
title = "Clerk"
role = "notarius"
kind = "office"
model = "model-x"
account = "a"
home = "estate"

[seats.muse]
title = "Muse"
kind = "crew"
model = "model-x"
run_model = "model-y"
account = "a"
home = "estate"
jurisdiction = ["the one concern"]

[seats.worker]
title = "Worker"
kind = "fleet"
model = "model-x"
account = "a"
managed_by = "warden"
'''

REPOS = '''
[repos.alpha]
path = "alpha"
remote = "https://github.com/org/alpha"
forge = "github"
beads_prefix = ["al"]
integration_branch = "main"
release_branch = "main"
gate = "just ci"
leaf = "just test"

[repos.nested]
path = "alpha/sub"
forge = "other"
integration_branch = "main"
gate = "just ci"
'''


@pytest.fixture
def estate(curia, cli, tmp_path, monkeypatch):
    """A scratch estate: two accounts (a falls back to b) with config dirs under
    tmp, one github repo with a nested second, and a seat of each kind."""
    monkeypatch.setattr(curia, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(curia, "ESTATES_FILE", tmp_path / "config" / "estates.toml")
    monkeypatch.setattr(curia, "DETACH_RUNS", False)   # fakes record in-process; the fork has its own test
    monkeypatch.setattr(curia, "run_processes", lambda: [])   # nothing here sweeps or stops a real process
    monkeypatch.setattr(curia, "machine_reading", lambda path: {"disk_free_gb": 500.0, "swap_used_gb": 0.0})
    ws = tmp_path / "ws"
    rc, out, err = cli("init", str(ws), "--name", "Scratch", "--principal", "Nobody Inparticular", "--shape", "factory")
    assert rc == 0, err
    cd = ws / "curia"
    for acct in ("a", "b"):
        (tmp_path / f"acct-{acct}").mkdir()
    (cd / "accounts.toml").write_text(
        f'[accounts.a]\nconfig_dir = "{tmp_path / "acct-a"}"\nfallback = "b"\n'
        f'[accounts.b]\nconfig_dir = "{tmp_path / "acct-b"}"\nfallback = ""\n')
    for rel in ("alpha", "alpha/sub"):
        (ws / rel / ".beads").mkdir(parents=True)
        (ws / rel / ".beads" / "issues.jsonl").write_text("")
    (cd / "repos.toml").write_text(REPOS)
    (cd / "roster.toml").write_text(ROSTER)
    for seat in ("warden", "clerk", "muse", "worker"):
        (cd / "seats" / seat).mkdir(parents=True)
        (cd / "seats" / seat / "charter.md").write_text(f"Charter of {seat}.\n")
    (cd / "prompts" / "lictor-cloud.md").write_text("You are the Lictor. Nudge.\n")
    meta = (cd / "estate.toml").read_text()
    meta = meta.replace('created = "YYYY-MM-DD"', 'created = "2026-01-01"')
    meta = meta.replace("choose one per estate so a seat name is never ambiguous", "scratch")
    meta = "settle_minutes = 0   # the last act reaches no forge unless a test asks\n" + meta
    (cd / "estate.toml").write_text(meta)
    return curia.Estate(cd)
