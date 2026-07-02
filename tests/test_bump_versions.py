"""
Tests for ccbr_actions.bump_versions
"""

import os
import pathlib

import requests
import textwrap

import pytest

from ccbr_actions.bump_versions import (
    LOCK_COMMENT,
    bump_workflow_file,
    bump_workflows,
    classify_ref,
    determine_new_ref,
    get_latest_release_tag_api,
    main,
    parse_action_ref,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class MockOKSession:
    """Minimal requests-alike that returns a fixed tag_name."""

    def __init__(self, tag_name="v9.0.0"):
        self.tag_name = tag_name
        self.calls = []

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url))
        return _MockResponse({"tag_name": self.tag_name})


class _MockResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class MockErrorSession:
    """Always raises an exception, simulating a network error."""

    def request(self, method, url, headers=None, **kwargs):
        raise requests.exceptions.RequestException("network error")


# ---------------------------------------------------------------------------
# parse_action_ref
# ---------------------------------------------------------------------------


def test_parse_action_ref_simple():
    repo, ref = parse_action_ref("actions/checkout@v4")
    assert repo == "actions/checkout"
    assert ref == "v4"


def test_parse_action_ref_nested():
    repo, ref = parse_action_ref("CCBR/actions/draft-release@v0.7")
    assert repo == "CCBR/actions"
    assert ref == "v0.7"


def test_parse_action_ref_full_semver():
    repo, ref = parse_action_ref("citation-file-format/cffconvert-github-action@2.0.0")
    assert repo == "citation-file-format/cffconvert-github-action"
    assert ref == "2.0.0"


def test_parse_action_ref_no_at_raises():
    with pytest.raises(ValueError):
        parse_action_ref("actions/checkout")


# ---------------------------------------------------------------------------
# classify_ref
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ref,expected",
    [
        ("v4", "major"),
        ("v0", "major"),
        ("4", "major"),
        ("v0.7", "major_minor"),
        ("v4.1", "major_minor"),
        ("v4.1.0", "semver"),
        ("4.1.0", "semver"),
        ("v4.2.0-rc1", "semver"),
        ("latest", "named"),
        ("stable", "named"),
        ("main", "named"),
        ("abc1234", "sha"),
        ("abc1234abc1234abc1234abc1234abc1234abcd1", "sha"),
    ],
)
def test_classify_ref(ref, expected):
    assert classify_ref(ref) == expected


# ---------------------------------------------------------------------------
# determine_new_ref
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current_ref,latest_tag,expected",
    [
        # major sliding tag bumped
        ("v7", "v8.0.0", "v8"),
        # major sliding tag unchanged (latest is within same major)
        ("v7", "v7.3.0", "v7"),
        # major sliding tag – no leading v on latest, keep current prefix
        ("v7", "8.0.0", "v8"),
        # major.minor sliding tag bumped
        ("v0.7", "v0.8.1", "v0.8"),
        # major.minor sliding tag unchanged
        ("v0.7", "v0.7.5", "v0.7"),
        # major.minor major bumped → new major.minor from latest tag
        ("v0.7", "v1.0.0", "v1.0"),
        # full semver bumped
        ("v4.1.0", "v4.2.0", "v4.2.0"),
        # full semver unchanged
        ("v4.1.0", "v4.1.0", "v4.1.0"),
        # full semver patch bump
        ("v4.1.0", "v4.1.3", "v4.1.3"),
        # named ref unchanged
        ("latest", "v4.2.0", "latest"),
        ("stable", "v5.0.0", "stable"),
        # SHA unchanged
        ("abc1234", "v5.0.0", "abc1234"),
        # no latest tag → unchanged
        ("v4", None, "v4"),
        # non-semver latest tag → unchanged
        ("v4", "edge", "v4"),
    ],
)
def test_determine_new_ref(current_ref, latest_tag, expected):
    assert determine_new_ref(current_ref, latest_tag) == expected


def test_determine_new_ref_major_bumps_to_latest_major():
    # v7 → v8 when latest is v8.0.0 and both have 'v' prefix
    result = determine_new_ref("v7", "v8.0.0")
    assert result == "v8"


# ---------------------------------------------------------------------------
# get_latest_release_tag_api
# ---------------------------------------------------------------------------


def test_get_latest_release_tag_api_success():
    session = MockOKSession(tag_name="v5.0.0")
    result = get_latest_release_tag_api(repo="some/repo", session=session)
    assert result == "v5.0.0"


