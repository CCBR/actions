import pytest
from ccbr_actions.github import (
    github_api_get,
    github_api_headers,
    github_api_post,
    github_api_request,
    list_rulesets,
    copy_ruleset,
)


class MockResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class MockRequestSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, headers, kwargs))
        return MockResponse({"ok": True})


class MockMethodSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url, headers, kwargs))
        return MockResponse({"files": []})

    def post(self, url, headers=None, **kwargs):
        self.calls.append(("POST", url, headers, kwargs))
        return MockResponse({"created": True}, status_code=201)


def test_github_api_headers_includes_auth_when_token_set():
    headers = github_api_headers(token="abc")

    assert headers["Authorization"] == "Bearer abc"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_github_api_request_supports_request_interface():
    session = MockRequestSession()

    response = github_api_request(
        method="GET",
        url="https://api.github.com/repos/CCBR/actions",
        token="abc",
        session=session,
    )

    assert response.status_code == 200
    assert session.calls[0][0] == "GET"


def test_github_api_get_supports_method_only_interface():
    session = MockMethodSession()

    payload = github_api_get(
        url="https://api.github.com/repos/CCBR/actions/compare/a...b",
        session=session,
    )

    assert payload == {"files": []}
    assert session.calls[0][0] == "GET"


def test_github_api_post_supports_method_only_interface():
    session = MockMethodSession()

    response = github_api_post(
        url="https://api.github.com/repos/CCBR/actions/actions/workflows/test.yml/dispatches",
        session=session,
        json={"ref": "main"},
    )

    assert response.status_code == 201
    assert session.calls[0][0] == "POST"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RULESET_SUMMARY = [
    {"id": 1, "name": "Require PR reviews", "enforcement": "active"},
    {"id": 2, "name": "Restrict force push", "enforcement": "evaluate"},
]

RULESET_DETAIL = {
    "id": 1,
    "node_id": "abc123",
    "name": "Require PR reviews",
    "enforcement": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-02T00:00:00Z",
    "_links": {
        "self": {"href": "https://api.github.com/repos/CCBR/actions/rulesets/1"}
    },
    "rules": [{"type": "pull_request"}],
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
}

CREATED_RULESET = {
    "id": 99,
    "name": "Require PR reviews",
    "enforcement": "active",
    "rules": [{"type": "pull_request"}],
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
}


class RulesetMockSession:
    """Mock session that serves realistic ruleset API responses."""

    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url))
        if url.endswith("/rulesets"):
            return MockResponse(RULESET_SUMMARY)
        if "/rulesets/1" in url:  # abs-path:ignore
            return MockResponse(RULESET_DETAIL)
        return MockResponse([], status_code=404)

    def post(self, url, headers=None, **kwargs):
        self.calls.append(("POST", url, kwargs.get("json")))
        return MockResponse(CREATED_RULESET, status_code=201)


# ---------------------------------------------------------------------------
# list_rulesets
# ---------------------------------------------------------------------------


def test_list_rulesets_returns_list():
    session = RulesetMockSession()

    result = list_rulesets(repo="CCBR/actions", session=session)

    assert result == RULESET_SUMMARY


def test_list_rulesets_calls_correct_url():
    session = RulesetMockSession()

    list_rulesets(repo="CCBR/actions", session=session)

    method, url = session.calls[0]
    assert method == "GET"
    assert url == "https://api.github.com/repos/CCBR/actions/rulesets"


def test_list_rulesets_returns_empty_list_when_none():
    class EmptySession:
        def get(self, url, headers=None, **kwargs):
            return MockResponse([])

    result = list_rulesets(repo="CCBR/empty-repo", session=EmptySession())

    assert result == []


# ---------------------------------------------------------------------------
# copy_ruleset
# ---------------------------------------------------------------------------


def test_copy_ruleset_returns_created_ruleset():
    session = RulesetMockSession()

    result = copy_ruleset(
        source_repo="CCBR/actions",
        target_repo="CCBR/other-repo",
        ruleset_name="Require PR reviews",
        session=session,
    )

    assert result == CREATED_RULESET


def test_copy_ruleset_strips_read_only_fields():
    session = RulesetMockSession()

    copy_ruleset(
        source_repo="CCBR/actions",
        target_repo="CCBR/other-repo",
        ruleset_name="Require PR reviews",
        session=session,
    )

    # Third call is POST; inspect the payload sent
    _, _url, payload = session.calls[2]
    for field in ("id", "node_id", "created_at", "updated_at", "_links"):
        assert field not in payload, f"Read-only field '{field}' should be stripped"


def test_copy_ruleset_preserves_rules_and_conditions():
    session = RulesetMockSession()

    copy_ruleset(
        source_repo="CCBR/actions",
        target_repo="CCBR/other-repo",
        ruleset_name="Require PR reviews",
        session=session,
    )

    _, _url, payload = session.calls[2]
    assert payload["rules"] == RULESET_DETAIL["rules"]
    assert payload["conditions"] == RULESET_DETAIL["conditions"]


def test_copy_ruleset_calls_correct_urls():
    session = RulesetMockSession()

    copy_ruleset(
        source_repo="CCBR/actions",
        target_repo="CCBR/other-repo",
        ruleset_name="Require PR reviews",
        session=session,
    )

    assert session.calls[0] == (
        "GET",
        "https://api.github.com/repos/CCBR/actions/rulesets",
    )
    assert session.calls[1] == (
        "GET",
        "https://api.github.com/repos/CCBR/actions/rulesets/1",
    )
    assert session.calls[2][0] == "POST"
    assert (
        session.calls[2][1] == "https://api.github.com/repos/CCBR/other-repo/rulesets"
    )


def test_copy_ruleset_raises_when_ruleset_not_found():
    session = RulesetMockSession()

    with pytest.raises(ValueError, match="'Nonexistent'"):
        copy_ruleset(
            source_repo="CCBR/actions",
            target_repo="CCBR/other-repo",
            ruleset_name="Nonexistent",
            session=session,
        )


def test_copy_ruleset_error_includes_available_names():
    session = RulesetMockSession()

    with pytest.raises(ValueError, match="Require PR reviews"):
        copy_ruleset(
            source_repo="CCBR/actions",
            target_repo="CCBR/other-repo",
            ruleset_name="Nonexistent",
            session=session,
        )
