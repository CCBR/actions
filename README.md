<!-- README.md is generated from README.qmd. Please edit that file -->

# CCBR actions 🤖

GitHub Actions for CCBR repos

[![build](https://github.com/CCBR/actions/actions/workflows/build-python.yml/badge.svg)](https://github.com/CCBR/actions/actions/workflows/build-python.yml)
[![codecov](https://codecov.io/gh/CCBR/actions/graph/badge.svg?token=yCtBbX4tap)](https://codecov.io/gh/CCBR/actions)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.13761059.svg)](https://doi.org/10.5281/zenodo.13761059)

## Examples

See [examples/](examples) for workflow examples. You can copy these to
your own repository in the `.github/workflows/` directory and modify
them for your needs.

- [auto-format](examples/auto-format.yml)
- [build-nextflow](examples/build-nextflow.yml)
- [build-python](examples/build-python.yml)
- [build-snakemake](examples/build-snakemake.yml)
- [docs-mkdocs](examples/docs-mkdocs.yml)
- [docs-quarto](examples/docs-quarto.yml)
- [draft-release](examples/draft-release.yml)
- [post-release](examples/post-release.yml)
- [techdev-project](examples/techdev-project.yml)
- [user-projects](examples/user-projects.yml)

## Actions

Custom actions used in our github workflows.

- [draft-release](draft-release) - Draft a new release based on
  conventional commits and prepare release notes
- [mkdocs-mike](mkdocs-mike) - Deploy documentation to github pages
  using mkdocs + mike
- [post-release](post-release) - Post-release cleanup chores, intended
  to be triggered by publishing a release

## Package

This repo contains a python package with helper functions for some of
our custom actions. You do not need to install anything in order to use
the example workflows, as the actions install their dependencies as
needed. However, you can install the package if you wish to use it
outside of GitHub Actions.

### Installation

You will need the GitHub CLI installed (this is pre-installed on all
github actions runners): https://github.com/cli/cli#installation

Then install the `ccbr_actions` package with pip:

```bash
pip install git+https://github.com/CCBR/actions
```

Or install it from a specific version or branch with:

```bash
pip install git+https://github.com/CCBR/actions@v0.1
```

## Help & Contributing

Come across a **bug**? Open an
[issue](https://github.com/CCBR/actions/issues) and include a minimal
reproducible example.

Have a **question**? Ask it in
[discussions](https://github.com/CCBR/actions/discussions).

Want to **contribute** to this project? Check out the [contributing
guidelines](.github/CONTRIBUTING.md).

## Citation

Please cite this software if you use it in a publication:

> Sovacool K., Koparde V. (2024). CCBR actions: GitHub Actions for CCBR
> repos (version v0.1.3). DOI: 10.5281/zenodo.13761059 URL:
> https://ccbr.github.io/actions/

### Bibtex entry

    @misc{YourReferenceHere,
    author = {Sovacool, Kelly and Koparde, Vishal},
    doi = {10.5281/zenodo.13761059},
    month = {9},
    title = {CCBR actions: GitHub Actions for CCBR repos},
    url = {https://ccbr.github.io/actions/},
    year = {2024}
    }
