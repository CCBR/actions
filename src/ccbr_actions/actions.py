import os
import requests

from .versions import get_latest_release_tag


def use_github_action(name, ref=None, url=None, save_as=None, repo="CCBR/actions"):
    """
    Download an example GitHub Actions workflow file from CCBR/actions.
    Inspired by https://usethis.r-lib.org/reference/github_actions.html
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
