"""
Cerebrus Pulse MCP Server

Exposes Cerebrus Pulse crypto intelligence API as MCP tools for AI agents.
Supports both free endpoints (health, coins) and paid x402 endpoints
(pulse, sentiment, funding, bundle).

For paid endpoints, the server makes standard HTTP requests. If x402 payment
is configured (via CEREBRUS_WALLET_KEY or CEREBRUS_WALLET_KEY_SOLANA env var),
it handles the 402 flow automatically. Otherwise, it returns the 402 response
details so the caller can handle payment.

Disclaimer: Data provided is for informational purposes only and does not
constitute financial advice. Cryptocurrency trading involves substantial
risk of loss.
"""

import argparse
import json
import os
import re
import sys
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from cerebrus_pulse_mcp import __version__ as _VERSION

_COIN_RE = re.compile(r"^[A-Za-z0-9_-]+$")

BASE_URL = os.environ.get("CEREBRUS_BASE_URL", "https://api.cerebruspulse.xyz")
REQUEST_TIMEOUT = 30.0

server = Server("cerebrus-pulse")


def _make_client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": f"cerebrus-pulse-mcp/{_VERSION}"},
    )


def _format_response(data: dict | list) -> str:
    return json.dumps(data, indent=2)


def _validate_coin(coin: str) -> str:
    """Validate and normalize a coin ticker. Raises ValueError on bad input."""
    coin = coin.strip().upper()
    if not _COIN_RE.match(coin):
        raise ValueError(f"Invalid coin ticker: {coin!r}")
    return coin


