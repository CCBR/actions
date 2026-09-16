FROM python:3.14-slim

ARG CCBR_ACTIONS_VERSION=latest

# marks that setup steps (python/pip/R) are already available, so composite
# actions can skip them when this image is used via `jobs.<id>.container`
ENV CCBR_ACTIONS_DOCKER=true

RUN apt-get update && \
    apt-get install --no-install-recommends -y git r-base && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "git+https://github.com/CCBR/actions@${CCBR_ACTIONS_VERSION}"

RUN Rscript -e "install.packages('cffr', repos = 'https://cloud.r-project.org')"
