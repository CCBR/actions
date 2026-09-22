# build-docker

**`build-docker`** - Build a docker container using CCBR guidelines

This action is designed to build Docker containers according to the
format used in [CCBR/dockers2](https://github.com/CCBR/Dockers2).

> \[!WARNING\] Do **not** run this action via
> `jobs.<job_id>.container: nciccbr/ccbr_actions:...`. This action
> builds/pushes Docker images, which would require Docker-in-Docker
> (mounting the host’s Docker socket into the container) – an
> ill-advised pattern. Run this action on a normal runner instead.

The `ccbr-actions-version` input selects the version of `ccbr_actions`
installed in the image being built. It is passed to the Dockerfile as
the `CCBR_ACTIONS_VERSION` build argument.

This action:

- Resolves an effective push mode: pushing is enabled only when ‘push’
  is ‘true’ and both DockerHub credentials are provided.
- Logs in to DockerHub only when effective push mode is enabled.
- Prepares build-time variables by running a custom script.
- Checks variables and creates a README file with build details in the
  same directory as the dockerfile.
- Checks whether the DockerHub tag is stale before building.
- Builds the Docker image only when a build is needed; pushes only when
  effective push mode is enabled.
- Updates the DockerHub description with the contents of the README file
  only if the image was successfully pushed.
- Opens and merges a PR with the README updates only when the DockerHub
  description update step runs successfully.

## Usage

### Basic example

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0
  - uses: CCBR/actions/build-docker@main
    with:
      dockerfile: Dockerfile.v1
      dockerhub-namespace: ${{ secrets.DOCKERHUB_NAMESPACE }}
      dockerhub-username: ${{ secrets.DOCKERHUB_USERNAME }}
      dockerhub-token: ${{ secrets.DOCKERHUB_TOKEN }}
      suffix: dev
      push: true
      ccbr-actions-version: v0.2
      github-token: ${{ github.token }}
      github-actor: ${{ github.actor }}
      config-file: "scripts/tool_version_commands.txt"
```

For an example to manually trigger the workflow for a single docker
container, see
[build-docker-manual.yml](/examples/build-docker-manual.yml).

For an advanced example to automatically build docker containers when
files change, see
[build-docker-auto.yml](/examples/build-docker-auto.yml).

Suffix behavior: `dev` appends `-dev`, `main` or an empty value leaves
the Dockerfile tag unchanged, and any other value appends `-feat`.

## Inputs

- `dockerfile`: path to the Dockerfile in the repo
  (e.g. common/ccbr_bwa/Dockerfile). **Required.**
- `dockerhub-namespace`: dockerhub namespace or org name (e.g. nciccbr).
  **Required.** Default: `nciccbr`.
- `dockerhub-username`: dockerhub username of a user with admin
  permissions for `dockerhub-namespace`. Recommend using secrets,
  e.g. secrets.DOCKERHUB_USERNAME.
- `dockerhub-token`: dockerhub token with read & write permissions.
  Strongly recommend using secrets, e.g. secrets.DOCKERHUB_TOKEN.
- `suffix`: Suffix to add to image tag eg. “dev” to add “-dev”.
  **Required.** Default: `feat`.
- `push`: Push to DockerHub (if false, just build the container without
  pushing). **Required.** Default: `false`.
- `force_build`: Force docker image build even when the Docker Hub tag
  is up-to-date. **Required.** Default: `false`.
- `ccbr-actions-version`: The version of ccbr_actions to install in the
  image. This value is passed to the Dockerfile as CCBR_ACTIONS_VERSION.
  **Required.** Default: `latest`.
- `python-version`: The version of Python to install. **Required.**
  Default: `3.14`.
- `github-actor`: Username of GitHub actor for the git commit when the
  README is updated. **Required.** Default: `258092125+CCBR-bot[bot]`.
- `github-token`: GitHub Actions token (e.g. github.token).
  **Required.**
- `print-versions`: Whether to print tool versions in the container for
  the README file using `config-file`. Default: `true`.
- `config-file`: Relative path to config file for tool version commands
  (text format with :: delimiters). If not provided and print-versions
  is true, the default config file from ccbr_actions will be used.
  Default: `scripts/tool_version_commands.txt`.
- `gh-merge-args`: arguments for `gh pr merge`. Default: `-ds --admin`.

## Outputs

- `push_success`: Whether Docker succeeded for this run
