import os

import pytest
from ccbr_tools.shell import exec_in_context

from ccbr_actions.actions import set_output, trigger_workflow, use_github_action


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
    url, _headers, _data = trigger_workflow(
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


def test_trigger_workflow_uses_gh_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "action-token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    calls = []

    def fake_github_api_post(url, token, json):
        calls.append((url, token, json))
        return type("Response", (), {"status_code": 204})()

    monkeypatch.setattr("ccbr_actions.actions.github_api_post", fake_github_api_post)

    response = trigger_workflow(
        workflow_name="auto-format.yml",
        branch="release-draft",
        repo="CCBR/actions",
    )

    assert response.status_code == 204
    assert calls == [
        (
            "https://api.github.com/repos/CCBR/actions/actions/workflows/auto-format.yml/dispatches",
            "action-token",
            {"ref": "release-draft"},
        )
    ]


def test_trigger_workflow_waits_for_new_run(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "action-token")
    responses = iter(
        [
            {"workflow_runs": [{"id": 10}]},
            {
                "workflow_runs": [
                    {"id": 11, "status": "in_progress"},
                    {"id": 10, "status": "completed", "conclusion": "success"},
                ]
            },
            {
                "workflow_runs": [
                    {"id": 11, "status": "completed", "conclusion": "success"}
                ]
            },
        ]
    )
    get_calls = []

    def fake_github_api_get(url, token):
        get_calls.append((url, token))
        return next(responses)

    monkeypatch.setattr("ccbr_actions.actions.github_api_get", fake_github_api_get)
    monkeypatch.setattr(
        "ccbr_actions.actions.github_api_post",
        lambda **_: type("Response", (), {"status_code": 204})(),
    )
    monkeypatch.setattr("ccbr_actions.actions.time.sleep", lambda _: None)

    response = trigger_workflow(
        workflow_name="auto-format.yml",
        branch="release/draft",
        repo="CCBR/actions",
        wait_for_completion=True,
    )

    assert response.status_code == 204
    assert len(get_calls) == 3
    assert all(
        url.endswith("/runs?branch=release%2Fdraft&event=workflow_dispatch&per_page=20")
        for url, _ in get_calls
    )
    assert all(token == "action-token" for _, token in get_calls)


def test_trigger_workflow_raises_if_new_run_fails(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "action-token")
    responses = iter(
        [
            {"workflow_runs": []},
            {
                "workflow_runs": [
                    {
                        "id": 11,
                        "status": "completed",
                        "conclusion": "failure",
                        "html_url": "https://github.com/CCBR/actions/actions/runs/11",
                    }
                ]
            },
        ]
    )
    monkeypatch.setattr(
        "ccbr_actions.actions.github_api_get",
        lambda **_: next(responses),
    )
    monkeypatch.setattr(
        "ccbr_actions.actions.github_api_post",
        lambda **_: type("Response", (), {"status_code": 204})(),
    )

    with pytest.raises(RuntimeError, match="failed for branch 'release-draft'"):
        trigger_workflow(
            workflow_name="auto-format.yml",
            branch="release-draft",
            repo="CCBR/actions",
            wait_for_completion=True,
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