def _api_get(path: str, params: dict | None = None) -> dict[str, Any]:
    """Make a GET request to the Cerebrus Pulse API."""
    with _make_client() as client:
        resp = client.get(path, params=params)

        if resp.status_code == 402:
            # Return payment details so the agent/user knows cost
            return {
                "status": "payment_required",
                "message": "This endpoint requires x402 USDC payment on Base or Solana.",
                "url": f"{BASE_URL}{path}",
                "payment_details": resp.headers.get("X-Payment", "See x402 SDK docs"),
                "help": "Install the x402 SDK and set CEREBRUS_WALLET_KEY (Base) or CEREBRUS_WALLET_KEY_SOLANA (Solana) to enable auto-payment. See https://cerebruspulse.xyz/guides/x402-payments",
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
                "Supports 6 timeframes: 5m, 15m, 1h, 4h, 1d, 1w (daily/weekly aggregated from 1h). "
                "Returns RSI, EMAs (20/50/200), ATR, Bollinger Bands, VWAP, Z-score, "
                "trend direction, cross-timeframe confluence with alignment scoring, "
                "derivatives data (funding, OI, spread), and market regime. Cost: $0.02 USDC via x402."
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
                        "description": "Comma-separated timeframes: 5m, 15m, 1h, 4h, 1d, 1w. Default: 1h,4h",
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
                "Get complete analysis bundle: multi-timeframe technical analysis "
                "(5m/15m/1h/4h/1d/1w) + sentiment + funding combined in one call. "
                "20% discount vs individual endpoints. Cost: $0.04 USDC via x402."
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
                        "description": "Comma-separated timeframes: 5m, 15m, 1h, 4h, 1d, 1w. Default: 1h,4h",
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
                "volatility regime, funding bias, multi-TF confluence score with alignment, "
                "and OI trend for each coin. "
                "Much cheaper than calling pulse individually. Cost: $0.04 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top coins to return (1-100). Default: 30",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100,
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
        Tool(
            name="cerebrus_stress",
            description=(
                "Get market stress index derived from cross-chain arbitrage detection. "
                "Scans 8 chains (Arbitrum, Base, Optimism, Polygon, etc.) for price dislocations. "
                "Returns stress level (LOW/MODERATE/HIGH/EXTREME), score (0-1), "
                "spread statistics, chain routes, and recent scan summaries. "
                "Unique signal — not available from any other provider. Cost: $0.015 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent scans to analyze (1-50). Default: 10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
            },
        ),
        Tool(
            name="cerebrus_cex_dex",
            description=(
                "Get CEX-DEX price divergence for a token. Compares Coinbase (CEX) vs "
                "Chainlink/Uniswap (DEX) prices. Returns spread in bps, direction "
                "(cex_premium or dex_premium), and interpretation. "
                "Refreshes every 5 minutes. Cost: $0.02 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "coin": {
                        "type": "string",
                        "description": "Coin ticker (e.g., ETH, BTC, LINK). Case-insensitive.",
                    },
                },
                "required": ["coin"],
            },
        ),
        Tool(
            name="cerebrus_basis",
            description=(
                "Get Chainlink basis analysis — compares Hyperliquid perpetual oracle price "
                "vs Chainlink aggregated spot price on Arbitrum. Returns basis in bps, "
                "direction (hl_premium/hl_discount/aligned), and contrarian signal. "
                "Positive = longs paying shorts, negative = deleveraging. Cost: $0.02 USDC via x402."
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
            name="cerebrus_depeg",
            description=(
                "Get USDC collateral health monitor via Chainlink oracle. "
                "Checks USDC/USD deviation from $1.00 peg, reports peg status "
                "(HEALTHY/ELEVATED/WARNING/CRITICAL), risk level, and Arbitrum "
                "sequencer status. Essential before sizing USDC-margined positions. "
                "Cost: $0.01 USDC via x402."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="cerebrus_liquidations",
            description=(
                "Get estimated liquidation heatmap for a Hyperliquid perpetual. "
                "Maps where liquidation clusters sit across 5 leverage tiers (3x-50x) "
                "for both longs and shorts. Returns cascade risk level "
                "(LOW/MODERATE/HIGH/EXTREME), estimated USD at each zone, proximity "
                "to current price, long/short ratio from funding skew, and nearest "
                "cluster alert. No other MCP provider offers this signal. "
                "Cost: $0.03 USDC via x402."
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
            coin = _validate_coin(arguments["coin"])
            timeframes = arguments.get("timeframes", "1h,4h")
            result = _api_get(f"/pulse/{coin}", params={"timeframes": timeframes})

        elif name == "cerebrus_sentiment":
            result = _api_get("/sentiment")

        elif name == "cerebrus_funding":
            coin = _validate_coin(arguments["coin"])
            lookback = arguments.get("lookback_hours", 24)
            result = _api_get(f"/funding/{coin}", params={"lookback_hours": lookback})

        elif name == "cerebrus_bundle":
            coin = _validate_coin(arguments["coin"])
            timeframes = arguments.get("timeframes", "1h,4h")
            result = _api_get(f"/bundle/{coin}", params={"timeframes": timeframes})

        elif name == "cerebrus_screener":
            top_n = arguments.get("top_n", 30)
            result = _api_get("/screener", params={"top_n": top_n})

        elif name == "cerebrus_oi":
            coin = _validate_coin(arguments["coin"])
            result = _api_get(f"/oi/{coin}")

        elif name == "cerebrus_spread":
            coin = _validate_coin(arguments["coin"])
            result = _api_get(f"/spread/{coin}")

        elif name == "cerebrus_correlation":
            result = _api_get("/correlation")

        elif name == "cerebrus_stress":
            limit = arguments.get("limit", 10)
            result = _api_get("/arb", params={"limit": limit})

        elif name == "cerebrus_cex_dex":
            coin = _validate_coin(arguments["coin"])
            result = _api_get(f"/cex-dex/{coin}")

        elif name == "cerebrus_basis":
            coin = _validate_coin(arguments["coin"])
            result = _api_get(f"/basis/{coin}")

        elif name == "cerebrus_depeg":
            result = _api_get("/depeg")

        elif name == "cerebrus_liquidations":
            coin = _validate_coin(arguments["coin"])
            result = _api_get(f"/liquidations/{coin}")

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=_format_response(result))]

    except ValueError as e:
        return [TextContent(
            type="text",
            text=_format_response({"error": str(e)}),
        )]
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
                "help": "Check that https://api.cerebruspulse.xyz is reachable.",
            }),
        )]


# ── CLI (--json mode) ───────────────────────────────────────────────────────

