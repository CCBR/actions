import os
import pytest
from ccbr_tools.shell import exec_in_context
from ccbr_actions.actions import use_github_action, set_output, trigger_workflow


def test_use_github_action(tmp_path):
    yml_path = tmp_path / "docs-mkdocs.yml"
    use_github_action(name="docs-mkdocs", save_as=yml_path)
    assert yml_path.exists()


def test_use_github_action_error():
    with pytest.raises(FileNotFoundError) as exc_info:
        use_github_action(name="not_an_action")
    assert "Failed to download" in str(exc_info.value)


def test_set_output(tmp_path):
    output_file = tmp_path / "github_output.txt"
    os.environ["TEST_GITHUB_OUTPUT"] = str(output_file)
    try:
        exec_in_context(
            set_output,
            "NAME",
            "VALUE",
            environ="TEST_GITHUB_OUTPUT",
        )
    finally:
        del os.environ["TEST_GITHUB_OUTPUT"]

    output_text = output_file.read_text()
    assert "NAME<<" in output_text
    assert "VALUE" in output_text


def test_trigger_workflow_debug():
    url, headers, data = trigger_workflow(
        workflow_name="test_workflow.yml",
        branch="dev",
        repo="CCBR/actions",
        inputs={"input1": "value1", "input2": "value2"},
        debug=True,
    )
    assert (
        url
        == "https://api.github.com/repos/CCBR/actions/actions/workflows/test_workflow.yml/dispatches"
    )


@pytest.mark.skipif(
    "GITHUB_TOKEN" not in os.environ,
    reason="this will fail when GITHUB_TOKEN is not an envvar",
)
def test_trigger_workflow():
    response = trigger_workflow(
        workflow_name="hello.yml", branch="main", repo="CCBR/actions", debug=False
    )
    assert response.status_code == 204
