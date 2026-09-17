"""
Tests for ccbr_actions.pre_commit module.
"""

import pytest

from ccbr_actions.pre_commit import (
    PRE_COMMIT_CI_TITLE,
    PRE_COMMIT_CONFIG_FILE,
    _is_version_bumped,
    check_only_pre_commit_config_changed,
    check_only_version_bumps,
    is_pre_commit_autoupdate_pr,
    review_pre_commit_pr,
)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class MockSession:
    """Records calls and returns pre-configured payloads keyed by URL.

    Only ``request`` is implemented: ``github_api_request`` always prefers a
    session's ``request`` method over ``get``/``post`` when present, so those
    would never be exercised.
    """

    def __init__(self, payloads=None, post_status=200):
        self.payloads = payloads or {}
        self.post_status = post_status
        self.calls = []

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        status = self.post_status if method == "POST" else 200
        default = {"data": {}} if method == "POST" else {}
        return MockResponse(self.payloads.get(url, default), status)


# ---------------------------------------------------------------------------
# Minimal unified-diff fixtures
# ---------------------------------------------------------------------------

VALID_PATCH = """\
@@ -5,7 +5,7 @@ repos:
 - repo: https://github.com/pre-commit/pre-commit-hooks
-  rev: v4.4.0
+  rev: v4.5.0
   hooks:
   - id: trailing-whitespace
 - repo: https://github.com/psf/black
-  rev: 23.1.0
+  rev: 24.3.0
   hooks:
   - id: black
"""

# Contains a non-rev changed line (a hook id was altered)
INVALID_PATCH_NON_REV_CHANGE = """\
@@ -5,7 +5,7 @@ repos:
 - repo: https://github.com/pre-commit/pre-commit-hooks
-  rev: v4.4.0
+  rev: v4.5.0
-  - id: trailing-whitespace
+  - id: trailing-whitespace-fixed
"""

# Only rev line changed but version was *downgraded*
DOWNGRADE_PATCH = """\
@@ -5,7 +5,7 @@ repos:
 - repo: https://github.com/pre-commit/pre-commit-hooks
-  rev: v4.5.0
+  rev: v4.4.0
"""

# Contains a commit-hash rev (non-semver) → different hash is OK
COMMIT_HASH_PATCH = """\
@@ -5,7 +5,7 @@ repos:
 - repo: https://github.com/citation-file-format/cffconvert
-  rev: abc1234deadbeef
+  rev: def5678cafebabe
"""


# ---------------------------------------------------------------------------
# is_pre_commit_autoupdate_pr
# ---------------------------------------------------------------------------


def test_is_pre_commit_autoupdate_pr_returns_true_for_matching_pr():
    assert is_pre_commit_autoupdate_pr(PRE_COMMIT_CI_TITLE, "Bot") is True


def test_is_pre_commit_autoupdate_pr_returns_false_for_wrong_title():
    assert is_pre_commit_autoupdate_pr("chore: bump deps", "Bot") is False


def test_is_pre_commit_autoupdate_pr_returns_false_for_non_bot_sender():
    assert is_pre_commit_autoupdate_pr(PRE_COMMIT_CI_TITLE, "User") is False


def test_is_pre_commit_autoupdate_pr_returns_false_when_both_wrong():
    assert is_pre_commit_autoupdate_pr("wrong title", "User") is False


# ---------------------------------------------------------------------------
# check_only_pre_commit_config_changed
# ---------------------------------------------------------------------------


def test_check_only_pre_commit_config_changed_returns_true_when_only_config_file():
    pr_files = [{"filename": PRE_COMMIT_CONFIG_FILE}]
    assert check_only_pre_commit_config_changed(pr_files) is True


def test_check_only_pre_commit_config_changed_returns_false_when_extra_files():
    pr_files = [{"filename": PRE_COMMIT_CONFIG_FILE}, {"filename": "README.md"}]
    assert check_only_pre_commit_config_changed(pr_files) is False


def test_check_only_pre_commit_config_changed_returns_false_when_no_config_file():
    pr_files = [{"filename": "README.md"}]
    assert check_only_pre_commit_config_changed(pr_files) is False


def test_check_only_pre_commit_config_changed_returns_false_when_empty():
    assert check_only_pre_commit_config_changed([]) is False


# ---------------------------------------------------------------------------
# _is_version_bumped
# ---------------------------------------------------------------------------


def test_is_version_bumped_returns_true_for_semver_increase():
    assert _is_version_bumped("v4.4.0", "v4.5.0") is True


def test_is_version_bumped_returns_false_for_semver_decrease():
    assert _is_version_bumped("v4.5.0", "v4.4.0") is False


def test_is_version_bumped_returns_false_for_same_semver():
    assert _is_version_bumped("v4.5.0", "v4.5.0") is False


