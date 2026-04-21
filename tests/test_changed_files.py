import json
import pathlib
import pytest

from ccbr_actions.changed_files import (
    format_changed_files_from_api,
    get_changed_file_list,
    get_changed_files,
    get_pull_request_changed_file_list,
    match_paths,
    match_paths_json,
    validate_comparison_mode,
)


class MockResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class MockSession:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append((url, headers))
        return MockResponse(self.payloads[url])


def test_match_paths_without_patterns_mirrors_js_output_shape():
    result = match_paths("a.txt\n\nsubdir/b.txt\n")

    assert result == {
        "changed_files": "a.txt\nsubdir/b.txt\n",
        "changed_files_json": '["a.txt", "subdir/b.txt"]',
        "matched_files": "",
        "matched_files_json": "[]",
    }


def test_match_paths_with_gitignore_patterns():
    changed_file_list = "README.md\nsrc/app.py\nsrc/main.js\ndocs/guide.md\n"
    paths = "*.md\nsrc/*.py"

    result = match_paths(changed_file_list, paths)

    assert result["changed_files"] == changed_file_list
    assert json.loads(result["changed_files_json"]) == [
        "README.md",
        "src/app.py",
        "src/main.js",
        "docs/guide.md",
    ]
    assert result["matched_files"] == "README.md\nsrc/app.py\ndocs/guide.md\n"
    assert json.loads(result["matched_files_json"]) == [
        "README.md",
        "src/app.py",
        "docs/guide.md",
    ]


def test_match_paths_with_negation_pattern():
    changed_file_list = "docs/index.md\ndocs/private.md\n"
    paths = "docs/*.md\n!docs/private.md"

    result = match_paths(changed_file_list, paths)

    assert result["matched_files"] == "docs/index.md\n"
    assert json.loads(result["matched_files_json"]) == ["docs/index.md"]


def test_match_paths_json_matches_python_payload():
    changed_file_list = "a\nb\n"
    paths = "a"

    result_json = match_paths_json(changed_file_list, paths)

    assert json.loads(result_json) == match_paths(changed_file_list, paths)


def test_validate_comparison_mode_rejects_invalid_value():
    with pytest.raises(ValueError, match="Invalid comparison mode"):
        validate_comparison_mode("invalid")


def test_format_changed_files_from_api_formats_newline_list():
    compare_payload = {"files": [{"filename": "a.txt"}, {"filename": "b.txt"}]}

    assert format_changed_files_from_api(compare_payload) == "a.txt\nb.txt\n"


def test_get_pull_request_changed_file_list_uses_latest_commit_compare_when_parent_exists():
    session = MockSession(
        {
            "https://api.github.com/repos/fork/repo/commits/headsha": {
                "parents": [{"sha": "parentsha"}]
            },
            "https://api.github.com/repos/fork/repo/compare/parentsha...headsha": {
                "files": [{"filename": "Dockerfile.cpu"}]
            },
        }
    )

    result = get_pull_request_changed_file_list(
        comparison_mode="latest-commit",
        pr_base_repo_full_name="base/repo",
        pr_base_sha="basesha",
        pr_head_label="fork:branch",
        pr_head_repo_full_name="fork/repo",
        pr_head_sha="headsha",
        token="token",
        session=session,
    )

    assert result == "Dockerfile.cpu\n"
    assert [call[0] for call in session.calls] == [
        "https://api.github.com/repos/fork/repo/commits/headsha",
        "https://api.github.com/repos/fork/repo/compare/parentsha...headsha",
    ]


def test_get_pull_request_changed_file_list_falls_back_to_full_pr_compare_without_parent():
    session = MockSession(
        {
            "https://api.github.com/repos/fork/repo/commits/headsha": {"parents": []},
            "https://api.github.com/repos/base/repo/compare/basesha...fork:branch": {
                "files": [{"filename": "Dockerfile.gpu"}]
            },
        }
    )

    result = get_pull_request_changed_file_list(
        comparison_mode="latest-commit",
        pr_base_repo_full_name="base/repo",
        pr_base_sha="basesha",
        pr_head_label="fork:branch",
        pr_head_repo_full_name="fork/repo",
        pr_head_sha="headsha",
        session=session,
    )

    assert result == "Dockerfile.gpu\n"
    assert session.calls[-1][0] == (
        "https://api.github.com/repos/base/repo/compare/basesha...fork:branch"
    )


def test_get_changed_file_list_uses_event_compare_for_pull_request_mode_event():
    session = MockSession(
        {
            "https://api.github.com/repos/base/repo/compare/basesha...fork:branch": {
                "files": [{"filename": "src/app.py"}]
            }
        }
    )

    result = get_changed_file_list(
        event_name="pull_request",
        comparison_mode="event",
        pr_base_repo_full_name="base/repo",
        pr_base_sha="basesha",
        pr_head_label="fork:branch",
        pr_head_repo_full_name="fork/repo",
        pr_head_sha="headsha",
        session=session,
    )

    assert result == "src/app.py\n"


def test_get_changed_file_list_uses_push_compare_for_push_events():
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/actions/compare/before...after": {
                "files": [{"filename": "README.md"}]
            }
        }
    )

    result = get_changed_file_list(
        event_name="push",
        comparison_mode="latest-commit",
        repository="CCBR/actions",
        before="before",
        after="after",
        session=session,
    )

    assert result == "README.md\n"


def test_get_changed_files_sets_result_output(monkeypatch, tmp_path):
    output_file = tmp_path / "github_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/actions/compare/before...after": {
                "files": [{"filename": "a.txt"}]
            }
        }
    )

    result_json = get_changed_files(
        paths="*.txt",
        event_name="push",
        comparison_mode="latest-commit",
        repository="CCBR/actions",
        before="before",
        after="after",
        session=session,
    )

    payload = json.loads(result_json)
    assert payload["matched_files"] == "a.txt\n"
    output_text = pathlib.Path(output_file).read_text()
    assert "result<<" in output_text
    assert result_json in output_text
