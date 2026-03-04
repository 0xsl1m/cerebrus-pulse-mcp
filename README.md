<!-- mcp-name: io.github.0xsl1m/cerebrus-pulse-mcp -->
# Cerebrus Pulse MCP Server

MCP server for [Cerebrus Pulse](https://pulse.openclaw.ai) — real-time crypto intelligence API for 30+ Hyperliquid perpetuals.

Use this server to give any MCP-compatible AI agent (Claude Desktop, Cursor, Windsurf, etc.) access to:

- **Technical analysis** — RSI, EMAs, ATR, Bollinger Bands, VWAP, Z-score, trend, regime, confluence scoring
- **Market sentiment** — Fear/greed, momentum, funding bias
- **Funding rates** — Current and historical with annualized projections
- **Analysis bundles** — All data combined at 20% discount

## Quick Start

### Install

```bash
pip install cerebrus-pulse-mcp
```

Or with [uvx](https://docs.astral.sh/uv/):

```bash
uvx cerebrus-pulse-mcp
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

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

### Cursor / Windsurf

Add to your MCP settings:

```json
{
  "cerebrus-pulse": {
    "command": "uvx",
    "args": ["cerebrus-pulse-mcp"]
  }
}
```

## Available Tools

| Tool | Cost | Description |
|------|------|-------------|
| `cerebrus_list_coins` | Free | List available coins (30+ Hyperliquid perpetuals) |
| `cerebrus_health` | Free | Check gateway health status |
| `cerebrus_pulse` | $0.02 | Multi-timeframe technical analysis (RSI, EMAs, Bollinger, trend, regime) |
| `cerebrus_sentiment` | $0.01 | Aggregated crypto market sentiment |
| `cerebrus_funding` | $0.01 | Funding rate analysis with historical data |
| `cerebrus_bundle` | $0.04 | Complete bundle: pulse + sentiment + funding (20% discount) |
| `cerebrus_screener` | $0.04 | Scan 30+ coins for signals, trends, vol regime, confluence |
| `cerebrus_oi` | $0.01 | Open interest analysis: delta, percentile, trend, divergence |
| `cerebrus_spread` | $0.008 | Spread analysis: slippage estimates, liquidity scoring |
| `cerebrus_correlation` | $0.03 | BTC-alt correlation matrix with regime classification |

## How Payment Works

Cerebrus Pulse uses [x402](https://www.x402.org/) — USDC micropayments on Base blockchain. No API keys or subscriptions.

**Free tools** (`cerebrus_list_coins`, `cerebrus_health`) work immediately with no setup.

**Paid tools** require x402 payment. Without a wallet configured, the server returns payment details (cost, address) so you can see what data is available. To enable auto-payment:

1. Get a Base wallet with USDC
2. Set `CEREBRUS_WALLET_KEY` environment variable
3. Payments happen automatically per query

## Example Usage

Once connected, you can ask your AI agent:

- "What's the technical analysis for BTC on the 1h timeframe?"
- "Show me ETH funding rates for the last 48 hours"
- "What's the current market sentiment?"
- "Get a complete analysis bundle for SOL"
- "List all available coins"

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CEREBRUS_BASE_URL` | `https://pulse.openclaw.ai` | API base URL |
| `CEREBRUS_WALLET_KEY` | — | Base wallet private key for x402 auto-payment |

## Links

- [Cerebrus Pulse Documentation](https://pulse.openclaw.ai/overview)
- [x402 Payment Guide](https://pulse.openclaw.ai/guides/x402-payments)
- [API Reference](https://pulse.openclaw.ai/api/pulse)
- [OpenAPI Spec](https://pulse.openclaw.ai/openapi.yaml)

## Disclaimer

Cerebrus Pulse provides market data and technical indicators for **informational purposes only**. Nothing provided by this MCP server or the underlying API constitutes financial advice, investment advice, or trading advice. AI-generated analysis, signals, and sentiment labels are algorithmic outputs — not recommendations to buy, sell, or hold any asset. Cryptocurrency trading involves substantial risk of loss. You are solely responsible for your own trading decisions.

## License

MIT
