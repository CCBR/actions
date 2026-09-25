"""
Tests for ccbr_actions.pre_commit module.
"""

import pytest

from ccbr_actions.pre_commit import (
    PRE_COMMIT_CI_TITLE,
    PRE_COMMIT_CONFIG_FILE,
    _extract_rev_changes,
    _github_repo_slug,
    _is_version_bumped,
    _resolve_commit_sha,
    _same_commit,
    check_only_pre_commit_config_changed,
    check_only_version_bumps,
    check_only_version_bumps_or_same_commit,
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

# A moving `vX.Y` alias tag replaces a more specific `vX.Y.Z` tag (e.g. CCBR/actions#218:
# v0.7.1 -> v0.7). Looks like a downgrade by version string, but may point at the same commit.
SLIDING_TAG_PATCH = """\
@@ -41,7 +41,7 @@ repos:
 additional_dependencies:
   - prettier@3.4.0
 - repo: https://github.com/CCBR/Tools
-  rev: v0.7.1
+  rev: v0.7
   hooks:
   - id: detect-absolute-paths
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


def test_check_only_version_bumps_returns_false_for_sliding_tag_without_lookup():
    # Without a commit-sha lookup, a moving `vX.Y` tag still looks like a downgrade.
    assert check_only_version_bumps(SLIDING_TAG_PATCH) is False


# ---------------------------------------------------------------------------
# _extract_rev_changes
# ---------------------------------------------------------------------------


def test_extract_rev_changes_associates_repo_url_with_each_rev_pair():
    changes = _extract_rev_changes(VALID_PATCH)
    assert changes == [
        ("https://github.com/pre-commit/pre-commit-hooks", "v4.4.0", "v4.5.0"),
        ("https://github.com/psf/black", "23.1.0", "24.3.0"),
    ]


def test_extract_rev_changes_returns_none_for_non_rev_line_changed():
    assert _extract_rev_changes(INVALID_PATCH_NON_REV_CHANGE) is None


def test_extract_rev_changes_returns_none_for_mismatched_rev_count():
    patch = "@@ -1,2 +1,1 @@\n-  rev: v1.0.0\n-  rev: v2.0.0\n+  rev: v1.1.0\n"
    assert _extract_rev_changes(patch) is None


def test_extract_rev_changes_returns_empty_list_for_empty_patch():
    assert _extract_rev_changes("") == []


def test_extract_rev_changes_does_not_leak_repo_across_hunk_boundary():
    # The second hunk's rev change has no repo: context line of its own, so it
    # must not inherit the repo from the first hunk.
    patch = (
        "@@ -5,7 +5,7 @@ repos:\n"
        " - repo: https://github.com/pre-commit/pre-commit-hooks\n"
        "-  rev: v4.4.0\n"
        "+  rev: v4.5.0\n"
        "@@ -41,7 +41,7 @@ repos:\n"
        "-  rev: v0.7.1\n"
        "+  rev: v0.7\n"
    )
    changes = _extract_rev_changes(patch)
    assert changes == [
        ("https://github.com/pre-commit/pre-commit-hooks", "v4.4.0", "v4.5.0"),
        (None, "v0.7.1", "v0.7"),
    ]


# ---------------------------------------------------------------------------
# _github_repo_slug
# ---------------------------------------------------------------------------


def test_github_repo_slug_extracts_owner_and_repo():
    assert _github_repo_slug("https://github.com/CCBR/Tools") == "CCBR/Tools"


def test_github_repo_slug_strips_trailing_slash():
    assert _github_repo_slug("https://github.com/CCBR/Tools/") == "CCBR/Tools"


def test_github_repo_slug_returns_none_for_non_github_url():
    assert _github_repo_slug("https://gitlab.com/CCBR/Tools") is None


def test_github_repo_slug_returns_none_for_none():
    assert _github_repo_slug(None) is None


# ---------------------------------------------------------------------------
# _resolve_commit_sha
# ---------------------------------------------------------------------------


def test_resolve_commit_sha_returns_sha_from_response():
    session = MockSession(
        {"https://api.github.com/repos/CCBR/Tools/commits/v0.7": {"sha": "abc123"}}
    )
    assert _resolve_commit_sha("CCBR/Tools", "v0.7", session=session) == "abc123"


def test_resolve_commit_sha_returns_none_when_ref_not_found():
    session = MockSession({})
    assert _resolve_commit_sha("CCBR/Tools", "v9.9", session=session) is None


def test_resolve_commit_sha_returns_none_on_request_exception():
    class RaisingSession:
        def request(self, *args, **kwargs):
            raise RuntimeError("boom")

    assert _resolve_commit_sha("CCBR/Tools", "v0.7", session=RaisingSession()) is None


# ---------------------------------------------------------------------------
# _same_commit
# ---------------------------------------------------------------------------


def test_same_commit_returns_true_when_both_revs_share_a_sha():
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7.1": {"sha": "c433"},
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7": {"sha": "c433"},
        }
    )
    assert (
        _same_commit("https://github.com/CCBR/Tools", "v0.7.1", "v0.7", session=session)
        is True
    )


def test_same_commit_returns_false_when_shas_differ():
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7.1": {"sha": "c433"},
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7": {"sha": "deadbeef"},
        }
    )
    assert (
        _same_commit("https://github.com/CCBR/Tools", "v0.7.1", "v0.7", session=session)
        is False
    )


def test_same_commit_returns_false_for_non_github_repo_url():
    session = MockSession({})
    assert (
        _same_commit("https://gitlab.com/CCBR/Tools", "v0.7.1", "v0.7", session=session)
        is False
    )


def test_same_commit_returns_false_when_sha_lookup_fails():
    session = MockSession({})
    assert (
        _same_commit("https://github.com/CCBR/Tools", "v0.7.1", "v0.7", session=session)
        is False
    )


# ---------------------------------------------------------------------------
# check_only_version_bumps_or_same_commit
# ---------------------------------------------------------------------------


def test_check_only_version_bumps_or_same_commit_accepts_sliding_tag_same_commit():
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7.1": {"sha": "c433"},
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7": {"sha": "c433"},
        }
    )
    assert (
        check_only_version_bumps_or_same_commit(SLIDING_TAG_PATCH, session=session)
        is True
    )


def test_check_only_version_bumps_or_same_commit_rejects_real_downgrade():
    session = MockSession(
        {
            "https://api.github.com/repos/pre-commit/pre-commit-hooks/commits/v4.5.0": {
                "sha": "newer-sha"
            },
            "https://api.github.com/repos/pre-commit/pre-commit-hooks/commits/v4.4.0": {
                "sha": "older-sha"
            },
        }
    )
    assert (
        check_only_version_bumps_or_same_commit(DOWNGRADE_PATCH, session=session)
        is False
    )


def test_check_only_version_bumps_or_same_commit_still_accepts_normal_bump():
    assert check_only_version_bumps_or_same_commit(VALID_PATCH) is True


def test_check_only_version_bumps_or_same_commit_returns_false_for_non_rev_change():
    assert (
        check_only_version_bumps_or_same_commit(INVALID_PATCH_NON_REV_CHANGE) is False
    )


def test_check_only_version_bumps_or_same_commit_fails_closed_when_repo_context_missing():
    # A downgrade-looking rev change with no repo: line in its hunk can't be
    # verified via the same-commit fallback and must not be approved, even if
    # a session is provided that would resolve a same-commit match for some
    # other repo's revs.
    patch = "@@ -41,7 +41,7 @@ repos:\n-  rev: v0.7.1\n+  rev: v0.7\n"
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7.1": {"sha": "c433"},
            "https://api.github.com/repos/CCBR/Tools/commits/v0.7": {"sha": "c433"},
        }
    )
    assert check_only_version_bumps_or_same_commit(patch, session=session) is False


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
    existing_reviews=None,
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
        reviews_url: existing_reviews if existing_reviews is not None else [],
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


def test_review_pre_commit_pr_approves_sliding_tag_pointing_at_same_commit():
    # Regression test for CCBR/actions#218: rev changed from v0.7.1 to v0.7,
    # which looks like a downgrade but both tags point at the same commit.
    session = _make_review_session(patch=SLIDING_TAG_PATCH)
    session.payloads["https://api.github.com/repos/CCBR/Tools/commits/v0.7.1"] = {
        "sha": "c433f1c"
    }
    session.payloads["https://api.github.com/repos/CCBR/Tools/commits/v0.7"] = {
        "sha": "c433f1c"
    }
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is True
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)


def test_review_pre_commit_pr_comments_when_sliding_tag_has_different_commit():
    # Same rev change as above, but the two tags point at different commits,
    # so it's a genuine downgrade and should still require human review.
    session = _make_review_session(patch=SLIDING_TAG_PATCH)
    session.payloads["https://api.github.com/repos/CCBR/Tools/commits/v0.7.1"] = {
        "sha": "c433f1c"
    }
    session.payloads["https://api.github.com/repos/CCBR/Tools/commits/v0.7"] = {
        "sha": "deadbeef"
    }
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/7/comments" in c[1]
    ]
    assert comment_calls
    assert "requires human review" in comment_calls[0][2]["json"]["body"]


def test_review_pre_commit_pr_skips_when_current_review_is_approved():
    session = _make_review_session(
        existing_reviews=[{"user": {"login": "ccbr-bot"}, "state": "APPROVED"}]
    )
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is True
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert not posted_urls


def test_review_pre_commit_pr_reviews_again_when_force_review_is_enabled():
    session = _make_review_session(
        existing_reviews=[{"user": {"login": "ccbr-bot"}, "state": "APPROVED"}]
    )
    result = review_pre_commit_pr(
        "CCBR/repo", 7, "alice", force_review=True, token="tok", session=session
    )
    assert result is True
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    assert any(c[2]["json"].get("event") == "APPROVE" for c in review_calls)


def test_review_pre_commit_pr_does_not_skip_superseded_approval():
    session = _make_review_session(
        existing_reviews=[
            {"user": {"login": "ccbr-bot"}, "state": "APPROVED"},
            {"user": {"login": "ccbr-bot"}, "state": "CHANGES_REQUESTED"},
        ]
    )
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is True
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    assert any(c[2]["json"].get("event") == "APPROVE" for c in review_calls)


def test_review_pre_commit_pr_comments_when_extra_file():
    session = _make_review_session(extra_files=[{"filename": "README.md", "patch": ""}])
    result = review_pre_commit_pr("CCBR/repo", 7, "alice", token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    # Should post a comment and request the given reviewer, but NOT approve.
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert not any(body.get("event") == "APPROVE" for body in review_bodies)
    assert not review_bodies
    assert any("issues/7/comments" in u for u in posted_urls)
    assert any("requested_reviewers" in u for u in posted_urls)


def test_review_pre_commit_pr_comments_for_non_rev_change():
    session = _make_review_session(patch=INVALID_PATCH_NON_REV_CHANGE)
    result = review_pre_commit_pr("CCBR/repo", 7, "bob", token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/7/comments" in c[1]
    ]
    assert comment_calls
    comment_body = comment_calls[0][2]["json"]["body"]
    assert "@bob" in comment_body


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


def test_review_pre_commit_pr_warns_when_human_review_comment_fails(monkeypatch):
    """Human-review comment errors should emit a warning but not raise."""
    session = _make_review_session(patch=DOWNGRADE_PATCH)

    def _fail_comment(*args, **kwargs):
        raise RuntimeError("comment is not allowed")

    monkeypatch.setattr("ccbr_actions.pre_commit.post_pr_comment", _fail_comment)

    with pytest.warns(UserWarning, match="Could not post human-review comment"):
        result = review_pre_commit_pr(
            "CCBR/repo", 7, "dave", token="tok", session=session
        )
    assert result is False


def test_review_pre_commit_pr_keeps_approval_when_auto_merge_api_fails():
    session = _make_review_session(
        graphql_payload={
            "errors": [{"message": "Resource not accessible by integration"}]
        }
    )

    result = review_pre_commit_pr("CCBR/repo", 7, "erin", token="tok", session=session)

    assert result is True
    review_request_calls = [
        c for c in session.calls if c[0] == "POST" and "requested_reviewers" in c[1]
    ]
    assert not review_request_calls
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    review_bodies = [c[2]["json"] for c in review_calls]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)
    assert not any(body.get("event") == "REQUEST_CHANGES" for body in review_bodies)
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/7/comments" in c[1]
    ]
    assert comment_calls
    comment_body = comment_calls[0][2]["json"]["body"]
    assert "@erin" in comment_body
    assert "GraphQL errors" in comment_body


def test_review_pre_commit_pr_comments_when_approval_fails(monkeypatch):
    session = _make_review_session()

    def _fail_approval(*args, **kwargs):
        raise RuntimeError("approval is not allowed")

    monkeypatch.setattr("ccbr_actions.pre_commit.approve_pr", _fail_approval)

    result = review_pre_commit_pr("CCBR/repo", 7, "erin", token="tok", session=session)

    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/7/comments" in c[1]
    ]
    assert comment_calls
    comment_body = comment_calls[0][2]["json"]["body"]
    assert "automatic approval could not be completed" in comment_body
    assert any("requested_reviewers" in c[1] for c in session.calls if c[0] == "POST")


def test_review_pre_commit_pr_warns_when_auto_merge_comment_fails(monkeypatch):
    session = _make_review_session(
        graphql_payload={"errors": [{"message": "auto-merge unavailable"}]}
    )

    def _fail_comment(*args, **kwargs):
        raise RuntimeError("comment is not allowed")

    monkeypatch.setattr("ccbr_actions.pre_commit.post_pr_comment", _fail_comment)

    with pytest.warns(UserWarning, match="Could not post auto-merge failure comment"):
        result = review_pre_commit_pr(
            "CCBR/repo", 7, "erin", token="tok", session=session
        )

    assert result is True


def test_review_pre_commit_pr_comments_when_title_or_sender_mismatch():
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
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/7/comments" in c[1]
    ]
    assert comment_calls
    comment_body = comment_calls[0][2]["json"]["body"]
    assert "@frank" in comment_body
    assert "autoupdate bot pattern" in comment_body


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
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/7/comments" in c[1]
    ]
    assert comment_calls
    assert "@a-human" in comment_calls[0][2]["json"]["body"]
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
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/7/comments" in c[1]
    ]
    assert comment_calls
    assert comment_calls[0][2]["json"]["body"].startswith("This pre-commit.ci")
    reviewer_calls = [
        c for c in session.calls if c[0] == "POST" and "requested_reviewers" in c[1]
    ]
    assert not reviewer_calls
