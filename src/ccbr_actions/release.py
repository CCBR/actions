"""
Helpers for drafting releases and cleaning up after releases are published.
"""

import os
import warnings
from ccbr_tools.shell import shell_run

from .actions import set_output, trigger_workflow
from .citation import update_citation
from .util import precommit_run, path_resolve
from .versions import (
    check_version_increments_by_one,
    match_semver,
    get_current_hash,
    get_latest_release_tag,
)


def prepare_draft_release(
    next_version_manual="${{ github.event.inputs.version_tag }}",
    next_version_convco="${{ steps.semver.outputs.next }}",
    current_version="${{ steps.semver.outputs.current }}",
    gh_event_name="${{ github.event_name }}",
    changelog_filepath="CHANGELOG.md",
    dev_header="development version",
    release_notes_filepath=".github/latest-release.md",
    version_filepath="VERSION",
    citation_filepath="CITATION.cff",
    release_branch="release-draft",
    pr_ref_name="${{ github.ref_name }}",
    repo="${{ github.repository }}",
    debug=False,
):
    """
    Prepare the release by updating version, changelog, and release notes.

    This function prepares the release by resolving file paths, determining the next version,
    updating the changelog and release notes, and setting the next version as an output.

    Args:
        dev_header (str): The header for the development version section in the changelog (default is "development version").
        release_notes_filepath (str): The path to the release notes file (default is ".github/latest-release.md").
        version_filepath (str): The path to the version file (default is "VERSION").
        citation_filepath (str): The path to the citation file (default is "CITATION.cff").
        release_branch (str): The name of the release branch (default is "release-draft").
        pr_ref_name (str): The reference name of the pull request (default is "${{ github.ref_name }}").
        repo (str): The GitHub repository (default is "${{ github.repository }}").
        debug (bool): If True, print debug information instead of writing to files (default is False).

    Raises:
        AssertionError: If the changelog or version file does not exist.

    Examples:
        >>> prepare_release()
        >>> prepare_release(dev_header="dev version", debug=True)
    """
    release_notes_filepath = path_resolve(release_notes_filepath)
    changelog_filepath = path_resolve(changelog_filepath)
    version_filepath = path_resolve(version_filepath)
    citation_filepath = path_resolve(citation_filepath)
    assert all([f.is_file() for f in (changelog_filepath, version_filepath)])

    next_version = get_release_version(
        next_version_manual=next_version_manual,
        next_version_convco=next_version_convco,
        current_version=current_version,
        gh_event_name=gh_event_name,
    )
    next_version_strict = next_version.lstrip("v")
    set_output("NEXT_VERSION", next_version)

    changelog_lines, next_release_lines = get_changelog_lines(
        latest_version_strict=current_version.lstrip("v"),
        next_version_strict=next_version_strict,
        changelog_filepath=changelog_filepath,
        dev_header=dev_header,
    )

    write_lines(release_notes_filepath, next_release_lines, debug=debug)
    write_lines(changelog_filepath, changelog_lines, debug=debug)
    write_lines(version_filepath, [f"{next_version_strict}\n"], debug=debug)

    if citation_filepath.is_file():
        update_citation(
            citation_file=citation_filepath, version=next_version, debug=debug
        )
    else:
        citation_filepath = ""

    changed_files = [
        str(f) for f in (citation_filepath, changelog_filepath, version_filepath) if f
    ]
    precommit_run(f'--files {" ".join(changed_files)}')
    push_release_draft_branch(
        release_branch=release_branch,
        pr_ref_name=pr_ref_name,
        next_version=next_version,
        files=changed_files,
        debug=debug,
    )
    if not debug:
        try:
            trigger_workflow(
                workflow_name="auto-format.yml", branch=release_branch, repo=repo
            )
        except Exception as e:
            warnings.warn(f"Failed to trigger workflow:\n{e}")
    release_url = create_release_draft(
        release_branch=release_branch,
        next_version=next_version,
        release_notes_filepath=release_notes_filepath,
        release_target=get_current_hash(),
        repo=repo,
        debug=debug,
    )
    set_output("RELEASE_URL", release_url)
    return release_url


def write_lines(filepath, lines, debug=False):
    """
    Write lines to a file or return them as a string for debugging.

    This function writes the provided lines to a specified file. If debugging is enabled,
    it returns the lines as a single string instead of writing to the file.

    Args:
        filepath (str): The path to the file where the lines should be written.
        lines (list of str): The lines to write to the file.
        debug (bool): If True, return the lines as a single string instead of writing to the file (default is False).

    Returns:
        str: The lines as a single string if debugging is enabled, otherwise None.

    Examples:
        >>> write_lines("output.txt", ["line 1\n", "line 2\n"])

        >>> write_lines("output.txt", ["line 1\n", "line 2\n"], debug=True)
        'line 1\nline 2\n'
    """
    if not debug:
        with open(path_resolve(filepath), "w") as outfile:
            outfile.writelines(lines)
    else:
        return "\n".join(lines)


