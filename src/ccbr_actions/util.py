"""
Utility functions for the package
"""

import datetime
import pathlib
from ccbr_tools.shell import shell_run


def date_today():
    """
    Returns the current date in ISO8601-compliant format (YYYY-MM-DD).

    Returns:
        str: The current date as a string in the format YYYY-MM-DD.
    """
    return datetime.datetime.today().strftime("%Y-%m-%d")


def precommit_run(args):
    """
    Run `pre-commit run` with the specified arguments.

    Args:
        args (str): The arguments to pass to the pre-commit command.

    Returns:
        subprocess.CompletedProcess: The result of the shell command execution.
    """
    return shell_run(f"pre-commit run {args}", check=False)


def path_resolve(filepath):
    """
    Resolves the given filepath to an absolute path.

    Args:
        filepath (str): The path to be resolved.

    Returns:
        pathlib.Path: The resolved absolute path.

    """
    return pathlib.Path(filepath).resolve()
