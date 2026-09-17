"""
Tests for ccbr_actions.pr_review module.
"""

import base64

import requests as requests_lib

from ccbr_actions.pr_review import (
    _codeowners_pattern_matches,
    approve_pr,
    determine_reviewer,
    enable_auto_merge,
    get_codeowners_content,
    get_last_human_committer,
    get_pr_files,
    match_codeowners,
    post_pr_comment,
    request_changes,
    request_reviewer,
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
# get_pr_files
# ---------------------------------------------------------------------------


def test_get_pr_files_calls_correct_url():
    files = [{"filename": ".pre-commit-config.yaml"}]
    session = MockSession(
        {"https://api.github.com/repos/CCBR/actions/pulls/42/files": files}
    )
    result = get_pr_files("CCBR/actions", 42, token="tok", session=session)
    assert result == files
    assert session.calls[0][0] == "GET"
    assert (
        session.calls[0][1]
        == "https://api.github.com/repos/CCBR/actions/pulls/42/files"
    )


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
# request_changes
# ---------------------------------------------------------------------------


def test_request_changes_posts_review_with_event_and_body():
    session = MockSession(post_status=200)
    request_changes("CCBR/actions", 42, "please review", token="tok", session=session)
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://api.github.com/repos/CCBR/actions/pulls/42/reviews"
    assert kwargs["json"]["event"] == "REQUEST_CHANGES"
    assert kwargs["json"]["body"] == "please review"


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
    graphql_call = next(c for c in session.calls if c[0] == "POST")
    assert graphql_call[2]["json"]["variables"]["mergeMethod"] == "SQUASH"


# ---------------------------------------------------------------------------
# request_reviewer
# ---------------------------------------------------------------------------


def test_request_reviewer_posts_to_requested_reviewers_endpoint():
    session = MockSession(post_status=201)
    request_reviewer("CCBR/actions", 42, "alice", token="tok", session=session)
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert (
        url == "https://api.github.com/repos/CCBR/actions/pulls/42/requested_reviewers"
    )
    assert kwargs["json"]["reviewers"] == ["alice"]


def test_request_reviewer_posts_team_reviewers_for_team_slug():
    session = MockSession(post_status=201)
    request_reviewer(
        "CCBR/actions", 42, "CCBR/maintainers", token="tok", session=session
    )
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert (
        url == "https://api.github.com/repos/CCBR/actions/pulls/42/requested_reviewers"
    )
    assert kwargs["json"] == {"team_reviewers": ["maintainers"]}


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
# get_codeowners_content
# ---------------------------------------------------------------------------


def test_get_codeowners_content_returns_first_match():
    content = "* @default-owner\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/actions/contents/docs/CODEOWNERS": {
                "content": encoded
            },
        }
    )
    result = get_codeowners_content("CCBR/actions", token="tok", session=session)
    assert result == content


def test_get_codeowners_content_returns_none_when_missing():
    session = MockSession({})
    result = get_codeowners_content("CCBR/actions", token="tok", session=session)
    assert result is None


class _ErrorThenSuccessSession(MockSession):
    """Raises a RequestException for the first CODEOWNERS path, succeeds after."""

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/contents/CODEOWNERS"):
            raise requests_lib.exceptions.ConnectionError("boom")
        return MockResponse(self.payloads.get(url, {}))


def test_get_codeowners_content_skips_paths_that_error():
    content = "* @default-owner\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    session = _ErrorThenSuccessSession(
        {
            "https://api.github.com/repos/CCBR/actions/contents/.github/CODEOWNERS": {
                "content": encoded
            },
        }
    )
    result = get_codeowners_content("CCBR/actions", token="tok", session=session)
    assert result == content


# ---------------------------------------------------------------------------
# _codeowners_pattern_matches
# ---------------------------------------------------------------------------


def test_codeowners_pattern_matches_returns_false_for_bare_slash():
    assert _codeowners_pattern_matches("/", ".pre-commit-config.yaml") is False


def test_codeowners_pattern_matches_prefix_match_for_directory_pattern():
    assert _codeowners_pattern_matches("docs/", "docs/CODEOWNERS") is True
    assert _codeowners_pattern_matches("docs/", "README.md") is False


# ---------------------------------------------------------------------------
# match_codeowners
# ---------------------------------------------------------------------------


