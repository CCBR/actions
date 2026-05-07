import os
import pytest
import warnings

from ccbr_actions.release import (
    prepare_draft_release,
    write_lines,
    write_description_version,
    create_release_draft,
    push_release_draft_branch,
    get_changelog_lines,
    get_news_filepath,
    get_release_version,
    get_r_dev_version,
    is_strict_semver,
    post_release_cleanup,
    set_release_version,
    is_r_package,
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
    with pytest.raises(ValueError) as exc_info:
        get_release_version(next_version_manual="v2", current_version="v1")
    assert "Tag v2 does not match semantic versioning guidelines." in str(
        exc_info.value
    )
    with pytest.raises(ValueError) as exc_info:
        get_release_version(next_version_manual="v1.2.3.9000", current_version="v1.2.2")
    assert "Tag v1.2.3.9000 does not match semantic versioning guidelines." in str(
        exc_info.value
    )


def test_get_r_dev_version():
    assert get_r_dev_version("0.2.0") == "0.2.0.9000"
    assert get_r_dev_version("v0.2.0") == "0.2.0.9000"


@pytest.mark.parametrize(
    "version",
    ["", " 1.2.3 ", "0.2.0.9000", "1.0", "v1.0", "1.2.a", "1.2.3-alpha", "1.2.3.4"],
)
def test_get_r_dev_version_error(version):
    with pytest.raises(ValueError) as exc_info:
        get_r_dev_version(version)
    assert "R package release version must follow semantic versioning" in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    ("version", "with_leading_v", "expected"),
    [
        ("1.2.3", False, True),
        ("v1.2.3", True, True),
        ("1.2.3.9000", False, False),
        ("v1.2.3.9000", True, False),
        ("v1.2", True, False),
        ("1.2", False, False),
    ],
)
def test_is_strict_semver(version, with_leading_v, expected):
    assert is_strict_semver(version, with_leading_v=with_leading_v) is expected


def test_is_r_package(tmp_path):
    desc = tmp_path / "DESCRIPTION"
    desc.write_text("Package: mypkg\nVersion: 0.1.0\n")
    assert is_r_package(description_filepath=desc)


def test_get_news_filepath_default(tmp_path):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert get_news_filepath() == "NEWS.md"
    finally:
        os.chdir(original_cwd)


def test_write_description_version_missing_version(tmp_path):
    description = tmp_path / "DESCRIPTION"
    description.write_text("Package: mypkg\nTitle: Example\n")
    with pytest.raises(ValueError) as exc_info:
        write_description_version(description_filepath=description, version="1.2.3")
    assert "No Version field found in DESCRIPTION file" in str(exc_info.value)


def test_prepare_draft_release_r_package(github_output_file, tmp_path, data_dir):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    original_cwd = os.getcwd()
    os.chdir(repo_dir)
    shell_run("git init > /dev/null 2>&1")
    shell_run(
        "git -c user.name=ci -c user.email=ci@example.com commit --allow-empty -m 'initial commit' > /dev/null 2>&1"
    )
    (repo_dir / "NEWS.md").write_text(
        "## mypkg development version\n\nnotes\n\n## mypkg 0.1.0\n\nolder notes\n"
    )
    (repo_dir / "DESCRIPTION").write_text(
        "Package: mypkg\nVersion: 0.1.0\nTitle: Example\n"
    )
    (repo_dir / "CITATION.cff").write_text((data_dir / "CITATION.cff").read_text())
    try:
        output = exec_in_context(
            prepare_draft_release,
            next_version_manual="v0.2.0",
            next_version_convco="v0.2.0",
            current_version="v0.1.0",
            gh_event_name="push",
            changelog_filepath="CHANGELOG.md",
            release_notes_filepath=".github/latest-release.md",
            version_filepath="VERSION",
            citation_filepath="CITATION.cff",
            repo="CCBR/mypkg",
            debug=True,
        )
    finally:
        os.chdir(original_cwd)
    assert "git add" in output
    assert "NEWS.md" in output
    assert "DESCRIPTION" in output
    assert "Version: 0.2.0" in output
    assert "Rscript -e" in output


