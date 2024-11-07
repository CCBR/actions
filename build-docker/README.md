# build-docker

**`build-docker`** - Build a docker container using CCBR guidelines

This action is designed to be used to build Docker containers according
to the CCBR format as used in
[CCBR/dockers2](https://github.com/CCBR/Dockers2).

This action:

- Logs in to DockerHub if the ‘push’ input is set to ‘true’.
- Prepares build-time variables by running a custom script.
- Checks variables and creates a temporary README file with build
  details.
- Builds and optionally pushes the Docker image using the
  docker/build-push-action.
- Lists Docker images on the runner.
- Updates the DockerHub description with the contents of the temporary
  README file if the image was successfully pushed.

## Usage

### Basic example

[docs-mkdocs.yml](/examples/build-docker-manual.yml)

``` yaml
steps:
  - uses: actions/checkout@v4
    with:
        fetch-depth: 0
  - uses: CCBR/actions/build-docker@main
    with:
        github-token: ${{ github.token }}
```

## Inputs

- `dockerfile`: path to the Dockerfile in the repo
  (e.g. common/ccbr_bwa/Dockerfile) . **Required.**
- `dockerhub-namespace`: dockerhub namespace or org name (e.g. nciccbr)
  . **Required.** Default: `nciccbr`.
- `dockerhub-username`: dockerhub username of a user with admin
  permissions for `dockerhub-namespace`. Recommend using secrets,
  e.g. secrets.DOCKERHUB_USERNAME . **Required.**
- `dockerhub-token`: dockerhub token with read & write permissions.
  Strongly recommend using secrets, e.g. secrets.DOCKERHUB_TOKEN .
- `suffix`: Suffix to add to image tag eg. “dev” to add “-dev” .
  **Required.** Default: `feat`.
- `push`: Push to DockerHub (leave unchecked to just build the container
  without pushing) . **Required.**
- `ccbr-actions-version`: The version of ccbr_actions to use .
  **Required.** Default: `main`.
- `python-version`: The version of Python to install . **Required.**
  Default: `3.11`.
- `github-actor`: Username of GitHub actor for the git commit when the
  README is updated . **Required.** Default:
  `41898282+github-actions[bot]`.
- `github-token`: GitHub Actions token (e.g. github.token) .
  **Required.**
