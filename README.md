# Cerebrus Pulse MCP

[![PyPI](https://img.shields.io/pypi/v/cerebrus-pulse-mcp)](https://pypi.org/project/cerebrus-pulse-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/cerebrus-pulse-mcp/)

MCP server for [Cerebrus Pulse](https://cerebruspulse.xyz) — real-time crypto intelligence for AI agents. Provides 15 tools covering technical analysis, liquidation heatmaps, market stress, funding rates, and more across 50+ Hyperliquid perpetuals.

## Tools

| Tool | Description | Cost |
|------|-------------|------|
| `cerebrus_health` | Gateway health check | Free |
| `cerebrus_list_coins` | List all available tickers (50+) | Free |
| `cerebrus_pulse` | Multi-timeframe technicals (RSI, EMAs, BBands, VWAP, regime) | $0.02 |
| `cerebrus_sentiment` | Aggregated market sentiment + fear/greed | $0.01 |
| `cerebrus_funding` | Funding rate analysis with historical context | $0.01 |
| `cerebrus_bundle` | Pulse + sentiment + funding combined (20% discount) | $0.04 |
| `cerebrus_screener` | Scan all coins for top signals | $0.04 |
| `cerebrus_oi` | Open interest delta, percentile, trend | $0.01 |
| `cerebrus_spread` | Bid-ask spread + slippage estimates | $0.008 |
| `cerebrus_correlation` | BTC-altcoin correlation matrix | $0.03 |
| `cerebrus_stress` | Cross-chain arbitrage-derived market stress index | $0.015 |
| `cerebrus_cex_dex` | CEX vs DEX price divergence | $0.02 |
| `cerebrus_basis` | Chainlink oracle vs Hyperliquid basis | $0.02 |
| `cerebrus_depeg` | USDC collateral health via Chainlink | $0.01 |
| `cerebrus_liquidations` | Liquidation heatmap across 5 leverage tiers | $0.03 |

Paid endpoints use [x402](https://x402.org/) micropayments (USDC on **Base** or **Solana**). Free tools work without any configuration.

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

To enable automatic x402 payments for paid endpoints, add your wallet key:

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

Set either or both — the x402 SDK picks the chain your wallet is configured for.

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
| `CEREBRUS_WALLET_KEY_SOLANA` | Solana wallet private key for x402 auto-payment | No |

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
