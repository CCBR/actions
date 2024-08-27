# mkdocs-mike

**`mkdocs-mike`** - Deploy documentation to github pages using mkdocs +
mike

This action is designed to be used with a repository that uses mkdocs to
generate documentation and mike to deploy it to github pages. The action
will checkout the repository, install the necessary python packages,
build the documentation, and deploy it to the specified branch.

## Usage

Any python requirements for your docs website (mkdocs, mike, other
extensions) should be placed in `docs/requirements.txt`. You will also
need an mkdocs config file `mkdocs.yml` in the root of your repository.
To properly configure mike for your website, you will also need to
complete these one-time steps:

- delete all files in gh-pages

  ```sh
  git switch gh-pages
  git rm -rf $(git ls-files)
  git commit -m 'docs: delete gh-pages files to prepare for mike'
  ```

- check out the previous release tag and deploy it

  ```sh
  git checkout v1.0.0
  mike deploy 1.0 latest --push --update-aliases --branch gh-pages
  ```

- set the default landing page:

  ```sh
  mike set-default latest
  ```

- deploy the dev version from main

  ```sh
  git switch main
  mike deploy dev --push --update-aliases --branch gh-pages
  ```

### Basic example

[docs-mkdocs.yml](/examples/docs-mkdocs.yml)

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
- `ccbr-actions-version`: The version of ccbr_actions to install.
  **Required.** Default: `main`.
- `python-version`: The version of Python to install. **Required.**
  Default: `3.11`.
- `docs-branch`: The branch to deploy the docs website to. **Required.**
  Default: `gh-pages`.
- `github-actor`: Username of GitHub actor for the git commit when the
  docs branch is deployed. **Required.** Default:
  `41898282+github-actions[bot]`.

## Outputs

- `version`: The version of the docs being deployed..
- `alias`: The alias of the version being deployed..
