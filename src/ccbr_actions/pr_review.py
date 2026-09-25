"""
Generic helpers for automating GitHub pull request reviews.
"""

import base64
import fnmatch

import requests

from .github import (
    GITHUB_API_URL,
    github_api_get,
    github_api_post,
    github_graphql_post,
)

_CODEOWNERS_PATHS = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")


def get_pr_files(repo, pr_number, token=None, session=None):
    """
    Return the list of file objects changed in a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        list[dict]: File objects from the GitHub pull request files API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/files"
    return github_api_get(url=url, token=token, session=session)


def approve_pr(repo, pr_number, token=None, session=None):
    """
    Submit an *APPROVE* review on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        requests.Response: Response from the GitHub reviews API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/reviews"
    response = github_api_post(
        url=url,
        token=token,
        session=session,
        json={"event": "APPROVE"},
    )
    response.raise_for_status()
    return response


def get_pr_reviews(repo, pr_number, token=None, session=None):
    """
    Return the list of reviews submitted on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        list[dict]: Review objects from the GitHub pull request reviews API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/reviews"
    return github_api_get(url=url, token=token, session=session)


def is_pr_approved(repo, pr_number, token=None, session=None):
    """
    Check whether a pull request currently has an APPROVED review.

    The reviews API returns the review history, so an earlier APPROVED review
    must not count after that reviewer submits a later review. The latest
    review for each reviewer is treated as their current state. A current
    REQUEST_CHANGES review takes precedence over approvals from other
    reviewers.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        bool: ``True`` if the current review state includes an APPROVED review
        and no current reviewer has requested changes.
    """
    reviews = get_pr_reviews(repo, pr_number, token=token, session=session)
    latest_reviews = {}
    for review_index, review in enumerate(reviews):
        reviewer = review.get("user", {}).get("login")
        if reviewer is None:
            reviewer = review.get("user", {}).get("id", review.get("id"))
        review_key = (
            review.get("submitted_at") or review.get("created_at") or "",
            review_index,
        )
        previous = latest_reviews.get(reviewer)
        if previous is None or review_key > previous[0]:
            latest_reviews[reviewer] = (review_key, review)

    current_states = [review[1].get("state") for review in latest_reviews.values()]
    has_changes_requested = "CHANGES_REQUESTED" in current_states
    has_approval = "APPROVED" in current_states
    result = has_approval and not has_changes_requested
    return result


def request_changes(repo, pr_number, comment, token=None, session=None):
    """
    Submit a *REQUEST_CHANGES* review on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        comment (str): Review body explaining why changes are requested.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        requests.Response: Response from the GitHub reviews API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/reviews"
    response = github_api_post(
        url=url,
        token=token,
        session=session,
        json={"event": "REQUEST_CHANGES", "body": comment},
    )
    response.raise_for_status()
    return response


def enable_auto_merge(repo, pr_number, token=None, session=None):
    """
    Enable squash auto-merge on a pull request via the GitHub GraphQL API.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        dict: Parsed GraphQL response data.

    Raises:
        RuntimeError: If the GraphQL mutation returns errors.
    """
    pr_url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}"
    pr_data = github_api_get(url=pr_url, token=token, session=session)
    node_id = pr_data["node_id"]

    mutation = """
    mutation EnableAutoMerge($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!) {
      enablePullRequestAutoMerge(input: {
        pullRequestId: $pullRequestId
        mergeMethod: $mergeMethod
      }) {
        pullRequest {
          autoMergeRequest {
            enabledAt
          }
        }
      }
    }
    """
    return github_graphql_post(
        query=mutation,
        variables={"pullRequestId": node_id, "mergeMethod": "SQUASH"},
        token=token,
        session=session,
    )


def approve_pending_workflow_runs(repo, branch, token=None, session=None):
    """
    Approve workflow runs awaiting approval for a branch.

    Some repositories require manual approval before workflow runs triggered
    by a pull request are allowed to execute. This lists runs for *branch*
    with status ``action_required`` and approves each of them.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        branch (str): Branch name (typically a pull request's head ref).
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        list[int]: IDs of the workflow runs that were approved.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/runs"
    data = github_api_get(
        url=url,
        token=token,
        session=session,
        params={"branch": branch, "status": "action_required"},
    )
    approved_run_ids = []
    for run in data.get("workflow_runs", []):
        run_id = run["id"]
        approve_url = f"{GITHUB_API_URL}/repos/{repo}/actions/runs/{run_id}/approve"
        response = github_api_post(url=approve_url, token=token, session=session)
        response.raise_for_status()
        approved_run_ids.append(run_id)
    return approved_run_ids


def get_last_workflow_run_actor(repo, workflow_file, token=None, session=None):
    """
    Return the triggering actor's login for the most recent run of a workflow.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        workflow_file (str): Workflow filename (e.g. ``"draft-release.yml"``).
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        str | None: Login of the actor who triggered the most recent run, or
        ``None`` if no runs were found or the request failed.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_file}/runs"
    try:
        data = github_api_get(
            url=url, token=token, session=session, params={"per_page": 1}
        )
    except requests.exceptions.RequestException:
        data = {}
    runs = data.get("workflow_runs", [])
    actor = (
        (runs[0].get("triggering_actor") or runs[0].get("actor") or {}) if runs else {}
    )
    return actor.get("login")


