# install-r-pak

**`Install R + pak`** - Install R and dependencies with pak

Install R package dependencies with pak

## Usage

The repository must have a `DESCRIPTION` file at the root with any
dependencies listed.

Additional dependencies can optionally be recorded in a `versions-file`,
which will be read and passed along to the `extra-packages` argument of
[`setup-r-dependencies`](https://github.com/r-lib/actions/tree/v2-branch/setup-r-dependencies).

### Basic example

[R-CMD-check.yaml](/examples/R-CMD-check.yaml)

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: CCBR/actions/install-r-pak
    with:
      extra-packages: local::.
```

### Customized inputs

[R-CMD-check.yaml](/examples/R-CMD-check.yaml)

```yaml
jobs:
  R-CMD-check:
    strategy:
      fail-fast: false
      matrix:
        config:
          - { os: ubuntu-latest, r: "release" }
          - { os: ubuntu-latest, r: "oldrel-1" }

    runs-on: ${{ matrix.config.os }}
    name: ${{ matrix.config.os }} (${{ matrix.config.r }})
    steps:
      - uses: actions/checkout@v4

      - uses: CCBR/actions/install-r-pak
        with:
          versions-file: .github/package-versions.txt
          extra-packages: local::.
          needs: dev
          r-version: ${{ matrix.config.r }}
          http-user-agent: ${{ matrix.config.http-user-agent }}
```

## Inputs

- `r-version`: The version of R to install. Default: `release`.
- `http-user-agent`: .
- `use-public-rspm`: . Default: `True`.
- `versions-file`: File with content to pass to the extra-packages
  argument of setup-r-dependencies.
- `extra-packages`: More packages to install in addition to those
  specified in versions-file.
- `needs`: Config/Needs field from DESCRIPTION to pass along to
  setup-r-dependencies.
