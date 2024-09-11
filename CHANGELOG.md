## actions 0.1.2

- fix the `draft-release` action to properly use the full owner & repo name when creating a draft release. (#13, @kelly-sovacool)
- new option in `post-release` to update a sliding branch (typically named `major.minor`) with new patch releases. (#13, @kelly-sovacool)
- fix logic for `get_latest_release_tag()` to ignore draft releases. (#14, @kelly-sovacool)

## actions 0.1.1

- fix `draft-release` action to only use a manual version if it is provided, otherwise default to automatically determine it based on conventional commits. (#10, @kelly-sovacool)
- document one-time setup steps for `mkdocs-mike` action. (#11, @kelly-sovacool)

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
