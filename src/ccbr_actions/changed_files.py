"""
Helpers for changed-files action matching logic.
"""

import json
import requests

from pathspec import GitIgnoreSpec

from .actions import set_output


GITHUB_API_URL = "https://api.github.com"


def validate_comparison_mode(comparison_mode):
    """
    Validate the comparison mode used to collect changed files.

    Args:
        comparison_mode (str): Comparison mode name.

    Returns:
        str: The validated comparison mode.

    Raises:
        ValueError: If the comparison mode is not recognized.
    """
    allowed_modes = {"event", "latest-commit"}
    if comparison_mode not in allowed_modes:
        raise ValueError(
            f"Invalid comparison mode: {comparison_mode!r}. Must be one of: {sorted(allowed_modes)}"
        )
    return comparison_mode


def github_api_get(url, token=None, session=requests):
    """
    Perform an authenticated GET request against the GitHub API.

    Args:
        url (str): API URL to fetch.
        token (str, optional): GitHub token.
        session: Object with a requests-compatible ``get`` method.

    Returns:
        dict: Parsed JSON response.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = session.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def format_multiline_file_list(files):
    return "".join(f"{file}\n" for file in files)


def format_changed_files_from_api(compare_payload):
    """
    Extract filenames from a GitHub compare API payload.

    Args:
        compare_payload (dict): Response JSON from the compare API.

    Returns:
        str: Newline-separated filenames.
    """
    files = [file_info["filename"] for file_info in compare_payload.get("files", [])]
    return format_multiline_file_list(files)


def get_pull_request_changed_file_list(
    comparison_mode,
    pr_base_repo_full_name,
    pr_base_sha,
    pr_head_label,
    pr_head_repo_full_name,
    pr_head_sha,
    token=None,
    session=requests,
):
    """
    Get changed files for a pull request event.

    Args:
        comparison_mode (str): Comparison mode.
        pr_base_repo_full_name (str): Base repository full name.
        pr_base_sha (str): Base commit SHA.
        pr_head_label (str): Pull request head label.
        pr_head_repo_full_name (str): Head repository full name.
        pr_head_sha (str): Head commit SHA.
        token (str, optional): GitHub token.
        session: Object with a requests-compatible ``get`` method.

    Returns:
        str: Newline-separated changed files.
    """
    comparison_mode = validate_comparison_mode(comparison_mode)

    if comparison_mode == "latest-commit":
        commit_payload = github_api_get(
            url=f"{GITHUB_API_URL}/repos/{pr_head_repo_full_name}/commits/{pr_head_sha}",
            token=token,
            session=session,
        )
        parent_sha = next(
            (
                parent.get("sha")
                for parent in commit_payload.get("parents", [])
                if parent.get("sha")
            ),
            "",
        )
        if parent_sha:
            compare_payload = github_api_get(
                url=f"{GITHUB_API_URL}/repos/{pr_head_repo_full_name}/compare/{parent_sha}...{pr_head_sha}",
                token=token,
                session=session,
            )
            return format_changed_files_from_api(compare_payload)

    compare_payload = github_api_get(
        url=f"{GITHUB_API_URL}/repos/{pr_base_repo_full_name}/compare/{pr_base_sha}...{pr_head_label}",
        token=token,
        session=session,
    )
    return format_changed_files_from_api(compare_payload)


def get_changed_file_list(
    event_name,
    comparison_mode="latest-commit",
    repository="",
    before="",
    after="",
    pr_base_repo_full_name="",
    pr_base_sha="",
    pr_head_label="",
    pr_head_repo_full_name="",
    pr_head_sha="",
    token=None,
    session=requests,
):
    """
    Get the changed file list for the current GitHub Actions event.

    Args:
        event_name (str): GitHub event name.
        comparison_mode (str): Comparison mode.
        repository (str): Repository full name for non-PR events.
        before (str): Previous SHA for push events.
        after (str): New SHA for push events.
        pr_base_repo_full_name (str): Base repository full name.
        pr_base_sha (str): Base SHA for pull requests.
        pr_head_label (str): Head label for pull requests.
        pr_head_repo_full_name (str): Head repository full name.
        pr_head_sha (str): Head SHA for pull requests.
        token (str, optional): GitHub token.
        session: Object with a requests-compatible ``get`` method.

    Returns:
        str: Newline-separated changed files.
    """
    comparison_mode = validate_comparison_mode(comparison_mode)

    if event_name == "pull_request":
        return get_pull_request_changed_file_list(
            comparison_mode=comparison_mode,
            pr_base_repo_full_name=pr_base_repo_full_name,
            pr_base_sha=pr_base_sha,
            pr_head_label=pr_head_label,
            pr_head_repo_full_name=pr_head_repo_full_name,
            pr_head_sha=pr_head_sha,
            token=token,
            session=session,
        )

    compare_payload = github_api_get(
        url=f"{GITHUB_API_URL}/repos/{repository}/compare/{before}...{after}",
        token=token,
        session=session,
    )
    return format_changed_files_from_api(compare_payload)


def match_paths(changed_file_list, paths=None):
    """
    Mirror the `match-paths` JavaScript step output from actions/changed-files/action.yml.

    Args:
        changed_file_list (str): Newline-separated changed file paths.
        paths (str, optional): .gitignore-style pattern list as a string.

    Returns:
        dict: A dictionary with keys matching the JavaScript step payload.
    """
    changed_files = [file for file in changed_file_list.split("\n") if file]

    if paths:
        matcher = GitIgnoreSpec.from_lines(paths.splitlines())
        matched_files = [file for file in changed_files if matcher.match_file(file)]
    else:
        matched_files = []

    return {
        "changed_files": format_multiline_file_list(changed_files),
        "changed_files_json": json.dumps(changed_files),
        "matched_files": format_multiline_file_list(matched_files),
        "matched_files_json": json.dumps(matched_files),
    }


def match_paths_json(changed_file_list, paths=None):
    """
    Return the `match_paths` payload JSON-encoded.

    This mirrors `return JSON.stringify({...})` in the JavaScript step.
    """
    return json.dumps(match_paths(changed_file_list=changed_file_list, paths=paths))


def get_changed_files(
    paths="",
    event_name="",
    comparison_mode="latest-commit",
    repository="",
    before="",
    after="",
    pr_base_repo_full_name="",
    pr_base_sha="",
    pr_head_label="",
    pr_head_repo_full_name="",
    pr_head_sha="",
    token=None,
    session=requests,
):
    """
    Compute and emit the `result` output for the changed-files action.

    Args:
        paths (str, optional): .gitignore-style pattern list.
        event_name (str): GitHub event name.
        comparison_mode (str): Comparison mode.
        repository (str): Repository full name for non-PR events.
        before (str): Previous SHA for push events.
        after (str): New SHA for push events.
        pr_base_repo_full_name (str): Base repository full name.
        pr_base_sha (str): Base SHA for pull requests.
        pr_head_label (str): Head label for pull requests.
        pr_head_repo_full_name (str): Head repository full name.
        pr_head_sha (str): Head SHA for pull requests.
        token (str, optional): GitHub token.
        session: Object with a requests-compatible ``get`` method.

    Returns:
        str: JSON-encoded payload written to the `result` output.
    """
    changed_file_list = get_changed_file_list(
        event_name=event_name,
        comparison_mode=comparison_mode,
        repository=repository,
        before=before,
        after=after,
        pr_base_repo_full_name=pr_base_repo_full_name,
        pr_base_sha=pr_base_sha,
        pr_head_label=pr_head_label,
        pr_head_repo_full_name=pr_head_repo_full_name,
        pr_head_sha=pr_head_sha,
        token=token,
        session=session,
    )
    result = match_paths_json(changed_file_list=changed_file_list, paths=paths)
    set_output("result", result)
    return result
