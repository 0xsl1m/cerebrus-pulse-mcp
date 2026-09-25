"""
Cerebrus Pulse MCP Server

Exposes Cerebrus Pulse crypto intelligence API as MCP tools for AI agents.
Supports both free endpoints (health, coins) and paid x402 endpoints
(pulse, sentiment, funding, bundle).

Paid endpoints:
  * With CEREBRUS_WALLET_KEY set, the 402 flow is settled automatically
    against Base and the data is returned directly. The x402 client is a
    core dependency since 0.5.2 (it was an optional [pay] extra that the
    documented uvx setup never installed).
  * Otherwise the tool returns structured payment terms (price, network,
    recipient) parsed from the 402 so the caller can pay itself.
  * Auto-payment is bounded client-side before anything is signed: a per-call
    cap (CEREBRUS_MAX_PAYMENT_USD), a per-process budget
    (CEREBRUS_MAX_SPEND_USD), and a payee allowlist (CEREBRUS_ALLOWED_PAYTO).
    Only USDC on Base is paid.
  * The --json CLI starts a new process, and so a fresh budget, on every run.
    It only auto-pays when CEREBRUS_CLI_AUTOPAY=1 says the caller accepts that.

Versions before 0.5.0 advertised automatic payment but never implemented it --
there was no x402 client dependency at all, and the 402 handler read a header
name the server does not send. Paid tools were a dead end for every caller.

Disclaimer: Data provided is for informational purposes only and does not
constitute financial advice. Cryptocurrency trading involves substantial
risk of loss.
"""

import argparse
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
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


# ── Spend controls ──────────────────────────────────────────────────────────

# The published Base payTo of api.cerebruspulse.xyz. Auto-pay refuses any other
# payee unless CEREBRUS_ALLOWED_PAYTO says otherwise. This default MUST be
# updated whenever the gateway's payTo address is rotated:
# scripts/check_payto.py --live (CI, release workflow) fails while the two
# differ, and scripts/release.py check refuses an address in RETIRED_PAYTO.
DEFAULT_ALLOWED_PAYTO = "0xfDFB12764c76B5113153acaa2317081F4Abc2a88"
# The most expensive endpoint costs $0.06 (screener).
DEFAULT_MAX_PAYMENT_USD = "0.10"
# Total auto-pay may sign during one server process.
DEFAULT_MAX_SPEND_USD = "1.00"

_BASE_NETWORKS = frozenset({"eip155:8453", "base"})  # x402 v2 / v1 names
_BASE_USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
_USDC_UNIT = Decimal(1_000_000)
_EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _env_usd(name: str, default: str) -> Decimal:
    raw = os.environ.get(name, "").strip() or default
    try:
        value = Decimal(raw.lstrip("$"))
    except InvalidOperation:
        raise ValueError(f"{name}={raw!r} is not a USD amount") from None
    # is_signed() also rejects "-0", which the x402 SDK cannot parse.
    if not value.is_finite() or value.is_signed():
        raise ValueError(f"{name}={raw!r} must be a non-negative USD amount")
    return value


def _env_allowed_pay_to() -> list[str]:
    raw = os.environ.get("CEREBRUS_ALLOWED_PAYTO", "").strip() or DEFAULT_ALLOWED_PAYTO
    addresses = [a.strip() for a in raw.split(",") if a.strip()]
    bad = [a for a in addresses if not _EVM_ADDRESS_RE.match(a)]
    if bad or not addresses:
        raise ValueError(f"CEREBRUS_ALLOWED_PAYTO has invalid address(es): {bad or raw!r}")
    return addresses


