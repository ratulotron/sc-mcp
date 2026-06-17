"""sc-mcp — an MCP server wrapping the Scalable Capital `sc` CLI.

Exposes broker overview, holdings, transactions, analytics, and security news
as MCP tools over stdio. Requires the `sc` CLI on PATH and an authenticated
session (`sc login`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

mcp = FastMCP("scalable-capital")

# major.minor of the `sc` CLI this release was tested against. `sc` is pre-1.0,
# so its surface can change between minor versions — we warn on drift at startup.
SUPPORTED_SC_VERSION = "0.2"

# ── Session cache ─────────────────────────────────────────────────────────────
# TTL in seconds; set SC_MCP_CACHE_TTL=0 to disable caching entirely.
_SC_CACHE: dict[str, tuple[float, dict | list]] = {}
_SC_CACHE_TTL = int(os.environ.get("SC_MCP_CACHE_TTL", "300"))
_SC_TIMEOUT = 30  # seconds per CLI call


def _run_sc(*args: str) -> dict | list:
    """Run a `sc <args> --json` command and return parsed JSON.

    Successful results are cached for SC_MCP_CACHE_TTL seconds (0 disables).
    Every failure raises ToolError so the MCP result is marked isError, with a
    message the model can read and act on.
    """
    key = " ".join(args)
    now = time.monotonic()

    if _SC_CACHE_TTL > 0 and key in _SC_CACHE:
        ts, data = _SC_CACHE[key]
        if now - ts < _SC_CACHE_TTL:
            return data

    sc_path = shutil.which("sc")
    if not sc_path:
        raise ToolError("sc CLI not found on PATH — install the Scalable Capital CLI")

    try:
        result = subprocess.run(
            [sc_path, *args, "--json"],
            capture_output=True,
            text=True,
            timeout=_SC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(
            f"`sc {key}` timed out after {_SC_TIMEOUT}s — the broker may be unreachable"
        ) from None

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "unknown error"
        print(f"[sc-mcp] `sc {key}` exited {result.returncode}: {err}", file=sys.stderr)
        raise ToolError(f"`sc {key}` failed: {err}")

    out = result.stdout.strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        print(f"[sc-mcp] `sc {key}` non-JSON output: {out[:200]!r}", file=sys.stderr)
        raise ToolError(
            f"`sc {key}` returned output that was not valid JSON "
            "(session may have expired — try `sc login`)"
        ) from None

    if _SC_CACHE_TTL > 0:
        _SC_CACHE[key] = (now, data)
    return data


@mcp.tool()
def sc_overview(
    portfolio_id: Annotated[str | None, "Portfolio ID override (omit for default)"] = None,
    include_ytd: Annotated[bool, "Include year-to-date performance points"] = False,
) -> dict | list:
    """Get Scalable Capital broker portfolio overview — total value, cash, performance.
    Returns live data directly from the broker."""
    args = ["broker", "overview"]
    if portfolio_id:
        args += ["--portfolio-id", portfolio_id]
    if include_ytd:
        args.append("--include-year-to-date")
    return _run_sc(*args)


@mcp.tool()
def sc_holdings(
    portfolio_id: Annotated[str | None, "Portfolio ID override (omit for default)"] = None,
    include_ytd: Annotated[bool, "Include year-to-date performance for each position"] = False,
) -> dict | list:
    """Get Scalable Capital portfolio holdings — all positions with current prices,
    quantities, and market values. Live broker data."""
    args = ["broker", "holdings"]
    if portfolio_id:
        args += ["--portfolio-id", portfolio_id]
    if include_ytd:
        args.append("--include-year-to-date")
    return _run_sc(*args)


@mcp.tool()
def sc_transactions(
    page_size: Annotated[int, "Transactions per page (1-100)"] = 50,
    from_time: Annotated[str | None, "Start date ISO-8601 (e.g. 2026-01-01T00:00:00Z)"] = None,
    to_time: Annotated[str | None, "End date ISO-8601"] = None,
    isin: Annotated[str | None, "Filter by security ISIN"] = None,
    type_filter: Annotated[str | None, "Transaction type filter (e.g. BUY, SELL, DIVIDEND)"] = None,
    cursor: Annotated[str | None, "Pagination cursor from previous response"] = None,
    portfolio_id: Annotated[str | None, "Portfolio ID override"] = None,
) -> dict | list:
    """List Scalable Capital broker transactions with optional filters.
    Use for reconciliation, tax analysis, or reviewing trade history."""
    args = ["broker", "transactions", "--page-size", str(page_size)]
    if portfolio_id:
        args += ["--portfolio-id", portfolio_id]
    if from_time:
        args += ["--from-time", from_time]
    if to_time:
        args += ["--to-time", to_time]
    if isin:
        args += ["--isin", isin]
    if type_filter:
        args += ["--type-filter", type_filter]
    if cursor:
        args += ["--cursor", cursor]
    return _run_sc(*args)


@mcp.tool()
def sc_analytics(
    portfolio_id: Annotated[str | None, "Portfolio ID override (omit for default)"] = None,
) -> dict | list:
    """Get Scalable Capital portfolio analytics — allocation breakdowns, sector/region
    exposure, and performance attribution."""
    args = ["broker", "analytics"]
    if portfolio_id:
        args += ["--portfolio-id", portfolio_id]
    return _run_sc(*args)


@mcp.tool()
def sc_security_news(
    isin: Annotated[str, "Security ISIN (e.g. IE00B4L5Y983 for IWDA)"],
    locale: Annotated[str, "Locale for news language (e.g. en_DE, de_DE)"] = "en_DE",
) -> dict | list:
    """Get latest news summary for a specific security by ISIN from Scalable Capital."""
    return _run_sc("broker", "security-news", "--isin", isin, "--locale", locale)


@mcp.tool()
def sc_quote(
    isin: Annotated[str, "Security ISIN (e.g. IE00B4L5Y983 for IWDA)"],
    portfolio_id: Annotated[str | None, "Portfolio ID override"] = None,
    include_ytd: Annotated[bool, "Include year-to-date performance points"] = False,
) -> dict | list:
    """Get the current Scalable Capital quote for a security by ISIN."""
    args = ["broker", "quote", "--isin", isin]
    if portfolio_id:
        args += ["--portfolio-id", portfolio_id]
    if include_ytd:
        args.append("--include-year-to-date")
    return _run_sc(*args)


@mcp.tool()
def sc_search(
    query: Annotated[str, "Search query text (name, ISIN, or ticker)"],
    portfolio_id: Annotated[str | None, "Portfolio ID override"] = None,
) -> dict | list:
    """Search securities within the Scalable Capital broker portfolio context."""
    args = ["broker", "search", query]
    if portfolio_id:
        args += ["--portfolio-id", portfolio_id]
    return _run_sc(*args)


@mcp.tool()
def sc_transaction(
    transaction_id: Annotated[str, "Broker transaction ID"],
    portfolio_id: Annotated[str | None, "Portfolio ID override"] = None,
) -> dict | list:
    """Get details for a single Scalable Capital broker transaction by ID."""
    args = ["broker", "transaction", "details", "--transaction-id", transaction_id]
    if portfolio_id:
        args += ["--portfolio-id", portfolio_id]
    return _run_sc(*args)


def _warn_on_sc_version_drift() -> None:
    """Soft, non-fatal: warn to stderr if the installed `sc` differs from the
    tested major.minor. Never blocks startup — `sc capabilities` needs no auth."""
    sc_path = shutil.which("sc")
    if not sc_path:
        print("[sc-mcp] warning: sc CLI not found on PATH", file=sys.stderr)
        return
    try:
        result = subprocess.run(
            [sc_path, "capabilities", "--json"],
            capture_output=True,
            text=True,
            timeout=_SC_TIMEOUT,
        )
        version = json.loads(result.stdout)["data"]["version"]
    except (subprocess.SubprocessError, ValueError, KeyError):
        return  # never let a version probe block the server
    if not version.startswith(SUPPORTED_SC_VERSION + "."):
        print(
            f"[sc-mcp] warning: tested against sc {SUPPORTED_SC_VERSION}.x, "
            f"found {version} — tools may misbehave",
            file=sys.stderr,
        )


def main() -> None:
    print("[sc-mcp] starting Scalable Capital MCP server (stdio)", file=sys.stderr)
    _warn_on_sc_version_drift()
    mcp.run(transport="stdio")