def test_get_latest_release_tag_api_network_error():
    session = MockErrorSession()
    result = get_latest_release_tag_api(repo="some/repo", session=session)
    assert result is None


# ---------------------------------------------------------------------------
# bump_workflow_file
# ---------------------------------------------------------------------------


def _write_workflow(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    wf = tmp_path / "workflow.yml"
    wf.write_text(textwrap.dedent(content))
    return wf


def test_bump_workflow_file_major_tag(tmp_path):
    content = """\
        steps:
          - uses: actions/checkout@v4
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflow_file(wf, session=session)
    assert len(changes) == 1
    assert "v5" in changes[0]
    assert "v4" in changes[0]
    assert "v5" in wf.read_text()


def test_bump_workflow_file_no_change_when_up_to_date(tmp_path):
    content = """\
        steps:
          - uses: actions/checkout@v5
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflow_file(wf, session=session)
    assert changes == []


def test_bump_workflow_file_lock_comment_skipped(tmp_path):
    content = f"""\
        steps:
          - uses: actions/checkout@v4  # {LOCK_COMMENT}
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflow_file(wf, session=session)
    assert changes == []
    assert "v4" in wf.read_text()


def test_bump_workflow_file_named_ref_unchanged(tmp_path):
    content = """\
        steps:
          - uses: psf/black@stable
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v24.0.0")
    changes = bump_workflow_file(wf, session=session)
    assert changes == []


def test_bump_workflow_file_debug_does_not_write(tmp_path, capsys):
    content = """\
        steps:
          - uses: actions/checkout@v4
    """
    wf = _write_workflow(tmp_path, content)
    original = wf.read_text()
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflow_file(wf, session=session, debug=True)
    assert changes  # changes reported
    assert wf.read_text() == original  # file unchanged
    captured = capsys.readouterr()
    assert "Would update" in captured.out


def test_bump_workflow_file_full_semver(tmp_path):
    content = """\
        steps:
          - uses: citation-file-format/cffconvert-github-action@2.0.0
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="2.0.1")
    changes = bump_workflow_file(wf, session=session)
    assert len(changes) == 1
    assert "2.0.1" in wf.read_text()


def test_bump_workflow_file_major_minor_sliding_tag(tmp_path):
    content = """\
        steps:
          - uses: CCBR/actions/draft-release@v0.7
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v0.8.0")
    changes = bump_workflow_file(wf, session=session)
    assert len(changes) == 1
    assert "v0.8" in wf.read_text()


def test_bump_workflow_file_sha_unchanged(tmp_path):
    sha = "abc1234def5678901234567890abcdef12345678"
    content = f"""\
        steps:
          - uses: actions/checkout@{sha}
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflow_file(wf, session=session)
    assert changes == []


def test_bump_workflow_file_caches_repo_calls(tmp_path):
    content = """\
        steps:
          - uses: actions/checkout@v4
          - uses: actions/checkout@v4
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v5.0.0")
    bump_workflow_file(wf, session=session)
    # Both lines use same repo, should only call once
    repos_queried = [url for _, url in session.calls]
    assert len(repos_queried) == 1


def test_bump_workflow_file_step_uses_without_dash(tmp_path):
    content = """\
        steps:
          - name: Checkout
            uses: actions/checkout@v4
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflow_file(wf, session=session)
    assert len(changes) == 1
    assert "v5" in wf.read_text()


# ---------------------------------------------------------------------------
# bump_workflows
# ---------------------------------------------------------------------------


def test_bump_workflows(tmp_path):
    wf1 = tmp_path / "ci.yml"
    wf2 = tmp_path / "release.yml"
    wf1.write_text("steps:\n  - uses: actions/checkout@v4\n")
    wf2.write_text("steps:\n  - uses: actions/setup-python@v4\n")
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflows(workflows_dir=tmp_path, session=session)
    assert len(changes) == 2
    assert "v5" in wf1.read_text()
    assert "v5" in wf2.read_text()


def test_bump_workflows_empty_dir(tmp_path):
    changes = bump_workflows(workflows_dir=tmp_path)
    assert changes == []


def test_bump_workflows_yaml_extension(tmp_path):
    """bump_workflows also picks up *.yaml files."""
    wf = tmp_path / "ci.yaml"
    wf.write_text("steps:\n  - uses: actions/checkout@v4\n")
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflows(workflows_dir=tmp_path, session=session)
    assert len(changes) == 1
    assert "v5" in wf.read_text()


# ---------------------------------------------------------------------------
# determine_new_ref – latest_tag with major-only or major.minor style
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current_ref,latest_tag,expected",
    [
        # latest tag is major.minor (e.g. "v5.1") — covers elif m_mm branch
        ("v4", "v5.1", "v5"),
        ("v4.0", "v5.1", "v5.1"),
        ("v4.1.0", "v5.1", "v5.1.0"),
        # latest tag is major-only (e.g. "v5") — covers elif m_maj branch
        ("v4", "v5", "v5"),
        ("v4.0", "v5", "v5.0"),
        ("v4.1.0", "v5", "v5.0.0"),
    ],
)
def test_determine_new_ref_non_full_semver_latest_tag(
    current_ref, latest_tag, expected
):
    assert determine_new_ref(current_ref, latest_tag) == expected


# ---------------------------------------------------------------------------
# bump_workflow_file – ValueError path (action without '@' after regex match)
# ---------------------------------------------------------------------------


def test_bump_workflow_file_local_action_no_at(tmp_path):
    """Local actions (uses: ./path/to/action) have no '@' and are skipped."""
    content = """\
        steps:
          - uses: ./local-action
    """
    wf = _write_workflow(tmp_path, content)
    session = MockOKSession(tag_name="v5.0.0")
    changes = bump_workflow_file(wf, session=session)
    assert changes == []
    assert "./local-action" in wf.read_text()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_reads_gh_token_env(tmp_path, monkeypatch):
    """main() picks up GH_TOKEN and delegates to bump_workflows."""
    wf = tmp_path / "ci.yml"
    wf.write_text("steps:\n  - uses: actions/checkout@v4\n")
    monkeypatch.setenv("GH_TOKEN", "fake-token")

    calls = []

    def fake_bump_workflows(workflows_dir, token, debug):
        calls.append({"workflows_dir": workflows_dir, "token": token, "debug": debug})
        return []

    monkeypatch.setattr(
        "ccbr_actions.bump_versions.bump_workflows", fake_bump_workflows
    )
    result = main(workflows_dir=str(tmp_path), debug=True)
    assert result == []
    assert calls[0]["token"] == "fake-token"
    assert calls[0]["debug"] is True


def test_main_falls_back_to_github_token(monkeypatch):
    """main() uses GITHUB_TOKEN when GH_TOKEN is absent."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")

    calls = []

    def fake_bump_workflows(workflows_dir, token, debug):
        calls.append(token)
        return []

    monkeypatch.setattr(
        "ccbr_actions.bump_versions.bump_workflows", fake_bump_workflows
    )
    main()
    assert calls[0] == "github-token"


