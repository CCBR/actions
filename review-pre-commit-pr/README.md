# review-pre-commit-pr

**`review-pre-commit-pr`** - Review a pre-commit.ci autoupdate PR:
approve and enable auto-merge when only rev: versions changed, otherwise
request a human reviewer

This action automates the review of pull requests opened by the
[pre-commit.ci](https://pre-commit.ci) bot with the title
`[pre-commit.ci] pre-commit autoupdate`.

The action verifies two conditions:

1.  **Only `.pre-commit-config.yaml` was changed** – no other files
    should be modified by a routine autoupdate.
2.  **The only changes are `rev:` version bumps** – no repos are added
    or removed and no fields other than `rev:` are changed.

When both conditions are satisfied the action:

- Approves the PR as the token’s actor (typically CCBR-bot).
- Enables squash auto-merge so the PR merges automatically once all
  required checks pass.

When either condition is **not** satisfied the action:

- Requests the configured `reviewer` as a human reviewer.
- Posts a comment on the PR tagging the reviewer and explaining which
  conditions were not met.

## Usage

You should call this action from a workflow that is triggered on
`pull_request` events. Generate a CCBR-bot token first (using
`actions/create-github-app-token`) so that the approval and merge
operations are performed as CCBR-bot.

### Basic example

[review-pre-commit-pr.yml](/examples/review-pre-commit-pr.yml)

``` yaml
name: review-pre-commit-pr

on:
  pull_request:
    types:
      - opened

permissions:
  contents: write
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  review-pre-commit-pr:
    runs-on: ubuntu-latest
    # Only run for pre-commit.ci autoupdate PRs
    if: >
      github.event.pull_request.title == '[pre-commit.ci] pre-commit autoupdate'
      && github.event.sender.type == 'Bot'

    steps:
      - name: Generate CCBR-bot token
        id: generate-token
        uses: actions/create-github-app-token@v2
        with:
          app-id: ${{ vars.CCBR_BOT_APP_ID }}
          private-key: ${{ secrets.CCBR_BOT_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}

      - uses: CCBR/actions/review-pre-commit-pr@v0.7
        with:
          github-token: ${{ steps.generate-token.outputs.token }}
          pr-number: ${{ github.event.pull_request.number }}
          repo: ${{ github.repository }}
          reviewer: ${{ github.repository_owner }}
```

## Inputs

- `github-token`: GitHub API token (e.g. a CCBR-bot token generated with
  actions/create-github-app-token). **Required.**
- `pr-number`: Pull request number to review. **Required.**
- `repo`: Repository full name (e.g. CCBR/actions). **Required.**
  Default: `${{ github.repository }}`.
- `reviewer`: GitHub username to request as reviewer when the PR
  requires human review. **Required.**
- `ccbr-actions-version`: The version of CCBR/actions to install
  (branch, tag, or ‘latest’). **Required.** Default: `latest`.
- `python-version`: Python version to use. **Required.** Default:
  `3.11`.
