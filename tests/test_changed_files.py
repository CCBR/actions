import json
import pathlib

from ccbr_actions.changed_files import get_changed_files, match_paths, match_paths_json


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


def test_get_changed_files_sets_result_output(monkeypatch, tmp_path):
    output_file = tmp_path / "github_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setenv("CHANGED_FILE_LIST", "a.txt\n")
    monkeypatch.setenv("PATHS", "*.txt")

    result_json = get_changed_files()

    payload = json.loads(result_json)
    assert payload["matched_files"] == "a.txt\n"
    output_text = pathlib.Path(output_file).read_text()
    assert "result<<" in output_text
    assert result_json in output_text