def post_release_cleanup(
    changelog_filepath="CHANGELOG.md",
    repo="${{ github.repository }}",
    release_tag="${{ github.ref_name }}",
    pr_branch="${{ inputs.branch }}",
    pr_reviewer="${{ github.triggering_actor }}",
    draft_branch="release-draft",
    dev_header="development version",
    version_filepath="VERSION",
    citation_filepath="CITATION.cff",
    debug=False,
):
    """
    Perform post-release cleanup tasks.

    This function performs cleanup tasks after a release has been created. It updates the changelog,
    resets the version file, and creates a pull request to merge the changes back into the main branch.

    Args:
        changelog_filepath (str): The path to the changelog file (default is "CHANGELOG.md").
        repo (str): The GitHub repository (default is "${{ github.repository }}").
        release_tag (str): The tag of the release (default is "${{ github.ref_name }}").
        pr_branch (str): The branch for the pull request (default is "${{ inputs.branch }}").
        pr_reviewer (str): The reviewer for the pull request (default is "${{ github.triggering_actor }}").
        draft_branch (str): The name of the draft branch (default is "release-draft").
        dev_header (str): The header for the development version section in the changelog (default is "development version").
        version_filepath (str): The path to the version file (default is "VERSION").
        citation_filepath (str): The path to the citation file (default is "CITATION.cff").

    Examples:
        >>> post_release_cleanup()
        >>> post_release_cleanup(changelog_filepath="docs/CHANGELOG.md", pr_branch="main")
    """
    changelog_filepath = path_resolve(changelog_filepath)
    version_filepath = path_resolve(version_filepath)
    citation_filepath = path_resolve(citation_filepath)

    with open(changelog_filepath, "r") as infile:
        lines = infile.readlines()
    lines.insert(0, f"## { os.path.basename(repo) } {dev_header}\n\n")

    with open(version_filepath, "r") as infile:
        version = infile.read().strip()

    changed_files = " ".join(
        [
            str(filepath)
            for filepath in (citation_filepath, changelog_filepath, version_filepath)
            if filepath.is_file()
        ]
    )

    commit_cmd = f'git add {changed_files} && git commit -m "chore: bump changelog & version after release of { release_tag }" && git push --set-upstream origin { pr_branch }'
    pr_cmd = f"gh pr create --fill-first --reviewer { pr_reviewer }"
    delete_cmd = f'git push origin --delete {draft_branch} || echo "No {draft_branch} branch to delete"'

    if debug:
        print(commit_cmd, pr_cmd, delete_cmd, sep="\n", end="")
        pr_url = ""
    else:
        with open(path_resolve(changelog_filepath), "w") as outfile:
            outfile.writelines(lines)
        with open(path_resolve(version_filepath), "w") as outfile:
            outfile.write(f"{version}-dev\n")
        precommit_run(f"--files {changed_files}")
        shell_run(commit_cmd)
        pr_url = shell_run(f"gh pr create --fill-first --reviewer { pr_reviewer }")
        shell_run(delete_cmd)

    set_output("PR_URL", pr_url)
    return pr_url


def get_release_version(
    next_version_manual=None,
    next_version_convco=None,
    current_version=None,
    gh_event_name=None,
    with_leading_v=True,
):
    """
    Get the next release version based on manual input or conventional commit history.

    If a manual version is provided, it is used regardless of the conventional commit history.

    Args:
        next_version_manual (str, optional): The manually specified next version (default is None).
        next_version_convco (str, optional): The next version determined by conventional commit history (default is None).
        current_version (str, optional): The current version of the project (default is None).
        gh_event_name (str, optional): The name of the GitHub event triggering the release (default is None).
        with_leading_v (bool, optional): Whether to include a leading 'v' in the version string (default is True).

    Returns:
        str: The next release version.

    Raises:
        Warning: If the manual version does not match the version determined by conventional commit history.

    Examples:
        >>> get_release_version(next_version_manual="1.2.0")
        '1.2.0'
        >>> get_release_version(next_version_convco="1.2.1", current_version="1.2.0")
        '1.2.1'
    """
    if next_version_manual:
        next_version = next_version_manual
        if next_version_convco and next_version_manual != next_version_convco:
            warnings.warn(
                f"Manual version ({next_version_manual}) not equal to version determined by conventional commit history ({next_version_convco})"
            )
    else:
        next_version = next_version_convco
    # assert semantic version pattern
    check_version_increments_by_one(
        current_version, next_version, with_leading_v=with_leading_v
    )
    return next_version


