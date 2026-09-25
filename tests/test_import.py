"""The server must import and register its handlers on the mcp 1.x SDK.

mcp 2.0 removed the lowlevel ``Server.list_tools()`` / ``Server.call_tool()``
decorators that ``server.py`` applies at import time, so an unbounded
``mcp>=1.0.0`` let fresh installs resolve 2.x and crash on import (F004).
"""

import asyncio
import re
from importlib.metadata import requires, version

import mcp.types


def _mcp_requirement() -> str:
    reqs = [r for r in requires("cerebrus-pulse-mcp") or [] if re.match(r"mcp\b", r)]
    assert len(reqs) == 1, reqs
    return reqs[0]


def test_mcp_dependency_has_upper_bound_below_2():
    req = _mcp_requirement().replace(" ", "")
    assert "<2" in req, f"mcp must be pinned below 2.x, got {req!r}"


def test_installed_mcp_is_1x():
    assert version("mcp").split(".")[0] == "1"


def test_server_module_imports_and_registers_handlers():
    from cerebrus_pulse_mcp import server

    handlers = server.server.request_handlers
    assert mcp.types.ListToolsRequest in handlers
    assert mcp.types.CallToolRequest in handlers


def test_list_tools_returns_all_tools():
    from cerebrus_pulse_mcp import server

    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert len(tools) == 15
    assert {"cerebrus_health", "cerebrus_list_coins", "cerebrus_pulse"} <= names
