"""
Utility functions for shell command execution.

This module provides utility functions to execute shell commands and capture their output.

Examples
--------
>>> shell_run("echo Hello, World!")
'Hello, World!\n'
>>> shell_run("invalid_command")
'/bin/sh: invalid_command: command not found\n'
"""

import datetime
import subprocess


def shell_run(cmd_str):
    """
    Execute a shell command and capture its output.

    Uses `subprocess.run` and captures both stdout and stderr as text.

    Parameters
    ----------
    cmd_str : str
        The shell command to execute.

    Returns
    -------
    str
        The combined standard output and standard error of the command.

    See Also
    --------
    subprocess.run : For executing shell commands.

    Examples
    --------
    >>> shell_run("echo Hello, World!")
    'Hello, World!\n'
    >>> shell_run("invalid_command")
    '/bin/sh: invalid_command: command not found\n'
    """
    run = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    return "\n".join([run.stdout, run.stderr])


def date_today():
    return datetime.datetime.today().strftime("%Y-%m-%d")


def precommit_run(args):
    return shell_run(f"pre-commit run {args}")