def request_reviewer(repo, pr_number, reviewer, token=None, session=None):
    """
    Request a reviewer (user or team) on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        reviewer (str): GitHub username, or ``org/team-slug`` team, to request.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        requests.Response: Response from the GitHub requested reviewers API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    if "/" in reviewer:
        payload = {"team_reviewers": [reviewer.rsplit("/", 1)[-1]]}
    else:
        payload = {"reviewers": [reviewer]}
    response = github_api_post(
        url=url,
        token=token,
        session=session,
        json=payload,
    )
    response.raise_for_status()
    return response


def post_pr_comment(repo, pr_number, comment, token=None, session=None):
    """
    Post a comment on a pull request.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        pr_number (int | str): Pull request number.
        comment (str): Comment body text (Markdown supported).
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        requests.Response: Response from the GitHub issue comments API.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/issues/{pr_number}/comments"
    response = github_api_post(
        url=url,
        token=token,
        session=session,
        json={"body": comment},
    )
    response.raise_for_status()
    return response


def get_codeowners_content(repo, token=None, session=None):
    """
    Fetch the raw contents of the repository's ``CODEOWNERS`` file, if any.

    Checks the standard locations GitHub recognizes: repo root, ``.github/``,
    and ``docs/``.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        str | None: Raw ``CODEOWNERS`` file contents, or ``None`` if no such
        file exists in any of the standard locations.
    """
    for path in _CODEOWNERS_PATHS:
        url = f"{GITHUB_API_URL}/repos/{repo}/contents/{path}"
        try:
            data = github_api_get(url=url, token=token, session=session)
        except requests.exceptions.RequestException:
            continue
        encoded_content = data.get("content")
        if encoded_content:
            return base64.b64decode(encoded_content).decode("utf-8")
    return None


def _codeowners_pattern_matches(pattern, filepath):
    """
    Return whether a single ``CODEOWNERS`` pattern matches *filepath*.

    Args:
        pattern (str): A single pattern from a ``CODEOWNERS`` line.
        filepath (str): Path to match against, relative to the repo root.

    Returns:
        bool: ``True`` if *pattern* matches *filepath*.
    """
    normalized = pattern.lstrip("/")
    if not normalized:
        return False
    if normalized in ("*", "**"):
        return True
    if normalized.endswith("/"):
        return filepath.startswith(normalized)
    return fnmatch.fnmatch(filepath, normalized) or fnmatch.fnmatch(
        filepath, f"*/{normalized}"
    )


def match_codeowners(content, filepath):
    """
    Return the owners responsible for *filepath* per a ``CODEOWNERS`` file.

    The last matching pattern in the file wins, per ``CODEOWNERS`` semantics.
    Email-address owners are excluded since they cannot be used as GitHub
    reviewer usernames/teams.

    Args:
        content (str): Raw ``CODEOWNERS`` file contents.
        filepath (str): Path to match against, relative to the repo root.

    Returns:
        list[str]: Matching owner usernames/teams (leading ``@`` stripped),
        or an empty list if no pattern matches.
    """
    matched_owners = []
    for line in content.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, *owners = line.split()
        if not owners:
            continue
        if _codeowners_pattern_matches(pattern, filepath):
            matched_owners = [o[1:] for o in owners if o.startswith("@")]
    return matched_owners


def get_last_human_committer(repo, path, token=None, session=None):
    """
    Return the GitHub username of the most recent non-bot committer to *path*.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        path (str): File path to query commit history for.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        str | None: Login of the most recent human committer, or ``None`` if
        none is found.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/commits"
    try:
        commits = github_api_get(
            url=url, token=token, session=session, params={"path": path}
        )
    except requests.exceptions.RequestException:
        return None
    for commit in commits:
        login = (commit.get("author") or {}).get("login", "")
        if login and "[bot]" not in login.lower() and "copilot" not in login.lower():
            return login
    return None


def determine_reviewer(repo, reviewer=None, path=None, token=None, session=None):
    """
    Determine which GitHub user or team to request for human review.

    Resolution order:

    1. Use *reviewer* if explicitly provided.
    2. Otherwise, look up the owner(s) of *path* in the repository's
       ``CODEOWNERS`` file, if present.
    3. Otherwise, fall back to the most recent human (non-bot) committer to
       *path*.

    Args:
        repo (str): Repository full name (e.g. ``"CCBR/actions"``).
        reviewer (str, optional): Explicit reviewer override.
        path (str, optional): File path used to resolve owners/committers when
            *reviewer* is not provided.
        token (str, optional): GitHub API token.
        session: Requests-compatible session object for dependency injection.

    Returns:
        str | None: GitHub username or team to request as reviewer, or
        ``None`` if none could be determined.
    """
    if reviewer:
        return reviewer

    if path:
        codeowners_content = get_codeowners_content(repo, token=token, session=session)
        if codeowners_content:
            owners = match_codeowners(codeowners_content, path)
            if owners:
                return owners[0]

        return get_last_human_committer(repo, path, token=token, session=session)

    return None
