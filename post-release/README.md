# post-release

Post-release cleanup chores, intended to be triggered by publishing a
release

This action is designed to be used in conjunction with
[`draft-release`](/draft-release) to help automate parts of the release
process.

## Usage

### Basic example

[post-release.yml](post-release.yml)

```yaml
TODO
```

### Customized inputs

```yaml
TODO
```

## Inputs

- `version_tag`: Version tag for the release event. Recommended to use
  “${{ github.ref_name }}"
  . Default: `${{ github.ref_name }}\`.
- `github-token`: GitHub Actions token (e.g. github.token).
  **Required.**
- `ccbr-actions-version`: The version of CCBR/actions to use.
  **Required.** Default: `main`.
- `python-version`: . **Required.** Default: `3.11`.
- `pr-branch`: Branch to use for the post-release chores, where a PR
  will be opened. Recommended to use ‘release/{TAG_NAME}’. **Required.**
  Default: `release/${{ github.ref_name }}`.
- `draft-branch`: Branch used for the prior release draft. **Required.**
  Default: `release-draft`.
- `version-filepath`: . Default: `VERSION`.
- `changelog-filepath`: . Default: `CHANGELOG.md`.
- `citation-filepath`: . Default: `CITATION.cff`.
- `dev-header`: . Default: `development version`.
- `github-actor`: Username of GitHub actor for the git commit when the
  docs branch is deployed. **Required.** Default:
  `41898282+github-actions[bot]`.

## Outputs
