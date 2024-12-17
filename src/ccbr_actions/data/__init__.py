"""
Data files for CCBR actions
"""

import importlib.resources


def get_file_path(filename):
    """
    Get the file path for a given filename within the package.

    This function retrieves the path to a specified file within the package's
    data files using the `importlib.resources` module.

    Args:
        filename (str): The name of the file for which to retrieve the path.

    Returns:
        pathlib.Path: The path to the specified file within the package.

    Raises:
        FileNotFoundError: If the specified file is not found within the package data.

    Examples:
        >>> get_file_path('tool_version_commands.json')
        PosixPath('/path/to/package/tool_version_commands.json')
    """
    pkg_files = importlib.resources.files(__package__)
    file_path = pkg_files / filename
    if not file_path.exists():
        raise FileNotFoundError(f"{filename} not found in package data")
    return file_path
