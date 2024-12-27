"""
Download and use GitHub Actions workflow files.

See Also:
    [](`~ccbr_actions.versions.get_latest_release_tag`) : Get the latest release tag from a GitHub repository.

Examples:
    >>> use_github_action("docs-mkdocs")
    >>> use_github_action("docs-mkdocs", ref="v1.0.0")
    >>> use_github_action("docs-mkdocs", save_as="custom/path/example-action.yml")
"""

import os
import requests
import uuid

from .util import path_resolve
from .versions import get_latest_release_tag


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
        latest_release = get_latest_release_tag(args=f"--repo {repo}")
        ref = latest_release if latest_release else "main"
    if not url:
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/examples/{filename}"
    if not save_as:
        save_as = os.path.join(".github", "workflows", filename)

    response = requests.get(url)
    if response.status_code == 200:
        with open(path_resolve(save_as), "w") as outfile:
            outfile.write(response.text)
    else:
        raise ValueError(
            f"Failed to download {url}. Are you sure {name} is a valid GitHub Action in {repo}?"
        )


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

    Examples:
        >>> set_output("VERSION", "1.0.0")
        >>> set_output("ALIAS", "latest")
    """
    if os.environ.get(environ):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            delimiter = uuid.uuid1()
            print(f"{name}<<{delimiter}", file=fh)
            print(value, file=fh)
            print(delimiter, file=fh)
    else:
        print(f"::set-output name={name}::{value}")
