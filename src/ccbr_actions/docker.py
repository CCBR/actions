"""
Prepare Docker build variables to match the legacy bash script.
"""

from __future__ import annotations

import datetime
import os
import pathlib
import subprocess
from typing import Dict, Optional

import requests

from .actions import set_output


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
    if "." not in dockerfile:
        raise ValueError(
            f"The dockerfile {dockerfile} must contain a dot to separate the version tag, e.g. Dockerfile.v1"
        )
    bn_dockerfile = os.path.basename(dockerfile)
    return bn_dockerfile.split(".", 1)[-1]


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


def parse_iso_timestamp(raw: str) -> datetime.datetime:
    """
    Parse an ISO timestamp and normalize it to UTC.

    Args:
        raw (str): ISO8601 timestamp (for example ``2026-01-01T12:00:00Z``).

    Returns:
        datetime.datetime: Timezone-aware UTC datetime.
    """
    return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
        datetime.timezone.utc
    )


def image_tag_from_image_name(image_name: str) -> str:
    """
    Extract the tag suffix from a Docker image name.

    Args:
        image_name (str): Docker image reference, optionally including a tag.

    Returns:
        str: Tag string, or an empty string if no tag is present.
    """
    reference = image_name.split("@", 1)[0]
    last_slash = reference.rfind("/")
    last_colon = reference.rfind(":")
    tag = ""
    if last_colon > last_slash:
        tag = reference[last_colon + 1 :]
    return tag


def dockerfile_last_commit_iso(dockerfile_path: str) -> str:
    """
    Get the last git commit timestamp for the Dockerfile.

    Args:
        dockerfile_path (str): Path to the Dockerfile in the repository.

    Returns:
        str: ISO8601 timestamp from git ``%cI`` format, or an empty string
        when the file is missing, untracked, or has no git history.
    """
    last_commit_iso = ""
    try:
        last_commit_iso = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", dockerfile_path],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        last_commit_iso = ""
    return last_commit_iso


def dockerhub_tag_last_updated(
    dockerhub_namespace: str,
    repo_name: str,
    image_tag: str,
    timeout: int = 20,
    session=requests,
) -> Optional[str]:
    """
    Get Docker Hub tag ``last_updated`` timestamp.

    Args:
        dockerhub_namespace (str): Docker Hub namespace/org.
        repo_name (str): Docker Hub repository name.
        image_tag (str): Docker image tag.
        timeout (int): HTTP timeout in seconds.
        session: Object with a requests-compatible ``get`` method.

    Returns:
        str or None: ISO8601 ``last_updated`` value, or ``None`` when tag is absent.
    """
    tag_url = (
        f"https://hub.docker.com/v2/namespaces/{dockerhub_namespace}/"
        f"repositories/{repo_name}/tags/{image_tag}"
    )
    response = session.get(tag_url, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    return (payload.get("last_updated") or "").strip()


def evaluate_docker_build_staleness(
    dockerfile_path: str,
    image_name: str,
    dockerhub_namespace: str,
    repo_name: str,
) -> Dict[str, str]:
    """
    Decide whether to build a Docker image based on Dockerfile git history and tag freshness.

    Args:
        dockerfile_path (str): Path to Dockerfile in repository.
        image_name (str): Target image name, including tag.
        dockerhub_namespace (str): Docker Hub namespace/org.
        repo_name (str): Docker Hub repository name.

    Returns:
        dict: Build decision fields suitable for GitHub Action outputs.
    """
    should_build = True
    tag_exists = False
    tag_last_updated = ""
    reason = "default_build"

    dockerfile_last_commit = dockerfile_last_commit_iso(dockerfile_path)
    if not dockerfile_last_commit:
        reason = "no_git_history_for_dockerfile"
    else:
        image_tag = image_tag_from_image_name(image_name)
        if not image_tag:
            reason = "missing_image_tag"
        else:
            try:
                tag_last_updated_value = dockerhub_tag_last_updated(
                    dockerhub_namespace=dockerhub_namespace,
                    repo_name=repo_name,
                    image_tag=image_tag,
                )
                if tag_last_updated_value is None:
                    reason = "tag_not_found"
                else:
                    tag_exists = True
                    tag_last_updated = tag_last_updated_value
                    if tag_last_updated:
                        dockerfile_dt = parse_iso_timestamp(dockerfile_last_commit)
                        tag_dt = parse_iso_timestamp(tag_last_updated)
                        should_build = dockerfile_dt > tag_dt
                        if should_build:
                            reason = "dockerfile_changed_after_tag"
                        else:
                            reason = "tag_is_newer_or_equal_to_dockerfile"
                    else:
                        reason = "tag_missing_last_updated"
            except requests.HTTPError as exc:
                status_code = getattr(exc.response, "status_code", "unknown")
                reason = f"dockerhub_http_{status_code}"
            except Exception as exc:
                reason = f"dockerhub_lookup_failed_{type(exc).__name__}"

    return {
        "should_build": "true" if should_build else "false",
        "tag_exists": "true" if tag_exists else "false",
        "dockerfile_last_commit": dockerfile_last_commit,
        "tag_last_updated": tag_last_updated,
        "reason": reason,
    }


def evaluate_docker_build_staleness_and_set_outputs(
    dockerfile_path: str,
    image_name: str,
    dockerhub_namespace: str,
    repo_name: str,
) -> Dict[str, str]:
    """
    Evaluate Docker build staleness and set step outputs.

    Args:
        dockerfile_path (str): Path to Dockerfile in repository.
        image_name (str): Target image name, including tag.
        dockerhub_namespace (str): Docker Hub namespace/org.
        repo_name (str): Docker Hub repository name.

    Returns:
        dict: Build decision fields written to GitHub Action outputs.
    """
    result = evaluate_docker_build_staleness(
        dockerfile_path=dockerfile_path,
        image_name=image_name,
        dockerhub_namespace=dockerhub_namespace,
        repo_name=repo_name,
    )
    for name, value in result.items():
        set_output(name, value)

    if result["should_build"] == "true":
        print(f"::notice::Will build image. reason={result['reason']}")
    else:
        print(
            "::notice::Skipping docker build because Docker Hub tag is up-to-date "
            f"(dockerfile_last_commit={result['dockerfile_last_commit']}, "
            f"tag_last_updated={result['tag_last_updated']})."
        )

    return result
