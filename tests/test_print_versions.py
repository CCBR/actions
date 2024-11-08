import pytest

from ccbr_tools.shell import shell_run


def test_print_versions_errors():
    with pytest.raises(Exception) as exc_info:
        out = shell_run("print_versions.py")
        assert "error: the following arguments are required: --json" in out
