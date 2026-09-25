"""Client-side spend controls on x402 auto-payment (F071).

These tests drive the real x402 SDK client: payloads are signed locally with a
fake key and nothing touches the network.
"""

import json
from decimal import Decimal

import pytest
import requests
from x402 import NoMatchingRequirementsError
from x402.schemas import PaymentRequired, PaymentRequirements, ResourceInfo

from cerebrus_pulse_mcp import server

# A syntactically valid, obviously fake secp256k1 key. Never funded.
DUMMY_KEY = "0x" + "11" * 32
PAY_TO = server.DEFAULT_ALLOWED_PAYTO
OTHER_PAY_TO = "0x000000000000000000000000000000000000dEaD"
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
LIMIT_VARS = ("CEREBRUS_MAX_PAYMENT_USD", "CEREBRUS_MAX_SPEND_USD", "CEREBRUS_ALLOWED_PAYTO")


def _atomic(usd: str) -> str:
    return str(int(Decimal(usd) * 1_000_000))


def offer(usd: str, pay_to: str = PAY_TO, network: str = "eip155:8453",
          asset: str = BASE_USDC) -> PaymentRequirements:
    return PaymentRequirements(
        scheme="exact", network=network, asset=asset, amount=_atomic(usd),
        pay_to=pay_to, max_timeout_seconds=300,
        extra={"name": "USD Coin", "version": "2"},
    )


def required(*offers: PaymentRequirements) -> PaymentRequired:
    return PaymentRequired(
        x402_version=2, accepts=list(offers),
        resource=ResourceInfo(url="https://api.cerebruspulse.xyz/pulse/BTC"),
    )


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    for name in LIMIT_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(server, "_PAYING_SESSION", None)
    monkeypatch.setattr(server, "_PAYMENT_INIT_ERROR", None)
    monkeypatch.setattr(server, "_SPEND_GUARD", None)


def make_client():
    guard = server.SpendGuard.from_env()
    return guard, server._build_payment_client(DUMMY_KEY, guard)


# ── Defaults ────────────────────────────────────────────────────────────────

def test_safe_defaults():
    guard = server.SpendGuard.from_env()
    assert guard.max_payment_usd == Decimal("0.10")
    assert guard.max_spend_usd == Decimal("1.00")
    assert guard.allowed_pay_to == {PAY_TO.lower()}
    assert guard.spent_usd == 0


def test_pays_published_payto_within_limits():
    guard, client = make_client()
    payload = client.create_payment_payload(required(offer("0.025")))
    assert payload.accepted.pay_to == PAY_TO
    assert guard.spent_usd == Decimal("0.025")


# ── Per-call cap ────────────────────────────────────────────────────────────

def test_per_call_cap_blocks_expensive_payment(monkeypatch):
    monkeypatch.setenv("CEREBRUS_MAX_PAYMENT_USD", "0.05")
    guard, client = make_client()
    with pytest.raises(NoMatchingRequirementsError):
        client.create_payment_payload(required(offer("0.06")))
    assert guard.spent_usd == 0


def test_per_call_cap_reason_names_the_setting():
    guard = server.SpendGuard(Decimal("0.05"), Decimal("1"), [PAY_TO])
    assert "CEREBRUS_MAX_PAYMENT_USD" in guard.refusal(offer("0.06"))
    assert guard.refusal(offer("0.05")) is None


def test_per_call_cap_can_be_raised_above_sdk_default(monkeypatch):
    # The SDK's own default cap is $1 per payment; our setting must win.
    monkeypatch.setenv("CEREBRUS_MAX_PAYMENT_USD", "2")
    monkeypatch.setenv("CEREBRUS_MAX_SPEND_USD", "5")
    guard, client = make_client()
    client.create_payment_payload(required(offer("1.50")))
    assert guard.spent_usd == Decimal("1.50")


# ── Session budget ──────────────────────────────────────────────────────────

def test_session_budget_stops_signing_once_reached(monkeypatch):
    monkeypatch.setenv("CEREBRUS_MAX_SPEND_USD", "0.05")
    guard, client = make_client()
    client.create_payment_payload(required(offer("0.025")))
    client.create_payment_payload(required(offer("0.025")))
    assert guard.spent_usd == Decimal("0.05")

    with pytest.raises(NoMatchingRequirementsError):
        client.create_payment_payload(required(offer("0.01")))
    assert "CEREBRUS_MAX_SPEND_USD" in guard.last_refusal
    assert guard.spent_usd == Decimal("0.05")


def test_zero_budget_never_signs(monkeypatch):
    monkeypatch.setenv("CEREBRUS_MAX_SPEND_USD", "0")
    guard, client = make_client()
    with pytest.raises(NoMatchingRequirementsError):
        client.create_payment_payload(required(offer("0.01")))
    assert guard.spent_usd == 0


# ── payTo and asset pin ─────────────────────────────────────────────────────

def test_unknown_payto_is_refused():
    guard, client = make_client()
    with pytest.raises(NoMatchingRequirementsError):
        client.create_payment_payload(required(offer("0.01", pay_to=OTHER_PAY_TO)))
    assert "CEREBRUS_ALLOWED_PAYTO" in guard.last_refusal
    assert guard.spent_usd == 0


def test_payto_match_is_case_insensitive():
    guard, client = make_client()
    client.create_payment_payload(required(offer("0.01", pay_to=PAY_TO.lower())))
    assert guard.spent_usd == Decimal("0.01")


def test_mixed_offers_pay_only_the_allowlisted_payee():
    guard, client = make_client()
    payload = client.create_payment_payload(
        required(offer("0.01", pay_to=OTHER_PAY_TO), offer("0.01"))
    )
    assert payload.accepted.pay_to == PAY_TO


