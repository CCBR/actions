from ccbr_actions.util import precommit_run


def test_precommit():
    assert "usage: pre-commit run [-h]" in precommit_run("--help")
