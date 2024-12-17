# label-issue-repo-name

**`add-issue-label-list`** - Update issue description with a list of
issues of a given label

## Usage

### Basic example

[add-issue-label-list.yml](/examples/add-issue-label-list.yml)

```yaml
name: add-issue-label-list

on:
  workflow_dispatch:
    inputs:
      issue-num:
        required: true
        type: string
        description: "Number of the issue to update (issue should already exist!)"
      label-name:
        required: true
        type: string
        description: "Name of the label to create a task list for (eg. RENEE, ccbr1310, etc.)"

jobs:
  add-list:
    runs-on: ubuntu-latest
    steps:
      - uses: CCBR/actions/add-issue-label-list
        with:
          github-token: ${{ github.token }}
          issue-num: ${{ inputs.issue-num }}
          label-name: ${{ inputs.label-name }}
```

## Inputs

- `issue-num`: Number of the issue to update (issue should already
  exist!). **Required.**
- `label-name`: Name of the label to create a task list for (eg. RENEE
  or ccbr1310, etc.). **Required.**
- `github-token`: GitHub Actions token (e.g. { github.token }).
  **Required.**
