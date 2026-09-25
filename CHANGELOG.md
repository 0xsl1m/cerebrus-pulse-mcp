# Changelog

All notable changes to Cerebrus Pulse MCP Server.

## [0.5.2] - 2026-09-24

### Fixed
- **Fresh installs crashed on import.** `mcp>=1.0.0` had no upper bound and
  now resolves to mcp 2.x, which removed the `Server.list_tools()` /
  `call_tool()` decorators this server uses. Pinned to `mcp>=1.2,<2`.
- **The documented `uvx cerebrus-pulse-mcp` setup could never pay.** The x402
  client sat behind the optional `[pay]` extra, which uvx and the MCP registry
  never install. The payment dependencies are now core; `[pay]` remains as an
  empty alias so the old install command still works.
- README prices for pulse, bundle, screener, oi, spread, correlation and
  stress were stale; the table now matches the API's live
  `/.well-known/x402` manifest. The bundle row's "20% discount" claim is gone.
- A signed payment that the API refused fell through to an extra unpaid
  request and reported "Auto-payment unavailable: None". It now returns
  `payment_rejected` with the payment terms. The failure hint no longer asks
  for ETH gas, which x402 payers do not need.

### Added
- Auto-payment spend limits, checked before anything is signed:
  `CEREBRUS_MAX_PAYMENT_USD` (default $0.10 per call),
  `CEREBRUS_MAX_SPEND_USD` (default $1.00 per server process) and
  `CEREBRUS_ALLOWED_PAYTO` (default: the published Cerebrus Pulse Base
  address). Only USDC on Base is paid. A refusal returns `payment_blocked`
  with the reason; a malformed limit disables auto-payment.
- `server.json` declares its environment variables (the wallet key as an
  optional secret) and `runtimeHint: uvx`.
- Tests, and a CI workflow: tests on Python 3.10-3.13, a clean-env install of
  the built wheel, and a live free-endpoint and price-parity check.
- `publish.yml`, which releases a pushed `vX.Y.Z` tag through PyPI Trusted
  Publishing with provenance attestations.
- `scripts/check_prices.py`, which checks advertised prices against the API's
  x402 manifest.

### Changed
- `x402[evm]` floor raised from 2.5 to 2.20, the first release with client
  spend controls.
- `scripts/release.py` keeps `server.json` in step with the other version
  sources, and `publish` now hands off to the tag-triggered workflow
  (`publish --twine` keeps the old token upload as a fallback).

## [0.5.1] - 2026-08-28

### Added
- `mcp-name:` ownership marker in the README, required by the MCP registry to
  verify the `io.github.0xsl1m/*` namespace. Without it publishing is rejected,
  which is why the registry entry sat at 0.2.0 from 2026-03-05.

### Changed
- Shortened the registry description to fit the registry's 100-character limit
  (the previous one was 196 characters and was rejected outright).

## [0.5.0] - 2026-08-28

### Fixed
- **Automatic x402 payment now actually works.** Since 0.3.0 the package
  advertised auto-payment via `CEREBRUS_WALLET_KEY` but shipped no x402 client
  dependency at all - the 402 branch only returned a message, so every paid
  tool was a dead end. Payment is now implemented against the x402 SDK.
- 402 handling read a response header named `X-Payment`, which the API has
  never sent. Payment terms are now parsed from the x402 v1 JSON body, so
  callers that pay themselves get a real price, network, and recipient.
- Corrected 7 of 13 advertised prices, which had drifted from the live API:
  pulse $0.02 -> $0.025, bundle $0.04 -> $0.05, screener $0.04 -> $0.06,
  oi $0.01 -> $0.015, spread $0.008 -> $0.015, correlation $0.03 -> $0.05,
  stress $0.015 -> $0.02.
- Bundle savings claim corrected from 20% to 17% (components total $0.06).
- `cerebrus_basis` description carried a copy-pasted funding-rate sentence
  describing the wrong metric.

### Added
- `pay` optional extra: `pip install "cerebrus-pulse-mcp[pay]"` installs the
  x402 EVM client. Kept optional so free-endpoint users stay dependency-light.
- Paid tools return structured `payment_terms` (price, network, pay_to, asset)
  instead of an opaque message when no wallet is configured.

### Known limitations
- Auto-payment covers Base (EVM) only. `CEREBRUS_WALLET_KEY_SOLANA` is not yet
  wired to a Solana signer; the API still accepts Solana if you pay yourself.

## [0.4.1] - 2026-04-18

### Added
- Solana payment support documentation — x402 now accepts USDC on Base or Solana
- `CEREBRUS_WALLET_KEY_SOLANA` environment variable for Solana auto-payment
- MCP config example showing both Base and Solana wallet keys

### Changed
- 402 response messaging updated for dual-chain (Base + Solana)
- Health endpoint version bumped to 1.2.0 (reflects server-side Solana support)

## [0.4.0] - 2026-04-15

### Added
- `--json` CLI flag for direct tool access without an MCP client (closes #7)
- Positional and `key=value` argument support for CLI mode
- `--json` with no tool name lists all available tools with parameter schemas
- Full README with tool reference, install guide, CLI examples, and configuration docs

### Changed
- Version bump to 0.4.0

## [0.3.2] - 2026-03-29

### Added
- Smithery configuration with wallet key support
- ASCII art branding in README
- PyPI badges (version, downloads, license)
- GitHub Discussions: announcement, FAQ, use cases, feature requests

## [0.3.1] - 2026-03-23

### Added
- Liquidation heatmap tool (`cerebrus_liquidations`) — leverage tiers with cascade risk
- Market Stress Index tool (`cerebrus_stress`) — cross-chain arbitrage-derived signal
- CEX-DEX divergence tool (`cerebrus_cex_dex`) — Coinbase vs Hyperliquid pricing
- Chainlink basis tool (`cerebrus_basis`) — oracle vs spot with contrarian signals
- USDC depeg monitor tool (`cerebrus_depeg`) — collateral health via Chainlink
- Open interest tool (`cerebrus_oi`) — delta, percentile, trend, divergence
- Spread analysis tool (`cerebrus_spread`) — slippage estimates, liquidity scoring
- Correlation tool (`cerebrus_correlation`) — BTC-alt matrix with regime classification

### Changed
- Expanded from 7 to 15 tools
- Updated tool descriptions for clarity

## [0.2.0] - 2026-03-14

### Added
- Screener tool (`cerebrus_screener`) — scan all 50+ coins
- Bundle tool (`cerebrus_bundle`) — combined analysis at discount
- Funding rate tool (`cerebrus_funding`) — current + historical with annualized

## [0.1.0] - 2026-03-05

### Added
- Initial release
- Core tools: `cerebrus_pulse`, `cerebrus_sentiment`, `cerebrus_list_coins`, `cerebrus_health`
- x402 micropayment integration (USDC on Base)
- Claude Desktop, Cursor, Windsurf configuration support
