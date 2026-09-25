# review-post-release-pr

**`review-post-release-pr`** - Review a post-release cleanup PR: approve
pending workflow runs, approve, and enable auto-merge when only
version/date bumps matching a real release tag are present, otherwise
request a human reviewer

This action automates the review of post-release cleanup pull requests
opened by the [post-release](./post-release) action, with titles of the
form `chore: post-release cleanup for <tag>`.

The action verifies five conditions:

1.  **The PR matches the post-release cleanup pattern** – the title
    matches `chore: post-release cleanup for <tag>`, the sender is a
    GitHub App (Bot), and `<tag>` corresponds to an actual GitHub
    release in the repo.
2.  **Only allowed files were changed** – the version file, citation
    file, `codemeta.json`, changelog file, news file, and/or readme
    files. No other files should be modified, and the full list of
    changed files must be retrievable (the action fails closed if a
    pagination mismatch is detected).
3.  **The version file was actually bumped** – auditing that the
    `post-release` action did its job, not just that the changed files
    are individually allowed. For an R package where the version and
    description files are the same `DESCRIPTION` file, a validated
    description bump satisfies this condition.
4.  **Every changed file’s new content is a valid bump for its role** –
    the version file must match the expected dev version exactly;
    `CITATION.cff` and `codemeta.json` may only change their
    version/date fields, matching the release tag and the release’s
    actual published/created date exactly; the changelog/news file must
    have gained only the expected release heading; and readme files may
    only have existing version/date tokens replaced in a recognized
    citation context (a “version” mention or a bibtex `month`/`year`
    field, with no inserted lines), matching a re-rendered citation
    snippet from the `auto-format` action.
5.  **No reviewer currently has changes requested** – an active
    `CHANGES_REQUESTED` review blocks automatic approval even if the
    file checks above pass, so CCBR-bot never silently overrides a
    human’s request.

When all conditions are satisfied the action:

- Re-checks the PR’s head commit immediately before acting, aborting if
  it changed since validation (e.g. a concurrent push), to avoid
  approving unreviewed changes.
- Approves workflow runs pending approval on the PR’s head branch,
  filtered to the validated commit so an unrelated run sharing the
  branch name isn’t approved.
- Approves the PR, pinned to the validated commit, as the token’s actor
  (typically CCBR-bot).
- Attempts to enable squash auto-merge so the PR merges automatically
  once all required checks pass. If auto-merge is unavailable, the
  approval remains and the action posts a comment containing the GitHub
  API error.

When any condition is **not** satisfied the action:

- Posts a comment listing which conditions were not met.
- Requests a human reviewer, resolved in this order:
  1.  the `reviewer` input, if provided;
  2.  otherwise, the actor that triggered the most recent
      `draft-release.yml` workflow run;
  3.  otherwise, the repo’s default (catch-all `*`) `CODEOWNERS` entry.

If the PR already has an APPROVED review tied to its _current_ head
commit, no new review is submitted. A stale approval left on an earlier
commit (e.g. before the `auto-format` action pushes a citation rerender)
does not count, so the PR is re-validated — trigger your workflow on the
`synchronize` PR event (as shown below) so new commits are re-checked.
Set `force-review` to `true` to re-submit the review and reviewer
request even when the PR already has a current approval. It defaults to
`false`.

## Usage

You should call this action from a workflow that is triggered on
`pull_request` events. Generate a CCBR-bot token first (using
`actions/create-github-app-token`) so that the approval and merge
operations are performed as CCBR-bot. The workflow and GitHub App token
must allow `actions: write` (to approve pending workflow runs),
`contents: write`, `pull-requests: write`, and `issues: write`. The
`contents` permission is required to enable auto-merge; `issues` is used
for comments when auto-merge cannot be enabled. The GitHub App
installation must have these repository permissions as well.

### Basic example

```yaml
name: review-post-release-pr

on:
  pull_request:
    types:
      - opened
      - review_requested
      - synchronize

permissions:
  actions: write
  contents: write
  issues: write
  pull-requests: write

jobs:
  review-post-release-pr:
    runs-on: ubuntu-latest
    container: nciccbr/ccbr_actions:latest
    # Only run for post-release cleanup PRs
    if: startsWith(github.event.pull_request.title, 'chore: post-release cleanup for')
    steps:
      - uses: actions/create-github-app-token@v3
        id: generate-token
        with:
          client-id: ${{ vars.CCBR_BOT_APP_ID }}
          private-key: ${{ secrets.CCBR_BOT_PRIVATE_KEY }}
      - uses: CCBR/actions/review-post-release-pr@main
        with:
          github-token: ${{ steps.generate-token.outputs.token }}
          pr-number: ${{ github.event.pull_request.number }}
```

See also [pre-review-pr.yml](./examples/pre-review-pr.yml).

## Inputs

- `github-token`: GitHub API token (e.g. a CCBR-bot token generated with
  actions/create-github-app-token). **Required.**
- `pr-number`: Pull request number to review. **Required.**
- `repo`: Repository full name (e.g. CCBR/actions). **Required.**
  Default: `${{ github.repository }}`.
- `reviewer`: GitHub username to request as reviewer when the PR
  requires human review. If omitted, it is resolved from the actor that
  triggered the most recent draft-release workflow run, falling back to
  the repo’s default CODEOWNERS entry.
- `force-review`: Re-submit the review and reviewer request even when
  the PR already has an approval. Default: `false`.
- `version-filepath`: Path to the file containing the current version.
  Default: `VERSION`.
- `citation-filepath`: Path to the citation file. Default:
  `CITATION.cff`.
- `changelog-filepath`: Path to the changelog or news file. Default:
  `CHANGELOG.md`.
- `description-filepath`: Path to the R DESCRIPTION file, used when an R
  package is detected. Default: `DESCRIPTION`.
- `dev-header`: Header string to match to find the development version
  entry in the changelog, typically of the form ‘\## <software name>
  development version’. Default: `development version`.
- `ccbr-actions-version`: The version of CCBR/actions to install when
  running outside the ccbr_actions container (branch, tag, or ‘latest’).
  **Required.** Default: `latest`.
- `python-version`: Python version to use. **Required.** Default:
  `3.14`.
