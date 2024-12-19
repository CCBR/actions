"""
Module for managing documentation versions.

Determine the appropriate version and alias for the documentation website
based on the latest release tag and the current hash.
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


def get_docs_version(release_args=""):
    """
    Get correct version and alias for documentation website.

    Determines the appropriate version and alias for the
    documentation based on the latest release tag and the current hash.

    Args:
        release_args (str, optional): Additional arguments to pass to the `gh release` GitHub CLI command (default is "").

    Returns:
        tuple: A tuple containing:
            - docs_version (str): The major and minor version of the latest release.
            - docs_alias (str): The alias for the documentation version, e.g., "latest".

    Raises:
        ValueError: If the current commit hash is not a descendant of the latest release.

    See Also:
        [](`~ccbr_actions.docs.set_docs_version`): Sets the version and alias in the GitHub environment.

    Examples:
        >>> get_docs_version()
        ('1.0', 'latest')
    """
    release_tag = get_latest_release_tag(args=release_args).lstrip("v")
    if not release_tag:
        warnings.warn("No latest release found")

    release_hash = get_latest_release_hash(args=release_args)
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

    Raises:
        ValueError: If the current commit hash is not a descendant of the latest release.

    See Also:
        [](`~ccbr_actions.docs.get_docs_version`): Retrieves the documentation version and alias.
        [](`~ccbr_actions.actions.set_output`): Sets the GitHub Actions environment variable.

    Examples:
        >>> set_docs_version()
    """
    version, alias = get_docs_version()
    set_output("VERSION", version)
    set_output("ALIAS", alias)


def parse_action_yaml(filename):
    """
    Parses a YAML file and returns its contents as a dictionary.

    Args:
        filename (str): The path to the YAML file to be parsed.

    Returns:
        dict: The contents of the YAML file as a dictionary.
    """
    with open(filename, "r") as infile:
        action = yaml.load(infile, Loader=yaml.FullLoader)
    return action


def action_markdown_desc(action_dict):
    """
    Generates a markdown formatted description for a given action.

    Args:
        action_dict (dict): A dictionary containing action details. Expected keys are:
            - "name" (str): The name of the action.
            - "description" (str): A brief description of the action.

    Returns:
        str: A markdown formatted string with the action name in bold and code format, followed by the description.
    """
    name = action_dict.get("name", "")
    description = action_dict.get("description", "")
    return f"**`{name}`** - {description}\n\n"


def action_markdown_header(action_dict):
    """
    Generates a markdown header for a given action.

    Args:
        action_dict (dict): A dictionary containing action details. Expected keys are:
            - "name" (str): The name of the action.
            - "description" (str): A brief description of the action.

    Returns:
        str: A formatted markdown string with the action's name as a header and the description as the content.
    """
    name = action_dict.get("name", "")
    description = action_dict.get("description", "")
    return f"# {name}\n\n{description}\n\n"


def action_markdown_io(action_dict):
    """
    Generates a markdown string documenting the inputs and outputs of a given action.

    Args:
        action_dict (dict): A dictionary containing the action's inputs and outputs.
            The dictionary should have the following structure:
            {
                "inputs": {
                    "input_name": {
                        "description": "Description of the input",
                        "required": bool,
                        "default": "default_value"
                    },
                    ...
                },
                "outputs": {
                    "output_name": {
                        "description": "Description of the output"
                    },
                    ...
                }
            }

    Returns:
        str: A markdown formatted string documenting the inputs and outputs of the action.
    """
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
