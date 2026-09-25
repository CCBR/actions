"""
Tests for ccbr_actions.post_release_pr module.
"""

import pytest
import requests as requests_lib

from ccbr_actions.post_release_pr import (
    POST_RELEASE_PR_TITLE_PATTERN,
    _allowed_basenames,
    _is_valid_bump_line,
    _is_valid_insertion,
    _release_bump_values,
    _split_tokens,
    check_only_allowed_files_changed,
    check_patch_is_version_bump,
    check_version_date_bumps,
    determine_post_release_reviewer,
    extract_release_tag,
    get_release_by_tag,
    is_allowed_filename,
    is_post_release_pr,
    review_post_release_pr,
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
            raise requests_lib.exceptions.HTTPError(f"HTTP {self.status_code}")


class MockSession:
    """Records calls and returns pre-configured payloads keyed by URL."""

    def __init__(self, payloads=None, post_status=200):
        self.payloads = payloads or {}
        self.post_status = post_status
        self.calls = []

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        status = self.post_status if method == "POST" else 200
        default = {"data": {}} if method == "POST" else {}
        return MockResponse(self.payloads.get(url, default), status)


class _RaisingSession(MockSession):
    """Always raises a RequestException on GET."""

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        raise requests_lib.exceptions.ConnectionError("boom")


# ---------------------------------------------------------------------------
# Fixture patches, based on CCBR/Tools#229
# ---------------------------------------------------------------------------

RELEASE_TAG = "v0.7.1"
PR_TITLE = f"chore: post-release cleanup for {RELEASE_TAG}"
RELEASE = {
    "tag_name": RELEASE_TAG,
    "published_at": "2026-09-17T00:00:00Z",
    "created_at": "2026-09-17T00:00:00Z",
}

CHANGELOG_PATCH = """\
@@ -1,5 +1,7 @@
 ## Tools development version

+## Tools 0.7.1
+
 - minor documentation improvements. (#197, #198, @kelly-sovacool)
"""

README_PATCH = """\
@@ -181,7 +181,7 @@ guidelines](https://CCBR.github.io/Tools/CONTRIBUTING).
 Please cite this software if you use it in a publication:

 > Sovacool K., Koparde V., Kuhn S., Tandon M., and Huse S. (2026). CCBR
-> Tools: Utilities for CCBR Bioinformatics Software (version v0.7.0).
+> Tools: Utilities for CCBR Bioinformatics Software (version v0.7.1).
 > DOI: 10.5281/zenodo.13377166 URL: https://ccbr.github.io/Tools/

 ### Bibtex entry
@@ -190,7 +190,7 @@ Please cite this software if you use it in a publication:
 @misc{YourReferenceHere,
   author = {Sovacool, Kelly and Koparde, Vishal and Kuhn, Skyler and Tandon, Mayank and Huse, Susan},
   doi = {10.5281/zenodo.13377166},
-  month = {6},
+  month = {9},
   title = {CCBR Tools: Utilities for CCBR Bioinformatics Software},
   url = {https://ccbr.github.io/Tools/},
   year = {2026}
"""

CITATION_PATCH = """\
@@ -29,5 +29,5 @@ identifiers:
   type: doi
   value: 10.5281/zenodo.13377166
 doi: 10.5281/zenodo.13377166
-version: v0.7.0
-date-released: "2026-06-10"
+version: v0.7.1
+date-released: "2026-09-17"
"""

VERSION_PATCH = """\
@@ -1 +1 @@
-0.7.0-dev
+0.7.1-dev
"""

# A non-version change slipped into the changelog (invalid)
INVALID_CHANGELOG_PATCH = """\
@@ -1,5 +1,5 @@
 ## Tools development version

-- minor documentation improvements. (#197, #198, @kelly-sovacool)
+- MAJOR documentation improvements. (#197, #198, @kelly-sovacool)
"""


def _pr_files():
    return [
        {"filename": "CHANGELOG.md", "patch": CHANGELOG_PATCH},
        {"filename": "README.md", "patch": README_PATCH},
        {"filename": "src/ccbr_tools/CITATION.cff", "patch": CITATION_PATCH},
        {"filename": "src/ccbr_tools/VERSION", "patch": VERSION_PATCH},
    ]


# ---------------------------------------------------------------------------
# is_post_release_pr / extract_release_tag
# ---------------------------------------------------------------------------


def test_post_release_pr_title_pattern_matches_expected_title():
    assert POST_RELEASE_PR_TITLE_PATTERN.match(PR_TITLE)


def test_is_post_release_pr_returns_true_for_matching_pr():
    assert is_post_release_pr(PR_TITLE, "Bot") is True


def test_is_post_release_pr_returns_false_for_wrong_title():
    assert is_post_release_pr("chore: bump deps", "Bot") is False


def test_is_post_release_pr_returns_false_for_non_bot_sender():
    assert is_post_release_pr(PR_TITLE, "User") is False


def test_extract_release_tag_returns_tag():
    assert extract_release_tag(PR_TITLE) == RELEASE_TAG


def test_extract_release_tag_returns_none_for_wrong_title():
    assert extract_release_tag("chore: bump deps") is None


# ---------------------------------------------------------------------------
# get_release_by_tag
# ---------------------------------------------------------------------------


def test_get_release_by_tag_returns_release_when_found():
    session = MockSession(
        {"https://api.github.com/repos/CCBR/Tools/releases/tags/v0.7.1": RELEASE}
    )
    assert get_release_by_tag("CCBR/Tools", "v0.7.1", session=session) == RELEASE


def test_get_release_by_tag_returns_none_when_missing():
    class NotFoundSession(MockSession):
        def request(self, method, url, headers=None, **kwargs):
            self.calls.append((method, url, kwargs))
            raise requests_lib.exceptions.HTTPError("404")

    assert get_release_by_tag("CCBR/Tools", "v9.9.9", session=NotFoundSession()) is None


# ---------------------------------------------------------------------------
# _allowed_basenames / is_allowed_filename / check_only_allowed_files_changed
# ---------------------------------------------------------------------------


def test_allowed_basenames_includes_defaults():
    basenames = _allowed_basenames(
        "VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION"
    )
    assert basenames == {
        "VERSION",
        "CITATION.cff",
        "CHANGELOG.md",
        "DESCRIPTION",
        "codemeta.json",
        "NEWS.md",
        "NEWS",
    }


def test_is_allowed_filename_matches_basename_regardless_of_path():
    basenames = _allowed_basenames(
        "VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION"
    )
    assert is_allowed_filename("src/ccbr_tools/VERSION", basenames) is True


def test_is_allowed_filename_matches_readme_case_insensitively():
    basenames = _allowed_basenames(
        "VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION"
    )
    assert is_allowed_filename("Readme.qmd", basenames) is True


def test_is_allowed_filename_returns_false_for_disallowed_file():
    basenames = _allowed_basenames(
        "VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION"
    )
    assert is_allowed_filename("src/main.py", basenames) is False


def test_check_only_allowed_files_changed_returns_true_for_pr_files():
    basenames = _allowed_basenames(
        "VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION"
    )
    assert check_only_allowed_files_changed(_pr_files(), basenames) is True


def test_check_only_allowed_files_changed_returns_false_when_extra_file():
    basenames = _allowed_basenames(
        "VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION"
    )
    pr_files = _pr_files() + [{"filename": "src/main.py"}]
    assert check_only_allowed_files_changed(pr_files, basenames) is False


def test_check_only_allowed_files_changed_returns_false_when_empty():
    basenames = _allowed_basenames(
        "VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION"
    )
    assert check_only_allowed_files_changed([], basenames) is False


# ---------------------------------------------------------------------------
# _release_bump_values
# ---------------------------------------------------------------------------


def test_release_bump_values_includes_version_and_date_tokens():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert "v0.7.1" in values
    assert "0.7.1" in values
    assert "0.7.1-dev" in values
    assert "2026-09-17" in values
    assert "2026" in values
    assert "9" in values
    assert "17" in values


# ---------------------------------------------------------------------------
# _split_tokens
# ---------------------------------------------------------------------------


def test_split_tokens_separates_text_and_numeric_tokens():
    text, tokens = _split_tokens("version: v0.7.0")
    assert tokens == ["0.7.0"]
    assert text == ["version: v", ""]


# ---------------------------------------------------------------------------
# _is_valid_bump_line
# ---------------------------------------------------------------------------


def test_is_valid_bump_line_accepts_version_bump():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _is_valid_bump_line("version: v0.7.0", "version: v0.7.1", values) is True


def test_is_valid_bump_line_rejects_non_matching_version():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _is_valid_bump_line("version: v0.7.0", "version: v9.9.9", values) is False


def test_is_valid_bump_line_rejects_changed_surrounding_text():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _is_valid_bump_line("version: v0.7.0", "ver: v0.7.1", values) is False


def test_is_valid_bump_line_rejects_mismatched_token_count():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _is_valid_bump_line("v0.7.0", "v0.7.1 v0.7.1", values) is False


# ---------------------------------------------------------------------------
# _is_valid_insertion
# ---------------------------------------------------------------------------


def test_is_valid_insertion_accepts_blank_line():
    assert _is_valid_insertion("", "0.7.1") is True
    assert _is_valid_insertion("   ", "0.7.1") is True


def test_is_valid_insertion_accepts_heading_with_release_version():
    assert _is_valid_insertion("## Tools 0.7.1", "0.7.1") is True


def test_is_valid_insertion_rejects_unrelated_line():
    assert _is_valid_insertion("- a new unrelated bullet point", "0.7.1") is False


# ---------------------------------------------------------------------------
# check_patch_is_version_bump
# ---------------------------------------------------------------------------


def test_check_patch_is_version_bump_accepts_changelog_heading_insertion():
    assert check_patch_is_version_bump(CHANGELOG_PATCH, {"0.7.1"}, "0.7.1") is True


def test_check_patch_is_version_bump_accepts_readme_citation_rerender():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert check_patch_is_version_bump(README_PATCH, values, "0.7.1") is True


def test_check_patch_is_version_bump_accepts_citation_cff_bump():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert check_patch_is_version_bump(CITATION_PATCH, values, "0.7.1") is True


def test_check_patch_is_version_bump_accepts_version_file_bump():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert check_patch_is_version_bump(VERSION_PATCH, values, "0.7.1") is True


def test_check_patch_is_version_bump_rejects_non_version_change():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert (
        check_patch_is_version_bump(INVALID_CHANGELOG_PATCH, values, "0.7.1") is False
    )


def test_check_patch_is_version_bump_rejects_version_not_matching_release():
    # Looks like a version bump, but doesn't match the fetched release's version.
    patch = "@@ -1 +1 @@\n-0.7.0-dev\n+0.9.9-dev\n"
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert check_patch_is_version_bump(patch, values, "0.7.1") is False


def test_check_patch_is_version_bump_returns_true_for_empty_patch():
    assert check_patch_is_version_bump("", {"0.7.1"}, "0.7.1") is True


# ---------------------------------------------------------------------------
# check_version_date_bumps
# ---------------------------------------------------------------------------


def test_check_version_date_bumps_returns_true_for_valid_pr_files():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert check_version_date_bumps(_pr_files(), values, "0.7.1") is True


def test_check_version_date_bumps_returns_false_when_one_file_invalid():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    pr_files = _pr_files()
    pr_files[0] = {"filename": "CHANGELOG.md", "patch": INVALID_CHANGELOG_PATCH}
    assert check_version_date_bumps(pr_files, values, "0.7.1") is False


def test_check_version_date_bumps_returns_false_when_patch_missing():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    pr_files = [{"filename": "CHANGELOG.md"}]
    assert check_version_date_bumps(pr_files, values, "0.7.1") is False


def test_check_version_date_bumps_returns_false_for_empty_files():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert check_version_date_bumps([], values, "0.7.1") is False


# ---------------------------------------------------------------------------
# determine_post_release_reviewer
# ---------------------------------------------------------------------------


def test_determine_post_release_reviewer_prefers_explicit_reviewer():
    session = MockSession({})
    result = determine_post_release_reviewer(
        "CCBR/Tools", reviewer="explicit-user", token="tok", session=session
    )
    assert result == "explicit-user"
    assert session.calls == []


def test_determine_post_release_reviewer_uses_last_draft_release_actor():
    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    session = MockSession(
        {runs_url: {"workflow_runs": [{"triggering_actor": {"login": "actor-user"}}]}}
    )
    result = determine_post_release_reviewer("CCBR/Tools", token="tok", session=session)
    assert result == "actor-user"


def test_determine_post_release_reviewer_falls_back_to_default_codeowner():
    import base64

    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    content = "* @default-owner\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    session = MockSession(
        {
            runs_url: {"workflow_runs": []},
            "https://api.github.com/repos/CCBR/Tools/contents/CODEOWNERS": {
                "content": encoded
            },
        }
    )
    result = determine_post_release_reviewer("CCBR/Tools", token="tok", session=session)
    assert result == "default-owner"


