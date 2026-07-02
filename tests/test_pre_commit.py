"""
Tests for ccbr_actions.pre_commit module.
"""

import pytest

from ccbr_actions.pre_commit import (
    PRE_COMMIT_CI_TITLE,
    PRE_COMMIT_CONFIG_FILE,
    _is_version_bumped,
    approve_pr,
    check_only_pre_commit_config_changed,
    check_only_version_bumps,
    enable_auto_merge,
    get_pr_files,
    is_pre_commit_autoupdate_pr,
    post_pr_comment,
    request_reviewer,
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
    """Records calls and returns pre-configured payloads keyed by URL."""

    def __init__(self, payloads=None, post_status=200):
        self.payloads = payloads or {}
        self.post_status = post_status
        self.calls = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url))
        return MockResponse(self.payloads.get(url, {}))

    def post(self, url, headers=None, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return MockResponse(self.payloads.get(url, {"data": {}}), self.post_status)

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        return MockResponse(self.payloads.get(url, {}))


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
    patch = (
        "@@ -1,2 +1,1 @@\n"
        "-  rev: v1.0.0\n"
        "-  rev: v2.0.0\n"
        "+  rev: v1.1.0\n"
    )
    assert check_only_version_bumps(patch) is False


def test_check_only_version_bumps_returns_true_for_empty_patch():
    assert check_only_version_bumps("") is True


# ---------------------------------------------------------------------------
# get_pr_files
# ---------------------------------------------------------------------------


def test_get_pr_files_calls_correct_url():
    files = [{"filename": PRE_COMMIT_CONFIG_FILE}]
    session = MockSession(
        {"https://api.github.com/repos/CCBR/actions/pulls/42/files": files}
    )
    result = get_pr_files("CCBR/actions", 42, token="tok", session=session)
    assert result == files
    assert session.calls[0][0] == "GET"
    assert session.calls[0][1] == "https://api.github.com/repos/CCBR/actions/pulls/42/files"


# ---------------------------------------------------------------------------
# approve_pr
# ---------------------------------------------------------------------------


def test_approve_pr_posts_to_reviews_endpoint():
    session = MockSession(post_status=200)
    approve_pr("CCBR/actions", 42, token="tok", session=session)
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://api.github.com/repos/CCBR/actions/pulls/42/reviews"
    assert kwargs["json"]["event"] == "APPROVE"


# ---------------------------------------------------------------------------
# enable_auto_merge
# ---------------------------------------------------------------------------


def test_enable_auto_merge_calls_rest_then_graphql():
    pr_url = "https://api.github.com/repos/CCBR/actions/pulls/42"
    graphql_url = "https://api.github.com/graphql"
    session = MockSession(
        {
            pr_url: {"node_id": "PR_NODE_ID_42"},
            graphql_url: {
                "data": {
                    "enablePullRequestAutoMerge": {
                        "pullRequest": {"autoMergeRequest": {"enabledAt": "2024-01-01"}}
                    }
                }
            },
        }
    )
    enable_auto_merge("CCBR/actions", 42, token="tok", session=session)
    methods = [c[0] for c in session.calls]
    assert "GET" in methods
    assert "POST" in methods


# ---------------------------------------------------------------------------
# request_reviewer
# ---------------------------------------------------------------------------


def test_request_reviewer_posts_to_requested_reviewers_endpoint():
    session = MockSession(post_status=201)
    request_reviewer("CCBR/actions", 42, "alice", token="tok", session=session)
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://api.github.com/repos/CCBR/actions/pulls/42/requested_reviewers"
    assert kwargs["json"]["reviewers"] == ["alice"]


# ---------------------------------------------------------------------------
# post_pr_comment
# ---------------------------------------------------------------------------


def test_post_pr_comment_posts_to_issue_comments_endpoint():
    session = MockSession(post_status=201)
    post_pr_comment("CCBR/actions", 42, "hello world", token="tok", session=session)
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://api.github.com/repos/CCBR/actions/issues/42/comments"
    assert kwargs["json"]["body"] == "hello world"


# ---------------------------------------------------------------------------
# review_pre_commit_pr
# ---------------------------------------------------------------------------


def _make_review_session(*, extra_files=None, patch=None):
    """Build a MockSession suitable for review_pre_commit_pr tests."""
    if patch is None:
        patch = VALID_PATCH
    pr_files = [{"filename": PRE_COMMIT_CONFIG_FILE, "patch": patch}]
    if extra_files:
        pr_files.extend(extra_files)

    pr_url = "https://api.github.com/repos/CCBR/repo/pulls/7/files"
    pr_node_url = "https://api.github.com/repos/CCBR/repo/pulls/7"
    graphql_url = "https://api.github.com/graphql"
    comment_url = "https://api.github.com/repos/CCBR/repo/issues/7/comments"

    return MockSession(
        {
            pr_url: pr_files,
            pr_node_url: {"node_id": "PR_NODE_7"},
            graphql_url: {
                "data": {
                    "enablePullRequestAutoMerge": {
                        "pullRequest": {
                            "autoMergeRequest": {"enabledAt": "2024-01-01"}
                        }
                    }
                }
            },
            comment_url: {"id": 1},
        }
    )


def test_review_pre_commit_pr_approves_when_conditions_met():
    session = _make_review_session()
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is True
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert any("reviews" in u for u in posted_urls)
    assert any("graphql" in u for u in posted_urls)


def test_review_pre_commit_pr_requests_human_review_when_extra_file():
    session = _make_review_session(extra_files=[{"filename": "README.md", "patch": ""}])
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    # Should request reviewer and post comment, but NOT submit approval review
    assert not any("reviews" in u for u in posted_urls)
    assert any("comments" in u for u in posted_urls)


def test_review_pre_commit_pr_requests_human_review_for_non_rev_change():
    session = _make_review_session(patch=INVALID_PATCH_NON_REV_CHANGE)
    result = review_pre_commit_pr("CCBR/repo", 7, "bob", token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert any("comments" in u for u in posted_urls)
    # comment body should mention condition 2
    comment_calls = [c for c in session.calls if c[0] == "POST" and "comments" in c[1]]
    assert comment_calls
    comment_body = comment_calls[0][2]["json"]["body"]
    assert "@bob" in comment_body


def test_review_pre_commit_pr_warns_when_reviewer_request_fails(monkeypatch):
    """reviewer request error should emit a warning but still post a comment."""
    session = _make_review_session(patch=DOWNGRADE_PATCH)

    def _fail_request(*args, **kwargs):
        raise RuntimeError("reviewer not allowed on PR")

    monkeypatch.setattr(
        "ccbr_actions.pre_commit.request_reviewer", _fail_request
    )

    with pytest.warns(UserWarning, match="Could not request reviewer"):
        result = review_pre_commit_pr(
            "CCBR/repo", 7, "dave", token="tok", session=session
        )
    assert result is False
