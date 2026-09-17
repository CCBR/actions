# review-pre-commit-pr

**`review-pre-commit-pr`** - Review a pre-commit.ci autoupdate PR:
approve and attempt auto-merge when only rev: versions changed,
otherwise request a human reviewer

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
- Attempts to enable squash auto-merge so the PR merges automatically
  once all required checks pass. If auto-merge is unavailable, the
  approval remains and the action posts a comment containing the GitHub
  API error.

When either condition is **not** satisfied the action:

- Submits a `REQUEST_CHANGES` review listing which conditions were not
  met.
- Requests a human reviewer, resolved in this order:
  1.  the `reviewer` input, if provided;
  2.  otherwise, the owner(s) of `.pre-commit-config.yaml` per the
      repo’s `CODEOWNERS` file (checked at the repo root, `.github/`,
      and `docs/`);
  3.  otherwise, the most recent human (non-bot, non-Copilot) committer
      to `.pre-commit-config.yaml`.

## Usage

You should call this action from a workflow that is triggered on
`pull_request` events. Generate a CCBR-bot token first (using
`actions/create-github-app-token`) so that the approval and merge
operations are performed as CCBR-bot. The workflow and GitHub App token
must allow `contents: write`, `pull-requests: write`, and
`issues: write`. The `contents` permission is required to enable
auto-merge; `issues` is used for comments when auto-merge cannot be
enabled. The GitHub App installation must have these repository
permissions as well.

We recommended creating a branch protection rule to require that status
checks must pass before PRs can be merged, and include the pre-commit
check as one of the required checks. In your repo’s rulesets
(`github.com/OWNER/REPO/settings/rules`), create a rule, check
`[x] Require status checks to pass`, and add `pre-commit.ci - pr`.
Consider also including other desired checks such as your build/test
workflow, auto-format, etc.

![Branch protection
rule](https://raw.githubusercontent.com/CCBR/actions/main/review-pre-commit-pr/img/branch-protection-rule.png)

### Basic example

[review-pre-commit-pr.yml](./examples/review-pre-commit-pr.yml)

```yaml
name: review-pre-commit-pr

on:
  pull_request:
    types:
      - opened
  # Manually re-scan open PRs for any that meet the pre-commit.ci autoupdate criteria
  workflow_dispatch:

permissions:
  contents: write
  issues: write
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  find-prs:
    # Only needed when manually dispatched; the pull_request event already has a single PR to act on
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    outputs:
      pr-numbers: ${{ steps.search.outputs.pr-numbers }}
    steps:
      - name: Search for open pre-commit.ci autoupdate PRs
        id: search
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          pr_numbers=$(gh pr list \
            --repo "${{ github.repository }}" \
            --state open \
            --json number,title,author \
            --jq '[.[] | select(.title == "[pre-commit.ci] pre-commit autoupdate" and .author.is_bot)] | map(.number)')
          echo "pr-numbers=${pr_numbers}" >> "$GITHUB_OUTPUT"

  review-pre-commit-pr:
    needs: [find-prs]
    runs-on: ubuntu-latest
    container: nciccbr/ccbr_actions:latest
    # Only run for pre-commit.ci autoupdate PRs, whether from the pull_request event or a manual re-scan
    if: >
      always() &&
      (
        (github.event_name == 'pull_request' && github.event.pull_request.title == '[pre-commit.ci] pre-commit autoupdate' && github.event.sender.type == 'Bot')
        || (github.event_name == 'workflow_dispatch' && needs.find-prs.outputs.pr-numbers != '[]')
      )
    strategy:
      fail-fast: false
      matrix:
        pr-number: ${{ github.event_name == 'workflow_dispatch' && fromJson(needs.find-prs.outputs.pr-numbers) || fromJson(format('[{0}]', github.event.pull_request.number)) }}

    steps:
      - uses: actions/checkout@v7
        if: ${{ env.CCBR_ACTIONS_DOCKER != 'true' }}
      - name: Generate CCBR-bot token
        id: generate-token
        uses: actions/create-github-app-token@v3
        with:
          client-id: ${{ vars.CCBR_BOT_APP_ID }}
          private-key: ${{ secrets.CCBR_BOT_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}
          permission-contents: write
          permission-issues: write
          permission-pull-requests: write

      - uses: CCBR/actions/review-pre-commit-pr@latest
        with:
          github-token: ${{ steps.generate-token.outputs.token }}
          pr-number: ${{ matrix.pr-number }}
          repo: ${{ github.repository }}
          reviewer: CCBR/adminteam
```

## Inputs

- `github-token`: GitHub API token (e.g. a CCBR-bot token generated with
  actions/create-github-app-token). **Required.**
- `pr-number`: Pull request number to review. **Required.**
- `repo`: Repository full name (e.g. CCBR/actions). **Required.**
  Default: `${{ github.repository }}`.
- `reviewer`: GitHub username to request as reviewer when the PR
  requires human review.
- `ccbr-actions-version`: The version of CCBR/actions to install
  (branch, tag, or ‘latest’). **Required.** Default: `latest`.
- `python-version`: Python version to use. **Required.** Default:
  `3.11`.
