import os
import warnings

from .versions import (
    get_latest_release_tag,
    get_latest_release_hash,
    get_current_hash,
    get_major_minor_version,
    is_ancestor,
)


def get_docs_version():
    """
    Get correct version and alias for documentation website
    """
    release_tag = get_latest_release_tag().lstrip("v")
    if not release_tag:
        warnings.warn("No latest release found")

    release_hash = get_latest_release_hash()
    current_hash = get_current_hash()

    if release_hash == current_hash:
        docs_alias = "latest"
        docs_version = get_major_minor_version(release_tag)
    else:
        if is_ancestor(ancestor=release_hash, descendant=current_hash):
            docs_alias = ""
            docs_version = "dev"
        else:
            raise ValueError(
                f"The current commit hash {current_hash[:7]} is not a descendent of the latest release {release_tag} {release_hash[:7]}"
            )
    return docs_version, docs_alias


def set_docs_version():
    """
    Set version and alias in GitHub environment variables for docs website action
    """
    version, alias = get_docs_version()
    with open(os.getenv("GITHUB_ENV"), "a") as out_env:
        out_env.write(f"VERSION={version}\n")
        out_env.write(f"ALIAS={alias}\n")
