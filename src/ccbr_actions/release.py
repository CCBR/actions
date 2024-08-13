"""
Helpers for drafting releases and cleaning up after releases are published.
"""

import json
import warnings

from .actions import set_output
from .citation import update_citation
from .util import shell_run, precommit_run
from .versions import check_version_increments_by_one, match_semver, get_current_hash


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
    repo="${{ github.event.repository.name }}",
    debug=False,
):
    next_version = get_release_version(
        next_version_manual=next_version_manual,
        next_version_convco=next_version_convco,
        current_version=current_version,
        gh_event_name=gh_event_name,
    )
    next_version_strict = next_version.lstrip("v")
    set_output("NEXT_VERSION", next_version)

    changelog_lines, next_release_lines = get_changelog_lines(
        latest_version=get_latest_release_tag().lstrip("v"),
        next_version=next_version_strict,
        changelog_filepath=changelog_filepath,
        dev_header=dev_header,
    )

    with open(release_notes_filepath, "w") as outfile:
        outfile.writelines(next_release_lines)
    with open(changelog_filepath, "w") as outfile:
        outfile.writelines(changelog_lines)
    with open(version_filepath, "w") as outfile:
        outfile.write(f"{next_version_strict}\n")

    update_citation(citation_file=citation_filepath, next_version=next_version)
    changed_files = [citation_filepath, changelog_filepath, version_filepath]
    precommit_run(f'--files {" ".join(changed_files)}')
    push_release_draft_branch(
        release_branch=release_branch,
        pr_ref_name=pr_ref_name,
        next_version=next_version,
        files=changed_files,
        debug=debug,
    )
    create_release_draft(
        release_branch=release_branch,
        next_version=next_version,
        release_notes_filepath=release_notes_filepath,
        release_target=get_current_hash(),
        repo=repo,
        debug=debug,
    )


def get_releases(limit=1, args="", json_fields="name,tagName,isLatest,publishedAt"):
    """
    Get a list of releases from GitHub.

    Uses the GitHub CLI to retrieve a list of releases from a repository.

    Parameters
    ----------
    limit : int, optional
        The maximum number of releases to retrieve (default is 1).
    args : str, optional
        Additional arguments to pass to the GitHub CLI command (default is "").
    json_fields : str, optional
        The JSON fields to include in the output (default is "name,tagName,isLatest,publishedAt").

    Returns
    -------
    list
        A list of dictionaries containing release information.

    See Also
    --------
    get_latest_release_tag : Get the tag name of the latest release.
    get_latest_release_hash : Get the commit hash of the latest release.

    Notes
    -----
    gh cli docs: <https://cli.github.com/manual/gh_release_list>

    Examples
    --------
    >>> get_releases(limit=2)
    [{'name': 'v1.0.0', 'tagName': 'v1.0.0', 'isLatest': True, 'publishedAt': '2021-01-01T00:00:00Z'},
     {'name': 'v0.9.0', 'tagName': 'v0.9.0', 'isLatest': False, 'publishedAt': '2020-12-01T00:00:00Z'}]
    >>> get_releases(limit=2, args="--repo CCBR/RENEE")
    [{'isLatest': True, 'name': 'RENEE 2.5.12', 'publishedAt': '2024-04-12T14:49:11Z', 'tagName': 'v2.5.12'},
     {'isLatest': False, 'name': 'RENEE 2.5.11', 'publishedAt': '2024-01-22T21:02:30Z', 'tagName': 'v2.5.11'}]
    """
    releases = shell_run(f"gh release list --limit {limit} --json {json_fields} {args}")
    return json.loads(releases)


def get_latest_release_tag(args=""):
    """
    Get the tag name of the latest release.

    Uses the GitHub CLI to retrieve the latest release tag from a repository.

    Parameters
    ----------
    args : str, optional
        Additional arguments to pass to the GitHub CLI command (default is "").

    Returns
    -------
    str or None
        The tag name of the latest release, or None if no latest release is found.

    See Also
    --------
    get_releases : Get a list of releases from GitHub.

    Examples
    --------
    >>> get_latest_release_tag()
    'v1.0.0'
    """
    releases = get_releases(limit=1, args=args)
    return releases[0]["tagName"] if releases and releases[0]["isLatest"] else None


def get_latest_release_hash():
    """
    Get the commit hash of the latest release.

    Uses git rev-list to get the commit hash of the latest release tag.

    Returns
    -------
    str
        The commit hash of the latest release.

    Raises
    ------
    ValueError
        If the tag is not found in the repository commit history.

    See Also
    --------
    get_latest_release_tag : Get the tag name of the latest release.

    Examples
    --------
    >>> get_latest_release_hash()
    'abc123def4567890abcdef1234567890abcdef12'
    """
    tag_name = get_latest_release_tag()
    tag_hash = shell_run(f"git rev-list -n 1 {tag_name}")
    if "fatal: ambiguous argument" in tag_hash:
        raise ValueError(f"Tag {tag_name} not found in repository commit history")
    return tag_hash


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
    """
    if gh_event_name == "workflow_dispatch" and next_version_manual:
        next_version = next_version_manual
        if next_version_convco and next_version_manual != next_version_convco:
            raise warnings.warn(
                f"Manual version ({next_version_manual}) not equal to version determined by conventional commit history ({next_version_convco})"
            )
    else:
        next_version = next_version_convco
    # assert semantic version pattern
    check_version_increments_by_one(
        next_version, current_version, with_leading_v=with_leading_v
    )
    return next_version


def set_release_version(
    next_version_manual="${{ github.event.inputs.version_tag }}",
    next_version_convco="${{ steps.semver.outputs.next }}",
    current_version="${{ steps.semver.outputs.current }}",
    gh_event_name="${{ github.event_name }}",
):
    """
    Set the next release version for github actions based on manual input or conventional commit history.
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
    Prepare the changelog to draft a release
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
    repo="${{ github.event.repository.name }}",
    debug=False,
):
    cmd = f"""gh release create {next_version} \
--draft \
--notes-file {release_notes_filepath} \
--target {release_target} \
--title "{repo} {next_version.lstrip('v')}"
"""
    if debug:
        print(cmd)
    else:
        shell_run(cmd)
