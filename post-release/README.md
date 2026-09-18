# post-release

**`post-release`** - Post-release cleanup chores, intended to be
triggered by publishing a release

This action is designed to be triggered by publishing a release. On
completion, it will open a pull request to merge post-release clean up
chores such as bumping the development version in the version file and
changelog. It works best when used in conjunction with
[`draft-release`](/draft-release) to help automate parts of the release
process.

> \[!WARNING\] If your repository contains a `DESCRIPTION` file
> (i.e. it’s an R package), do **not** run this action via
> `jobs.<job_id>.container: nciccbr/ccbr_actions:...`. This action
> relies on `r-lib/actions/setup-r-dependencies` to install both `cffr`
> and your package’s own dependencies declared in `DESCRIPTION`; the
> container only has `cffr` preinstalled, so your package’s dependencies
> would be missing. Run on a normal runner (no `container`) so that step
> can install everything your package needs.

## Usage

Required files:

- `CHANGELOG.md` - a changelog or news file with entries in reverse
  chronological order. The newest entry should contain “development
  header”.
- `VERSION` - a single-source version file.
- `CITATION.cff` - a citation file. (optional)

### Basic example

[post-release.yml](/examples/post-release.yml)

```yaml
name: post-release

on:
  release:
    types:
      - published

permissions:
  contents: write
  pull-requests: write
  actions: write

jobs:
  cleanup:
    runs-on: ubuntu-latest
    # optional: run in the ccbr_actions image (built for each release tag) to skip
    # installing python/R/ccbr_actions -- omit `container` to install them via pip instead.
    # do NOT set `container` if this repo is an R package (i.e. has a DESCRIPTION file):
    # setup-r-dependencies installs both cffr and your package's own DESCRIPTION
    # dependencies, but the container only has cffr preinstalled.
    container: nciccbr/ccbr_actions:latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: CCBR/actions/post-release@v0.7.2
        with:
          github-token: ${{ github.token }}
          update-sliding-tags: false
```

### Customized inputs

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0
  - uses: CCBR/actions/post-release@main
    with:
      github-token: ${{ github.token }}
      ccbr-actions-version: main
      python-version: 3.11
      pr-branch: release/${{ github.ref_name }}
      draft-branch: release-draft
      version-filepath: VERSION
      changelog-filepath: CHANGELOG.md
      citation-filepath: CITATION.cff
      dev-header: "development version"
      github-actor: "41898282+github-actions[bot]"
      update-sliding-tags: false
```

## Inputs

- `github-token`: GitHub Actions token (e.g. github.token).
  **Required.**
- `ccbr-actions-version`: The version of CCBR/actions to use.
  **Required.** Default: `latest`.
- `python-version`: The version of Python to install. **Required.**
  Default: `3.14`.
- `pr-branch`: Branch to use for the post-release chores, from where a
  PR will be opened. Recommended to use ‘release/{TAG_NAME}’.
  **Required.** Default: `release/${{ github.ref_name }}`.
- `draft-branch`: Branch used for the prior release draft (see
  `draft-release` action). **Required.** Default: `release-draft`.
- `version-filepath`: Path to the file containing the current version.
  Default: `VERSION`.
- `description-filepath`: Path to the R DESCRIPTION file, used when an R
  package is detected. Default: `DESCRIPTION`.
- `changelog-filepath`: Path to the changelog or news file. Default:
  `CHANGELOG.md`.
- `citation-filepath`: Path to the citation file. Default:
  `CITATION.cff`.
- `dev-header`: Header string to match to find the development version
  entry in the changelog, typically of the form ‘\## <software name>
  development version’. Default: `development version`.
- `github-actor`: Username of GitHub actor for the git commit when the
  docs branch is deployed. **Required.** Default:
  `41898282+github-actions[bot]`.
- `update-sliding-tags`: Whether to update the sliding tags (major.minor
  & latest) to the new patch version. Default: `false`.
- `dry-run`: Print cleanup commands without creating branches, commits,
  or pull requests. Default: `false`.