def test_prepare_draft_release_warns_on_autoformat_trigger_failure(
    github_output_file, tmp_path, monkeypatch
):
    changelog_file = tmp_path / "CHANGELOG.md"
    version_file = tmp_path / "VERSION"
    notes_file = tmp_path / "latest-release.md"
    changelog_file.write_text(
        "## actions development version\n\nnotes\n\n## actions 0.1.0\n"
    )
    version_file.write_text("0.1.0\n")

    monkeypatch.setattr("ccbr_actions.release.precommit_run", lambda *_: None)
    monkeypatch.setattr(
        "ccbr_actions.release.push_release_draft_branch", lambda **_: None
    )
    monkeypatch.setattr("ccbr_actions.release.get_current_hash", lambda: "abc123")
    monkeypatch.setattr(
        "ccbr_actions.release.create_release_draft",
        lambda **_: "https://example.com/release",
    )
    monkeypatch.setattr("ccbr_actions.release.set_output", lambda *_: None)
    monkeypatch.setattr(
        "ccbr_actions.release.trigger_workflow",
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.warns(UserWarning, match="Failed to trigger workflow"):
        release_url = prepare_draft_release(
            next_version_manual="v0.2.0",
            next_version_convco="v0.2.0",
            current_version="v0.1.0",
            gh_event_name="push",
            changelog_filepath=str(changelog_file),
            release_notes_filepath=str(notes_file),
            version_filepath=str(version_file),
            citation_filepath="not/a/file/CITATION.cff",
            release_branch="release-draft",
            pr_ref_name="feature/branch",
            repo="CCBR/actions",
            debug=False,
        )

    assert release_url == "https://example.com/release"


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


def test_post_release_cleanup_r_package(github_output_file, tmp_path, monkeypatch):
    news_file = tmp_path / "NEWS.md"
    description_file = tmp_path / "DESCRIPTION"
    citation_file = tmp_path / "CITATION.cff"
    news_file.write_text("## mypkg 0.2.0\n\nnotes\n")
    description_file.write_text("Package: mypkg\nVersion: 0.2.0\nTitle: Example\n")
    citation_file.write_text("cff-version: 1.2.0\ntitle: test\n")

    monkeypatch.setattr("ccbr_actions.release.precommit_run", lambda *args: None)

    commands = []

    def _shell_run(command):
        commands.append(command)
        return "https://example.com/pr" if "gh pr create" in command else ""

    monkeypatch.setattr("ccbr_actions.release.shell_run", _shell_run)
    monkeypatch.setattr("ccbr_actions.release.set_output", lambda *_: None)

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        post_release_cleanup(
            changelog_filepath="CHANGELOG.md",
            version_filepath="VERSION",
            citation_filepath=str(citation_file),
            description_filepath=str(description_file),
            repo="CCBR/mypkg",
            release_tag="v0.2.0",
            pr_branch="release/v0.2.0",
            pr_reviewer="reviewer",
            draft_branch="release-draft",
            debug=False,
        )
    finally:
        os.chdir(original_cwd)

    version_line = next(
        (
            line
            for line in description_file.read_text().splitlines()
            if line.startswith("Version:")
        ),
        None,
    )
    assert version_line is not None, f"No Version line found in {description_file}"
    assert version_line == "Version: 0.2.0.9000"
    assert any("Rscript -e" in command for command in commands)


def test_post_release_cleanup_r_package_missing_description_version(
    github_output_file, tmp_path
):
    news_file = tmp_path / "NEWS.md"
    description_file = tmp_path / "DESCRIPTION"
    bad_version_file = tmp_path / "DESCRIPTION.bad"
    news_file.write_text("## mypkg 0.2.0\n\nnotes\n")
    description_file.write_text("Package: mypkg\nVersion: 0.2.0\nTitle: Example\n")
    bad_version_file.write_text("Package: mypkg\nTitle: Example\n")

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with pytest.raises(ValueError) as exc_info:
            post_release_cleanup(
                changelog_filepath="CHANGELOG.md",
                version_filepath=str(bad_version_file),
                description_filepath=str(description_file),
                repo="CCBR/mypkg",
                release_tag="v0.2.0",
                pr_branch="release/v0.2.0",
                pr_reviewer="reviewer",
                draft_branch="release-draft",
                debug=False,
            )
    finally:
        os.chdir(original_cwd)

    assert "No Version field found in DESCRIPTION file" in str(exc_info.value)


def test_post_release_cleanup_non_r_writes_dev_suffix(
    github_output_file, tmp_path, monkeypatch
):
    changelog_file = tmp_path / "CHANGELOG.md"
    version_file = tmp_path / "VERSION"
    changelog_file.write_text("## actions 0.2.0\n\nnotes\n")
    version_file.write_text("0.2.0\n")

    monkeypatch.setattr("ccbr_actions.release.precommit_run", lambda *_: None)
    monkeypatch.setattr(
        "ccbr_actions.release.shell_run",
        lambda command: "https://example.com/pr" if "gh pr create" in command else "",
    )
    monkeypatch.setattr("ccbr_actions.release.set_output", lambda *_: None)

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        post_release_cleanup(
            changelog_filepath=str(changelog_file),
            version_filepath=str(version_file),
            citation_filepath="not/a/file/CITATION.cff",
            repo="CCBR/actions",
            release_tag="v0.2.0",
            pr_branch="release/v0.2.0",
            pr_reviewer="reviewer",
            draft_branch="release-draft",
            debug=False,
        )
    finally:
        os.chdir(original_cwd)

    assert version_file.read_text() == "0.2.0-dev\n"


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


def test_push_release_draft_branch_non_debug(monkeypatch):
    commands = []
    monkeypatch.setattr(
        "ccbr_actions.release.shell_run", lambda command: commands.append(command) or ""
    )
    push_release_draft_branch(
        release_branch="release-draft",
        pr_ref_name="feature/branch",
        next_version="v0.2.0",
        files=["CHANGELOG.md", "VERSION"],
        debug=False,
    )
    assert len(commands) == 1
    assert "git push --set-upstream origin release-draft" in commands[0]


def test_create_release_draft_non_debug(monkeypatch):
    monkeypatch.setattr(
        "ccbr_actions.release.shell_run", lambda *_: "https://example.com/release"
    )
    release_url = create_release_draft(
        release_branch="release-draft",
        next_version="v0.2.0",
        release_notes_filepath=".github/latest-release.md",
        release_target="abc123",
        repo="CCBR/actions",
        debug=False,
    )
    assert release_url == "https://example.com/release"


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
