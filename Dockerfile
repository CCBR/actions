FROM python:3.14-slim

ARG CCBR_ACTIONS_VERSION=latest

# marks that setup steps (python/pip/R) are already available, so composite
# actions can skip them when this image is used via `jobs.<id>.container`
ENV CCBR_ACTIONS_DOCKER=true

# cffr's dependencies (e.g. git2r) build from source on Debian, so pull in a
# toolchain temporarily and drop it again once the compiled package is installed
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
      gh \
      git \
      r-base \
      build-essential \
      r-base-dev \
      libgit2-dev \
      libssl-dev \
      libcurl4-openssl-dev \
      zlib1g-dev \
      pkg-config && \
    Rscript -e "install.packages('cffr', repos = 'https://cloud.r-project.org')" && \
    apt-get purge -y --auto-remove \
      build-essential \
      r-base-dev \
      libgit2-dev \
      libssl-dev \
      libcurl4-openssl-dev \
      zlib1g-dev \
      pkg-config && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "git+https://github.com/CCBR/actions@${CCBR_ACTIONS_VERSION}"

# GitHub Actions job containers must run as root to access runner mounts.
RUN test "$(id -u)" -eq 0
