# mkdocs-mike action

Deploy documentation to github pages using mkdocs + mike

This action is designed to be used with a repository that uses mkdocs to generate documentation and mike to deploy it to github pages. The action will checkout the repository, install the necessary python packages, build the documentation, and deploy it to the specified branch.

## Usage

Any python requirements for your docs website (mkdocs, mike, other extensions) should be placed in `docs/requirements.txt`.

You will also need an mkdocs config file `mkdocs.yml` in the root of your repository.

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
        actor: "41898282+github-actions[bot]"


```

## Inputs

- github-token: Github token to use for deployment. **Required**. Recommend using `${{ github.token }}`.
- ccbr-actions-version: Version of CCBR/actions to use. Default: `main`.
- python version: Python version to use. Default: `3.11`.
- docs-branch: Branch to deploy documentation to. Default: `gh-pages`.
- actor: Username of GitHub actor for the git commit when the docs branch is deployed. Default: `41898282+github-actions[bot]` (the GitHub Actions bot).
