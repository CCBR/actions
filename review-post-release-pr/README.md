# review-post-release-pr

**`review-post-release-pr`** - Review a post-release cleanup PR: approve
pending workflow runs, approve, and enable auto-merge when only
version/date bumps matching a real release tag are present, otherwise
request a human reviewer

This action automates the review of post-release cleanup pull requests
opened by the [post-release](/post-release) action, with titles of the
form `chore: post-release cleanup for <tag>`.

The action verifies three conditions:

1.  **The PR matches the post-release cleanup pattern** – the title
    matches `chore: post-release cleanup for <tag>`, the sender is a
    GitHub App (Bot), and `<tag>` corresponds to an actual GitHub
    release in the repo.
2.  **Only allowed files were changed** – the version file, citation
    file, `codemeta.json`, changelog file, news file, and/or readme
    files. No other files should be modified.
3.  **Only version/date bumps were made** – every change in those files
    must be a version or date bump consistent with the release found in
    condition
    1.  A readme file’s suggested citation snippet may also be
        re-rendered by the `auto-format` action in response to the
        version/date bump; that type of change is accepted the same way.

When all three conditions are satisfied the action:

- Approves any workflow runs pending approval on the PR’s head branch.
- Approves the PR as the token’s actor (typically CCBR-bot).
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

Set `force-review` to `true` to re-submit the review and reviewer
request even when the PR already has an approval. It defaults to
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
on:
  pull_request:
    types:
      - opened
      - review_requested

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

See also [pre-review-pr.yml](/examples/pre-review-pr.yml).

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
- `ccbr-actions-version`: The version of CCBR/actions to install when
  running outside the ccbr_actions container (branch, tag, or ‘latest’).
  **Required.** Default: `latest`.
- `python-version`: Python version to use. **Required.** Default:
  `3.14`.
