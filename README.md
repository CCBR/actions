# CCBR actions 🤖

<!-- README.md is generated from README.qmd. Please edit that file -->

GitHub Actions for CCBR repos

[![build](https://github.com/CCBR/actions/actions/workflows/build-python.yml/badge.svg)](https://github.com/CCBR/actions/actions/workflows/build-python.yml)
[![codecov](https://codecov.io/gh/CCBR/actions/graph/badge.svg?token=yCtBbX4tap)](https://codecov.io/gh/CCBR/actions)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.13761059.svg)](https://doi.org/10.5281/zenodo.13761059)

## Examples

See [examples/](examples) for workflow examples. You can copy these to
your own repository in the `.github/workflows/` directory and modify
them for your needs.

- [add-issue-label-list](examples/add-issue-label-list.yml)
- [auto-format](examples/auto-format.yml)
- [build-docker-auto](examples/build-docker-auto.yml)
- [build-docker-manual](examples/build-docker-manual.yml)
- [build-nextflow](examples/build-nextflow.yml)
- [build-python](examples/build-python.yml)
- [build-snakemake](examples/build-snakemake.yml)
- [docs-mkdocs](examples/docs-mkdocs.yml)
- [docs-quarto](examples/docs-quarto.yml)
- [draft-release](examples/draft-release.yml)
- [label-issues-repo-name](examples/label-issues-repo-name.yml)
- [post-release](examples/post-release.yml)
- [techdev-project](examples/techdev-project.yml)
- [update-cff-R](examples/update-cff-R.yml)
- [user-projects](examples/user-projects.yml)

View the [GitHub Actions docs](https://docs.github.com/en/actions) for
more information on how to write and use GitHub Actions workflows.

## Actions

Custom actions used in our github workflows.

- [add-issue-label-list](add-issue-label-list) - Update issue
  description with a list of issues of a given label
- [build-docker](build-docker) - Build a docker container using CCBR
  guidelines
- [draft-release](draft-release) - Draft a new release based on
  conventional commits and prepare release notes
- [label-issue-repo-name](label-issue-repo-name) - Label issues & PRs
  with the repository name
- [mkdocs-mike](mkdocs-mike) - Deploy documentation to github pages
  using mkdocs + mike
- [post-release](post-release) - Post-release cleanup chores, intended
  to be triggered by publishing a release

## Package

`ccbr_actions` is a Python package with helper functions used by our
custom GitHub Actions. You do not need to install the package in order
to use the example workflows, as the actions install their dependencies
as needed. However, you can install the package if you wish to use it
outside of GitHub Actions or contribute changes.

### Installation

You will need the GitHub CLI installed (this is pre-installed on all
github actions runners): <https://github.com/cli/cli#installation>

Then install the `ccbr_actions` package with pip:

```bash
pip install git+https://github.com/CCBR/actions
```

Or install it from a specific version or branch with:

```bash
pip install git+https://github.com/CCBR/actions@v0.1
```

View the package documentation
[here](https://CCBR.github.io/actions/package).

## Help & Contributing

Come across a **bug**? Open an
[issue](https://github.com/CCBR/actions/issues) and include a minimal
reproducible example.

Have a **question**? Ask it in
[discussions](https://github.com/CCBR/actions/discussions).

Want to **contribute** to this project? Check out the [contributing
guidelines](https://CCBR.github.io/actions/CONTRIBUTING).

## Citation

Please cite this software if you use it in a publication:

> Sovacool K., Koparde V. (2024). CCBR actions: GitHub Actions for CCBR
> repos (version v0.2.3). DOI: 10.5281/zenodo.13761059 URL:
> https://ccbr.github.io/actions/

### Bibtex entry

```bibtex
@misc{YourReferenceHere,
author = {Sovacool, Kelly and Koparde, Vishal},
doi = {10.5281/zenodo.13761059},
month = {12},
title = {CCBR actions: GitHub Actions for CCBR repos},
url = {https://ccbr.github.io/actions/},
year = {2024}
}
```

## Inspiration

This project was inspired by
[r-lib/actions](https://github.com/r-lib/actions/) and
[{usethis}](https://usethis.r-lib.org/reference/github_actions.html).
Check them out for actions, workflows, and helper functions for R
packages!
