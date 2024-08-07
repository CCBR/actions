"""
Module for downloading and using GitHub Actions workflow files.

This module provides functionality to download example GitHub Actions workflow files
from a specified repository and save them to a local directory.

See Also
--------
get_latest_release_tag : Get the latest release tag from a GitHub repository.

Examples
--------
>>> use_github_action("docs-mkdocs")
>>> use_github_action("docs-mkdocs", ref="v1.0.0")
>>> use_github_action("docs-mkdocs", save_as="custom/path/example-action.yml")
"""

import os
import requests


from .versions import get_latest_release_tag


def use_github_action(name, ref=None, url=None, save_as=None, repo="CCBR/actions"):
    """
    Download an example GitHub Actions workflow file from CCBR/actions.

    This function was inspired by {usethis}: <https://usethis.r-lib.org/reference/github_actions.html>

    Parameters
    ----------
    name : str
        The name of the GitHub Actions workflow file to download.
    ref : str, optional
        The git reference (branch, tag, or commit SHA) to use (default is None, in which case the latest release or "main" is used).
    url : str, optional
        The URL to download the workflow file from (default is to build it based on the repo and ref).
    save_as : str, optional
        The path to save the downloaded workflow file (default is to build it based on .github/workflows/name.yml).
    repo : str, optional
        The GitHub repository to download the workflow file from (default is "CCBR/actions").

    Raises
    ------
    ValueError
        If the download fails or the specified action is not valid.

    See Also
    --------
    get_latest_release_tag : Get the latest release tag from a GitHub repository.
    get_docs_version : Get the documentation version and alias.

    Notes
    -----
    If `ref` is not provided, the latest release tag is used (if available) or main.
    If `url` is not provided, the URL is constructed based on the repository and reference.
    If `save_as` is not provided, the file is saved in the `.github/workflows` directory.

    Examples
    --------
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
        with open(save_as, "w") as outfile:
            outfile.write(response.text)
    else:
        raise ValueError(
            f"Failed to download {url}. Are you sure {name} is a valid GitHub Action in {repo}?"
        )
