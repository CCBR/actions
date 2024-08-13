# Usage

# post-release

Post-release cleanup chores, intended to be triggered by publishing a
release

This action is designed to be triggered by publishing a release. On
completion, it will open a pull request to merge post-release clean up
chores such as bumping the developemnt version in the version file and
changelog. It works best when used in conjunction with
[`draft-release`](/draft-release) to help automate parts of the release
process.

Required files:

- `CHANGELOG.md` - a changelog or news file with entries in reverse
  chronological order. The newest entry should contain “development
  header”.
- `VERSION` - a single-source version file.
- `CITATION.cff` - a citation file.

### Basic example

[post-release.yml](post-release.yml)

```yaml
name: post-release

on:
  release:
    types:
      - published

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/CCBR/actions/draft-release@main
        with:
          github-token: ${{ github.token }}
          pr-branch: release/${{ github.ref_name }}
          draft-branch: release-draft
          version-filepath: VERSION
          changelog-filepath: CHANGELOG.md
          citation-filepath: CITATION.cff
          dev-header: "development version"
```

### Customized inputs

```yaml
TODO
```

## Inputs

- `version_tag`: Version tag for the release event. Recommended to use
  “${{ github.ref_name }}" . Default: `${{ github.ref_name }}\`.
- `github-token`: GitHub Actions token (e.g. github.token).
  **Required.**
- `ccbr-actions-version`: The version of CCBR/actions to use.
  **Required.** Default: `main`.
- `python-version`: The version of Python to install. **Required.**
  Default: `3.11`.
- `pr-branch`: Branch to use for the post-release chores, from where a
  PR will be opened. Recommended to use ‘release/{TAG_NAME}’.
  **Required.** Default: `release/${{ github.ref_name }}`.
- `draft-branch`: Branch used for the prior release draft (see
  `draft-release` action). **Required.** Default: `release-draft`.
- `version-filepath`: Path to the file containing the current version.
  Default: `VERSION`.
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

## Outputs
