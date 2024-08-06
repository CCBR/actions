import os
import tempfile

from ccbr_actions.actions import use_github_action


def test_use_github_action():
    with tempfile.TemporaryDirectory() as tmpdir:
        use_github_action(
            name="docs-mkdocs", save_as=os.path.join(tmpdir, "docs-mkdocs.yml")
        )
        assert os.path.exists(os.path.join(tmpdir, "docs-mkdocs.yml"))
