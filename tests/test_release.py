import os
import pytest
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
from ccbr_tools.shell import exec_in_context, shell_run


POST_RELEASE_PR_CREATE_COMMAND = (
    "gh pr create --title 'chore: post-release cleanup for ${{ github.ref_name }}' "
    "--body 'Automated post-release cleanup.' --base main --head ${{ inputs.branch }} "
    "--reviewer ${{ github.triggering_actor }}"
)


def test_write_lines(tmp_path):
    tmp_file = tmp_path / "tmp.txt"
    write_lines(tmp_file, ["hello\n", "world"], debug=False)
    assert tmp_file.read_text() == "hello\nworld"


def test_prepare_draft_release(tmp_path, github_output_file, data_dir):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    original_cwd = os.getcwd()
    os.chdir(repo_dir)
    # Initialize a git repository to avoid git rev-parse errors
    shell_run("git init > /dev/null 2>&1")
    shell_run(
        "git -c user.name=ci -c user.email=ci@example.com commit --allow-empty -m 'initial commit' > /dev/null 2>&1"
    )
    try:
        output = exec_in_context(
            prepare_draft_release,
            next_version_manual="v1.0.0",
            next_version_convco="v1.0.0",
            current_version="v0.9.10",
            gh_event_name="push",
            changelog_filepath=str(data_dir / "example_changelog.md"),
            dev_header="development version",
            release_notes_filepath=str(data_dir / "latest-release.md"),
            version_filepath=str(data_dir / "VERSION"),
            citation_filepath=str(data_dir / "CITATION.cff"),
            release_branch="release-draft",
            pr_ref_name="PR_BRANCH_NAME",
            repo="CCBR/actions",
            debug=True,
        )
    finally:
        os.chdir(original_cwd)
    assert "gh release create v1.0.0 --draft --notes-file " in output
    assert (
        "latest-release.md --title 'actions 1.0.0' --repo CCBR/actions --target "
        in output
    )


def test_prepare_draft_release_no_citation(github_output_file, data_dir_rel):
    output = exec_in_context(
        prepare_draft_release,
        next_version_manual="v1.0.0",
        next_version_convco="v1.0.0",
        current_version="v0.9.10",
        gh_event_name="push",
        changelog_filepath=str(data_dir_rel / "example_changelog.md"),
        dev_header="development version",
        release_notes_filepath=str(data_dir_rel / "latest-release.md"),
        version_filepath=str(data_dir_rel / "VERSION"),
        citation_filepath="not/a/file.cff",
        release_branch="release-draft",
        pr_ref_name="PR_BRANCH_NAME",
        repo="CCBR/actions",
        debug=True,
    )
    assert "git add" in output
    assert ".cff" not in output


def test_create_release_draft(data_dir_rel):
    assert exec_in_context(
        create_release_draft,
        release_branch="release-draft",
        next_version="v1",
        release_notes_filepath=str(data_dir_rel / "example_changelog.md"),
        release_target="HEAD",
        repo="CCBR/actions",
        debug=True,
    ).startswith(
        f"gh release create v1 --draft --notes-file {data_dir_rel / 'example_changelog.md'} --title 'actions 1' --repo CCBR/actions --target HEAD\n"
    )


def test_push_release_draft_branch(data_dir_rel):
    assert exec_in_context(
        push_release_draft_branch,
        release_branch="release-draft",
        pr_ref_name="v1",
        next_version="v1",
        files=[str(data_dir_rel / "example_changelog.md")],
        debug=True,
    ).startswith(
        f"""git push origin --delete release-draft || echo "No release-draft branch to delete"
git switch -c release-draft || git switch release-draft
git merge --ff-only v1

git add {data_dir_rel / "example_changelog.md"}
git commit -m 'chore: 🤖 prepare release v1'
git push --set-upstream origin release-draft

"""
    )


def test_get_changelog_lines(data_dir_rel):
    new_changelog, release_notes = get_changelog_lines(
        "0.1.0",
        "0.2.0",
        changelog_filepath=str(data_dir_rel / "example_changelog.md"),
    )
    assert new_changelog[0] == "## actions 0.2.0\n"
    assert release_notes == ["\n", "development version notes go here\n", "\n"]


