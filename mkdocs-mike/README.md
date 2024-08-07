# mkdocs-mike action

Deploy documentation to github pages using mkdocs + mike

## Usage

Any python requirements for your docs website should be placed in `docs/requirements.txt`.

### Basic example

[docs-mkdocs.yml](examples/docs-mkdocs.yml)

```yaml
steps:
    - uses: actions/checkout@v4
    with:
        fetch-depth: 0
    - uses: CCBR/actions/mkdocs-mike@versions
    with:
        github-token: ${{ github.token }}
```

### Customized inputs

```yaml
steps:
    - uses: actions/checkout@v4
    with:
        fetch-depth: 0
    - uses: CCBR/actions/mkdocs-mike@versions
    with:
        github-token: ${{ github.token }}
        ccbr-actions-version: 0.1
        python-version: 3.12
        docs-branch: gh-pages
        actor: "41898282+github-actions[bot]"


```

## Inputs

- github-token: Github token to use for deployment. Required. Recommend using `${{ github.token }}`. Always required.
- ccbr-actions-version: Version of CCBR/actions to use. Default: `main`.
- python version: Python version to use. Default: `3.11`.
- docs-branch: Branch to deploy documentation to. Default: `gh-pages`.
- actor: Username of GitHub actor for the git commit when the docs branch is deployed. Default: `41898282+github-actions[bot]` (the GitHub Actions bot).
