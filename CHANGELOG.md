## actions development version

- fix `print_versions.py` script to work with new JSON version proposed [here](https://github.com/CCBR/Dockers2/issues/150). (#39, @kopardev)

## actions 0.2.1

- fix bug in `build-docker`, where version information was overwriting the docker container information in the README file & dockerhub description. (#35, @kelly-sovacool)

## actions 0.2.0

- new actions & example workflows:
  - `label-issue-repo-name` - Label issues & PRs with the repository name
  - `add-issue-label-list` - Update issue description with a list of issues of a given label
  - `update-cff-R` - For R packages: update the CITATION.cff file based on the DESCRIPTION file.
  - `build-docker` - Build docker containers for [CCBR/Dockers2](https://github.com/CCBR/dockers2). (#31, #33, @kelly-sovacool)
- minor documentation improvements.

## actions 0.1.3

- fix: make sure `get_latest_release_hash()` and `get_current_hash()` strip newlines in hash strings. (@kelly-sovacool)
  - this bug caused a malformed command string in `is_ancestor()`, which caused `mkdocs-mike` to fail.
- set `update-sliding-branch` to false by default in `post-release` action. (#18, @kelly-sovacool)
- fix bug that prevented `mkdocs-mike` from working on repos with no release. (#20, @kelly-sovacool)
- fix: resolve symlinks when writing files. (#23, #24, @kelly-sovacool)

## actions 0.1.2

- fix the `draft-release` action to properly use the full owner & repo name when creating a draft release. (#13, @kelly-sovacool)
- new option in `post-release` to update a sliding branch (typically named `v<major>.<minor>`) with new patch releases. (#13, #16, @kelly-sovacool)
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
