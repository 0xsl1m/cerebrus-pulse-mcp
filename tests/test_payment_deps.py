"""Auto-payment must work from the documented `uvx cerebrus-pulse-mcp` install.

uvx installs the bare package into an isolated environment, so payment
dependencies kept behind the optional `[pay]` extra never reached the
documented setups (F027). They are core dependencies now.
"""

import re
from importlib.metadata import metadata, requires

import pytest

from cerebrus_pulse_mcp import server

# A syntactically valid, obviously fake secp256k1 key. Never funded.
DUMMY_KEY = "0x" + "11" * 32


def _requirement(name: str) -> str:
    reqs = [r for r in requires("cerebrus-pulse-mcp") or [] if re.match(rf"{name}\b", r)]
    assert len(reqs) == 1, reqs
    return reqs[0]


@pytest.mark.parametrize("name", ["x402", "eth-account", "requests"])
def test_payment_dependencies_are_core(name):
    assert "extra" not in _requirement(name)


def test_pay_extra_still_resolves_for_old_install_commands():
    assert "pay" in (metadata("cerebrus-pulse-mcp").get_all("Provides-Extra") or [])


def test_wallet_key_alone_enables_auto_payment(monkeypatch):
    monkeypatch.setattr(server, "_PAYING_SESSION", None)
    monkeypatch.setattr(server, "_PAYMENT_INIT_ERROR", None)
    monkeypatch.setenv("CEREBRUS_WALLET_KEY", DUMMY_KEY)

    session = server._paying_session()

    assert server._PAYMENT_INIT_ERROR is None
    assert session is not None


def test_no_wallet_key_means_no_session(monkeypatch):
    monkeypatch.setattr(server, "_PAYING_SESSION", None)
    monkeypatch.setattr(server, "_PAYMENT_INIT_ERROR", None)
    monkeypatch.delenv("CEREBRUS_WALLET_KEY", raising=False)

    assert server._paying_session() is None
    assert server._PAYMENT_INIT_ERROR == "no_wallet_key"
