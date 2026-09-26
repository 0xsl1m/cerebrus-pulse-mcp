#!/usr/bin/env python3
"""
Check the prices this package advertises against the API's x402 manifest.

Usage:
    python scripts/check_prices.py --live                 # fetch /.well-known/x402
    python scripts/check_prices.py path/to/manifest.json  # use a saved copy

Compares every paid tool's price in the README table and in its MCP tool
description ("Cost: $X") with the price the gateway publishes, and fails if
any differ or if a tool has no priced endpoint. Free tools must not appear in
the manifest. Exit code 0 means everything agrees.
"""

import asyncio
import json
import re
import sys
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DEFAULT_BASE = "https://api.cerebruspulse.xyz"

_README_ROW = re.compile(r"^\|\s*`(cerebrus_[a-z_]+)`\s*\|.*\|\s*(Free|\$[0-9.]+)\s*\|\s*$")
_COST = re.compile(r"Cost: \$([0-9.]+)")


def fetch_manifest(base: str = DEFAULT_BASE) -> dict:
    req = urllib.request.Request(
        f"{base}/.well-known/x402",
        headers={"User-Agent": "cerebrus-pulse-mcp-price-check"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def manifest_prices(manifest: dict) -> dict[str, Decimal]:
    """Map endpoint path ("/pulse/*") to its published USD price."""
    prices = {}
    for endpoint in manifest.get("endpoints", []):
        path = re.sub(r"^https?://[^/]+", "", endpoint["url"])
        # Gateway 1.4.0 names path params ("/pulse/{coin}", F064); older
        # manifests used "/pulse/*". Normalise both to the "*" form.
        path = re.sub(r"\{[^}]+\}", "*", path)
        prices[path] = Decimal(str(endpoint["price"]["amount"]))
    return prices


def tool_paths() -> dict[str, str]:
    """Map MCP tool name to its API path, in manifest form ("/pulse/*")."""
    from cerebrus_pulse_mcp.server import _CLI_TOOLS

    return {
        "cerebrus_" + cli.replace("-", "_"): re.sub(r"\{[^}]+\}", "*", template)
        for cli, (template, _) in _CLI_TOOLS.items()
    }


def readme_prices(text: str) -> dict[str, Decimal | None]:
    """Tool name to README price (None for Free)."""
    prices = {}
    for line in text.splitlines():
        m = _README_ROW.match(line)
        if m:
            prices[m.group(1)] = None if m.group(2) == "Free" else Decimal(m.group(2)[1:])
    return prices


def description_prices() -> dict[str, Decimal | None]:
    """Tool name to the "Cost: $X" in its MCP description (None if it has none)."""
    from cerebrus_pulse_mcp.server import list_tools

    prices = {}
    for tool in asyncio.run(list_tools()):
        m = _COST.search(tool.description or "")
        prices[tool.name] = Decimal(m.group(1)) if m else None
    return prices


def check(manifest: dict, readme_text: str | None = None) -> list[str]:
    """Return a list of human-readable mismatches (empty when all agree)."""
    published = manifest_prices(manifest)
    paths = tool_paths()
    sources = {
        "README": readme_prices(README.read_text(encoding="utf-8") if readme_text is None else readme_text),
        "tool description": description_prices(),
    }
    problems = []
    for tool, path in sorted(paths.items()):
        expected = published.get(path)
        for source, prices in sources.items():
            if tool not in prices:
                problems.append(f"{source}: {tool} is missing")
                continue
            if prices[tool] != expected:
                want = "Free (not in manifest)" if expected is None else f"${expected}"
                got = "Free/none" if prices[tool] is None else f"${prices[tool]}"
                problems.append(f"{source}: {tool} ({path}) says {got}, manifest says {want}")
    unused = sorted(set(published) - set(paths.values()))
    if unused:
        problems.append(f"manifest endpoints with no MCP tool: {', '.join(unused)}")
    return problems


def main(argv: list[str]) -> int:
    if argv == ["--live"]:
        manifest = fetch_manifest()
    elif len(argv) == 1:
        manifest = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    else:
        print(__doc__)
        return 2
    problems = check(manifest)
    for p in problems:
        print(f"  MISMATCH  {p}")
    if not problems:
        print(f"  All {len(tool_paths())} tool prices match the x402 manifest.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
