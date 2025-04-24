import os
import pytest
import tempfile
import warnings

from ccbr_actions.docs import (
    get_docs_version,
    set_docs_version,
    parse_action_yaml,
    action_markdown_desc,
    action_markdown_header,
    action_markdown_io,
)
from ccbr_actions.actions import use_github_action
from ccbr_tools.shell import exec_in_context


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


def test_get_docs_version():
    with pytest.warns(UserWarning) as record1:
        result1 = get_docs_version(repo="CCBR/CCBR_NextflowTemplate")
    assert all(
        [
            result1 == ("dev", ""),
            "No latest release found" in str(record1[0].message.args[0]),
        ]
    )


def test_get_docs_version_strict():
    with pytest.raises(ValueError) as exc_info:
        get_docs_version(
            repo="CCBR/Tools", release_tag="notAVersion", strict_semver=True
        )
    assert (
        "The major & minor components of the version cannot be determined from the release tag"
        in str(exc_info.value)
    )


def test_get_docs_version_nonsemantic():
    tag1, alias1 = get_docs_version(
        repo="CCBR/HowTos", release_tag="1.0", strict_semver=False
    )
    assert all([tag1 == "1.0", alias1 == ""])


def test_set_docs_version():
    output = exec_in_context(set_docs_version, repo="CCBR/Tools", environ="ABC")
    assert output == "::set-output name=VERSION::dev\n::set-output name=ALIAS::\n"
