#!/usr/bin/env python3
"""
Check that auto-pay's default payTo pin matches the payee the API charges.

Usage:
    python scripts/check_payto.py --live    # fetch an unpaid 402 from a paid route

Auto-pay refuses any payee not in CEREBRUS_ALLOWED_PAYTO, which defaults to
DEFAULT_ALLOWED_PAYTO in server.py. If the gateway's Base payTo is rotated and
that default is not, every install with default settings answers every paid
tool with payment_blocked. This script sends one GET to a paid route without
paying (nothing is signed) and runs each Base offer in the 402, from the v2
PAYMENT-REQUIRED header and from the v1 body, through a SpendGuard built from
the package defaults. Exit code 0 means a default install would pay it.
"""

import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal

DEFAULT_BASE = "https://api.cerebruspulse.xyz"
# The cheapest paid route, and it takes no path parameter.
PROBE_PATH = "/sentiment"


def fetch_402(base: str = DEFAULT_BASE, path: str = PROBE_PATH) -> tuple[int, dict, bytes]:
    """GET a paid route without a payment. Returns (status, headers, body)."""
    req = urllib.request.Request(
        f"{base}{path}",
        headers={"User-Agent": "cerebrus-pulse-mcp-payto-check"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:  # a 402 lands here
        return e.code, dict(e.headers), e.read()


def offers(headers: dict, body: bytes) -> dict[str, list]:
    """The payment offers in a 402, keyed by where they were found."""
    from x402.http.utils import decode_payment_required_header
    from x402.schemas.v1 import PaymentRequiredV1

    found = {}
    header = {k.lower(): v for k, v in headers.items()}.get("payment-required")
    if header:
        found["v2 PAYMENT-REQUIRED header"] = decode_payment_required_header(header).accepts
    try:
        data = json.loads(body or b"null")
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("x402Version") == 1:
        found["v1 body"] = PaymentRequiredV1.model_validate(data).accepts
    return found


def check(status: int, headers: dict, body: bytes) -> list[str]:
    """Return human-readable problems (empty when a default install would pay)."""
    from cerebrus_pulse_mcp import server

    if status != 402:
        return [f"the probe route answered {status}, not 402"]
    guard = server.SpendGuard(
        Decimal(server.DEFAULT_MAX_PAYMENT_USD),
        Decimal(server.DEFAULT_MAX_SPEND_USD),
        [server.DEFAULT_ALLOWED_PAYTO],
    )
    problems, base_offers = [], 0
    for source, accepts in offers(headers, body).items():
        for requirement in accepts:
            if str(requirement.network) not in server._BASE_NETWORKS:
                continue  # auto-pay pays Base only
            base_offers += 1
            reason = guard.refusal(requirement)
            if reason is not None:
                problems.append(f"{source}: a default install would refuse: {reason}")
    if not base_offers:
        problems.append("the 402 has no Base offer, so auto-pay can never pay")
    return problems


def main(argv: list[str]) -> int:
    if argv != ["--live"]:
        print(__doc__)
        return 2
    problems = check(*fetch_402())
    for p in problems:
        print(f"  MISMATCH  {p}")
    if problems:
        print("  If the gateway's payTo was rotated, set DEFAULT_ALLOWED_PAYTO in "
              "src/cerebrus_pulse_mcp/server.py to the new address.")
        return 1
    print(f"  A default install would pay the live {PROBE_PATH} 402.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
