import pytest

from ccbr_tools.shell import shell_run


def test_prepare_docker_errors():
    with pytest.raises(Exception) as exc_info:
        out = shell_run("prepare_docker_build_variables.sh not/a/file abc nciccbr")
        assert "No such file or directory" in out