def test_get_changelog_lines_sinclair(data_dir_rel):
    new_changelog, release_notes = get_changelog_lines(
        "0.3.0",
        "0.3.1",
        changelog_filepath=str(data_dir_rel / "sinclair_changelog.md"),
    )
    assert isinstance(new_changelog, list)
    assert isinstance(release_notes, list)


def test_get_changelog_lines_error(data_dir_rel):
    with pytest.raises(ValueError) as exc_info1:
        get_changelog_lines(
            "0.1..9000",
            "0.2.0",
            changelog_filepath=str(data_dir_rel / "example_changelog.md"),
        )
    with pytest.raises(ValueError) as exc_info2:
        get_changelog_lines(
            "0.1.0",
            "alpha-0.2.0",
            changelog_filepath=str(data_dir_rel / "example_changelog.md"),
        )
    assert "Version 0.1..9000 does not match semantic versioning pattern" in str(
        exc_info1.value
    )
    assert "Version alpha-0.2.0 does not match semantic versioning pattern" in str(
        exc_info2.value
    )


def test_get_release_version():
    assert (
        get_release_version(
            next_version_manual="",
            next_version_convco="v1.10.0",
            current_version="v1.9.10",
        )
        == "v1.10.0"
    )
    assert (
        get_release_version(
            next_version_manual="v1.10.0",
            next_version_convco="v1.9.11",
            current_version="v1.9.10",
        )
        == "v1.10.0"
    )


def test_get_release_version_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(UserWarning) as exc_info1:
            get_release_version(
                next_version_manual="v2.0.0",
                next_version_convco="v1.10.0",
                current_version="v1.9.10",
            )
    with pytest.raises(ValueError) as exc_info2:
        get_release_version(
            next_version_manual="v3.0.0",
            next_version_convco="v1.10.0",
            current_version="v1.9.10",
        )
    assert (
        "Manual version (v2.0.0) not equal to version determined by conventional commit history (v1.10.0)"
        in str(exc_info1.value)
    )
    assert (
        "Next version must only increment one number at a time. Current version: v1.9.10. Proposed next version: v3.0.0."
        in str(exc_info2.value)
    )


def test_get_release_version_semver_error():
    with pytest.raises(Exception) as exc_info:
        get_release_version(next_version_manual="v2", current_version="v1")
    assert "Tag v2 does not match semantic versioning guidelines." in str(
        exc_info.value
    )


def test_post_release_cleanup(github_output_file, data_dir_rel):
    output = exec_in_context(
        post_release_cleanup,
        changelog_filepath=str(data_dir_rel / "example_changelog.md"),
        version_filepath=str(data_dir_rel / "VERSION"),
        citation_filepath=str(data_dir_rel / "CITATION.cff"),
        debug=True,
    )
    assert str(data_dir_rel / "CITATION.cff") in output
    assert str(data_dir_rel / "example_changelog.md") in output
    assert str(data_dir_rel / "VERSION") in output
    assert POST_RELEASE_PR_CREATE_COMMAND in output
    assert "git push origin --delete release-draft || echo" in output


def test_post_release_cleanup_no_citation(github_output_file, data_dir_rel):
    output = exec_in_context(
        post_release_cleanup,
        changelog_filepath=str(data_dir_rel / "example_changelog.md"),
        version_filepath=str(data_dir_rel / "VERSION"),
        citation_filepath="not/a/file/CITATION.cff",
        debug=True,
    )
    assert "CITATION.cff" not in output
    assert str(data_dir_rel / "example_changelog.md") in output
    assert str(data_dir_rel / "VERSION") in output
    assert POST_RELEASE_PR_CREATE_COMMAND in output
    assert "git push origin --delete release-draft || echo" in output


def test_set_release_version(github_output_file):
    exec_in_context(
        set_release_version,
        next_version_manual="v1.0.0",
        next_version_convco="v1.0.0",
        current_version="v0.9.10",
        gh_event_name="push",
    )
    output = github_output_file.read_text()
    assert "NEXT_VERSION" in output
    assert "v1.0.0" in output
    assert "NEXT_STRICT" in output
    assert "1.0.0" in output
