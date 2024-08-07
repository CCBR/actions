# examples

<!--
echo "# examples\n"; for f in examples/*.yml; do title=$(echo $f | sed 's|examples/||g' | sed 's|.yml||g'); echo "## $title \n"; echo "\`\`\`yaml"; cat $f; echo "\`\`\`\n"; done > examples/README.md
-->

## build-nextflow

```yaml
name: build

on:
  push:
    branches:
      - main
      - develop
  pull_request:
    branches:
      - main
      - develop
  workflow_dispatch:
    inputs:
      test_run:
        type: boolean
        default: false
        required: true

env:
  test_run: ${{ github.event_name == 'workflow_dispatch' && github.event.inputs.test_run }}

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 2
    strategy:
      matrix:
        python-version: ["3.9"]
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"
      - name: Install nextflow
        uses: nf-core/setup-nextflow@v1
      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip setuptools
          pip install click pyyaml cffconvert
      - name: check out-of-the-box CLI script
        run: |
          bash bin/champagne --help
          cd tests/cli && ../../bin/champagne --help
      - name: Install champagne python package
        run: |
          pip install .[dev,test]
          python -c 'from champagne.src.util import chmod_bins_exec; chmod_bins_exec()'
      - name: Check CLI basics
        run: |
          which champagne
          champagne --version
          champagne --citation
      - name: Stub run
        run: |
          cd tests/cli
          champagne init
          champagne run -stub -c ci_stub.config --max_cpus 2 --max_memory 6.GB
      - name: Test run
        if: ${{ env.test_run == 'true' }}
        run: |
          cd tests/cli
          champagne init
          champagne run -profile docker -c ci_test.config
      - name: "Upload Artifact"
        uses: actions/upload-artifact@v3
        if: always() # run even if previous steps fail
        with:
          name: nextflow-log
          path: .nextflow.log
  build-status: # https://github.com/orgs/community/discussions/4324#discussioncomment-3477871
    runs-on: ubuntu-latest
    needs: [build]
    if: always()
    steps:
      - name: Successful build
        if: ${{ !(contains(needs.*.result, 'failure')) }}
        run: exit 0
      - name: Failing build
        if: ${{ contains(needs.*.result, 'failure') }}
        run: exit 1
```

## build-snakemake

```yaml
name: Tests

on:
  push:
    branches:
      - master
      - main
      - develop
  pull_request:

jobs:
  dryrun-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker://snakemake/snakemake:v7.32.4
      - name: Dry-run
        run: |
          docker run -v $PWD:/opt2 -w /opt2 snakemake/snakemake:v7.32.4 \
            ./bin/renee run \
              --input .tests/KO_S3.R1.fastq.gz .tests/KO_S3.R2.fastq.gz .tests/KO_S4.R1.fastq.gz .tests/KO_S4.R2.fastq.gz .tests/WT_S1.R1.fastq.gz .tests/WT_S1.R2.fastq.gz .tests/WT_S2.R1.fastq.gz .tests/WT_S2.R2.fastq.gz \
              --output output \
              --genome config/genomes/biowulf/hg38_30.json \
              --shared-resources .tests/shared_resources/ \
              --mode local \
              --dry-run
      - name: Lint
        continue-on-error: true
        run: |
          docker run -v $PWD:/opt2 snakemake/snakemake:v7.32.4 \
            snakemake --lint -s /opt2/output/workflow/Snakefile -d /opt2/output || \
          echo 'There may have been a few warnings or errors. Please read through the log to determine if its harmless.'

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11"]
        snakemake-version: ["7.32.3"]
    steps:
      - uses: actions/checkout@v4
      - uses: mamba-org/setup-micromamba@v1
        with:
          environment-name: test
          cache-environment: true
          condarc: |
            channels:
              - conda-forge
              - bioconda
          create-args: >-
            python=${{ matrix.python-version }}
            snakemake=${{ matrix.snakemake-version }}
            setuptools
            pip
            pytest
      - name: check CLI basics
        run: |
          ./bin/renee --help
          ./bin/renee --version
        shell: micromamba-shell {0}
      - name: pip install python package
        run: |
          pip install .[dev,test]
        shell: micromamba-shell {0}
      - name: Test
        run: |
          python -m pytest
        env:
          TMPDIR: ${{ runner.temp }}
        shell: micromamba-shell {0}

  build-status: # https://github.com/orgs/community/discussions/4324#discussioncomment-3477871
    runs-on: ubuntu-latest
    needs: [dryrun-lint, test]
    if: always()
    steps:
      - name: Successful build
        if: ${{ !(contains(needs.*.result, 'failure')) }}
        run: exit 0
      - name: Failing build
        if: ${{ contains(needs.*.result, 'failure') }}
        run: exit 1
```

## docs-mkdocs

```yaml
name: docs
on:
  workflow_dispatch:
  release:
    types:
      - published
  push:
    branches:
      - main
    paths:
      - "docs/**"
      - "**.md"
      - .github/workflows/docs-mkdocs.yml
      - mkdocs.yml

jobs:
  mkdocs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: CCBR/actions/mkdocs-mike@main
        with:
          github-token: ${{ github.token }}
```

## docs-quarto

```yaml
name: docs

on:
  workflow_dispatch:
  push:
    branches: main
    paths:
      - "docs/**"
      - ".github/workflows/quarto-publish.yml"

permissions:
  contents: write
  pages: write

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Quarto
        uses: quarto-dev/quarto-actions/setup@v2

      - name: Publish to GitHub Pages (and render)
        uses: quarto-dev/quarto-actions/publish@v2
        with:
          target: gh-pages
          path: docs/
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## draft-release

```yaml
name: draft-release

on:
  workflow_dispatch:
    inputs:
      version_tag:
        description: |
          Semantic version tag for next release.
          If not provided, it will be determined based on conventional commit history.
          Example: v2.5.11
        required: false
        type: string
        default: ""

env:
  GH_TOKEN: ${{ github.token }}
  BRANCH: release-draft

jobs:
  draft-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # required to include tags
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
          cache: "pip"
      - run: pip install cffconvert>=2.0.0 pyyaml

      - name: Get Date
        run: |
          echo "DATE=$(date +"%Y-%m-%d")" >> "$GITHUB_ENV"

      - name: Get current and next versions
        id: semver
        uses: ietf-tools/semver-action@v1
        with:
          token: ${{ github.token }}
          branch: ${{ github.ref_name }}

      - name: Set version variables
        shell: python {0}
        run: |
          import os
          import re
          import warnings

          convco_version = "${{ steps.semver.outputs.next }}"
          if "${{ github.event_name }}" == 'workflow_dispatch' and "${{ github.event.inputs.version_tag }}":
            next_version = "${{ github.event.inputs.version_tag }}"
            if next_version != convco_version:
              warnings.warn(f"Manual version ({next_version}) not equal to version determined by conventional commit history ({convco_version})")
          else:
            next_version = convco_version

          with open(os.getenv("GITHUB_ENV"), 'a') as out_env:
            out_env.write(f"NEXT_VERSION={next_version}\n")
            out_env.write(f"NEXT_STRICT={next_version.strip('v')}\n")
          current_version = "${{ steps.semver.outputs.current }}"

          # assert semantic version pattern
          semver_pattern = 'v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?'
          next_semver = re.match(semver_pattern, next_version)
          if not next_semver:
            extra_msg = ''
            if not next_version.startswith('v'):
              extra_msg = "The tag does not start with 'v'."
            raise ValueError(f"Tag {next_version} does not match semantic versioning guidelines. {extra_msg}\nView the guidelines here: https://semver.org/")

          # assert next version is only 1 greater than current
          current_semver = re.match(semver_pattern, current_version)
          groups = ['major', 'minor', 'patch']
          greater = sum([next_semver.group(grp) > current_semver.group(grp) for grp in groups])
          if not (greater == 1):
            raise ValueError(f"Next version must only increment one number at a time. Current version: {current_version}. Proposed next version: {next_version}")

      - name: Get release notes, update changelog & version file
        shell: python {0}
        run: |
          import os
          latest_version = "${{ steps.semver.outputs.current }}".strip('v')
          next_version = "${{ env.NEXT_STRICT }}"

          changelog_lines = list()
          next_release_lines = list()
          for_next = True
          with open("CHANGELOG.md", "r") as infile:
            for line in infile:
              if line.startswith('#') and 'development version' in line:
                line = line.replace('development version', next_version)
              elif latest_version in line:
                for_next = False

              changelog_lines.append(line)
              if for_next and next_version not in line:
                next_release_lines.append(line)

          with open(".github/latest-release.md", "w") as outfile:
            outfile.writelines(next_release_lines)
          with open('CHANGELOG.md', 'w') as outfile:
            outfile.writelines(changelog_lines)
          with open("VERSION", "w") as outfile:
            outfile.write(f"{next_version}\n")

      - name: Update citation
        shell: python {0}
        run: |
          from cffconvert.cli.create_citation import create_citation
          from cffconvert.cli.validate_or_write_output import validate_or_write_output
          import yaml

          citation = create_citation('CITATION.cff', None)
          citation._implementation.cffobj['version'] = "${{ env.NEXT_VERSION }}"
          citation._implementation.cffobj['date-released'] = "${{ env.DATE }}"
          with open('CITATION.cff', 'w') as outfile:
            outfile.write(yaml.dump(citation._implementation.cffobj, sort_keys=False, indent=2))

      - uses: pre-commit/action@v3.0.0
        with:
          extra_args: --files CITATION.cff CHANGELOG.md VERSION
        continue-on-error: true

      - name: Commit & push to branch
        run: |
          git config --local user.name "github-actions[bot]"
          git config --local user.email "41898282+github-actions[bot]@users.noreply.github.com"

          git push origin --delete ${{ env.BRANCH }} || echo "No ${{ env.BRANCH }} branch to delete"
          git switch -c ${{ env.BRANCH }} || git switch ${{ env.BRANCH }}
          git merge --ff-only ${{ github.ref_name }}

          git add CITATION.cff CHANGELOG.md VERSION
          git commit -m 'chore: prepare release ${{ env.NEXT_VERSION }}'
          git push --set-upstream origin ${{ env.BRANCH }}

          echo "COMMIT_HASH=$(git rev-parse HEAD)" >> "$GITHUB_ENV"

      - name: Tag & draft release
        run: |
          gh release create ${{ env.NEXT_VERSION }} \
            --draft \
            --notes-file .github/latest-release.md \
            --target ${{ env.COMMIT_HASH }} \
            --title "${{ github.event.repository.name }} ${{ env.NEXT_STRICT }}"

      - name: Next steps
        run: |
          echo "Next steps: Take a look at the changes in the ${{ env.BRANCH }} branch and the release notes on the web. If everything is correct, publish the release. Otherwise, delete the release draft and cut the release manually."
```

## post-release

```yaml
name: post-release

on:
  release:
    types:
      - published

env:
  GH_TOKEN: ${{ github.token }}
  BRANCH: release/${{ github.ref_name }}

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Configure git
        run: |
          git config --local user.name "github-actions[bot]"
          git config --local user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git push origin --delete ${{ env.BRANCH }} || echo "No ${{ env.BRANCH }} branch to delete"
          git switch -c ${{ env.BRANCH }}
      - name: Bump changelog & version
        shell: python {0}
        run: |
          with open("CHANGELOG.md", "r") as infile:
            lines = infile.readlines()
          lines.insert(0, "## ${{ github.event.repository.name }} development version\n\n")
          with open("CHANGELOG.md", "w") as outfile:
            outfile.writelines(lines)

          with open('VERSION', 'r') as infile:
            version = infile.read().strip()
          with open('VERSION', 'w') as outfile:
            outfile.write(f"{version}-dev\n")

      - uses: pre-commit/action@v3.0.0
        with:
          extra_args: --files CITATION.cff CHANGELOG.md VERSION
        continue-on-error: true

      - name: Open pull request
        run: |
          git add CHANGELOG.md VERSION
          git commit -m "chore: bump changelog & version after release of ${{ github.ref_name }}"
          git push --set-upstream origin ${{ env.BRANCH }}

          gh pr create \
            --fill-first \
            --reviewer ${{ github.triggering_actor }}

      - name: Clean up release-draft branch
        run: |
          git push origin --delete release-draft || echo "No release-draft branch to delete"
```

## techdev-project

```yaml
name: Add issues/PRs to the TechDev project

on:
  issues:
    types:
      - opened
  pull_request:
    types:
      - opened

jobs:
  add-to-project:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/add-to-project@v1.0.2
        with:
          project-url: https://github.com/orgs/CCBR/projects/17
          github-token: ${{ secrets.ADD_TO_PROJECT_PAT }}
```

## user-projects

```yaml
name: Add to personal projects

on:
  issues:
    types:
      - assigned
  pull_request:
    types:
      - assigned

jobs:
  add-to-project:
    uses: CCBR/.github/.github/workflows/auto-add-user-project.yml@v0.1.0
    secrets: inherit
```
