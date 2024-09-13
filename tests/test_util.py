from ccbr_actions.util import date_today, precommit_run, path_resolve


def test_precommit():
    assert "usage: pre-commit run [-h]" in precommit_run("--help")


def test_path_resolve_symlink():
    assert str(path_resolve("tests/data/file_ln")).endswith("tests/data/file.txt")
