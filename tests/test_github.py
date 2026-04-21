from ccbr_actions.github import (
    github_api_get,
    github_api_headers,
    github_api_post,
    github_api_request,
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
