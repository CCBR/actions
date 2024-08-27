import pytest
import warnings

from ccbr_actions.release import (
    create_release_draft,
    push_release_draft_branch,
    get_changelog_lines,
    get_release_version,
)
from ccbr_actions.util import exec_in_context


def test_create_release_draft():
    assert (
        exec_in_context(
            create_release_draft,
            release_branch="release-draft",
            next_version="v1",
            release_notes_filepath="CHANGELOG.md",
            release_target="HEAD",
            repo="CCBR/actions",
            debug=True,
        )
        == "gh release create v1 --draft --notes-file CHANGELOG.md --title 'CCBR/actions 1' --repo CCBR/actions --target HEAD\n"
    )


def test_push_release_draft_branch():
    assert (
        exec_in_context(
            push_release_draft_branch,
            release_branch="release-draft",
            pr_ref_name="v1",
            next_version="v1",
            files=["CHANGELOG.md"],
            debug=True,
        )
        == """git push origin --delete release-draft || echo "No release-draft branch to delete"
git switch -c release-draft || git switch release-draft
git merge --ff-only v1

git add CHANGELOG.md
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
