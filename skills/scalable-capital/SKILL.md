---
description: How to use the Scalable Capital (sc-mcp) broker tools — when discussing the user's portfolio, holdings, transactions, quotes, or broker account at Scalable Capital.
---

# Scalable Capital broker tools

Use the `sc_*` tools to answer questions about the user's Scalable Capital
broker account. Pick by intent:

- Account value / cash / performance → `sc_overview`
- Positions and market values → `sc_holdings`
- Trade history (tax, reconciliation) → `sc_transactions` (filter by date/ISIN/type)
- A single transaction's detail → `sc_transaction`
- Allocation / sector / region exposure → `sc_analytics`
- Live price of one security → `sc_quote`
- Find a security → `sc_search`
- News for a security → `sc_security_news`

## Rules

- **Read-only.** These tools never place trades or change the account. If asked
  to buy/sell/set alerts, say it's out of scope and point to the `sc` CLI.
- **Always fetch; never quote prices or values from memory or earlier in the
  chat** — markets move. Call the tool again.
- Responses may be **up to ~5 minutes stale** (server-side cache). For a
  fresh-to-the-second number, say so or note the staleness.
- **Not financial advice.** Report the data; don't recommend trades.
- On an error mentioning login/session, tell the user to run `sc login`.
