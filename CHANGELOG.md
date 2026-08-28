# Changelog

All notable changes to Cerebrus Pulse MCP Server.

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
