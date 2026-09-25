"""server.json (the MCP registry manifest) must be valid and declare our env vars.

Without `environmentVariables`, registry-driven installers never prompt for the
wallet key or the spend limits (F027, F071).
"""

import json
from pathlib import Path

import jsonschema

from cerebrus_pulse_mcp import server

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
# Copied from the URL in server.json's "$schema" so the check runs offline.
SCHEMA = json.loads(
    (Path(__file__).parent / "fixtures" / "server.schema.2025-12-11.json").read_text(encoding="utf-8")
)


def _env_vars() -> dict[str, dict]:
    (package,) = MANIFEST["packages"]
    return {v["name"]: v for v in package.get("environmentVariables", [])}


def test_manifest_matches_the_registry_schema():
    assert MANIFEST["$schema"] == SCHEMA["$id"]
    jsonschema.validate(MANIFEST, SCHEMA)


def test_manifest_declares_every_env_var_the_server_reads():
    source = Path(server.__file__).read_text(encoding="utf-8")
    declared = set(_env_vars())
    for name in ("CEREBRUS_WALLET_KEY", "CEREBRUS_MAX_PAYMENT_USD", "CEREBRUS_MAX_SPEND_USD",
                 "CEREBRUS_ALLOWED_PAYTO", "CEREBRUS_BASE_URL"):
        assert name in source
        assert name in declared


def test_wallet_key_is_optional_and_secret():
    key = _env_vars()["CEREBRUS_WALLET_KEY"]
    assert key["isSecret"] is True
    assert key["isRequired"] is False


def test_declared_defaults_match_the_code():
    env = _env_vars()
    assert env["CEREBRUS_MAX_PAYMENT_USD"]["default"] == server.DEFAULT_MAX_PAYMENT_USD
    assert env["CEREBRUS_MAX_SPEND_USD"]["default"] == server.DEFAULT_MAX_SPEND_USD
    assert env["CEREBRUS_BASE_URL"]["default"] == "https://api.cerebruspulse.xyz"
