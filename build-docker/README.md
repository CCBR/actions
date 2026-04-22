# build-docker

**`build-docker`** - Build a docker container using CCBR guidelines

This action is designed to build Docker containers according to the
format used in [CCBR/dockers2](https://github.com/CCBR/Dockers2).

This action:

- Resolves an effective push mode: pushing is enabled only when ‘push’
  is ‘true’ and both DockerHub credentials are provided.
- Logs in to DockerHub only when effective push mode is enabled.
- Prepares build-time variables by running a custom script.
- Checks variables and creates a README file with build details in the
  same directory as the dockerfile.
- Builds the Docker image in all cases; pushes only when effective push
  mode is enabled.
- Lists Docker images on the runner.
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

## Inputs

- `dockerfile`: path to the Dockerfile in the repo
  (e.g. common/ccbr_bwa/Dockerfile). **Required.**
- `dockerhub-namespace`: dockerhub namespace or org name (e.g. nciccbr).
  **Required.** Default: `nciccbr`.
- `dockerhub-username`: dockerhub username of a user with admin
  permissions for `dockerhub-namespace`. Recommend using secrets,
  e.g. secrets.DOCKERHUB_USERNAME. **Required.**
- `dockerhub-token`: dockerhub token with read & write permissions.
  Strongly recommend using secrets, e.g. secrets.DOCKERHUB_TOKEN.
- `suffix`: Suffix to add to image tag eg. “dev” to add “-dev”.
  **Required.** Default: `feat`.
- `push`: Push to DockerHub (leave unchecked to just build the container
  without pushing). **Required.**
- `force_build`: Force docker image build even when the Docker Hub tag
  is up-to-date. **Required.**
- `ccbr-actions-version`: The version of ccbr_actions to use.
  **Required.** Default: `main`.
- `python-version`: The version of Python to install. **Required.**
  Default: `3.11`.
- `github-actor`: Username of GitHub actor for the git commit when the
  README is updated. **Required.** Default:
  `41898282+github-actions[bot]`.
- `github-token`: GitHub Actions token (e.g. github.token).
  **Required.**
- `print-versions`: Whether to print tool versions in the container for
  the README file using `config-file`. Default: `True`.
- `config-file`: Relative path to config file for tool version commands
  (text format with :: delimiters). If not provided and print-versions
  is true, the default config file from ccbr_actions will be used.
  Default: `scripts/tool_version_commands.txt`.
- `gh-merge-args`: arguments for `gh pr merge`. Default: `-ds --admin`.

## Outputs

- `push_success`: Whether Docker succeeded for this run
