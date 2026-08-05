FROM python:3.11-slim

ARG CCBR_ACTIONS_VERSION=main

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "git+https://github.com/CCBR/actions@${CCBR_ACTIONS_VERSION}"
