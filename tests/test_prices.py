"""Advertised prices must match what the API charges (F045).

The fixture is https://api.cerebruspulse.xyz/.well-known/x402 as fetched on
2026-09-24. CI also runs `scripts/check_prices.py --live` against the API.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads(
    (Path(__file__).parent / "fixtures" / "well_known_x402.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def check_prices():
    spec = importlib.util.spec_from_file_location("check_prices", ROOT / "scripts" / "check_prices.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_and_tool_descriptions_match_the_manifest(check_prices):
    assert check_prices.check(MANIFEST) == []


def test_every_paid_tool_is_in_the_manifest(check_prices):
    published = check_prices.manifest_prices(MANIFEST)
    paths = check_prices.tool_paths()
    free = {tool for tool, path in paths.items() if path not in published}
    assert free == {"cerebrus_health", "cerebrus_list_coins"}


def test_a_price_change_is_detected(check_prices):
    manifest = copy.deepcopy(MANIFEST)
    for endpoint in manifest["endpoints"]:
        if endpoint["url"].endswith("/pulse/*"):
            endpoint["price"]["amount"] = 0.03
    problems = check_prices.check(manifest)
    assert any("README: cerebrus_pulse" in p for p in problems)
    assert any("tool description: cerebrus_pulse" in p for p in problems)


def test_a_stale_readme_row_is_detected(check_prices):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    stale = readme.replace("| $0.06 |", "| $0.04 |")
    assert stale != readme
    problems = check_prices.check(MANIFEST, readme_text=stale)
    assert any("cerebrus_screener" in p for p in problems)


def test_a_new_manifest_endpoint_without_a_tool_is_reported(check_prices):
    manifest = copy.deepcopy(MANIFEST)
    manifest["endpoints"].append({
        "method": "GET", "url": "https://api.cerebruspulse.xyz/new-thing",
        "description": "", "price": {"amount": 0.01, "currency": "USD", "asset": "USDC"},
    })
    assert any("/new-thing" in p for p in check_prices.check(manifest))