def test_determine_post_release_reviewer_returns_none_when_nothing_resolves():
    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    session = MockSession({runs_url: {"workflow_runs": []}})
    result = determine_post_release_reviewer("CCBR/Tools", token="tok", session=session)
    assert result is None


# ---------------------------------------------------------------------------
# review_post_release_pr
# ---------------------------------------------------------------------------


def _make_review_session(
    *,
    pr_files=None,
    pr_node_payload=None,
    graphql_payload=None,
    release_payload=None,
    existing_reviews=None,
    action_required_runs=None,
):
    """Build a MockSession suitable for review_post_release_pr tests."""
    if pr_files is None:
        pr_files = _pr_files()
    if pr_node_payload is None:
        pr_node_payload = {
            "node_id": "PR_NODE_9",
            "title": PR_TITLE,
            "user": {"type": "Bot"},
            "head": {"ref": "release/v0.7.1"},
        }
    if graphql_payload is None:
        graphql_payload = {
            "data": {
                "enablePullRequestAutoMerge": {
                    "pullRequest": {"autoMergeRequest": {"enabledAt": "2026-09-17"}}
                }
            }
        }
    if release_payload is None:
        release_payload = RELEASE

    pr_files_url = "https://api.github.com/repos/CCBR/Tools/pulls/9/files"
    pr_node_url = "https://api.github.com/repos/CCBR/Tools/pulls/9"
    graphql_url = "https://api.github.com/graphql"
    reviews_url = "https://api.github.com/repos/CCBR/Tools/pulls/9/reviews"
    reviewers_url = (
        "https://api.github.com/repos/CCBR/Tools/pulls/9/requested_reviewers"
    )
    release_url = f"https://api.github.com/repos/CCBR/Tools/releases/tags/{RELEASE_TAG}"
    runs_url = "https://api.github.com/repos/CCBR/Tools/actions/runs"
    draft_runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )

    payloads = {
        pr_files_url: pr_files,
        pr_node_url: pr_node_payload,
        graphql_url: graphql_payload,
        reviews_url: existing_reviews if existing_reviews is not None else [],
        reviewers_url: {},
        release_url: release_payload,
        runs_url: {"workflow_runs": action_required_runs or []},
        draft_runs_url: {"workflow_runs": []},
    }
    return MockSession(payloads)


