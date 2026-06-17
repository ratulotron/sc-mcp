# Maintaining sc-mcp

This server is a thin wrapper around the Scalable Capital `sc` CLI. Its main
maintenance burden is **staying in sync with `sc`**, which is pre-1.0 and can
change its command surface between minor versions.

## When a new `sc` version ships

Run the machine-readable capability dump and compare it against what the server
assumes:

```bash
sc --version
sc capabilities --json | python3 -m json.tool | less
```

1. **Version.** Compare `data.version` to `SUPPORTED_SC_VERSION` in
   `src/sc_mcp/server.py`. If the major.minor changed, work through the rest of
   this list, then bump the constant.
2. **Commands.** Diff `data.commands` against the 8 tools in `server.py`
   (`broker.overview`, `broker.holdings`, `broker.transactions`,
   `broker.transaction.details`, `broker.analytics`, `broker.quote`,
   `broker.search`, `broker.security-news`). New read-only broker command →
   consider adding a tool. Renamed/removed → update or drop the tool.
3. **Flags.** For each wrapped command, re-check its `--help`. If a flag the
   server passes was renamed or removed, fix the tool **and** its case in
   `ARGV_CASES` in `tests/test_sc_mcp.py`.
4. **Exit codes / envelope.** `data.exit_codes` and `data.output` describe the
   error and JSON-envelope contract `_run_sc` relies on. If they change, adjust
   error handling.
5. Update the **Compatibility** line in `README.md` and `SUPPORTED_SC_VERSION`.

## Before committing

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Versioning the change

SemVer on the tools (see README → Versioning): tool removed/renamed = MAJOR,
tool/optional-param added = MINOR, fix = PATCH. Then:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
gh release create vX.Y.Z --title vX.Y.Z --notes "..."
```

## Invariants — do not break

- **Read-only.** Never add `trade` or `savings-plans` tools — money-moving and
  out of scope. `watchlist`/`price-alerts` may be added only behind
  `SC_MCP_ENABLE_WRITES`, **off by default**.
- **Every failure raises `ToolError`** so the MCP result is marked `isError`
  with a message the model can read. Don't return `{"error": ...}` as success.
- **Never block startup** on the `sc`-version probe — it stays a warning.
