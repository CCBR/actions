"""
Shared utilities for interacting with the GitHub API.
"""

import requests


GITHUB_API_URL = "https://api.github.com"


def github_api_headers(token=None, accept="application/vnd.github+json"):
    """
    Build standard headers for GitHub API requests.

    Args:
        token (str, optional): GitHub token.
        accept (str): Accept header value.

    Returns:
        dict: HTTP headers.
    """
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_api_request(method, url, token=None, session=requests, **kwargs):
    """
    Execute a GitHub API request.

    Args:
        method (str): HTTP method.
        url (str): Full API URL.
        token (str, optional): GitHub token.
        session: Object with a requests-compatible ``request`` method.
        **kwargs: Additional arguments passed to ``session.request``.

    Returns:
        requests.Response: HTTP response.
    """
    if session is None:
        session = requests

    headers = github_api_headers(token=token)
    provided_headers = kwargs.pop("headers", {}) or {}
    headers.update(provided_headers)

    if hasattr(session, "request"):
        return session.request(method=method, url=url, headers=headers, **kwargs)

    method_name = method.lower()
    request_fn = getattr(session, method_name)
    return request_fn(url, headers=headers, **kwargs)


def github_api_get(url, token=None, session=requests, **kwargs):
    """
    Perform a GET request against the GitHub API and parse JSON.

    Args:
        url (str): Full API URL.
        token (str, optional): GitHub token.
        session: Object with a requests-compatible ``request`` method.
        **kwargs: Additional arguments passed to ``github_api_request``.

    Returns:
        dict: Parsed JSON response.
    """
    response = github_api_request(
        method="GET", url=url, token=token, session=session, **kwargs
    )
    response.raise_for_status()
    return response.json()


def github_api_post(url, token=None, session=requests, **kwargs):
    """
    Perform a POST request against the GitHub API.

    Args:
        url (str): Full API URL.
        token (str, optional): GitHub token.
        session: Object with a requests-compatible ``request`` method.
        **kwargs: Additional arguments passed to ``github_api_request``.

    Returns:
        requests.Response: HTTP response.
    """
    return github_api_request(
        method="POST", url=url, token=token, session=session, **kwargs
    )