def test_review_post_release_pr_approves_when_conditions_met():
    session = _make_review_session()
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert any("reviews" in u for u in posted_urls)
    assert any("graphql" in u for u in posted_urls)
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)


def test_review_post_release_pr_approves_pending_workflow_runs():
    session = _make_review_session(action_required_runs=[{"id": 555}])
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    approve_run_urls = [
        c[1]
        for c in session.calls
        if c[0] == "POST" and "actions/runs/555/approve" in c[1]
    ]
    assert approve_run_urls


def test_review_post_release_pr_skips_when_current_review_is_approved():
    session = _make_review_session(
        existing_reviews=[{"user": {"login": "ccbr-bot"}, "state": "APPROVED"}]
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert not posted_urls


def test_review_post_release_pr_reviews_again_when_force_review_is_enabled():
    session = _make_review_session(
        existing_reviews=[{"user": {"login": "ccbr-bot"}, "state": "APPROVED"}]
    )
    result = review_post_release_pr(
        "CCBR/Tools", 9, force_review=True, token="tok", session=session
    )
    assert result is True
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    assert any(c[2]["json"].get("event") == "APPROVE" for c in review_calls)


def test_review_post_release_pr_requests_human_review_when_extra_file_changed():
    pr_files = _pr_files() + [{"filename": "src/main.py", "patch": "@@ -1 +1 @@\n"}]
    session = _make_review_session(pr_files=pr_files)
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert not any(body.get("event") == "APPROVE" for body in review_bodies)
    assert any("issues/9/comments" in u for u in posted_urls)


def test_review_post_release_pr_requests_human_review_when_non_bump_change():
    pr_files = _pr_files()
    pr_files[0] = {"filename": "CHANGELOG.md", "patch": INVALID_CHANGELOG_PATCH}
    session = _make_review_session(pr_files=pr_files)
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "requires human review" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_requests_human_review_when_release_not_found():
    class NoReleaseSession(MockSession):
        def request(self, method, url, headers=None, **kwargs):
            self.calls.append((method, url, kwargs))
            if "releases/tags/" in url:
                raise requests_lib.exceptions.HTTPError("404")
            status = self.post_status if method == "POST" else 200
            default = {"data": {}} if method == "POST" else {}
            return MockResponse(self.payloads.get(url, default), status)

    session = _make_review_session()
    session.__class__ = NoReleaseSession
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "no matching GitHub release tag" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_requests_human_review_when_title_or_sender_mismatch():
    session = _make_review_session(
        pr_node_payload={
            "node_id": "PR_NODE_9",
            "title": "chore: bump deps",
            "user": {"type": "User"},
            "head": {"ref": "some-branch"},
        }
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "post-release cleanup pattern" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_uses_resolved_reviewer_in_comment():
    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    session = _make_review_session(
        pr_node_payload={
            "node_id": "PR_NODE_9",
            "title": "chore: bump deps",
            "user": {"type": "User"},
            "head": {"ref": "some-branch"},
        }
    )
    session.payloads[runs_url] = {
        "workflow_runs": [{"triggering_actor": {"login": "kelly-sovacool"}}]
    }
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert "@kelly-sovacool" in comment_calls[0][2]["json"]["body"]
    reviewer_calls = [
        c for c in session.calls if c[0] == "POST" and "requested_reviewers" in c[1]
    ]
    assert reviewer_calls
    assert reviewer_calls[0][2]["json"]["reviewers"] == ["kelly-sovacool"]


def test_review_post_release_pr_keeps_approval_when_auto_merge_api_fails():
    session = _make_review_session(
        graphql_payload={
            "errors": [{"message": "Resource not accessible by integration"}]
        }
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    review_bodies = [c[2]["json"] for c in review_calls]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "GraphQL errors" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_comments_when_approval_fails(monkeypatch):
    session = _make_review_session()

    def _fail_approval(*args, **kwargs):
        raise RuntimeError("approval is not allowed")

    monkeypatch.setattr("ccbr_actions.post_release_pr.approve_pr", _fail_approval)

    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)

    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    comment_body = comment_calls[0][2]["json"]["body"]
    assert "automatic approval could not be completed" in comment_body


def test_review_post_release_pr_warns_when_reviewer_request_fails(monkeypatch):
    pr_files = _pr_files() + [{"filename": "src/main.py", "patch": "@@ -1 +1 @@\n"}]
    session = _make_review_session(pr_files=pr_files)

    def _fail_request(*args, **kwargs):
        raise RuntimeError("reviewer not allowed on PR")

    monkeypatch.setattr("ccbr_actions.post_release_pr.request_reviewer", _fail_request)
    monkeypatch.setattr(
        "ccbr_actions.post_release_pr.determine_post_release_reviewer",
        lambda *args, **kwargs: "dave",
    )

    with pytest.warns(UserWarning, match="Could not request reviewer"):
        result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
