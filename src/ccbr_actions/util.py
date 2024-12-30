"""
Utility functions for the package
"""

import datetime
import pathlib
import ccbr_tools.shell
import ccbr_tools.pkg_util


def repo_base(*paths):
    """
    Get the absolute path to a file in the repository

    Args:
        *paths (str): Additional paths to join with the base path.

    Returns:
        path (str): The absolute path to the file in the repository.
    """
    basedir = pathlib.Path(__file__).absolute().parent
    return basedir.joinpath(*paths)


def print_citation(context, param, value):
    if not value or context.resilient_parsing:
        return
    ccbr_tools.pkg_util.print_citation(
        citation_file=repo_base("CITATION.cff"), output_format="bibtex"
    )
    context.exit()


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
    return ccbr_tools.shell.shell_run(f"pre-commit run {args}", check=False)


def path_resolve(filepath):
    """
    Resolves the given filepath to an absolute path.

    Args:
        filepath (str): The path to be resolved.

    Returns:
        pathlib.Path: The resolved absolute path.

    """
    return pathlib.Path(filepath).resolve()
