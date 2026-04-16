# Changelog

All notable changes to Cerebrus Pulse MCP Server.

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
