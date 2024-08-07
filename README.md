# CCBR Actions

GitHub Actions for CCBR repos

[![build](https://github.com/CCBR/actions/actions/workflows/build-python.yml/badge.svg)](https://github.com/CCBR/actions/actions/workflows/build-python.yml)
[![codecov](https://codecov.io/gh/CCBR/actions/graph/badge.svg?token=yCtBbX4tap)](https://codecov.io/gh/CCBR/actions)

## Examples

See [CCBR/actions/examples](examples) for workflow examples.
You can copy and paste these into your own repository in `.github/workflows/`
and modify them for your needs.

<!--
```sh
for f in examples/*.yml; do
    title=$(echo $f | sed 's|examples/||g' | sed 's|.yml||g')
    echo "- [$title]($f)"
done | pbcopy
```
-->

- [build-nextflow](examples/build-nextflow.yml)
- [build-snakemake](examples/build-snakemake.yml)
- [docs-mkdocs](examples/docs-mkdocs.yml)
- [docs-quarto](examples/docs-quarto.yml)
- [draft-release](examples/draft-release.yml)
- [post-release](examples/post-release.yml)
- [techdev-project](examples/techdev-project.yml)
- [user-projects](examples/user-projects.yml)

## Actions

- [mkdocs-mike](mkdocs-mike/README.md): Deploy documentation to github pages using mkdocs + mike.

## Package

This repo contains a python package with helper functions for some of our
custom actions.
You do not need to install anything in order to use the example workflows,
as the actions install their dependencies as needed.
However, you can install the package if you wish to use it outside of GitHub Actions.

### Installation

You will need the GitHub CLI installed:
https://github.com/cli/cli#installation

(this is pre-installed on all github actions runners)

Then install the `ccbr_actions` package with pip:

```bash
pip install git+https://github.com/CCBR/ccbr_actions
```

Or install it from a specific version or branch with:

```bash
pip install git+https://github.com/CCBR/ccbr_actions
```