def test_allowlist_env_replaces_the_default(monkeypatch):
    monkeypatch.setenv("CEREBRUS_ALLOWED_PAYTO", f" {OTHER_PAY_TO} , 0x{'22' * 20}")
    guard, client = make_client()
    with pytest.raises(NoMatchingRequirementsError):
        client.create_payment_payload(required(offer("0.01")))
    client.create_payment_payload(required(offer("0.01", pay_to=OTHER_PAY_TO)))
    assert guard.spent_usd == Decimal("0.01")


def test_only_usdc_on_base_is_paid():
    guard = server.SpendGuard(Decimal("1"), Decimal("1"), [PAY_TO])
    other_token = "0x" + "33" * 20
    assert "only USDC on Base" in guard.refusal(offer("0.01", asset=other_token))
    assert "only USDC on Base" in guard.refusal(offer("0.01", network="eip155:1"))
    assert guard.refusal(offer("0.01")) is None


# ── Malformed settings fail closed ──────────────────────────────────────────

@pytest.mark.parametrize("name,value", [
    ("CEREBRUS_MAX_PAYMENT_USD", "ten cents"),
    ("CEREBRUS_MAX_SPEND_USD", "-1"),
    ("CEREBRUS_MAX_SPEND_USD", "NaN"),
    ("CEREBRUS_ALLOWED_PAYTO", "0x1234"),
])
def test_malformed_limit_disables_auto_payment(monkeypatch, name, value):
    monkeypatch.setenv("CEREBRUS_WALLET_KEY", DUMMY_KEY)
    monkeypatch.setenv(name, value)
    assert server._paying_session() is None
    assert server._PAYMENT_INIT_ERROR.startswith("invalid spend limit setting")
    assert name in server._PAYMENT_INIT_ERROR


# ── End to end through _api_get, HTTP mocked at the transport ───────────────

def _gateway_402(url: str, usd: str = "0.025", pay_to: str = PAY_TO) -> requests.Response:
    """The x402 v1 body the gateway sends with every 402."""
    body = {
        "x402Version": 1,
        "error": "Payment required",
        "accepts": [{
            "scheme": "exact", "network": "base", "maxAmountRequired": _atomic(usd),
            "resource": url, "description": "", "mimeType": "application/json",
            "payTo": pay_to, "maxTimeoutSeconds": 300, "asset": BASE_USDC,
            "extra": {"name": "USD Coin", "version": "2"},
        }],
    }
    return _response(402, body, url)


def _response(status: int, body: dict, url: str) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(body).encode()
    resp.headers["Content-Type"] = "application/json"
    resp.url = url
    return resp


@pytest.fixture
def transport(monkeypatch):
    """Replace the network under the x402 adapter; forbid the unpaid client."""
    calls = []
    script = {}

    def send(self, request, **kwargs):
        paid = bool(request.headers.get("PAYMENT-SIGNATURE") or request.headers.get("X-PAYMENT"))
        calls.append({"url": request.url, "paid": paid})
        return script["paid" if paid else "unpaid"](request.url)

    def no_unpaid_client():
        raise AssertionError("an unpaid retry was made")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(server, "_make_client", no_unpaid_client)
    monkeypatch.setenv("CEREBRUS_WALLET_KEY", DUMMY_KEY)
    return calls, script


def test_api_get_pays_and_counts_spend(transport):
    calls, script = transport
    script["unpaid"] = _gateway_402
    script["paid"] = lambda url: _response(200, {"coin": "BTC"}, url)

    assert server._api_get("/pulse/BTC") == {"coin": "BTC"}
    assert [c["paid"] for c in calls] == [False, True]
    assert server._SPEND_GUARD.spent_usd == Decimal("0.025")


def test_api_get_reports_blocked_payment_without_unpaid_retry(transport, monkeypatch):
    calls, script = transport
    script["unpaid"] = lambda url: _gateway_402(url, pay_to=OTHER_PAY_TO)
    script["paid"] = lambda url: pytest.fail("a payment was signed")

    result = server._api_get("/pulse/BTC")

    assert result["status"] == "payment_blocked"
    assert "CEREBRUS_ALLOWED_PAYTO" in result["message"]
    assert len(calls) == 1
    assert server._SPEND_GUARD.spent_usd == 0


def test_api_get_reports_sdk_cap_refusal_as_blocked(transport, monkeypatch):
    monkeypatch.setenv("CEREBRUS_MAX_PAYMENT_USD", "0.01")
    calls, script = transport
    script["unpaid"] = _gateway_402
    script["paid"] = lambda url: pytest.fail("a payment was signed")

    result = server._api_get("/pulse/BTC")

    assert result["status"] == "payment_blocked"
    assert "max_amount_per_payment" in result["message"]
    assert len(calls) == 1


def test_api_get_reports_server_rejection_with_terms(transport):
    calls, script = transport
    script["unpaid"] = _gateway_402
    script["paid"] = _gateway_402  # the API refused the signed payment

    result = server._api_get("/pulse/BTC")

    assert result["status"] == "payment_rejected"
    assert result["payment_terms"]["price_usdc"] == 0.025
    assert result["payment_terms"]["pay_to"] == PAY_TO
    assert "None" not in result["help"]
    assert [c["paid"] for c in calls] == [False, True]


@pytest.mark.parametrize("amount", ["-5", "0.5", "abc", ""])
def test_unreadable_amount_is_refused(amount):
    guard = server.SpendGuard(Decimal("1"), Decimal("1"), [PAY_TO])
    bad = offer("0.01").model_copy(update={"amount": amount})
    assert "unreadable amount" in guard.refusal(bad)
