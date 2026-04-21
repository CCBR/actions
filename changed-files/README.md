# changed-files

**`Changed Files`** - Get a list of changed files and filter them by a
list of path patterns similar to .gitignore

Get a list of changed files in a GitHub Actions workflow and optionally
filter them using `.gitignore`-style patterns.

This action retrieves the list of files changed in a pull request or
push event, and can filter the results by one or more patterns. It uses
the GitHub API (via Python) to fetch changed files and `pathspec` for
pattern matching.

By default, `comparison-mode` is `latest-commit`, which compares only
the latest commit for pull requests and uses the full `before...after`
range for push events.

## Usage

### Basic example

[changed-files.yml](./examples/changed-files.yml)

Get all changed files:

```yaml
steps:
  - uses: CCBR/actions/changed-files@main
    id: changed-files
    with:
      comparison-mode: latest-commit

  - run: |
      echo "Changed files:"
      echo "${{ steps.changed-files.outputs.changed_files }}"
```

### Filter by patterns

Filter changed files by `.gitignore`-style patterns:

```yaml
steps:
  - uses: CCBR/actions/changed-files@main
    id: changed-files
    with:
      comparison-mode: event
      paths: |
        src/**
        tests/**

  - run: |
      echo "Matched files:"
      echo "${{ steps.changed-files.outputs.matched_files }}"
```

### With negation patterns

Exclude specific files using negation patterns:

```yaml
steps:
  - uses: CCBR/actions/changed-files@main
    id: changed-files
    with:
      comparison-mode: latest-commit
      paths: |
        *.py
        !tests/**

  - run: |
      echo "Python files (excluding tests):"
      echo "${{ steps.changed-files.outputs.matched_files }}"
```

### Customized inputs

Specify Python version and ccbr-actions version:

```yaml
steps:
  - uses: CCBR/actions/changed-files@main
    id: changed-files
    with:
      paths: "docs/**"
      python-version: "3.12"
      ccbr-actions-version: "v1.0.0"
      comparison-mode: latest-commit

  - run: |
      echo "Documentation files changed:"
      echo "${{ steps.changed-files.outputs.matched_files }}"
```

### Latest commit only (fork-safe PRs)

Compare only the latest commit in pull requests (`head^...head`) so
updates to older commits in a PR do not keep re-matching files from
earlier pushes. This mode is API-based and works for both same-repo and
fork pull requests.

```yaml
steps:
  - uses: CCBR/actions/changed-files@main
    id: changed-files
    with:
      paths: |
        **/Dockerfile.*
      comparison-mode: latest-commit

  - run: |
      echo "Dockerfiles changed in latest commit:"
      echo "${{ steps.changed-files.outputs.matched_files }}"
```

### Full event range mode

Use `comparison-mode: event` when you need all files changed across the
full event range.

```yaml
steps:
  - uses: CCBR/actions/changed-files@main
    id: changed-files
    with:
      comparison-mode: event
      paths: |
        src/**
        tests/**

  - run: |
      echo "Files changed across full event range:"
      echo "${{ steps.changed-files.outputs.matched_files }}"
```

## Inputs

- `paths`: Pattern list in the .gitignore syntax to match against
  changed files.
- `token`: GitHub token used for `gh api` calls. Default:
  `${{ github.token }}`.
- `python-version`: The version of Python to install. Default: `3.11`.
- `ccbr-actions-version`: The version of ccbr_actions to use. Default:
  `main`.
- `comparison-mode`: Comparison mode for collecting changed files.
  - latest-commit (default): for pull_request, compare head^…head
    (latest commit only)
  - event: compare full event range (PR base…head or push before…after).
    Default: `latest-commit`.

## Outputs

- `changed_files`: A multi-line string containing the list of changed
  files.
- `changed_files_json`: A JSON string containing the list of changed
  files.
- `matched_files`: A multi-line string containing the list of changed
  files matching `paths` patterns. Empty (““) if `paths` is not given.
- `matched_files_json`: A JSON string containing the list of changed
  files matching `paths` patterns. Empty (“\[\]”) if `paths` is not
  given.
- `error`: Error message if changed file collection fails. Empty on
  success.