def set_release_version(
    next_version_manual="${{ github.event.inputs.version_tag }}",
    next_version_convco="${{ steps.semver.outputs.next }}",
    current_version="${{ steps.semver.outputs.current }}",
    gh_event_name="${{ github.event_name }}",
):
    """
    Set the next release version for GitHub Actions based on manual input or conventional commit history.

    This function determines and sets the next release version for GitHub Actions. It uses either a manually
    specified version or a version determined by conventional commit history. The determined version is then
    set as an output for use in subsequent GitHub Actions steps.

    Args:
        next_version_manual (str): The manually specified next version (default is "${{ github.event.inputs.version_tag }}").
        next_version_convco (str): The next version determined by conventional commit history (default is "${{ steps.semver.outputs.next }}").
        current_version (str): The current version of the project (default is "${{ steps.semver.outputs.current }}").
        gh_event_name (str): The name of the GitHub event triggering the release (default is "${{ github.event_name }}").

    Examples:
        >>> set_release_version()
        >>> set_release_version(next_version_manual="1.2.0")
    """
    next_version = get_release_version(
        next_version_manual, next_version_convco, current_version, gh_event_name
    )
    set_output("NEXT_VERSION", next_version)
    set_output("NEXT_STRICT", next_version.strip("v"))


def get_changelog_lines(
    latest_version_strict,
    next_version_strict,
    changelog_filepath="CHANGELOG.md",
    dev_header="development version",
):
    """
    Prepare the changelog to draft a release.

    This function reads the changelog file and prepares it for the next release by
    replacing the development version header with the next version string and
    collecting lines for the next release.

    Args:
        latest_version_strict (str): The latest version string that follows semantic versioning.
        next_version_strict (str): The next version string that follows semantic versioning.
        changelog_filepath (str, optional): The path to the changelog file. Defaults to "CHANGELOG.md".
        dev_header (str, optional): The header used for the development version in the changelog. Defaults to "development version".

    Returns:
        tuple: A tuple containing two lists:
            - changelog_lines (list): The complete list of lines from the changelog file with the development version header replaced.
            - next_release_lines (list): The list of lines that pertain to the next release.

    Raises:
        ValueError: If any of the provided version strings do not match the semantic versioning pattern.
    """
    for version in [latest_version_strict, next_version_strict]:
        if not match_semver(version):
            raise ValueError(
                f"Version {version} does not match semantic versioning pattern"
            )
    changelog_lines = list()
    next_release_lines = list()
    for_next = True
    with open(changelog_filepath, "r") as infile:
        for line in infile:
            if line.startswith("#") and dev_header in line:
                line = line.replace(dev_header, next_version_strict)
            elif latest_version_strict in line:
                for_next = False

            changelog_lines.append(line)
            if for_next and next_version_strict not in line:
                next_release_lines.append(line)
    return changelog_lines, next_release_lines


def push_release_draft_branch(
    release_branch="release-draft",
    pr_ref_name="${{ github.ref_name }}",
    next_version=None,
    files=["CHANGELOG.md", "VERSION", "CITATION.cff"],
    debug=False,
):
    """
    Pushes a release draft branch to the remote repository.

    This function creates or switches to a specified release branch, merges changes from a pull request reference,
    stages specified files, commits the changes with a message indicating the next version, and pushes the branch to
    the remote repository. If the branch already exists, it will be deleted before creating a new one.

    Args:
        release_branch (str): The name of the release branch to create or switch to. Defaults to "release-draft".
        pr_ref_name (str): The reference name of the pull request to merge. Defaults to "${{ github.ref_name }}".
        next_version (str, optional): The next version number to include in the commit message. Defaults to None.
        files (list): A list of files to stage and commit. Defaults to ["CHANGELOG.md", "VERSION", "CITATION.cff"].
        debug (bool): If True, prints the generated git commands instead of executing them. Defaults to False.

    Returns:
        None
    """
    cmd = f"""git push origin --delete {release_branch} || echo "No {release_branch} branch to delete"
git switch -c {release_branch} || git switch {release_branch}
git merge --ff-only { pr_ref_name }

git add { " ".join(files) }
git commit -m 'chore: 🤖 prepare release { next_version }'
git push --set-upstream origin {release_branch}
"""
    if debug:
        print(cmd)
    else:
        shell_run(cmd)


def create_release_draft(
    release_branch="release-draft",
    next_version="${{ steps.release.outputs.NEXT_VERSION }}",
    release_notes_filepath=".github/latest-release.md",
    release_target=get_current_hash(),
    repo="${{ github.repository }}",
    debug=False,
):
    """
    Create a draft release on GitHub.

    Args:
        release_branch (str): The name of the release branch. Defaults to "release-draft".
        next_version (str): The next version of the release. Defaults to "${{ steps.release.outputs.NEXT_VERSION }}".
        release_notes_filepath (str): The file path to the release notes. Defaults to ".github/latest-release.md".
        release_target (str): The target commit hash for the release. Defaults to the current commit hash.
        repo (str): The GitHub repository in the format "owner/repo". Defaults to "${{ github.repository }}".
        debug (bool): If True, print the command instead of executing it. Defaults to False.

    Returns:
        str: The URL of the created release draft, or an empty string if in debug mode.
    """
    version_strict = next_version.lstrip("v")
    cmd = f"gh release create {next_version} --draft --notes-file {release_notes_filepath} --title '{os.path.basename(repo)} {version_strict}' --repo {repo} --target {release_target}"
    if debug:
        print(cmd)
        release_url = ""
    else:
        release_url = shell_run(cmd)
    return release_url
