<!-- mcp-name: io.github.0xsl1m/cerebrus-pulse-mcp -->
# Cerebrus Pulse MCP Server

MCP server for [Cerebrus Pulse](https://cerebruspulse.xyz) — real-time crypto intelligence API for 50+ Hyperliquid perpetuals. Pays with USDC on Base or Solana via x402.

Use this server to give any MCP-compatible AI agent (Claude Desktop, Cursor, Windsurf, etc.) access to:

- **Technical analysis** — RSI, EMAs, ATR, Bollinger Bands, VWAP, Z-score, trend, regime, confluence scoring
- **Liquidation heatmap** — Estimated liquidation zones by leverage tier with cascade risk
- **Market Stress Index** — Cross-chain arbitrage-derived stress signal across 8 chains
- **CEX-DEX divergence** — Centralized vs decentralized exchange price comparison
- **Chainlink basis** — HL perpetual oracle vs Chainlink spot with contrarian signals
- **USDC depeg monitor** — Collateral health via Chainlink oracle + sequencer status
- **Market sentiment** — Fear/greed, momentum, funding bias
- **Funding rates** — Current and historical with annualized projections
- **Analysis bundles** — All data combined at discount

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

## Available Tools (15)

| Tool | Cost | Description |
|------|------|-------------|
| `cerebrus_list_coins` | Free | List available coins (50+ Hyperliquid perpetuals) |
| `cerebrus_health` | Free | Check gateway health status |
| `cerebrus_pulse` | $0.025 | Multi-timeframe technical analysis (RSI, EMAs, Bollinger, trend, regime) |
| `cerebrus_screener` | $0.06 | Scan 50+ coins for signals, trends, vol regime, confluence |
| `cerebrus_liquidations` | $0.03 | Liquidation heatmap by leverage tier (3x-50x) with cascade risk |
| `cerebrus_sentiment` | $0.01 | Aggregated crypto market sentiment |
| `cerebrus_funding` | $0.01 | Funding rate analysis with historical data |
| `cerebrus_oi` | $0.01 | Open interest analysis: delta, percentile, trend, divergence |
| `cerebrus_spread` | $0.008 | Spread analysis: slippage estimates, liquidity scoring |
| `cerebrus_correlation` | $0.03 | BTC-alt correlation matrix with regime classification |
| `cerebrus_stress` | $0.015 | Cross-chain market stress index (8 chains, arb-derived) |
| `cerebrus_cex_dex` | $0.02 | CEX-DEX price divergence (Coinbase vs Chainlink/Uniswap) |
| `cerebrus_basis` | $0.02 | Chainlink basis: HL perp oracle vs Chainlink spot price |
| `cerebrus_depeg` | $0.01 | USDC collateral health via Chainlink oracle |
| `cerebrus_bundle` | $0.05 | Complete bundle: pulse + sentiment + funding (9% discount) |

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
- "Where are the liquidation clusters for ETH?"
- "What's the current market stress level?"
- "Show me CEX-DEX divergence for BTC"
- "Is USDC holding its peg right now?"
- "Get a complete analysis bundle for SOL"
- "Scan all coins for the strongest signals"

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CEREBRUS_BASE_URL` | `https://api.cerebruspulse.xyz` | API base URL |
| `CEREBRUS_WALLET_KEY` | — | Base wallet private key for x402 auto-payment |

## Links

- [Cerebrus Pulse Documentation](https://cerebruspulse.xyz/overview)
- [x402 Payment Guide](https://cerebruspulse.xyz/guides/x402-payments)
- [API Reference](https://cerebruspulse.xyz/api/pulse)
- [Python SDK](https://github.com/0xsl1m/cerebrus-pulse-python)
- [LangChain Tools](https://github.com/0xsl1m/langchain-cerebrus-pulse)

## Disclaimer

Cerebrus Pulse provides market data and technical indicators for **informational purposes only**. Nothing provided by this MCP server or the underlying API constitutes financial advice, investment advice, or trading advice. AI-generated analysis, signals, and sentiment labels are algorithmic outputs — not recommendations to buy, sell, or hold any asset. Cryptocurrency trading involves substantial risk of loss. You are solely responsible for your own trading decisions.

## License

MIT
