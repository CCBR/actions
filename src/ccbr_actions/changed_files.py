"""
Helpers for changed-files action matching logic.
"""

import json
import os

from pathspec import GitIgnoreSpec

from .actions import set_output


def format_multiline_file_list(files):
    return "".join(f"{file}\n" for file in files)


def match_paths(changed_file_list, paths=None):
    """
    Mirror the `match-paths` JavaScript step output from actions/changed-files/action.yml.

    Args:
        changed_file_list (str): Newline-separated changed file paths.
        paths (str, optional): .gitignore-style pattern list as a string.

    Returns:
        dict: A dictionary with keys matching the JavaScript step payload.
    """
    changed_files = [file for file in changed_file_list.split("\n") if file]

    if paths:
        matcher = GitIgnoreSpec.from_lines(paths.splitlines())
        matched_files = [file for file in changed_files if matcher.match_file(file)]
    else:
        matched_files = []

    return {
        "changed_files": format_multiline_file_list(changed_files),
        "changed_files_json": json.dumps(changed_files),
        "matched_files": format_multiline_file_list(matched_files),
        "matched_files_json": json.dumps(matched_files),
    }


def match_paths_json(changed_file_list, paths=None):
    """
    Return the `match_paths` payload JSON-encoded.

    This mirrors `return JSON.stringify({...})` in the JavaScript step.
    """
    return json.dumps(match_paths(changed_file_list=changed_file_list, paths=paths))


def get_changed_files(changed_file_list=None, paths=None):
    """
    Compute and emit the `result` output for the changed-files action.

    Args:
        changed_file_list (str, optional): Newline-separated changed file paths.
            When omitted, this is read from CHANGED_FILE_LIST.
        paths (str, optional): .gitignore-style pattern list.
            When omitted, this is read from PATHS.

    Returns:
        str: JSON-encoded payload written to the `result` output.
    """
    changed_file_list = (
        os.environ.get("CHANGED_FILE_LIST", "")
        if changed_file_list is None
        else changed_file_list
    )
    paths = os.environ.get("PATHS", "") if paths is None else paths
    result = match_paths_json(changed_file_list=changed_file_list, paths=paths)
    set_output("result", result)
    return result
