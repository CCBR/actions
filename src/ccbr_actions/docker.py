"""
Prepare Docker build variables to match the legacy bash script.
"""

from __future__ import annotations

import datetime
import os
import pathlib
from typing import Dict, Optional


def base_image_name(dockerfile: str) -> str:
    """
    Get base image names from a Dockerfile.

    Matches the bash behavior: only lines starting with "FROM " are used and
    the literal "FROM " substring is removed everywhere on that line.
    """
    base_images = []
    with open(dockerfile, "r") as handle:
        for raw_line in handle:
            if raw_line.startswith("FROM "):
                base_images.append(raw_line.replace("FROM ", "").rstrip("\n"))
    return "\n".join(base_images)


def tag_from_dockerfile(dockerfile: str) -> str:
    """
    Extract the tag from the Dockerfile name (last extension).

    Mirrors bash ${bn_dockerfile##*.} behavior.
    """
    bn_dockerfile = os.path.basename(dockerfile)
    return bn_dockerfile.rsplit(".", 1)[-1]


def prepare_docker_build_variables(
    dockerfile: str,
    suffix: str,
    dockerhub_account: str,
    github_env: Optional[str] = None,
    now: Optional[datetime.datetime] = None,
) -> Dict[str, str]:
    """
    Prepare Docker build variables and optionally write them to GITHUB_ENV.

    Args:
            dockerfile (str): Path to the Dockerfile.
            suffix (str): Suffix for the image tag (e.g., "dev", "main").
            dockerhub_account (str): Docker Hub account/namespace.
            github_env (str, optional): Path to the GitHub Actions env file.
            now (datetime, optional): Override current time for deterministic output.

    Returns:
            dict: Mapping of variable names to their values.
    """
    print(f"Dockerfile: {dockerfile}")
    print(f"suffix: {suffix}")

    dt = (now or datetime.datetime.now()).strftime("%Y-%m-%d_%H:%M:%S")
    bn_dockerfile = os.path.basename(dockerfile)
    tag = tag_from_dockerfile(dockerfile)
    dn_dockerfile = os.path.dirname(dockerfile)
    reponame = os.path.basename(dn_dockerfile)
    baseimagename = base_image_name(dockerfile)

    if suffix == "dev":
        tag = f"{tag}-dev"
    elif suffix == "main" or "suffix" == "":
        tag = f"{tag}"
    else:
        tag = f"{tag}-feat"

    imagename = f"{dockerhub_account}/{reponame}:{tag}"
    mdfile = f"{dn_dockerfile}/{tag}.README.md"
    artifact_name = mdfile.replace("/", "_")

    values = {
        "DOCKERFILE_PATH": dockerfile,
        "DOCKERFILE_BASENAME": bn_dockerfile,
        "CONTEXT": str(pathlib.Path(dockerfile).parent),
        "IMAGENAME": imagename,
        "BASEIMAGENAME": baseimagename,
        "BUILD_DATE": dt,
        "BUILD_TAG": tag,
        "REPONAME": reponame,
        "MDFILE": mdfile,
        "ARTIFACT_NAME": artifact_name,
    }

    env_path = github_env or os.environ.get("GITHUB_ENV")
    if env_path:
        with open(env_path, "a") as env_handle:
            for key, value in values.items():
                env_handle.write(f"{key}={value}\n")

    return values
