"""
Module for managing documentation versions.

This module provides functions to determine the appropriate version and alias
for the documentation website based on the latest release tag and the current hash.
"""

import warnings
import yaml

from .versions import (
    get_latest_release_tag,
    get_latest_release_hash,
    get_current_hash,
    get_major_minor_version,
    is_ancestor,
)
from .actions import set_output


def get_docs_version():
    """
    Get correct version and alias for documentation website.

    Determines the appropriate version and alias for the
    documentation based on the latest release tag and the current hash.

    Returns
    -------
    tuple
        A tuple containing:
        - docs_version : str
            The major and minor version of the latest release.
        - docs_alias : str
            The alias for the documentation version, e.g., "latest".

    Raises
    ------
    ValueError
        If the current commit hash is not a descendant of the latest release.

    Warns
    -----
    UserWarning
        If no latest release is found.

    See Also
    --------
    set_docs_version : Sets the version and alias in the GitHub environment.

    Examples
    --------
    >>> get_docs_version()
    ('1.0', 'latest')
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
        if not release_hash or is_ancestor(
            ancestor=release_hash, descendant=current_hash
        ):
            docs_alias = ""
            docs_version = "dev"
        else:
            raise ValueError(
                f"The current commit hash {current_hash[:7]} is not a descendent of the latest release {release_tag} {release_hash[:7]}"
            )
    return docs_version, docs_alias


def set_docs_version():
    """
    Set version and alias in GitHub environment variables for docs website action.

    This function retrieves the documentation version and alias using
    `get_docs_version` and sets them as environment variables in the GitHub
    Actions environment.

    Raises
    ------
    ValueError
        If the current commit hash is not a descendant of the latest release.

    Warns
    -----
    UserWarning
        If no latest release is found.

    See Also
    --------
    get_docs_version : Retrieves the documentation version and alias.
    set_output : Sets the GitHub Actions environment variable.

    Examples
    --------
    >>> set_docs_version()
    """
    version, alias = get_docs_version()
    set_output("VERSION", version)
    set_output("ALIAS", alias)


def parse_action_yaml(filename):
    with open(filename, "r") as infile:
        action = yaml.load(infile, Loader=yaml.FullLoader)
    return action


def action_markdown_desc(action_dict):
    name = action_dict.get("name", "")
    description = action_dict.get("description", "")
    return f"**`{name}`** - {description}\n\n"


def action_markdown_header(action_dict):
    name = action_dict.get("name", "")
    description = action_dict.get("description", "")
    return f"# {name}\n\n{description}\n\n"


def action_markdown_io(action_dict):
    markdown = []
    inputs = action_dict.get("inputs", {})
    if inputs:
        markdown.append("## Inputs\n\n")
        for name, details in inputs.items():
            required = " **Required.**" if details.get("required", False) else ""
            default = (
                f" Default: `{details['default']}`."
                if details.get("default", None)
                else ""
            )
            markdown.append(
                f"  - `{name}`: {details.get('description', '')}.{required}{default}"
            )
    outputs = action_dict.get("outputs", {})
    if outputs:
        markdown.append("\n## Outputs\n\n")
        for name, details in outputs.items():
            markdown.append(f"  - `{name}`: {details.get('description', '')}.")
    return "\n".join(markdown)
