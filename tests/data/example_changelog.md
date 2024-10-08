## actions development version

development version notes go here

## actions 0.1.0

This is the first release of `ccbr_actions`! 🎉

### New actions

- `mkdocs-mike`- Deploy documentation to github pages
  using mkdocs + mike. (#1, @kelly-sovacool)
- `draft-release`- Draft a new release based on
  conventional commits and prepare release notes. (#4, @kelly-sovacool)
- `post-release` - Post-release cleanup chores, intended
  to be triggered by publishing a release. (#4, @kelly-sovacool)

### New examples

See [examples/](/examples):

- `build-nextflow.yml`
- `build-python.yml`
- `build-snakemake.yml`
- `docs-mkdocs.yml`
- `docs-quarto.yml`
- `draft-release.yml`
- `post-release.yml`
- `techdev-project.yml`
- `user-projects.yml`

### Package

`ccbr_actions` is a new Python package with helper functions for our custom GitHub Actions. (#1, @kelly-sovacool)
