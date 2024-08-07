# CCBR Actions

GitHub Actions for CCBR repos

## Examples

See [CCBR/actions/examples](examples) for workflow examples.
You can copy and paste these into your own repositories in `.github/workflows/`.

## Actions

- [mkdocs-mike](mkdocs-mike/README.md): Deploy documentation to github pages using mkdocs + mike.

## Package

This repo contains a python package with helper functions for some of our
custom actions.
You do not need to install anything in order to use the example workflows,
as the actions install their dependencies as needed.
However, you can install the package if you wish to use it outside of GitHub Actions.

### Installation

You will need the github CLI installed:
https://github.com/cli/cli#installation

(this is pre-installed on all github actions runners)

Then install it with pip:

```bash
pip install git+https://github.com/CCBR/ccbr_actions
```

Or install it from a specific version or branch with:

```bash
pip install git+https://github.com/CCBR/ccbr_actions
```
