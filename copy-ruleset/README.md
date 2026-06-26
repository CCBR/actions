# copy-ruleset

**`Copy Ruleset`** - Copy a repository ruleset from one GitHub
repository to another.

Copy a named ruleset from one GitHub repository to another. This action
fetches the full ruleset definition from the source repository via the
GitHub API and creates an identical ruleset in the target repository. It
is useful for standardising branch protection rules across multiple
repositories in an organisation.

## Usage

### Basic example

[copy-ruleset.yml](/examples/copy-ruleset.yml)

```yaml
name: copy-ruleset

on:
  workflow_dispatch:
    inputs:
      source-repo:
        description: "Source repository (owner/repo) to copy the ruleset from."
        required: true
      target-repo:
        description: "Target repository (owner/repo) to copy the ruleset to."
        required: true
      ruleset-name:
        description: "Name of the ruleset to copy."
        required: true
  push:
    branches:
      - main
      - master
  repository_dispatch:
    types:
      - copy-ruleset
  schedule:
    - cron: "0 5 * * 1"

permissions:
  contents: read

jobs:
  copy-ruleset:
    if: >-
      ${{
        github.event_name == 'workflow_dispatch' ||
        (vars.RULESET_SOURCE_REPO != '' && vars.RULESET_NAME != '')
      }}
    runs-on: ubuntu-latest
    steps:
      - uses: CCBR/actions/copy-ruleset@latest
        with:
          source-repo: ${{ github.event_name == 'workflow_dispatch' && inputs['source-repo'] || vars.RULESET_SOURCE_REPO }}
          target-repo: ${{ github.event_name == 'workflow_dispatch' && inputs['target-repo'] || vars.RULESET_TARGET_REPO || github.repository }}
          ruleset-name: ${{ github.event_name == 'workflow_dispatch' && inputs['ruleset-name'] || vars.RULESET_NAME }}
          token: ${{ secrets.ORG_PAT }}
```

For non-manual triggers (`push`, `repository_dispatch`, `schedule`), set repository
variables (`RULESET_SOURCE_REPO`, `RULESET_NAME`, and optionally
`RULESET_TARGET_REPO`; defaults to the current repository when unset).

### Using a PAT for cross-repository access

`github.token` is scoped to the repository running the workflow. To copy
rulesets to a repository outside the current one, supply a personal
access token (PAT) or a GitHub App token with `repo` scope on both
repositories:

```yaml
steps:
  - uses: CCBR/actions/copy-ruleset@main
    with:
      source-repo: CCBR/actions
      target-repo: CCBR/other-repo
      ruleset-name: "Require PR reviews"
      token: ${{ secrets.ORG_PAT }}
```

## Running locally

Both operations can also be performed directly in the terminal using the
[`gh` CLI](https://cli.github.com/) and `jq`, without installing any
additional packages.

**List rulesets** in a repository:

```bash
gh api repos/{owner}/{repo}/rulesets --jq '.[] | [.id, .enforcement, .name] | @tsv'
```

**Copy a ruleset** from one repository to another:

```bash
gh api repos/{source_owner}/{source_repo}/rulesets \
  --jq '.[] | select(.name == "Require PR reviews") | .id' \
  | xargs -I{} gh api repos/{source_owner}/{source_repo}/rulesets/{} \
  | jq 'del(.id, .node_id, .created_at, .updated_at, ._links)' \
  | gh api repos/{target_owner}/{target_repo}/rulesets \
      --method POST \
      --input -
```

Alternatively, using the `ccbr_actions` Python package:

```bash
# list rulesets
ccbr_actions list-rulesets owner/repo

# copy a ruleset
ccbr_actions copy-ruleset CCBR/actions CCBR/other-repo "Require PR reviews"
```

## Inputs

- `source-repo`: Source repository in owner/repo format. **Required.**
- `target-repo`: Target repository in owner/repo format. **Required.**
- `ruleset-name`: Name of the ruleset to copy. **Required.**
- `token`: GitHub token with repo scope on both repositories. Default:
  `${{ github.token }}`.
