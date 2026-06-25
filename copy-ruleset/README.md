# copy-ruleset

**`Copy Ruleset`** - Copy a repository ruleset from one GitHub
repository to another.

Copy a named ruleset from one GitHub repository to another. This action
fetches the full ruleset definition from the source repository via the
GitHub API and creates an identical ruleset in the target repository. It
is useful for standardising branch protection rules across multiple
repositories in an organisation.

> **Tip:** Not sure what rulesets exist in a repository? Run
> `ccbr_actions list-rulesets owner/repo` locally to see all available
> ruleset names and their enforcement status.

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

permissions:
  contents: read

jobs:
  copy-ruleset:
    runs-on: ubuntu-latest
    steps:
      - uses: CCBR/actions/copy-ruleset@latest
        with:
          source-repo: ${{ inputs.source-repo }}
          target-repo: ${{ inputs.target-repo }}
          ruleset-name: ${{ inputs.ruleset-name }}
          token: ${{ secrets.ORG_PAT }}
```

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

### Pinning versions

```yaml
steps:
  - uses: CCBR/actions/copy-ruleset@main
    with:
      source-repo: CCBR/actions
      target-repo: CCBR/other-repo
      ruleset-name: "Require PR reviews"
      token: ${{ secrets.ORG_PAT }}
      python-version: "3.12"
      ccbr-actions-version: "v1.0.0"
```

## Inputs

- `source-repo`: Source repository in owner/repo format. **Required.**
- `target-repo`: Target repository in owner/repo format. **Required.**
- `ruleset-name`: Name of the ruleset to copy. **Required.**
- `token`: GitHub token with repo scope on both repositories. Default:
  `${{ github.token }}`.
- `python-version`: The version of Python to install. Default: `3.11`.
- `ccbr-actions-version`: The version of ccbr_actions to use. Default:
  `main`.
