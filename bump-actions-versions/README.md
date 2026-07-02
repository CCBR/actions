# bump-actions-versions

**`bump-actions-versions`** - Bump GitHub Actions versions in workflow
files and open a PR with the changes

This action scans all `*.yml` files in `.github/workflows/` (or another
configured directory), queries the GitHub API for the latest release of
each referenced action, and bumps outdated version pins in place. It
then opens a pull request with the changes so that you can review and
merge at your convenience.

## Features

- **Sliding tag support** — if a workflow pins a major sliding tag
  (e.g. `v4`) and a new major is released (e.g. `v5.0.0`), the tag is
  bumped to `v5`. Similarly for `major.minor` sliding tags (e.g. `v0.7`
  → `v0.8`). Full semver pins (e.g. `v4.1.0`) are bumped to the exact
  latest release.
- **Named / non-semver tags preserved** — refs such as `latest`,
  `stable`, or `main` are left untouched.
- **Commit SHA refs skipped** — lines that pin an action to a full SHA
  are never modified.
- **Lock comment** — add `# ccbr_actions:lock-version` to a `uses:` line
  to prevent it from being bumped.

## Usage

### Basic example

[bump-actions-versions.yml](/examples/bump-actions-versions.yml)

```yaml
name: bump-actions-versions

on:
  schedule:
    - cron: "0 8 1 * *" # monthly, first of the month at 08:00 UTC
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  bump:
    runs-on: ubuntu-latest
    steps:
      - uses: CCBR/actions/bump-actions-versions@v0.8
        with:
          app-id: ${{ vars.CCBR_BOT_APP_ID }}
          app-private-key: ${{ secrets.CCBR_BOT_PRIVATE_KEY }}
```

### Locking a version

To prevent a specific action from being bumped, add the lock comment:

```yaml
- uses: actions/checkout@v4 # ccbr_actions:lock-version
```
