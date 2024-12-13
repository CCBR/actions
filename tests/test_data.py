from ccbr_actions.data import get_file_path
import pytest


def test_get_file_path():
    file = get_file_path("tool_version_commands.json")
    assert all([file.exists(), file.name == "tool_version_commands.json"])


def test_get_file_path_error():
    with pytest.raises(FileNotFoundError) as exc_info:
        get_file_path("not_a_file.txt")
        assert "FileNotFoundError: not_a_file.txt not found in package data" == str(
            exc_info
        )