class SpendGuard:
    """Client-side limits, checked before any payment is signed.

    Only USDC on Base to an allowlisted payTo is paid, no single payment may
    exceed ``max_payment_usd``, and the total signed by this process may not
    exceed ``max_spend_usd``. Every signed payment counts toward the budget,
    even one the API then rejects: a signed authorization can still settle.
    """

    def __init__(self, max_payment_usd: Decimal, max_spend_usd: Decimal,
                 allowed_pay_to: list[str]):
        self.max_payment_usd = max_payment_usd
        self.max_spend_usd = max_spend_usd
        self.allowed_pay_to = frozenset(a.lower() for a in allowed_pay_to)
        self.spent_usd = Decimal(0)
        self.last_refusal: str | None = None

    @classmethod
    def from_env(cls) -> "SpendGuard":
        """Read the limits from the environment. Raises ValueError if malformed."""
        return cls(
            _env_usd("CEREBRUS_MAX_PAYMENT_USD", DEFAULT_MAX_PAYMENT_USD),
            _env_usd("CEREBRUS_MAX_SPEND_USD", DEFAULT_MAX_SPEND_USD),
            _env_allowed_pay_to(),
        )

    def refusal(self, requirement) -> str | None:
        """Why this offer must not be paid, or None if it is within every limit."""
        network, asset = str(requirement.network), str(requirement.asset)
        if network not in _BASE_NETWORKS or asset.lower() != _BASE_USDC:
            return f"only USDC on Base is auto-paid (offer: asset {asset} on {network})"
        if str(requirement.pay_to).lower() not in self.allowed_pay_to:
            return f"payTo {requirement.pay_to} is not in CEREBRUS_ALLOWED_PAYTO"
        amount = str(requirement.get_amount())
        if not (amount.isascii() and amount.isdigit()):
            return f"unreadable amount {amount!r}"
        price = Decimal(int(amount)) / _USDC_UNIT
        if price > self.max_payment_usd:
            return f"price ${price} exceeds CEREBRUS_MAX_PAYMENT_USD (${self.max_payment_usd:f})"
        if self.spent_usd + price > self.max_spend_usd:
            return (
                f"budget reached: ${self.spent_usd} already signed this session and this "
                f"call costs ${price}, over CEREBRUS_MAX_SPEND_USD (${self.max_spend_usd:f})"
            )
        return None

    def policy(self, x402_version: int, requirements: list) -> list:
        """x402 PaymentPolicy: keep only the offers inside every limit."""
        kept, reasons = [], []
        for requirement in requirements:
            reason = self.refusal(requirement)
            if reason is None:
                kept.append(requirement)
            else:
                reasons.append(reason)
        if not kept:
            self.last_refusal = "; ".join(reasons) or "no payable offer"
        return kept

    def record(self, context) -> None:
        """x402 after-payment-creation hook: count every signed payment."""
        amount = int(context.selected_requirements.get_amount())
        self.spent_usd += Decimal(amount) / _USDC_UNIT


def _build_payment_client(key: str, guard: SpendGuard):
    """An x402 client that signs Base payments with ``key`` inside ``guard``."""
    from eth_account import Account
    from x402 import x402ClientSync
    from x402.mechanisms.evm.exact import register_exact_evm_client

    client = x402ClientSync()
    # SDK-level backstop for the per-call cap; it also limits payment to the
    # SDK's recognized stablecoins. The SDK parses this string only when it
    # pays and rejects exponent notation, which str() gives a Decimal read from
    # "1e1" or "0.0000001"; the :f format always writes plain digits.
    client.set_spend_controls({"max_amount_per_payment": f"${guard.max_payment_usd:f}"})
    # register_exact_evm_client wraps a raw LocalAccount for us, and
    # registers BOTH the v2 scheme and the v1 legacy schemes.
    register_exact_evm_client(
        client, Account.from_key(key), networks="eip155:8453", policies=[guard.policy]
    )
    client.on_after_payment_creation(guard.record)
    return client


_PAYING_SESSION: Any = None
_PAYMENT_INIT_ERROR: str | None = None
_SPEND_GUARD: SpendGuard | None = None
# Set by the --json CLI. Each CLI run is its own process, so the per-process
# budget cannot bound spend across runs; the CLI pays only on explicit opt-in.
_CLI_MODE = False


def _paying_session():
    """Build (once) a requests Session that settles x402 payments automatically.

    Returns None when no wallet key is configured or the payment dependencies
    cannot be imported. Never raises: an unpayable request must still return useful
    payment terms rather than blowing up the tool call.
    """
    global _PAYING_SESSION, _PAYMENT_INIT_ERROR, _SPEND_GUARD
    if _PAYING_SESSION is not None or _PAYMENT_INIT_ERROR is not None:
        return _PAYING_SESSION

    key = os.environ.get("CEREBRUS_WALLET_KEY", "").strip()
    if not key:
        _PAYMENT_INIT_ERROR = "no_wallet_key"
        return None

    if _CLI_MODE and os.environ.get("CEREBRUS_CLI_AUTOPAY", "").strip() != "1":
        _PAYMENT_INIT_ERROR = (
            "the --json CLI does not auto-pay unless CEREBRUS_CLI_AUTOPAY=1, because "
            "each CLI run starts a new CEREBRUS_MAX_SPEND_USD budget"
        )
        return None

    try:
        guard = SpendGuard.from_env()
    except ValueError as e:  # fail closed: a typo must not lift a limit
        _PAYMENT_INIT_ERROR = f"invalid spend limit setting: {e}"
        return None

    try:
        import eth_account  # noqa: F401
        import x402  # noqa: F401
        from x402.http.clients import x402_requests
    except ImportError as e:
        _PAYMENT_INIT_ERROR = (
            f"payment dependencies missing ({e}). Reinstall with: "
            "pip install --force-reinstall cerebrus-pulse-mcp"
        )
        return None

    try:
        _PAYING_SESSION = x402_requests(_build_payment_client(key, guard))
        _SPEND_GUARD = guard
        return _PAYING_SESSION
    except Exception as e:  # noqa: BLE001 - degrade to unpaid, never crash
        _PAYMENT_INIT_ERROR = f"payment client init failed: {e}"
        return None


