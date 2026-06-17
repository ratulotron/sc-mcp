"""Tests for sc-mcp.

Two things actually carry risk in this wrapper:
  1. argv assembly — each tool must build the right `sc ...` command line.
  2. failure handling — every failure path must raise ToolError, not crash
     or return a success result.
The cache is covered too since it gates every call.
"""

import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from sc_mcp import server as sc_mcp


class FakeResult:
    def __init__(self, stdout='{"ok": true}', returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


@pytest.fixture
def captured_argv(monkeypatch):
    """Capture the argv passed to subprocess.run; pretend `sc` is on PATH."""
    calls = []
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: "/usr/bin/sc")
    monkeypatch.setattr(sc_mcp, "_SC_CACHE_TTL", 0)  # disable cache for arg tests

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return FakeResult()

    monkeypatch.setattr(sc_mcp.subprocess, "run", fake_run)
    return calls


# ── argv assembly ─────────────────────────────────────────────────────────────
# Each case: (callable, kwargs) -> expected args between "sc" and "--json".
ARGV_CASES = [
    (sc_mcp.sc_overview, {}, ["broker", "overview"]),
    (sc_mcp.sc_overview, {"include_ytd": True}, ["broker", "overview", "--include-year-to-date"]),
    (sc_mcp.sc_overview, {"portfolio_id": "P1"}, ["broker", "overview", "--portfolio-id", "P1"]),
    (sc_mcp.sc_holdings, {"include_ytd": True}, ["broker", "holdings", "--include-year-to-date"]),
    (sc_mcp.sc_analytics, {"portfolio_id": "P1"}, ["broker", "analytics", "--portfolio-id", "P1"]),
    (sc_mcp.sc_transactions, {"page_size": 10}, ["broker", "transactions", "--page-size", "10"]),
    (
        sc_mcp.sc_transactions,
        {"page_size": 25, "isin": "IE00B4L5Y983", "type_filter": "BUY"},
        [
            "broker",
            "transactions",
            "--page-size",
            "25",
            "--isin",
            "IE00B4L5Y983",
            "--type-filter",
            "BUY",
        ],
    ),
    (sc_mcp.sc_quote, {"isin": "IE00B4L5Y983"}, ["broker", "quote", "--isin", "IE00B4L5Y983"]),
    (sc_mcp.sc_search, {"query": "world etf"}, ["broker", "search", "world etf"]),
    (
        sc_mcp.sc_transaction,
        {"transaction_id": "tx-9"},
        ["broker", "transaction", "details", "--transaction-id", "tx-9"],
    ),
    (
        sc_mcp.sc_security_news,
        {"isin": "IE00B4L5Y983"},
        ["broker", "security-news", "--isin", "IE00B4L5Y983", "--locale", "en_DE"],
    ),
]


@pytest.mark.parametrize("fn, kwargs, expected", ARGV_CASES)
def test_argv_assembly(captured_argv, fn, kwargs, expected):
    fn(**kwargs)
    argv = captured_argv[-1]
    assert argv[0] == "/usr/bin/sc"
    assert argv[-1] == "--json"
    assert argv[1:-1] == expected


# ── failure handling ───────────────────────────────────────────────────────────
def test_missing_cli_raises(monkeypatch):
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: None)
    with pytest.raises(ToolError, match="not found"):
        sc_mcp._run_sc("broker", "overview")


def test_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: "/usr/bin/sc")
    monkeypatch.setattr(sc_mcp, "_SC_CACHE_TTL", 0)
    monkeypatch.setattr(
        sc_mcp.subprocess,
        "run",
        lambda *a, **k: FakeResult(stdout="", returncode=1, stderr="not logged in"),
    )
    with pytest.raises(ToolError, match="not logged in"):
        sc_mcp._run_sc("broker", "overview")


def test_timeout_raises(monkeypatch):
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: "/usr/bin/sc")
    monkeypatch.setattr(sc_mcp, "_SC_CACHE_TTL", 0)

    def boom(*a, **k):
        raise sc_mcp.subprocess.TimeoutExpired(cmd="sc", timeout=30)

    monkeypatch.setattr(sc_mcp.subprocess, "run", boom)
    with pytest.raises(ToolError, match="timed out"):
        sc_mcp._run_sc("broker", "overview")


def test_non_json_raises(monkeypatch):
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: "/usr/bin/sc")
    monkeypatch.setattr(sc_mcp, "_SC_CACHE_TTL", 0)
    monkeypatch.setattr(
        sc_mcp.subprocess,
        "run",
        lambda *a, **k: FakeResult(stdout="<html>session expired</html>"),
    )
    with pytest.raises(ToolError, match="not valid JSON"):
        sc_mcp._run_sc("broker", "overview")


# ── cache ───────────────────────────────────────────────────────────────────────
def test_results_are_cached(monkeypatch):
    sc_mcp._SC_CACHE.clear()
    monkeypatch.setattr(sc_mcp, "_SC_CACHE_TTL", 300)
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: "/usr/bin/sc")
    calls = []

    def fake_run(*a, **k):
        calls.append(a)
        return FakeResult(stdout=json.dumps({"value": 42}))

    monkeypatch.setattr(sc_mcp.subprocess, "run", fake_run)

    first = sc_mcp._run_sc("broker", "overview")
    second = sc_mcp._run_sc("broker", "overview")

    assert first == {"value": 42} == second
    assert len(calls) == 1  # second served from cache


def test_cache_disabled_when_ttl_zero(monkeypatch):
    sc_mcp._SC_CACHE.clear()
    monkeypatch.setattr(sc_mcp, "_SC_CACHE_TTL", 0)
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: "/usr/bin/sc")
    calls = []

    def fake_run(*a, **k):
        calls.append(a)
        return FakeResult()

    monkeypatch.setattr(sc_mcp.subprocess, "run", fake_run)

    sc_mcp._run_sc("broker", "overview")
    sc_mcp._run_sc("broker", "overview")

    assert len(calls) == 2  # no caching → two real calls
    assert sc_mcp._SC_CACHE == {}


# ── sc version drift warning ────────────────────────────────────────────────────
def _patch_capabilities(monkeypatch, version):
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: "/usr/bin/sc")
    payload = json.dumps({"data": {"version": version}})
    monkeypatch.setattr(sc_mcp.subprocess, "run", lambda *a, **k: FakeResult(stdout=payload))


def test_matching_sc_version_is_silent(monkeypatch, capsys):
    _patch_capabilities(monkeypatch, sc_mcp.SUPPORTED_SC_VERSION + ".0")
    sc_mcp._warn_on_sc_version_drift()
    assert "warning" not in capsys.readouterr().err


def test_drifted_sc_version_warns(monkeypatch, capsys):
    _patch_capabilities(monkeypatch, "0.9.0")
    sc_mcp._warn_on_sc_version_drift()
    assert "0.9.0" in capsys.readouterr().err


def test_missing_sc_warns_but_does_not_raise(monkeypatch, capsys):
    monkeypatch.setattr(sc_mcp.shutil, "which", lambda _: None)
    sc_mcp._warn_on_sc_version_drift()  # must not raise
    assert "not found" in capsys.readouterr().err
