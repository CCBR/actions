"""
Utility functions for the package
"""

import datetime
import pathlib
from ccbr_tools.shell import shell_run


def date_today():
    return datetime.datetime.today().strftime("%Y-%m-%d")


def precommit_run(args):
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