def test_is_version_bumped_returns_true_for_different_commit_hashes():
    assert _is_version_bumped("abc123", "def456") is True


def test_is_version_bumped_returns_false_for_same_commit_hash():
    assert _is_version_bumped("abc123", "abc123") is False


def test_is_version_bumped_handles_version_without_v_prefix():
    assert _is_version_bumped("23.1.0", "24.3.0") is True


# ---------------------------------------------------------------------------
# check_only_version_bumps
# ---------------------------------------------------------------------------


def test_check_only_version_bumps_returns_true_for_valid_patch():
    assert check_only_version_bumps(VALID_PATCH) is True


def test_check_only_version_bumps_returns_false_when_non_rev_line_changed():
    assert check_only_version_bumps(INVALID_PATCH_NON_REV_CHANGE) is False


def test_check_only_version_bumps_returns_false_for_version_downgrade():
    assert check_only_version_bumps(DOWNGRADE_PATCH) is False


def test_check_only_version_bumps_accepts_commit_hash_rev_change():
    assert check_only_version_bumps(COMMIT_HASH_PATCH) is True


def test_check_only_version_bumps_returns_false_for_mismatched_rev_count():
    # More removals than additions
    patch = "@@ -1,2 +1,1 @@\n-  rev: v1.0.0\n-  rev: v2.0.0\n+  rev: v1.1.0\n"
    assert check_only_version_bumps(patch) is False


def test_check_only_version_bumps_returns_true_for_empty_patch():
    assert check_only_version_bumps("") is True


# ---------------------------------------------------------------------------
# review_pre_commit_pr
# ---------------------------------------------------------------------------


def _make_review_session(
    *,
    extra_files=None,
    patch=None,
    pr_node_payload=None,
    graphql_payload=None,
    codeowners_payload=None,
    commits_payload=None,
):
    """Build a MockSession suitable for review_pre_commit_pr tests."""
    if patch is None:
        patch = VALID_PATCH
    if pr_node_payload is None:
        pr_node_payload = {
            "node_id": "PR_NODE_7",
            "title": PRE_COMMIT_CI_TITLE,
            "user": {"type": "Bot"},
        }
    if graphql_payload is None:
        graphql_payload = {
            "data": {
                "enablePullRequestAutoMerge": {
                    "pullRequest": {"autoMergeRequest": {"enabledAt": "2024-01-01"}}
                }
            }
        }
    pr_files = [{"filename": PRE_COMMIT_CONFIG_FILE, "patch": patch}]
    if extra_files:
        pr_files.extend(extra_files)

    pr_url = "https://api.github.com/repos/CCBR/repo/pulls/7/files"
    pr_node_url = "https://api.github.com/repos/CCBR/repo/pulls/7"
    graphql_url = "https://api.github.com/graphql"
    reviews_url = "https://api.github.com/repos/CCBR/repo/pulls/7/reviews"
    reviewers_url = "https://api.github.com/repos/CCBR/repo/pulls/7/requested_reviewers"
    commits_url = "https://api.github.com/repos/CCBR/repo/commits"

    payloads = {
        pr_url: pr_files,
        pr_node_url: pr_node_payload,
        graphql_url: graphql_payload,
        reviews_url: {"id": 1},
        reviewers_url: {},
        commits_url: commits_payload if commits_payload is not None else [],
    }
    if codeowners_payload is not None:
        payloads["https://api.github.com/repos/CCBR/repo/contents/CODEOWNERS"] = (
            codeowners_payload
        )

    return MockSession(payloads)


def test_review_pre_commit_pr_approves_when_conditions_met():
    session = _make_review_session()
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is True
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert any("reviews" in u for u in posted_urls)
    assert any("graphql" in u for u in posted_urls)
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)


def test_review_pre_commit_pr_requests_human_review_when_extra_file():
    session = _make_review_session(extra_files=[{"filename": "README.md", "patch": ""}])
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    # Should submit a REQUEST_CHANGES review and request the given reviewer, but NOT approve
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert not any(body.get("event") == "APPROVE" for body in review_bodies)
    assert any(body.get("event") == "REQUEST_CHANGES" for body in review_bodies)
    assert any("requested_reviewers" in u for u in posted_urls)


def test_review_pre_commit_pr_requests_human_review_for_non_rev_change():
    session = _make_review_session(patch=INVALID_PATCH_NON_REV_CHANGE)
    result = review_pre_commit_pr("CCBR/repo", 7, "bob", token="tok", session=session)
    assert result is False
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    assert review_calls
    review_body = review_calls[0][2]["json"]
    assert review_body["event"] == "REQUEST_CHANGES"
    assert "@bob" in review_body["body"]


