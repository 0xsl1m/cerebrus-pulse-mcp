"""scripts/release.py keeps every version source in step, server.json included (F073)."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "PYPROJECT": "pyproject.toml",
    "INIT": "src/cerebrus_pulse_mcp/__init__.py",
    "CHANGELOG": "CHANGELOG.md",
    "SERVER_MANIFEST": "server.json",
}


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
    assert release.check() is True

    manifest = json.loads((sandbox / "server.json").read_text(encoding="utf-8"))
    manifest["packages"][0]["version"] = "0.0.1"
    (sandbox / "server.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert release.check() is False
    assert "server.json" in capsys.readouterr().out
