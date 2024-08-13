"""
Helpers for drafting releases and cleaning up after releases are published.
"""

import warnings

from .actions import set_output
from .citation import update_citation
from .util import shell_run, precommit_run
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
        latest_version_strict=get_latest_release_tag().lstrip("v"),
        next_version_strict=next_version_strict,
        changelog_filepath=changelog_filepath,
        dev_header=dev_header,
    )

    with open(release_notes_filepath, "w") as outfile:
        outfile.writelines(next_release_lines)
    with open(changelog_filepath, "w") as outfile:
        outfile.writelines(changelog_lines)
    with open(version_filepath, "w") as outfile:
        outfile.write(f"{next_version_strict}\n")

    update_citation(citation_file=citation_filepath, version=next_version)
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


def post_release_cleanup(
    changelog_filepath="CHANGELOG.md",
    repo="${{ github.event.repository.name }}",
    release_tag="${{ github.ref_name }}",
    pr_branch="${{ inputs.branch }}",
    pr_reviewer="${{ github.triggering_actor }}",
    draft_branch="release-draft",
    dev_header="development version",
    version_filepath="VERSION",
    citation_filepath="CITATION.cff",
):
    with open(changelog_filepath, "r") as infile:
        lines = infile.readlines()
    lines.insert(0, f"## { repo } {dev_header}\n\n")
    with open(changelog_filepath, "w") as outfile:
        outfile.writelines(lines)

    with open(version_filepath, "r") as infile:
        version = infile.read().strip()
    with open(version_filepath, "w") as outfile:
        outfile.write(f"{version}-dev\n")

    changed_files = " ".join([citation_filepath, changelog_filepath, version_filepath])
    precommit_run(f"--files {changed_files}")
    shell_run(
        f"""git add {changed_files}
git commit -m "chore: bump changelog & version after release of { release_tag }"
git push --set-upstream origin { pr_branch }
gh pr create \
    --fill-first \
    --reviewer { pr_reviewer }
git push origin --delete {draft_branch} || echo "No {draft_branch} branch to delete"
"""
    )


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
    repo="${{ github.event.repository.name }}",
    debug=False,
):
    version_strict = next_version.lstrip("v")
    cmd = f"gh release create {next_version} --draft --notes-file {release_notes_filepath} --title '{repo} {version_strict}' --target {release_target}"
    if debug:
        print(cmd)
    else:
        shell_run(cmd)