def _local_refusal(exc: BaseException) -> str | None:
    """The reason a payment was refused client-side (nothing signed), else None."""
    if _SPEND_GUARD is not None and _SPEND_GUARD.last_refusal:
        return _SPEND_GUARD.last_refusal
    try:
        from x402 import NoMatchingRequirementsError
    except ImportError:
        return None
    # The requests adapter wraps SDK errors: PaymentError(...) from <cause>.
    for err in (exc, exc.__cause__):
        if isinstance(err, NoMatchingRequirementsError):
            return str(err)
    return None


def _payment_terms(resp) -> dict[str, Any]:
    """Turn a 402 into structured, actionable terms for the calling agent.

    The gateway emits terms in BOTH the x402 v1 JSON body and the v2
    `Payment-Required` header. Read the body: it is the interoperable shape.
    (Earlier versions of this file read a header named `X-Payment`, which the
    server has never sent, so callers got nothing usable.)
    """
    terms: dict[str, Any] = {}
    try:
        body = resp.json()
        offers = body.get("accepts") or []
        if offers:
            offer = offers[0]
            terms = {
                "price_usdc": int(offer["maxAmountRequired"]) / 1_000_000,
                "network": offer.get("network"),
                "pay_to": offer.get("payTo"),
                "asset": offer.get("asset"),
                "resource": offer.get("resource"),
            }
    except Exception:  # noqa: BLE001 - a malformed 402 is still a 402
        pass
    return terms


def _api_get(path: str, params: dict | None = None) -> dict[str, Any]:
    """Make a GET request to the Cerebrus Pulse API, paying if configured."""
    session = _paying_session()
    if session is not None:
        if _SPEND_GUARD is not None:
            _SPEND_GUARD.last_refusal = None
        try:
            resp = session.get(f"{BASE_URL}{path}", params=params, timeout=REQUEST_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            refusal = _local_refusal(e)
            if refusal is not None:
                return {
                    "status": "payment_blocked",
                    "message": f"Auto-payment blocked by local spend limits: {refusal}",
                    "url": f"{BASE_URL}{path}",
                    "help": (
                        "The refused payment was not signed. Adjust CEREBRUS_MAX_PAYMENT_USD, "
                        "CEREBRUS_MAX_SPEND_USD or CEREBRUS_ALLOWED_PAYTO if this is expected, "
                        "or restart the server to reset the session budget."
                    ),
                }
            return {
                "status": "payment_failed",
                "message": f"x402 payment attempt failed: {e}",
                "url": f"{BASE_URL}{path}",
                "help": "Check the wallet holds enough USDC on Base.",
            }
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 402:
            # The adapter signed and retried, and the API still answered 402.
            # Report that directly; an unpaid retry would only burn rate limit.
            return {
                "status": "payment_rejected",
                "message": "A signed x402 payment was sent but the API did not accept it.",
                "url": f"{BASE_URL}{path}",
                "payment_terms": _payment_terms(resp),
                "help": (
                    "Check the wallet holds enough USDC on Base. "
                    "See https://cerebruspulse.xyz/guides/x402-payments"
                ),
            }
        # Anything else: fall through to the unpaid path for the usual handling.

    with _make_client() as client:
        resp = client.get(path, params=params)

        if resp.status_code == 402:
            if _PAYMENT_INIT_ERROR == "no_wallet_key":
                help_text = (
                    "Set CEREBRUS_WALLET_KEY to the private key of a dedicated, low-balance "
                    "Base wallet to pay automatically. "
                    "See https://cerebruspulse.xyz/guides/x402-payments"
                )
            elif _PAYMENT_INIT_ERROR:
                help_text = (
                    f"Auto-payment unavailable: {_PAYMENT_INIT_ERROR}. "
                    "See https://cerebruspulse.xyz/guides/x402-payments"
                )
            else:
                help_text = (
                    "Auto-payment is configured but this request was not paid; retry later. "
                    "See https://cerebruspulse.xyz/guides/x402-payments"
                )
            return {
                "status": "payment_required",
                "message": "This endpoint requires an x402 USDC payment on Base or Solana.",
                "url": f"{BASE_URL}{path}",
                "payment_terms": _payment_terms(resp),
                "help": help_text,
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
                "derivatives data (funding, OI, spread), and market regime. Cost: $0.025 USDC via x402."
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
                "17% discount vs individual endpoints. Cost: $0.05 USDC via x402."
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
                "Much cheaper than calling pulse individually. Cost: $0.06 USDC via x402."
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
                "and price-OI divergence signals. Cost: $0.015 USDC via x402."
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
                "and liquidity score (1-10). Cost: $0.015 USDC via x402."
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
                "Cost: $0.05 USDC via x402."
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
                "Unique signal — not available from any other provider. Cost: $0.02 USDC via x402."
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
    global _CLI_MODE
    _CLI_MODE = True
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
