import os
import pathlib
import pytest
import tempfile
import warnings

from ccbr_actions.release import (
    prepare_draft_release,
    write_lines,
    create_release_draft,
    push_release_draft_branch,
    get_changelog_lines,
    get_release_version,
    post_release_cleanup,
    set_release_version,
)
from ccbr_tools.shell import exec_in_context


def test_write_lines():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = pathlib.Path(tmp_dir) / "tmp.txt"
        write_lines(tmp_file, ["hello\n", "world"], debug=False)
        with open(tmp_file, "r") as fh:
            assert fh.read() == "hello\nworld"


def test_prepare_draft_release():
    output = exec_in_context(
        prepare_draft_release,
        next_version_manual="v1.0.0",
        next_version_convco="v1.0.0",
        current_version="v0.9.10",
        gh_event_name="push",
        changelog_filepath="tests/data/example_changelog.md",
        dev_header="development version",
        release_notes_filepath="tests/data/latest-release.md",
        version_filepath="tests/data/VERSION",
        citation_filepath="tests/data/CITATION.cff",
        release_branch="release-draft",
        pr_ref_name="PR_BRANCH_NAME",
        repo="CCBR/actions",
        debug=True,
    )
    assert all(
        [
            "gh release create v1.0.0 --draft --notes-file " in output,
            "latest-release.md --title 'actions 1.0.0' --repo CCBR/actions --target "
            in output,
        ]
    )


def test_prepare_draft_release_no_citation():
    output = exec_in_context(
        prepare_draft_release,
        next_version_manual="v1.0.0",
        next_version_convco="v1.0.0",
        current_version="v0.9.10",
        gh_event_name="push",
        changelog_filepath="tests/data/example_changelog.md",
        dev_header="development version",
        release_notes_filepath="tests/data/latest-release.md",
        version_filepath="tests/data/VERSION",
        citation_filepath="not/a/file.cff",
        release_branch="release-draft",
        pr_ref_name="PR_BRANCH_NAME",
        repo="CCBR/actions",
        debug=True,
    )
    assert all(["git add" in output, ".cff" not in output])


def test_create_release_draft():
    assert exec_in_context(
        create_release_draft,
        release_branch="release-draft",
        next_version="v1",
        release_notes_filepath="tests/data/example_changelog.md",
        release_target="HEAD",
        repo="CCBR/actions",
        debug=True,
    ).startswith(
        "gh release create v1 --draft --notes-file tests/data/example_changelog.md --title 'actions 1' --repo CCBR/actions --target HEAD\n"
    )


def test_push_release_draft_branch():
    assert exec_in_context(
        push_release_draft_branch,
        release_branch="release-draft",
        pr_ref_name="v1",
        next_version="v1",
        files=["tests/data/example_changelog.md"],
        debug=True,
    ).startswith(
        """git push origin --delete release-draft || echo "No release-draft branch to delete"
git switch -c release-draft || git switch release-draft
git merge --ff-only v1

git add tests/data/example_changelog.md
git commit -m 'chore: 🤖 prepare release v1'
git push --set-upstream origin release-draft

"""
    )


def test_get_changelog_lines():
    new_changelog, release_notes = get_changelog_lines(
        "0.1.0", "0.2.0", changelog_filepath="tests/data/example_changelog.md"
    )
    assert all(
        [
            new_changelog[0] == "## actions 0.2.0\n",
            release_notes == ["\n", "development version notes go here\n", "\n"],
        ]
    )


def test_get_changelog_lines_error():
    with pytest.raises(ValueError) as exc_info1:
        get_changelog_lines(
            "0.1..9000", "0.2.0", changelog_filepath="tests/data/example_changelog.md"
        )
    with pytest.raises(ValueError) as exc_info2:
        get_changelog_lines(
            "0.1.0", "alpha-0.2.0", changelog_filepath="tests/data/example_changelog.md"
        )
    assert all(
        [
            "Version 0.1..9000 does not match semantic versioning pattern"
            in str(exc_info1.value),
            "Version alpha-0.2.0 does not match semantic versioning pattern"
            in str(exc_info2.value),
        ]
    )


def test_get_release_version():
    assert all(
        [
            get_release_version(
                next_version_manual="",
                next_version_convco="v1.10.0",
                current_version="v1.9.10",
            )
            == "v1.10.0",
            get_release_version(
                next_version_manual="v1.10.0",
                next_version_convco="v1.9.11",
                current_version="v1.9.10",
            )
            == "v1.10.0",
        ]
    )


def test_get_release_version_warning():
    warnings.filterwarnings("error")
    with pytest.raises(UserWarning) as exc_info1:
        get_release_version(
            next_version_manual="v2.0.0",
            next_version_convco="v1.10.0",
            current_version="v1.9.10",
        )
    warnings.resetwarnings()
    with pytest.raises(ValueError) as exc_info2:
        get_release_version(
            next_version_manual="v3.0.0",
            next_version_convco="v1.10.0",
            current_version="v1.9.10",
        )
    assert all(
        [
            "Manual version (v2.0.0) not equal to version determined by conventional commit history (v1.10.0)"
            in str(exc_info1.value),
            "Next version must only increment one number at a time. Current version: v1.9.10. Proposed next version: v3.0.0."
            in str(exc_info2.value),
        ]
    )


def test_get_release_version_semver_error():
    with pytest.raises(Exception) as exc_info:
        get_release_version(next_version_manual="v2", current_version="v1")
    assert "Tag v2 does not match semantic versioning guidelines." in str(
        exc_info.value
    )


def test_post_release_cleanup():
    output = exec_in_context(
        post_release_cleanup,
        changelog_filepath="tests/data/example_changelog.md",
        version_filepath="tests/data/VERSION",
        citation_filepath="tests/data/CITATION.cff",
        debug=True,
    )
    assert all(
        [
            "tests/data/CITATION.cff" in output,
            "tests/data/example_changelog.md" in output,
            "tests/data/VERSION" in output,
            "gh pr create --fill-first --reviewer ${{ github.triggering_actor }}"
            in output,
            "git push origin --delete release-draft || echo" in output,
        ]
    )


def test_post_release_cleanup_no_citation():
    output = exec_in_context(
        post_release_cleanup,
        changelog_filepath="tests/data/example_changelog.md",
        version_filepath="tests/data/VERSION",
        citation_filepath="not/a/file/CITATION.cff",
        debug=True,
    )
    assert all(
        [
            "CITATION.cff" not in output,
            "tests/data/example_changelog.md" in output,
            "tests/data/VERSION" in output,
            "gh pr create --fill-first --reviewer ${{ github.triggering_actor }}"
            in output,
            "git push origin --delete release-draft || echo" in output,
        ]
    )


def test_set_release_version():
    output = exec_in_context(
        set_release_version,
        next_version_manual="v1.0.0",
        next_version_convco="v1.0.0",
        current_version="v0.9.10",
        gh_event_name="push",
    )
    assertions = []
    if os.environ.get("GITHUB_ACTIONS"):
        with open(os.environ["GITHUB_OUTPUT"], "r") as fh:
            output = fh.read()
        assertions.extend(
            [
                "NEXT_VERSION" in output,
                "v1.0.0" in output,
                "NEXT_STRICT" in output,
                "1.0.0" in output,
            ]
        )
    else:
        assertions.extend(
            [
                "::set-output name=NEXT_VERSION::v1.0.0" in output,
                "::set-output name=NEXT_STRICT::1.0.0" in output,
            ]
        )
    assert all(assertions)