def test_review_pre_commit_pr_warns_when_reviewer_request_fails(monkeypatch):
    """reviewer request error should emit a warning but still submit the request-changes review."""
    session = _make_review_session(patch=DOWNGRADE_PATCH)

    def _fail_request(*args, **kwargs):
        raise RuntimeError("reviewer not allowed on PR")

    monkeypatch.setattr("ccbr_actions.pre_commit.request_reviewer", _fail_request)

    with pytest.warns(UserWarning, match="Could not request reviewer"):
        result = review_pre_commit_pr(
            "CCBR/repo", 7, "dave", token="tok", session=session
        )
    assert result is False


def test_review_pre_commit_pr_warns_when_request_changes_fails(monkeypatch):
    """request-changes review error should emit a warning but not raise."""
    session = _make_review_session(patch=DOWNGRADE_PATCH)

    def _fail_request_changes(*args, **kwargs):
        raise RuntimeError("not allowed to request changes")

    monkeypatch.setattr(
        "ccbr_actions.pre_commit.request_changes", _fail_request_changes
    )

    with pytest.warns(UserWarning, match="Could not submit request-changes review"):
        result = review_pre_commit_pr(
            "CCBR/repo", 7, "dave", token="tok", session=session
        )
    assert result is False


def test_review_pre_commit_pr_falls_back_when_auto_merge_api_fails():
    session = _make_review_session(
        graphql_payload={
            "errors": [{"message": "Resource not accessible by integration"}]
        }
    )

    result = review_pre_commit_pr("CCBR/repo", 7, "erin", token="tok", session=session)

    assert result is False
    review_request_calls = [
        c for c in session.calls if c[0] == "POST" and "requested_reviewers" in c[1]
    ]
    assert review_request_calls
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    request_changes_calls = [
        c for c in review_calls if c[2]["json"].get("event") == "REQUEST_CHANGES"
    ]
    assert request_changes_calls
    comment_body = request_changes_calls[0][2]["json"]["body"]
    assert "@erin" in comment_body
    assert "GraphQL errors" in comment_body


def test_review_pre_commit_pr_requests_human_review_when_title_or_sender_mismatch():
    session = _make_review_session(
        pr_node_payload={
            "node_id": "PR_NODE_7",
            "title": "chore: bump deps",
            "user": {"type": "User"},
        }
    )
    result = review_pre_commit_pr("CCBR/repo", 7, "frank", token="tok", session=session)
    assert result is False
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    review_bodies = [c[2]["json"] for c in review_calls]
    assert not any(body.get("event") == "APPROVE" for body in review_bodies)
    request_changes_calls = [
        body for body in review_bodies if body.get("event") == "REQUEST_CHANGES"
    ]
    assert request_changes_calls
    assert "@frank" in request_changes_calls[0]["body"]
    assert "autoupdate bot pattern" in request_changes_calls[0]["body"]


def test_review_pre_commit_pr_works_without_reviewer_input():
    """When no reviewer is given, fall back to the last human committer of the config file."""
    session = _make_review_session(
        patch=INVALID_PATCH_NON_REV_CHANGE,
        commits_payload=[
            {"author": {"login": "copilot-swe-agent[bot]"}},
            {"author": {"login": "a-human"}},
        ],
    )
    result = review_pre_commit_pr("CCBR/repo", 7, token="tok", session=session)
    assert result is False
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    request_changes_calls = [
        c[2]["json"]
        for c in review_calls
        if c[2]["json"].get("event") == "REQUEST_CHANGES"
    ]
    assert request_changes_calls
    assert "@a-human" in request_changes_calls[0]["body"]
    reviewer_calls = [
        c for c in session.calls if c[0] == "POST" and "requested_reviewers" in c[1]
    ]
    assert reviewer_calls
    assert reviewer_calls[0][2]["json"]["reviewers"] == ["a-human"]


def test_review_pre_commit_pr_skips_reviewer_request_when_none_resolved():
    """No explicit reviewer, no CODEOWNERS match, and no human committer found."""
    session = _make_review_session(
        patch=INVALID_PATCH_NON_REV_CHANGE,
        commits_payload=[{"author": {"login": "dependabot[bot]"}}],
    )
    result = review_pre_commit_pr("CCBR/repo", 7, token="tok", session=session)
    assert result is False
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    request_changes_calls = [
        c[2]["json"]
        for c in review_calls
        if c[2]["json"].get("event") == "REQUEST_CHANGES"
    ]
    assert request_changes_calls
    assert request_changes_calls[0]["body"].startswith("This pre-commit.ci")
    reviewer_calls = [
        c for c in session.calls if c[0] == "POST" and "requested_reviewers" in c[1]
    ]
    assert not reviewer_calls