def test_match_codeowners_last_match_wins():
    content = "* @first-owner\n.pre-commit-config.yaml @second-owner\n"
    assert match_codeowners(content, ".pre-commit-config.yaml") == ["second-owner"]


def test_match_codeowners_filters_email_owners():
    content = ".pre-commit-config.yaml @a-user someone@example.com\n"
    assert match_codeowners(content, ".pre-commit-config.yaml") == ["a-user"]


def test_match_codeowners_returns_empty_for_no_match():
    content = "docs/* @docs-owner\n"
    assert match_codeowners(content, ".pre-commit-config.yaml") == []


def test_match_codeowners_skips_blank_and_comment_lines():
    content = "\n# a comment\n.pre-commit-config.yaml @an-owner\n"
    assert match_codeowners(content, ".pre-commit-config.yaml") == ["an-owner"]


def test_match_codeowners_skips_lines_without_owners():
    content = ".pre-commit-config.yaml\n.pre-commit-config.yaml @an-owner\n"
    assert match_codeowners(content, ".pre-commit-config.yaml") == ["an-owner"]


# ---------------------------------------------------------------------------
# get_last_human_committer
# ---------------------------------------------------------------------------


def test_get_last_human_committer_skips_bots_and_copilot():
    commits = [
        {"author": {"login": "copilot-swe-agent[bot]"}},
        {"author": {"login": "pre-commit-ci[bot]"}},
        {"author": {"login": "dependabot[bot]"}},
        {"author": {"login": "a-human"}},
    ]
    session = MockSession(
        {"https://api.github.com/repos/CCBR/actions/commits": commits}
    )
    result = get_last_human_committer(
        "CCBR/actions", ".pre-commit-config.yaml", token="tok", session=session
    )
    assert result == "a-human"


def test_get_last_human_committer_returns_none_when_all_bots():
    commits = [{"author": {"login": "dependabot[bot]"}}]
    session = MockSession(
        {"https://api.github.com/repos/CCBR/actions/commits": commits}
    )
    result = get_last_human_committer(
        "CCBR/actions", ".pre-commit-config.yaml", token="tok", session=session
    )
    assert result is None


class _RaisingSession(MockSession):
    """Always raises a RequestException on GET."""

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        raise requests_lib.exceptions.ConnectionError("boom")


def test_get_last_human_committer_returns_none_on_request_error():
    session = _RaisingSession({})
    result = get_last_human_committer(
        "CCBR/actions", ".pre-commit-config.yaml", token="tok", session=session
    )
    assert result is None


# ---------------------------------------------------------------------------
# determine_reviewer
# ---------------------------------------------------------------------------


def test_determine_reviewer_prefers_explicit_reviewer():
    session = MockSession({})
    result = determine_reviewer(
        "CCBR/actions",
        reviewer="explicit-user",
        path=".pre-commit-config.yaml",
        token="tok",
        session=session,
    )
    assert result == "explicit-user"
    assert session.calls == []


def test_determine_reviewer_falls_back_to_codeowners():
    content = ".pre-commit-config.yaml @codeowner\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/actions/contents/CODEOWNERS": {
                "content": encoded
            },
        }
    )
    result = determine_reviewer(
        "CCBR/actions", path=".pre-commit-config.yaml", token="tok", session=session
    )
    assert result == "codeowner"


def test_determine_reviewer_falls_back_to_last_committer():
    commits = [{"author": {"login": "a-human"}}]
    session = MockSession(
        {"https://api.github.com/repos/CCBR/actions/commits": commits}
    )
    result = determine_reviewer(
        "CCBR/actions", path=".pre-commit-config.yaml", token="tok", session=session
    )
    assert result == "a-human"


def test_determine_reviewer_falls_back_to_committer_when_codeowners_no_match():
    content = "docs/* @docs-owner\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    commits = [{"author": {"login": "a-human"}}]
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/actions/contents/CODEOWNERS": {
                "content": encoded
            },
            "https://api.github.com/repos/CCBR/actions/commits": commits,
        }
    )
    result = determine_reviewer(
        "CCBR/actions", path=".pre-commit-config.yaml", token="tok", session=session
    )
    assert result == "a-human"


def test_determine_reviewer_returns_none_without_reviewer_or_path():
    session = MockSession({})
    result = determine_reviewer("CCBR/actions", token="tok", session=session)
    assert result is None
    assert session.calls == []
