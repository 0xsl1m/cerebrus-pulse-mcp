# Cerebrus Pulse MCP

<!-- Ownership marker for the MCP registry; must match server.json name. -->
mcp-name: io.github.0xsl1m/cerebrus-pulse-mcp


[![PyPI](https://img.shields.io/pypi/v/cerebrus-pulse-mcp)](https://pypi.org/project/cerebrus-pulse-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/cerebrus-pulse-mcp/)

MCP server for [Cerebrus Pulse](https://cerebruspulse.xyz) — real-time crypto intelligence for AI agents. Provides 15 tools covering technical analysis, liquidation heatmaps, market stress, funding rates, and more across 50+ Hyperliquid perpetuals.

## Tools

| Tool | Description | Cost |
|------|-------------|------|
| `cerebrus_health` | Gateway health check | Free |
| `cerebrus_list_coins` | List all available tickers (50+) | Free |
| `cerebrus_pulse` | Multi-timeframe technicals (RSI, EMAs, BBands, VWAP, regime) | $0.025 |
| `cerebrus_sentiment` | Aggregated market sentiment + fear/greed | $0.01 |
| `cerebrus_funding` | Funding rate analysis with historical context | $0.01 |
| `cerebrus_bundle` | Pulse + sentiment + funding combined | $0.05 |
| `cerebrus_screener` | Scan all coins for top signals | $0.06 |
| `cerebrus_oi` | Open interest delta, percentile, trend | $0.015 |
| `cerebrus_spread` | Bid-ask spread + slippage estimates | $0.015 |
| `cerebrus_correlation` | BTC-altcoin correlation matrix | $0.05 |
| `cerebrus_stress` | Cross-chain arbitrage-derived market stress index | $0.02 |
| `cerebrus_cex_dex` | CEX vs DEX price divergence | $0.02 |
| `cerebrus_basis` | Chainlink oracle vs Hyperliquid basis | $0.02 |
| `cerebrus_depeg` | USDC collateral health via Chainlink | $0.01 |
| `cerebrus_liquidations` | Liquidation heatmap across 5 leverage tiers | $0.03 |

Paid endpoints use [x402](https://x402.org/) micropayments (USDC on **Base** or **Solana**). Free tools work without any configuration.

Prices are checked against the API's live x402 manifest
(`https://api.cerebruspulse.xyz/.well-known/x402`) with
`python scripts/check_prices.py --live`, which CI runs.

## Install

### Claude Desktop / Cursor / Windsurf

Add to your MCP config (`claude_desktop_config.json`, `.cursor/mcp.json`, etc.):

```json
{
  "mcpServers": {
    "cerebrus-pulse": {
      "command": "uvx",
      "args": ["cerebrus-pulse-mcp"]
    }
  }
}
```

To enable automatic x402 payments for paid endpoints, add a wallet key. The
x402 client ships with the package, so the same `uvx` command pays; there is no
extra to install:

```json
{
  "mcpServers": {
    "cerebrus-pulse": {
      "command": "uvx",
      "args": ["cerebrus-pulse-mcp"],
      "env": {
        "CEREBRUS_WALLET_KEY": "your-base-wallet-private-key",
        "CEREBRUS_WALLET_KEY_SOLANA": "your-solana-wallet-private-key"
      }
    }
  }
}
```

Automatic payment currently covers **Base** only. `CEREBRUS_WALLET_KEY_SOLANA`
is reserved for a future Solana signer — the API accepts Solana today, but you
would need to settle those payments yourself.

Use a dedicated hot wallet that holds a few dollars of USDC on Base, never a
main wallet: the key sits in plain text in the MCP config.

Auto-payment has spend limits, checked before anything is signed:

- no single payment above `CEREBRUS_MAX_PAYMENT_USD` (default `0.10`; the
  priciest tool costs $0.06);
- no more than `CEREBRUS_MAX_SPEND_USD` in total while the server process runs
  (default `1.00`; restart the server to reset it);
- only USDC on Base, and only to an address in `CEREBRUS_ALLOWED_PAYTO`
  (default: the published Cerebrus Pulse Base address), so a hijacked or
  mistyped `CEREBRUS_BASE_URL` cannot redirect payments.

A refused payment returns `"status": "payment_blocked"` with the reason; a
malformed limit disables auto-payment rather than lifting the limit.

Without a wallet key, paid tools still work as
discovery: they return the exact price, network, and recipient so the calling
agent can pay however it likes.

### pip

```bash
pip install cerebrus-pulse-mcp
```

## CLI Usage

The server includes a `--json` flag for direct CLI access without an MCP client:

```bash
# List all available CLI tools
cerebrus-pulse-mcp --json

# Free endpoints
cerebrus-pulse-mcp --json health
cerebrus-pulse-mcp --json list-coins

# Paid endpoints (returns payment details if wallet not configured)
cerebrus-pulse-mcp --json pulse BTC
cerebrus-pulse-mcp --json funding ETH lookback_hours=48
cerebrus-pulse-mcp --json screener top_n=10
cerebrus-pulse-mcp --json liquidations SOL
```

Arguments can be passed positionally (for coin) or as `key=value` pairs.

## Configuration

| Environment Variable | Description | Required |
|---------------------|-------------|----------|
| `CEREBRUS_BASE_URL` | API base URL (default: `https://api.cerebruspulse.xyz`) | No |
| `CEREBRUS_WALLET_KEY` | Base wallet private key for x402 auto-payment | No |
| `CEREBRUS_MAX_PAYMENT_USD` | Largest single payment auto-pay may sign (default: `0.10`) | No |
| `CEREBRUS_MAX_SPEND_USD` | Total auto-pay may sign per server process (default: `1.00`) | No |
| `CEREBRUS_ALLOWED_PAYTO` | Comma-separated payTo addresses auto-pay may pay (default: the published Cerebrus Pulse Base address) | No |
| `CEREBRUS_WALLET_KEY_SOLANA` | Reserved; Solana auto-payment not yet implemented | No |

## Example Response

```bash
$ cerebrus-pulse-mcp --json health
{
  "status": "ok",
  "engine": "available",
  "kill_switch": "enabled",
  "version": "1.2.0"
}
```

## Development

```bash
git clone https://github.com/0xsl1m/cerebrus-pulse-mcp.git
cd cerebrus-pulse-mcp
pip install -e .
```

## Links

- [Cerebrus Pulse](https://cerebruspulse.xyz) — API documentation and guides
- [x402 Protocol](https://x402.org/) — HTTP 402 micropayment standard
- [PyPI Package](https://pypi.org/project/cerebrus-pulse-mcp/)
- [Changelog](CHANGELOG.md)

## License

MIT
