"""
Download and use GitHub Actions workflow files.
"""

import os
import pathlib
import time
import urllib.parse
import uuid
import warnings

import requests

from .github import GITHUB_API_URL, github_api_get, github_api_headers, github_api_post
from .util import path_resolve
from .versions import get_latest_release_tag


def set_output(name, value, environ="GITHUB_OUTPUT"):
    """
    Set a GitHub Actions output variable.

    Write the given name and value to the GitHub Actions
    environment file specified by the `GITHUB_OUTPUT` environment variable.
    You can then access the variable in GitHub Actions using `${{ steps.<step_id>.outputs.<name> }}`.

    Args:
        name (str): The name of the output variable to set.
        value (str): The value of the output variable to set.
        environ (str, optional): The environment variable that specifies the
            GitHub Actions environment file. Defaults to "GITHUB_OUTPUT".

    Raises:
        RuntimeError: If the GitHub Actions output environment file variable
            is not set.

    Examples:
        >>> set_output("VERSION", "1.0.0")
        >>> set_output("ALIAS", "latest")
    """
    output_file = os.environ.get(environ)
    if output_file:
        with open(output_file, "a") as fh:
            delimiter = uuid.uuid1()
            print(f"{name}<<{delimiter}", file=fh)
            print(value, file=fh)
            print(delimiter, file=fh)
    else:
        raise RuntimeError(
            f"{environ} is not set. set_output() is only supported when "
            "running in a GitHub Actions environment with an output file."
        )


def use_github_action(name, ref=None, url=None, save_as=None, repo="CCBR/actions"):
    """
    Download an example GitHub Actions workflow file from CCBR/actions.

    This function was inspired by {usethis}: <https://usethis.r-lib.org/reference/github_actions.html>

    Args:
        name (str): The name of the GitHub Actions workflow file to download.
        ref (str, optional): The git reference (branch, tag, or commit SHA) to use. Defaults to None, in which case the latest release or "main" is used.
        url (str, optional): The URL to download the workflow file from. Defaults to building it based on the repo and ref.
        save_as (str, optional): The path to save the downloaded workflow file. Defaults to building it based on .github/workflows/name.yml.
        repo (str, optional): The GitHub repository to download the workflow file from. Defaults to "CCBR/actions".

    See Also:
        [](`~ccbr_actions.versions.get_latest_release_tag`): Get the latest release tag from a GitHub repository.
        [](`~ccbr_actions.docs.get_docs_version`): Get the documentation version and alias.

    Notes:
        If `ref` is not provided, the latest release tag is used (if available) or main.
        If `url` is not provided, the URL is constructed based on the repository and reference.
        If `save_as` is not provided, the file is saved in the `.github/workflows` directory.

    Examples:
        >>> use_github_action("docs-mkdocs")
        >>> use_github_action("docs-mkdocs", ref="v1.0.0")
        >>> use_github_action("docs-mkdocs", save_as="custom/path/example-action.yml")
    """
    filename = f"{name}.yml"
    if not ref:
        latest_release = get_latest_release_tag(repo=repo)
        ref = latest_release if latest_release else "main"
    if not url:
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/examples/{filename}"
    save_as = (
        path_resolve(save_as)
        if save_as
        else pathlib.Path(".github") / "workflows" / filename
    )
    # make directories
    save_as.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url)
    if response.status_code == 200:
        with open(save_as, "w") as outfile:
            outfile.write(response.text)
    else:
        raise FileNotFoundError(
            f"Failed to download {url}. Are you sure {name} is a valid GitHub Action in {repo}?"
        )


def trigger_workflow(
    workflow_name,
    branch,
    repo,
    inputs=None,
    debug=False,
    wait_for_completion=False,
):
    """
    Trigger a GitHub Actions workflow.

    Args:
        workflow_name (str): The name of the workflow to trigger.
        branch (str): The branch to trigger the workflow on.
        repo (str): The GitHub repository to trigger the workflow in.
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_name}/dispatches"
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = github_api_headers(token=token)
    data = {"ref": branch}
    if inputs and isinstance(inputs, dict):
        data.update(inputs)
    result = None
    if not debug:
        previous_run_ids = set()
        if wait_for_completion:
            previous_run_ids = _get_workflow_run_ids(
                workflow_name=workflow_name,
                branch=branch,
                repo=repo,
                token=token,
            )
        response = github_api_post(url=url, token=token, json=data)
        if response.status_code != 204:
            warnings.warn(f"Failed to trigger workflow:\n{response.text}")
            if wait_for_completion:
                raise RuntimeError(
                    f"Failed to trigger workflow {workflow_name!r}: "
                    f"HTTP {response.status_code}"
                )
        elif wait_for_completion:
            _wait_for_workflow_run(
                workflow_name=workflow_name,
                branch=branch,
                repo=repo,
                previous_run_ids=previous_run_ids,
                token=token,
            )
        result = response
    else:
        result = url, headers, data
    return result


def _workflow_runs_url(workflow_name, branch, repo):
    query = urllib.parse.urlencode(
        {"branch": branch, "event": "workflow_dispatch", "per_page": 20}
    )
    return (
        f"{GITHUB_API_URL}/repos/{repo}/actions/workflows/{workflow_name}/runs?{query}"
    )


def _get_workflow_run_ids(workflow_name, branch, repo, token):
    response = github_api_get(
        url=_workflow_runs_url(workflow_name, branch, repo), token=token
    )
    return {run["id"] for run in response.get("workflow_runs", [])}


def _wait_for_workflow_run(
    workflow_name,
    branch,
    repo,
    previous_run_ids,
    token,
    timeout_seconds=600,
):
    url = _workflow_runs_url(workflow_name, branch, repo)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = github_api_get(url=url, token=token)
        run = next(
            (
                item
                for item in response.get("workflow_runs", [])
                if item["id"] not in previous_run_ids
            ),
            None,
        )
        if run and run.get("status") == "completed":
            if run.get("conclusion") != "success":
                raise RuntimeError(
                    f"Workflow {workflow_name!r} failed for branch {branch!r}: "
                    f"{run.get('html_url', 'run URL unavailable')}"
                )
            return run
        time.sleep(5)

    raise TimeoutError(
        f"Timed out waiting for workflow {workflow_name!r} on branch {branch!r}"
    )
