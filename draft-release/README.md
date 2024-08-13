# draft-release

Draft a new release based on conventional commits and prepare release
notes

This action helps create a draft release based on the contents of the
changelog and commit history. It is designed to be used in conjunction
with the [`post-release`](/post-release) action.

## Usage

### Basic example

[draft-release.yml](examples/draft-release.yml)

```yaml
TODO
```

### Customized inputs

```yaml
TODO
```

## Inputs

- `version-tag`: Semantic version tag for next release. If not provided,
  it will be determined based on conventional commit history. Example:
  v2.5.11 .
- `github-token`: GitHub Actions token (e.g. github.token).
  **Required.**
- `ccbr-actions-version`: The version of CCBR/actions to use.
  **Required.** Default: `main`.
- `python-version`: . **Required.** Default: `3.11`.
- `draft-branch`: Branch name to push changes to for the release draft..
  **Required.** Default: `release-draft`.
- `version-filepath`: . Default: `VERSION`.
- `changelog-filepath`: . Default: `CHANGELOG.md`.
- `citation-filepath`: . Default: `CITATION.cff`.
- `dev-header`: . Default: `development version`.
- `github-actor`: Username of GitHub actor for the git commit when the
  docs branch is deployed. **Required.** Default:
  `41898282+github-actions[bot]`.

## Outputs
