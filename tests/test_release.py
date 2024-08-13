from ccbr_actions.release import create_release_draft, push_release_draft_branch
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
