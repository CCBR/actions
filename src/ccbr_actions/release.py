"""
Helpers for drafting releases and cleaning up after releases are published.
"""

import os
import warnings
from ccbr_tools.shell import shell_run

from .actions import set_output
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
    release_notes_filepath = path_resolve(release_notes_filepath)
    changelog_filepath = path_resolve(changelog_filepath)
    citation_filepath = path_resolve(citation_filepath)
    version_filepath = path_resolve(version_filepath)

    next_version = get_release_version(
        next_version_manual=next_version_manual,
        next_version_convco=next_version_convco,
        current_version=current_version,
        gh_event_name=gh_event_name,
    )
    next_version_strict = next_version.lstrip("v")
    set_output("NEXT_VERSION", next_version)

    changelog_lines, next_release_lines = get_changelog_lines(
        latest_version_strict=get_latest_release_tag().lstrip("v"),
        next_version_strict=next_version_strict,
        changelog_filepath=changelog_filepath,
        dev_header=dev_header,
    )

    write_lines(release_notes_filepath, next_release_lines, debug=debug)
    write_lines(changelog_filepath, changelog_lines, debug=debug)
    write_lines(version_filepath, [f"{next_version_strict}\n"], debug=debug)
    update_citation(citation_file=citation_filepath, version=next_version, debug=debug)

    changed_files = [
        str(f) for f in (citation_filepath, changelog_filepath, version_filepath)
    ]
    precommit_run(f'--files {" ".join(changed_files)}')
    push_release_draft_branch(
        release_branch=release_branch,
        pr_ref_name=pr_ref_name,
        next_version=next_version,
        files=changed_files,
        debug=debug,
    )
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
    with open(changelog_filepath, "r") as infile:
        lines = infile.readlines()
    lines.insert(0, f"## { os.path.basename(repo) } {dev_header}\n\n")

    with open(version_filepath, "r") as infile:
        version = infile.read().strip()

    changed_files = " ".join(
        [
            str(filepath)
            for filepath in (citation_filepath, changelog_filepath, version_filepath)
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
    repo="${{ github.repository }}",
    debug=False,
):
    version_strict = next_version.lstrip("v")
    cmd = f"gh release create {next_version} --draft --notes-file {release_notes_filepath} --title '{os.path.basename(repo)} {version_strict}' --repo {repo} --target {release_target}"
    if debug:
        print(cmd)
        release_url = ""
    else:
        release_url = shell_run(cmd)
    return release_url
