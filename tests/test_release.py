"""scripts/release.py keeps every version source in step, server.json included (F073).

It also refuses a retired auto-pay payTo default (review: server.py:77).
"""

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "PYPROJECT": "pyproject.toml",
    "INIT": "src/cerebrus_pulse_mcp/__init__.py",
    "CHANGELOG": "CHANGELOG.md",
    "SERVER_MANIFEST": "server.json",
    "SERVER": "src/cerebrus_pulse_mcp/server.py",
}
# Stands in for the gateway's next Base payTo.
NEW_PAY_TO = "0x" + "ab" * 20


def _load_release():
    spec = importlib.util.spec_from_file_location("release", ROOT / "scripts" / "release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def release():
    return _load_release()


@pytest.fixture
def sandbox(release, tmp_path, monkeypatch):
    """Point the release helper at copies of the version sources."""
    for attr, rel in SOURCES.items():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)
        monkeypatch.setattr(release, attr, dest)
    return tmp_path


def _set_default_pay_to(sandbox, address: str) -> None:
    path = sandbox / SOURCES["SERVER"]
    text, n = re.subn(
        r'^(DEFAULT_ALLOWED_PAYTO\s*=\s*)"[^"]+"', rf'\g<1>"{address}"',
        path.read_text(encoding="utf-8"), flags=re.MULTILINE,
    )
    assert n == 1
    path.write_text(text, encoding="utf-8")


def test_repo_version_sources_agree(release):
    version = release.get_pyproject_version()
    assert release.get_init_version() == version
    assert release.get_changelog_version() == version
    assert release.get_server_manifest_versions() == (version, version)


def test_bump_updates_server_json(release, sandbox):
    release.bump("9.9.9")

    manifest = json.loads((sandbox / "server.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "9.9.9"
    assert manifest["packages"][0]["version"] == "9.9.9"
    assert release.get_pyproject_version() == "9.9.9"
    assert release.get_init_version() == "9.9.9"


def test_bump_keeps_the_rest_of_server_json(release, sandbox):
    before = json.loads((sandbox / "server.json").read_text(encoding="utf-8"))
    release.bump("9.9.9")
    after = json.loads((sandbox / "server.json").read_text(encoding="utf-8"))

    for doc in (before, after):
        doc["version"] = doc["packages"][0]["version"] = "x"
    assert after == before


def test_check_flags_a_stale_server_json(release, sandbox, monkeypatch, capsys):
    version = release.get_pyproject_version()
    monkeypatch.setattr(release, "get_git_tags", lambda: [f"v{version}"])
    _set_default_pay_to(sandbox, NEW_PAY_TO)
    assert release.check() is True

    manifest = json.loads((sandbox / "server.json").read_text(encoding="utf-8"))
    manifest["packages"][0]["version"] = "0.0.1"
    (sandbox / "server.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert release.check() is False
    assert "server.json" in capsys.readouterr().out


def test_check_refuses_a_retired_default_payto(release, sandbox, monkeypatch, capsys):
    version = release.get_pyproject_version()
    monkeypatch.setattr(release, "get_git_tags", lambda: [f"v{version}"])
    retired = sorted(release.RETIRED_PAYTO)[0]
    _set_default_pay_to(sandbox, "0x" + retired[2:].upper())  # any case

    assert release.check() is False
    assert "DEFAULT_ALLOWED_PAYTO" in capsys.readouterr().out

    _set_default_pay_to(sandbox, NEW_PAY_TO)
    assert release.check() is True


def test_publish_refuses_a_retired_default_payto(release, sandbox, monkeypatch):
    version = release.get_pyproject_version()
    monkeypatch.setattr(release, "get_git_tags", lambda: [f"v{version}"])
    _set_default_pay_to(sandbox, sorted(release.RETIRED_PAYTO)[0])
    monkeypatch.setattr(
        release.subprocess, "run",
        lambda *a, **k: pytest.fail(f"publish ran a command: {a}"),
    )
    with pytest.raises(SystemExit):
        release.publish(use_twine=True)


def test_retired_payto_entries_are_lowercase_addresses(release):
    assert release.RETIRED_PAYTO
    for address in release.RETIRED_PAYTO:
        assert re.fullmatch(r"0x[0-9a-f]{40}", address)


def test_publish_defaults_to_the_tag_push_not_a_token_upload(release, monkeypatch, capsys):
    monkeypatch.setattr(release, "check", lambda: True)
    monkeypatch.setattr(
        release.subprocess, "run",
        lambda *a, **k: pytest.fail(f"publish ran a command: {a}"),
    )

    release.publish()

    out = capsys.readouterr().out
    assert f"git push origin v{release.get_pyproject_version()}" in out
    assert "Trusted Publishing" in out


def test_publish_twine_is_an_explicit_fallback(release, monkeypatch):
    monkeypatch.setattr(release, "check", lambda: True)
    commands = []
    monkeypatch.setattr(release.subprocess, "run", lambda cmd, **k: commands.append(cmd))

    release.publish(use_twine=True)

    assert any("twine" in cmd for cmd in commands)


def test_publish_refuses_inconsistent_versions(release, monkeypatch):
    monkeypatch.setattr(release, "check", lambda: False)
    with pytest.raises(SystemExit):
        release.publish()
