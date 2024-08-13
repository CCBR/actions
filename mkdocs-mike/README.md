# mkdocs-mike

Deploy documentation to github pages using mkdocs + mike

This action is designed to be used with a repository that uses mkdocs to
generate documentation and mike to deploy it to github pages. The action
will checkout the repository, install the necessary python packages,
build the documentation, and deploy it to the specified branch.

## Usage

Any python requirements for your docs website (mkdocs, mike, other
extensions) should be placed in `docs/requirements.txt`. You will also
need an mkdocs config file `mkdocs.yml` in the root of your repository.

### Basic example

[docs-mkdocs.yml](examples/docs-mkdocs.yml)

```yaml
steps:
    - uses: actions/checkout@v4
    with:
        fetch-depth: 0
    - uses: CCBR/actions/mkdocs-mike@main
    with:
        github-token: ${{ github.token }}
```

### Customized inputs

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0
  - uses: CCBR/actions/mkdocs-mike@main
    with:
      github-token: ${{ github.token }}
      ccbr-actions-version: 0.1
      python-version: 3.12
      docs-branch: gh-pages
      github-actor: "41898282+github-actions[bot]"
```

## Inputs

- `github-token`: GitHub Actions token (e.g. { github.token }).
  **Required.**
- `ccbr-actions-version`: The version of CCBR/actions to use.
  **Required.** Default: `main`.
- `python-version`: . **Required.** Default: `3.11`.
- `docs-branch`: . **Required.** Default: `gh-pages`.
- `github-actor`: Username of GitHub actor for the git commit when the
  docs branch is deployed. **Required.** Default:
  `41898282+github-actions[bot]`.

## Outputs

- `version`: The version of the docs being deployed..
- `alias`: The alias of the version being deployed..

## old

- `github-token` - Github token to use for deployment. **Required**.
  Recommend using `${{ github.token }}`.
- `ccbr-actions-version` - Version of CCBR/actions to use. Default:
  `main`.
- `python version` - Python version to use. Default: `3.11`.
- `docs-branch` - Branch to deploy documentation to. Default:
  `gh-pages`.
- `github-actor` - Username of GitHub actor for the git commit when the
  docs branch is deployed. Default: `41898282+github-actions[bot]` (the
  GitHub Actions bot).
