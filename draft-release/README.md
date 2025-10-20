# draft-release

**`draft-release`** - Draft a new release based on conventional commits
and prepare release notes

This action helps create a draft release based on the contents of the
changelog and commit history. It is designed to be used in a manually
triggered workflow to draft a release.

This action checks out the latest commit in the branch you run the
workflow from, updates files (including `CHANGELOG.md`, `VERSION`,
`CITATION.cff`, and `codemeta.json`), and then creates a draft release
with the new version and changelog entry.

After the workflow completes, navigate to the Releases page on GitHub
and ensure everything looks correct, then publish the release when
you’re ready.

## Usage

Input files:

- `CHANGELOG.md` - a changelog or news file with entries in reverse
  chronological order. The newest entry should contain a header with the
  phrase “development version”.
- `VERSION` - a single-source version file.
- `CITATION.cff` - a citation file. (optional)

When you’re ready to draft a new release, [run the workflow
manually](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/manually-running-a-workflow).
After the workflow completes, there will be a new draft release that you
can review and choose to publish.

### Basic example

[draft-release.yml](/examples/draft-release.yml)

```yaml
name: draft-release

on:
  workflow_dispatch:
    inputs:
      version-tag:
        description: |
          Semantic version tag for next release.
          If not provided, it will be determined based on conventional commit history.
          Example: v2.5.11
        required: false
        type: string
        default: ""

permissions:
  contents: write
  pull-requests: write
  actions: write

jobs:
  draft-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # required to include tags
      - uses: CCBR/actions/draft-release@v0.2
        with:
          github-token: ${{ github.token }}
          version-tag: ${{ github.event.inputs.version-tag }}
```

### Customized inputs

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0 # required to include tags
  - uses: CCBR/actions/draft-release@main
    with:
      github-token: ${{ github.token }}
      version-tag: ${{ github.event.inputs.version-tag }}
      ccbr-actions-version: main
      python-verson: 3.11
      draft-branch: "release-draft"
      version-filepath: VERSION
      changelog-filepath: CHANGELOG.md
      citation-filepath: CITATION.cff
      dev-header: "development version"
      github-actor: "41898282+github-actions[bot]"
```

## Inputs

- `version-tag`: Semantic version tag for next release. If not provided,
  it will be determined based on conventional commit history. Example:
  v2.5.11 .
- `github-token`: GitHub Actions token (e.g. github.token).
  **Required.**
- `ccbr-actions-version`: The version of ccbr_actions to use.
  **Required.** Default: `main`.
- `python-version`: The version of Python to install. **Required.**
  Default: `3.11`.
- `draft-branch`: The branch name to push changes to for the release
  draft.. **Required.** Default: `release-draft`.
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