def test_main_no_token_env(monkeypatch):
    """main() passes None as token when neither GH_TOKEN nor GITHUB_TOKEN is set."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    calls = []

    def fake_bump_workflows(workflows_dir, token, debug):
        calls.append(token)
        return []

    monkeypatch.setattr(
        "ccbr_actions.bump_versions.bump_workflows", fake_bump_workflows
    )
    main()
    assert calls[0] is None


# ---------------------------------------------------------------------------
# Defensive branches (lines not reachable through normal code paths)
# ---------------------------------------------------------------------------


def test_determine_new_ref_unknown_ref_type(monkeypatch):
    """Final fallthrough in determine_new_ref is hit when classify_ref returns
    an unrecognised type (defensive guard, line 228)."""
    import ccbr_actions.bump_versions as bv

    monkeypatch.setattr(bv, "classify_ref", lambda ref: "unknown_type")
    result = bv.determine_new_ref("v4", "v5.0.0")
    assert result == "v4"


def test_bump_workflow_file_parse_action_ref_raises(tmp_path, monkeypatch):
    """ValueError from parse_action_ref is silently skipped (lines 283-284)."""
    import ccbr_actions.bump_versions as bv

    content = """\
        steps:
          - uses: actions/checkout@v4
    """
    wf = _write_workflow(tmp_path, content)
    original = wf.read_text()
    monkeypatch.setattr(bv, "parse_action_ref", lambda s: (_ for _ in ()).throw(ValueError("forced")))
    session = MockOKSession(tag_name="v5.0.0")
    changes = bv.bump_workflow_file(wf, session=session)
    assert changes == []
    assert wf.read_text() == original
