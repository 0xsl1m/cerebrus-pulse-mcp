"""
Cerebrus Pulse MCP Server

Exposes Cerebrus Pulse crypto intelligence API as MCP tools for AI agents.
Supports both free endpoints (health, coins) and paid x402 endpoints
(pulse, sentiment, funding, bundle).

For paid endpoints, the server makes standard HTTP requests. If x402 payment
is configured (via CEREBRUS_WALLET_KEY env var), it handles the 402 flow
automatically. Otherwise, it returns the 402 response details so the caller
can handle payment.

Disclaimer: Data provided is for informational purposes only and does not
constitute financial advice. Cryptocurrency trading involves substantial
risk of loss.
"""

import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

BASE_URL = os.environ.get("CEREBRUS_BASE_URL", "https://api.cerebruspulse.xyz")
REQUEST_TIMEOUT = 30.0

server = Server("cerebrus-pulse")


def _make_client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "cerebrus-pulse-mcp/0.1.0"},
    )


def _format_response(data: dict | list) -> str:
    return json.dumps(data, indent=2)


def _api_get(path: str, params: dict | None = None) -> dict[str, Any]:
    """Make a GET request to the Cerebrus Pulse API."""
    with _make_client() as client:
        resp = client.get(path, params=params)

        if resp.status_code == 402:
            # Return payment details so the agent/user knows cost
            return {
                "status": "payment_required",
                "message": "This endpoint requires x402 USDC payment on Base.",
                "url": f"{BASE_URL}{path}",
                "payment_details": resp.headers.get("X-Payment", "See x402 SDK docs"),
                "help": "Install the x402 SDK and set CEREBRUS_WALLET_KEY to enable auto-payment. See https://cerebruspulse.xyz/guides/x402-payments",
            }

        if resp.status_code == 429:
            return {
                "status": "rate_limited",
                "message": "Rate limit exceeded. Back off and retry.",
                "detail": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
            }

        resp.raise_for_status()
        return resp.json()


