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

    response = None
    if hasattr(session, "request"):
        response = session.request(method=method, url=url, headers=headers, **kwargs)
    else:
        method_name = method.lower()
        request_fn = getattr(session, method_name)
        response = request_fn(url, headers=headers, **kwargs)
    return response


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


def list_rulesets(repo, token=None, session=requests):
    """
    List all rulesets for a GitHub repository.

    Args:
        repo (str): Repository in ``owner/repo`` format.
        token (str, optional): GitHub token with ``repo`` scope.
        session: Object with a requests-compatible ``request`` method.

    Returns:
        list[dict]: Rulesets as returned by the GitHub API. Each item
            contains at minimum ``id``, ``name``, and ``enforcement``.

    Raises:
        requests.HTTPError: If the GitHub API request fails.

    Examples:
        >>> list_rulesets("CCBR/actions", token="ghp_...")
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/rulesets"
    return github_api_get(url, token=token, session=session)


def copy_ruleset(
    source_repo,
    target_repo,
    ruleset_name,
    token=None,
    session=requests,
):
    """
    Copy a ruleset from one GitHub repository to another.

    Fetches all rulesets from ``source_repo``, finds the one matching
    ``ruleset_name``, and creates an identical ruleset in ``target_repo``.

    Args:
        source_repo (str): Source repository in ``owner/repo`` format.
        target_repo (str): Target repository in ``owner/repo`` format.
        ruleset_name (str): Name of the ruleset to copy.
        token (str, optional): GitHub token with ``repo`` scope.
        session: Object with a requests-compatible ``request`` method.

    Returns:
        dict: The created ruleset as returned by the GitHub API.

    Raises:
        ValueError: If no ruleset with ``ruleset_name`` is found in
            ``source_repo``.
        requests.HTTPError: If any GitHub API request fails.

    Examples:
        >>> copy_ruleset(
        ...     source_repo="CCBR/actions",
        ...     target_repo="CCBR/other-repo",
        ...     ruleset_name="Require PR reviews",
        ...     token="ghp_...",
        ... )
    """
    # Fetch all rulesets from the source repository
    list_url = f"{GITHUB_API_URL}/repos/{source_repo}/rulesets"
    rulesets = github_api_get(list_url, token=token, session=session)

    # Find the matching ruleset by name
    match = next((r for r in rulesets if r.get("name") == ruleset_name), None)
    if match is None:
        available = [r.get("name") for r in rulesets]
        raise ValueError(
            f"Ruleset {ruleset_name!r} not found in {source_repo!r}. "
            f"Available rulesets: {available}"
        )

    # Fetch the full ruleset definition (the list endpoint omits some fields)
    ruleset_id = match["id"]
    detail_url = f"{GITHUB_API_URL}/repos/{source_repo}/rulesets/{ruleset_id}"
    ruleset = github_api_get(detail_url, token=token, session=session)

    # Build the payload for the target repository, dropping read-only fields
    _read_only_fields = {"id", "node_id", "created_at", "updated_at", "_links"}
    payload = {k: v for k, v in ruleset.items() if k not in _read_only_fields}

    # Create the ruleset in the target repository
    create_url = f"{GITHUB_API_URL}/repos/{target_repo}/rulesets"
    response = github_api_post(create_url, token=token, session=session, json=payload)
    response.raise_for_status()
    return response.json()
