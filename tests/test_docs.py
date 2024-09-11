import os
import tempfile

from ccbr_actions.docs import (
    get_docs_version,
    parse_action_yaml,
    action_markdown_desc,
    action_markdown_header,
    action_markdown_io,
)
from ccbr_actions.actions import use_github_action


def test_parse_action_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        yml_filepath = os.path.join(tmpdir, "docs-mkdocs.yml")
        use_github_action(name="docs-mkdocs", save_as=yml_filepath)
        action_dict = parse_action_yaml(yml_filepath)

    assert action_dict.get("name") == "docs"


def test_action_markdown_desc():
    action_dict = parse_action_yaml("mkdocs-mike/action.yml")
    assert action_markdown_desc(action_dict).startswith(
        "**`mkdocs-mike`** - Deploy documentation to github pages using mkdocs + mike\n"
    )


def test_action_markdown_header():
    action_dict = parse_action_yaml("mkdocs-mike/action.yml")
    assert action_markdown_header(action_dict).startswith(
        "# mkdocs-mike\n\nDeploy documentation to github pages using mkdocs + mike\n"
    )


def test_action_markdown_io():
    action_md = action_markdown_io(parse_action_yaml("mkdocs-mike/action.yml"))
    assert all(
        [
            "## Inputs\n" in action_md,
            "## Outputs\n" in action_md,
            "The version of the docs being deployed." in action_md,
        ]
    )
