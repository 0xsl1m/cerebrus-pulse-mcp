"""CI and release workflows: SHA-pinned actions, tokenless publishing (F073, G-CICD-4)."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # YAML 1.1 reads the bare key `on` as boolean True.
    return workflow.get("on", workflow.get(True))


def _steps(workflow: dict):
    for job in workflow["jobs"].values():
        yield from job.get("steps", [])


@pytest.mark.parametrize("name", ["ci.yml", "publish.yml"])
def test_every_action_is_pinned_to_a_commit_sha(name):
    for step in _steps(_load(name)):
        if "uses" in step:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


@pytest.mark.parametrize("name", ["ci.yml", "publish.yml"])
def test_workflow_defaults_to_read_only_token(name):
    assert _load(name)["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("name", ["ci.yml", "publish.yml"])
def test_checkout_does_not_persist_credentials(name):
    for step in _steps(_load(name)):
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] is False


def test_ci_runs_tests_on_push_and_pull_request():
    ci = _load("ci.yml")
    triggers = _triggers(ci)
    assert "push" in triggers and "pull_request" in triggers
    test_steps = [s.get("run", "") for s in ci["jobs"]["test"]["steps"]]
    assert any("pytest" in run for run in test_steps)


def test_live_ci_checks_the_default_payto():
    runs = [s.get("run", "") for s in _load("ci.yml")["jobs"]["live"]["steps"]]
    assert "python scripts/check_payto.py --live" in runs


def test_publish_checks_the_default_payto_before_building():
    steps = _load("publish.yml")["jobs"]["build"]["steps"]
    names = [s.get("name") for s in steps]
    check = next(i for i, s in enumerate(steps) if "check_payto.py --live" in s.get("run", ""))
    assert check < names.index("Build")


def test_publish_uses_trusted_publishing_without_secrets():
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "secrets." not in text
    assert "password" not in text

    publish = _load("publish.yml")
    assert _triggers(publish) == {"push": {"tags": ["v*"]}}
    jobs = publish["jobs"]
    # Only the upload job may mint an OIDC token, and it runs in the pypi environment.
    assert jobs["publish"]["permissions"]["id-token"] == "write"
    assert jobs["publish"]["environment"]["name"] == "pypi"
    assert "permissions" not in jobs["build"]
    assert any(
        s.get("uses", "").startswith("pypa/gh-action-pypi-publish@")
        for s in jobs["publish"]["steps"]
    )


def test_publish_verifies_the_tag_before_building():
    build = _load("publish.yml")["jobs"]["build"]
    verify = next(s for s in build["steps"] if s.get("name") == "Verify the release source")
    assert "origin/main" in verify["run"]
    assert "release.py check" in verify["run"]
    assert 'test "v$version" = "$TAG"' in verify["run"]
