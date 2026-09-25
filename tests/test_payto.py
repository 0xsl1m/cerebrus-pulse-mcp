"""The default payTo pin must follow the gateway's payTo (review: server.py:77).

Auto-pay refuses every payee outside CEREBRUS_ALLOWED_PAYTO, whose default is
DEFAULT_ALLOWED_PAYTO. A gateway payTo rotation that the default misses turns
every paid call of every default install into payment_blocked, and the price
check cannot see it. scripts/check_payto.py (CI and the release workflow)
catches that drift; scripts/release.py refuses to release a retired default.
"""

import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest
from x402.http.utils import encode_payment_required_header
from x402.schemas import PaymentRequired, PaymentRequirements, ResourceInfo

from cerebrus_pulse_mcp import server

ROOT = Path(__file__).resolve().parent.parent
PAY_TO = server.DEFAULT_ALLOWED_PAYTO
NEW_PAY_TO = "0x" + "ab" * 20
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
SOLANA = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"
SOLANA_USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
URL = "https://api.cerebruspulse.xyz/sentiment"


@pytest.fixture(scope="module")
def check_payto():
    spec = importlib.util.spec_from_file_location("check_payto", ROOT / "scripts" / "check_payto.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _v2_header(base_pay_to: str | None = PAY_TO) -> str:
    """The base64 PAYMENT-REQUIRED header the gateway's x402 v2 SDK sends."""
    accepts = [PaymentRequirements(
        scheme="exact", network=SOLANA, asset=SOLANA_USDC, amount="10000",
        pay_to="So1anaPayee1111111111111111111111111111111", max_timeout_seconds=300,
    )]
    if base_pay_to:
        accepts.insert(0, PaymentRequirements(
            scheme="exact", network="eip155:8453", asset=BASE_USDC, amount="10000",
            pay_to=base_pay_to, max_timeout_seconds=300,
            extra={"name": "USD Coin", "version": "2"},
        ))
    return encode_payment_required_header(PaymentRequired(
        x402_version=2, accepts=accepts, resource=ResourceInfo(url=URL),
    ))


def _v1_body(pay_to: str = PAY_TO) -> bytes:
    """The informational v1 body the gateway adds to every 402 (Base only)."""
    return json.dumps({
        "x402Version": 1,
        "error": "Payment required",
        "accepts": [{
            "scheme": "exact", "network": "base", "maxAmountRequired": "10000",
            "resource": URL, "description": "", "mimeType": "application/json",
            "payTo": pay_to, "maxTimeoutSeconds": 300, "asset": BASE_USDC,
            "extra": {"name": "USD Coin", "version": "2"},
        }],
    }).encode()


def test_a_default_install_would_pay_the_current_gateway(check_payto):
    headers = {"Payment-Required": _v2_header()}
    assert check_payto.check(402, headers, _v1_body()) == []


def test_a_rotated_gateway_payto_is_reported(check_payto):
    headers = {"PAYMENT-REQUIRED": _v2_header(NEW_PAY_TO)}
    problems = check_payto.check(402, headers, _v1_body(NEW_PAY_TO))
    assert len(problems) == 2
    assert all(NEW_PAY_TO in p and "CEREBRUS_ALLOWED_PAYTO" in p for p in problems)


def test_drift_in_the_v1_body_alone_is_reported(check_payto):
    problems = check_payto.check(402, {"payment-required": _v2_header()}, _v1_body(NEW_PAY_TO))
    assert len(problems) == 1
    assert problems[0].startswith("v1 body")


def test_a_402_without_a_base_offer_is_reported(check_payto):
    problems = check_payto.check(402, {"payment-required": _v2_header(None)}, b"{}")
    assert problems == ["the 402 has no Base offer, so auto-pay can never pay"]


def test_a_non_402_answer_is_reported(check_payto):
    assert check_payto.check(200, {}, b"{}") == ["the probe route answered 200, not 402"]


def test_the_check_ignores_local_env_overrides(check_payto, monkeypatch):
    # It checks what a DEFAULT install does, not this machine's settings.
    monkeypatch.setenv("CEREBRUS_ALLOWED_PAYTO", NEW_PAY_TO)
    monkeypatch.setenv("CEREBRUS_MAX_PAYMENT_USD", "0")
    assert check_payto.check(402, {"payment-required": _v2_header()}, _v1_body()) == []


def _serve_402(monkeypatch, check_payto, pay_to: str) -> list:
    requests_seen = []

    def urlopen(req, timeout):
        requests_seen.append(req)
        raise urllib.error.HTTPError(
            req.full_url, 402, "Payment Required",
            {"Content-Type": "application/json", "PAYMENT-REQUIRED": _v2_header(pay_to)},
            io.BytesIO(_v1_body(pay_to)),
        )

    monkeypatch.setattr(check_payto.urllib.request, "urlopen", urlopen)
    return requests_seen


def test_live_probe_sends_no_payment_and_passes(check_payto, monkeypatch, capsys):
    seen = _serve_402(monkeypatch, check_payto, PAY_TO)

    assert check_payto.main(["--live"]) == 0

    (req,) = seen
    assert req.full_url == "https://api.cerebruspulse.xyz/sentiment"
    assert req.get_method() == "GET"
    sent = {k.lower() for k in req.headers}
    assert not sent & {"payment-signature", "x-payment"}
    assert "would pay" in capsys.readouterr().out


def test_live_probe_fails_after_an_unfollowed_rotation(check_payto, monkeypatch, capsys):
    _serve_402(monkeypatch, check_payto, NEW_PAY_TO)

    assert check_payto.main(["--live"]) == 1
    assert "DEFAULT_ALLOWED_PAYTO" in capsys.readouterr().out