# ── Tool Definitions ─────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="cerebrus_list_coins",
            description=(
                "List all available coins on Cerebrus Pulse. "
                "Returns tickers for 30+ Hyperliquid perpetuals. FREE — no payment required."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="cerebrus_health",
            description=(
                "Check Cerebrus Pulse gateway health status. "
                "FREE — no payment required."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="cerebrus_pulse",
            description=(
                "Get multi-timeframe technical analysis for a Hyperliquid perpetual. "
                "Returns RSI, EMAs (20/50/200), ATR, Bollinger Bands, VWAP, Z-score, "
                "trend direction, confluence scoring, derivatives data (funding, OI, spread), "
                "and market regime. Cost: $0.02 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Coin ticker (e.g., BTC, ETH, SOL). Case-insensitive.",
                    },
                    "timeframes": {
                        "type": "string",
                        "description": "Comma-separated timeframes: 15m, 1h, 4h. Default: 1h,4h",
                        "default": "1h,4h",
                    },
                },
                "required": ["coin"],
            },
        ),
        Tool(
            name="cerebrus_sentiment",
            description=(
                "Get aggregated crypto market sentiment analysis. "
                "Returns overall sentiment, fear/greed, momentum, and funding bias. "
                "Not coin-specific. Cost: $0.01 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="cerebrus_funding",
            description=(
                "Get funding rate analysis for a Hyperliquid perpetual. "
                "Returns current rate, annualized percentage, historical min/max/average. "
                "Cost: $0.01 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Coin ticker (e.g., BTC, ETH, SOL). Case-insensitive.",
                    },
                    "lookback_hours": {
                        "type": "integer",
                        "description": "Hours of historical data (1-168). Default: 24",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 168,
                    },
                },
                "required": ["coin"],
            },
        ),
        Tool(
            name="cerebrus_bundle",
            description=(
                "Get complete analysis bundle: technical analysis + sentiment + funding "
                "combined in one call. 20% discount vs individual endpoints. "
                "Cost: $0.04 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Coin ticker (e.g., BTC, ETH, SOL). Case-insensitive.",
                    },
                    "timeframes": {
                        "type": "string",
                        "description": "Comma-separated timeframes: 15m, 1h, 4h. Default: 1h,4h",
                        "default": "1h,4h",
                    },
                },
                "required": ["coin"],
            },
        ),
        Tool(
            name="cerebrus_screener",
            description=(
                "Scan all 30+ coins for top trading signals. Returns RSI zone, trend, "
                "volatility regime, funding bias, confluence score, and OI trend for each coin. "
                "Much cheaper than calling pulse individually. Cost: $0.04 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top coins to return (1-30). Default: 30",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 30,
                    },
                },
            },
        ),
        Tool(
            name="cerebrus_oi",
            description=(
                "Get open interest analysis for a Hyperliquid perpetual. "
                "Returns OI delta (1h/4h/24h), percentile rank, trend direction, "
                "and price-OI divergence signals. Cost: $0.01 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Coin ticker (e.g., BTC, ETH, SOL). Case-insensitive.",
                    },
                },
                "required": ["coin"],
            },
        ),
        Tool(
            name="cerebrus_spread",
            description=(
                "Get spread and liquidity analysis for a Hyperliquid perpetual. "
                "Returns bid-ask spread, estimated slippage at $10k/$50k/$100k/$500k, "
                "and liquidity score (1-10). Cost: $0.008 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Coin ticker (e.g., BTC, ETH, SOL). Case-insensitive.",
                    },
                },
                "required": ["coin"],
            },
        ),
        Tool(
            name="cerebrus_correlation",
            description=(
                "Get BTC-altcoin correlation matrix for top 15 Hyperliquid perpetuals. "
                "Returns 30-day rolling correlations, correlation regime "
                "(CORRELATED/DECORRELATED/MIXED), and sector averages. "
                "Cost: $0.03 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


# ── Tool Handlers ────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "cerebrus_list_coins":
            result = _api_get("/coins")

        elif name == "cerebrus_health":
            result = _api_get("/health")

        elif name == "cerebrus_pulse":
            coin = arguments["coin"]
            timeframes = arguments.get("timeframes", "1h,4h")
            result = _api_get(f"/pulse/{coin}", params={"timeframes": timeframes})

        elif name == "cerebrus_sentiment":
            result = _api_get("/sentiment")

        elif name == "cerebrus_funding":
            coin = arguments["coin"]
            lookback = arguments.get("lookback_hours", 24)
            result = _api_get(f"/funding/{coin}", params={"lookback_hours": lookback})

        elif name == "cerebrus_bundle":
            coin = arguments["coin"]
            timeframes = arguments.get("timeframes", "1h,4h")
            result = _api_get(f"/bundle/{coin}", params={"timeframes": timeframes})

        elif name == "cerebrus_screener":
            top_n = arguments.get("top_n", 30)
            result = _api_get("/screener", params={"top_n": top_n})

        elif name == "cerebrus_oi":
            coin = arguments["coin"]
            result = _api_get(f"/oi/{coin}")

        elif name == "cerebrus_spread":
            coin = arguments["coin"]
            result = _api_get(f"/spread/{coin}")

        elif name == "cerebrus_correlation":
            result = _api_get("/correlation")

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=_format_response(result))]

    except httpx.HTTPStatusError as e:
        error_body = e.response.text[:500] if e.response else "No response body"
        return [TextContent(
            type="text",
            text=_format_response({
                "error": f"HTTP {e.response.status_code}",
                "detail": error_body,
            }),
        )]
    except httpx.RequestError as e:
        return [TextContent(
            type="text",
            text=_format_response({
                "error": "Connection failed",
                "detail": str(e),
                "help": "Check that https://cerebruspulse.xyz is reachable.",
            }),
        )]


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    main()