# Maps CLI tool names to (api_path_template, param_specs).
# param_specs: list of (name, required, type, default).
_CLI_TOOLS: dict[str, tuple[str, list[tuple[str, bool, type, Any]]]] = {
    "list-coins":    ("/coins",             []),
    "health":        ("/health",            []),
    "pulse":         ("/pulse/{coin}",      [("coin", True, str, None),
                                             ("timeframes", False, str, "1h,4h")]),
    "sentiment":     ("/sentiment",         []),
    "funding":       ("/funding/{coin}",    [("coin", True, str, None),
                                             ("lookback_hours", False, int, 24)]),
    "bundle":        ("/bundle/{coin}",     [("coin", True, str, None),
                                             ("timeframes", False, str, "1h,4h")]),
    "screener":      ("/screener",          [("top_n", False, int, 30)]),
    "oi":            ("/oi/{coin}",         [("coin", True, str, None)]),
    "spread":        ("/spread/{coin}",     [("coin", True, str, None)]),
    "correlation":   ("/correlation",       []),
    "stress":        ("/arb",              [("limit", False, int, 10)]),
    "cex-dex":       ("/cex-dex/{coin}",    [("coin", True, str, None)]),
    "basis":         ("/basis/{coin}",      [("coin", True, str, None)]),
    "depeg":         ("/depeg",             []),
    "liquidations":  ("/liquidations/{coin}", [("coin", True, str, None)]),
}


def _cli_call(tool: str, kv_args: list[str]) -> int:
    """Execute a tool via direct HTTP and print JSON to stdout. Returns exit code."""
    if tool not in _CLI_TOOLS:
        available = ", ".join(sorted(_CLI_TOOLS))
        print(json.dumps({"error": f"Unknown tool: {tool}", "available": available}),
              file=sys.stderr)
        return 1

    path_template, param_specs = _CLI_TOOLS[tool]

    # Parse key=value pairs
    parsed: dict[str, Any] = {}
    positional_idx = 0
    required_names = [name for name, req, _, _ in param_specs if req]

    for arg in kv_args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            parsed[k] = v
        else:
            # Treat positional args as filling required params in order
            if positional_idx < len(required_names):
                parsed[required_names[positional_idx]] = arg
                positional_idx += 1
            else:
                print(json.dumps({"error": f"Unexpected positional argument: {arg}"}),
                      file=sys.stderr)
                return 1

    # Reject unrecognized keys
    known_names = {name for name, _, _, _ in param_specs}
    unknown = set(parsed) - known_names
    if unknown:
        print(json.dumps({"error": f"Unknown parameter(s): {', '.join(sorted(unknown))}",
                          "valid": sorted(known_names) if known_names else []}),
              file=sys.stderr)
        return 1

    # Validate and coerce types
    params: dict[str, Any] = {}
    path_vars: dict[str, str] = {}

    for name, required, typ, default in param_specs:
        if name in parsed:
            try:
                params[name] = typ(parsed[name])
            except (ValueError, TypeError):
                print(json.dumps({"error": f"Invalid value for {name}: {parsed[name]}"}),
                      file=sys.stderr)
                return 1
        elif required:
            print(json.dumps({"error": f"Missing required argument: {name}",
                              "usage": f"cerebrus-pulse-mcp --json {tool} {name}=VALUE"}),
                  file=sys.stderr)
            return 1
        else:
            params[name] = default

    # Separate path variables from query params (validate coin tickers)
    for name in list(params):
        if "{" + name + "}" in path_template:
            value = str(params.pop(name))
            if name == "coin":
                try:
                    value = _validate_coin(value)
                except ValueError as e:
                    print(json.dumps({"error": str(e)}), file=sys.stderr)
                    return 1
            path_vars[name] = value

    path = path_template.format(**path_vars)

    # Remove params that equal their defaults (keep the URL clean)
    query_params = {k: v for k, v in params.items() if v is not None}

    try:
        result = _api_get(path, params=query_params if query_params else None)
        print(json.dumps(result, indent=2))
        return 0
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1


# ── Entry Points ────────────────────────────────────────────────────────────

async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point — MCP server (default) or CLI with --json flag."""
    parser = argparse.ArgumentParser(
        prog="cerebrus-pulse-mcp",
        description="Cerebrus Pulse MCP server — crypto intelligence for AI agents",
    )
    parser.add_argument(
        "--json",
        dest="json_tool",
        metavar="TOOL",
        nargs="?",
        const="__list__",
        help=(
            "CLI mode: call a tool and print JSON to stdout. "
            "Use '--json' alone to list tools, or '--json TOOL [key=value ...]' to call one."
        ),
    )
    parser.add_argument("cli_args", nargs="*", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.json_tool is not None:
        if args.json_tool == "__list__":
            tools = {name: {"params": {p[0]: {"required": p[1], "type": p[2].__name__, "default": p[3]}
                                       for p in specs}}
                     for name, (_, specs) in sorted(_CLI_TOOLS.items())}
            print(json.dumps({"tools": tools}, indent=2))
            sys.exit(0)
        sys.exit(_cli_call(args.json_tool, args.cli_args))

    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    main()
