"""
Utility functions for the package
"""

import datetime
from ccbr_tools.shell import shell_run


def date_today():
    return datetime.datetime.today().strftime("%Y-%m-%d")


def precommit_run(args):
    return shell_run(f"pre-commit run {args}")
