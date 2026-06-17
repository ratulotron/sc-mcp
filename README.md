# sc-mcp

An [MCP](https://modelcontextprotocol.io) server that wraps the
[Scalable Capital](https://scalable.capital) `sc` CLI, exposing your broker
data to any MCP-capable harness (Claude Code, Claude Desktop, Codex, Cursor, …).

> **Unofficial.** This is a community, **read-only** wrapper around Scalable
> Capital's official `sc` CLI — not affiliated with or endorsed by Scalable
> Capital. It's a stopgap until they ship a first-party MCP server; expect to
> retire it when they do.
>
> **No warranty / use at your own risk.** Provided "as is" under the MIT
> License, with no warranty of any kind. The author takes no responsibility for
> any loss, damage, incorrect data, or financial consequence arising from its
> use. This is a personal tool for your own broker data — you are responsible
> for verifying anything you act on. It is **not** financial advice.

## Tools

| Tool | What it returns |
|------|-----------------|
| `sc_overview` | Portfolio total value, cash, performance |
| `sc_holdings` | All positions with prices, quantities, market values |
| `sc_transactions` | Trade history with filters (date, ISIN, type, paging) |
| `sc_analytics` | Allocation, sector/region exposure, attribution |
| `sc_security_news` | Latest news summary for a security by ISIN |
| `sc_quote` | Current quote for a security by ISIN |
| `sc_search` | Search securities within the portfolio context |
| `sc_transaction` | Details for a single transaction by ID |

This server is **read-only** — it never places trades or mutates account state.
All calls hit the broker live. Responses are cached in-process for 5 minutes.

The `sc` CLI also exposes write operations (watchlist, price-alerts,
savings-plans, trades). These are **deliberately not included** in this release.
Any future write support will be **opt-in**, disabled by default, and enabled
only via an explicit environment flag — never on by default. Money-moving
commands (`trade`, `savings-plans`) are out of scope entirely.

## Prerequisites

1. The `sc` CLI installed and on `PATH`.
2. An authenticated session: `sc login`.

## Compatibility

Tested against **`sc` 0.2.x**. The `sc` CLI is pre-1.0, so its command surface
can change between minor versions — the server logs a warning to stderr at
startup if your installed `sc` differs from the tested major.minor. `sc` is an
external binary, not a Python dependency, so this is the only enforcement
available; if you see the warning and a tool misbehaves, that mismatch is the
likely cause.

## Install

No clone needed — run straight from GitHub with [uv](https://docs.astral.sh/uv/):

```bash
uvx --from git+https://github.com/ratulotron/sc-mcp sc-mcp
```

(That command starts the stdio server; harnesses launch it for you — see below.)

### Claude Code

```bash
claude mcp add scalable-capital -- uvx --from git+https://github.com/ratulotron/sc-mcp sc-mcp
```

### Claude Desktop / Codex / Cursor

Add to the harness's MCP config (`claude_desktop_config.json`,
`~/.codex/config.toml` `[mcp_servers]`, etc.):

```json
{
  "mcpServers": {
    "scalable-capital": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ratulotron/sc-mcp", "sc-mcp"]
    }
  }
}
```

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `SC_MCP_CACHE_TTL` | `300` | Seconds to cache successful responses in-process. Set `0` to disable caching (always hit the broker live). |

## Develop

```bash
uv sync
uv run sc-mcp      # starts the stdio server
uv run pytest
```

## Versioning

This package uses [SemVer](https://semver.org/). The tools are the public API:

| Bump | Trigger |
|------|---------|
| **MAJOR** | A tool is removed/renamed, or a parameter changes incompatibly |
| **MINOR** | A tool or optional parameter is added |
| **PATCH** | Bug fix, error-message wording, internals |

Releases are tagged `vX.Y.Z`. **Pin a tag** when installing — `uvx --from
git+...` tracks the default branch (latest) by default, so without a pin your
tool surface can change underneath you:

```bash
uvx --from git+https://github.com/ratulotron/sc-mcp@v0.1.0 sc-mcp
```

Most version bumps here are driven by `sc` CLI changes (see Compatibility), but
the version number is this package's own — it does not mirror the `sc` version.

## License

MIT

