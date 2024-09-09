import os
import tempfile
from ccbr_tools.shell import exec_in_context
from ccbr_actions.actions import use_github_action, set_output


def test_use_github_action():
    with tempfile.TemporaryDirectory() as tmpdir:
        use_github_action(
            name="docs-mkdocs", save_as=os.path.join(tmpdir, "docs-mkdocs.yml")
        )
        assert os.path.exists(os.path.join(tmpdir, "docs-mkdocs.yml"))


def test_set_output():
    assert (
        exec_in_context(set_output, "NAME", "VALUE", environ="ABC")
        == "::set-output name=NAME::VALUE\n\n"
    )
