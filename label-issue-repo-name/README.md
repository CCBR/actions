# label-issue-repo-name

**`label-issue-repo-name`** - Label issues & PRs with the repository
name

This action labels issues & PRs with the name of the repository. It is
useful for organizing GitHub Project boards with issues from multiple
repos.

## Usage

### Basic example

[label-issues-reponame.yml](/examples/label-issues-repo-name.yml)

```yaml
name: label-issues-repo-name

on:
  issues:
    types:
      - opened
  pull_request:
    types:
      - opened

jobs:
  add-label:
    uses: CCBR/actions/label-issue-repo-name
    with:
      github-token: ${{ secrets.ADD_TO_PROJECT_PAT }}
```

## Inputs

- `github-token`: GitHub Actions token (e.g. { github.token }).
  **Required.**
