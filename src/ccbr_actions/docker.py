"""
Prepare Docker build variables to match the legacy bash script.
"""

from __future__ import annotations

import dataclasses
import datetime
import os
import pathlib
import re
import subprocess

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
    bn_dockerfile = os.path.basename(dockerfile)
    if "." not in bn_dockerfile:
        raise ValueError(
            f"The dockerfile {dockerfile} must contain a dot to separate the version tag, e.g. Dockerfile.v1"
        )
    return bn_dockerfile.split(".", 1)[-1]


def prepare_docker_build_variables(
    dockerfile: str,
    suffix: str,
    dockerhub_account: str,
    github_env: str | None = None,
    now: datetime.datetime | None = None,
) -> dict[str, str]:
    """
    Prepare Docker build variables and optionally write them to GITHUB_ENV.

    For a root-level Dockerfile, derive the image repository name from
    GITHUB_REPOSITORY and write the README path relative to the workspace.

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

    dt = (now or datetime.datetime.now(tz=datetime.timezone.utc)).strftime(
        "%Y-%m-%d_%H:%M:%S"
    )
    bn_dockerfile = os.path.basename(dockerfile)
    tag = tag_from_dockerfile(dockerfile)
    dn_dockerfile = os.path.dirname(os.path.normpath(dockerfile))
    if not dn_dockerfile:
        dockerfile = os.path.normpath(dockerfile)
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        owner, separator, repo = repository.partition("/")
        reponame = re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")
        if not owner or not separator or not reponame:
            raise ValueError(
                "GITHUB_REPOSITORY must contain an owner and a valid repository "
                "name when building a root-level Dockerfile"
            )
    else:
        reponame = os.path.basename(dn_dockerfile)
    baseimagename = base_image_name(dockerfile)

    if suffix == "dev":
        tag = f"{tag}-dev"
    elif suffix in ("main", ""):
        tag = f"{tag}"
    else:
        tag = f"{tag}-feat"

    imagename = f"{dockerhub_account}/{reponame}:{tag}"
    mdfile = os.path.join(dn_dockerfile, f"{tag}.README.md")
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
            env_handle.writelines(f"{key}={value}\n" for key, value in values.items())

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


REGISTRY_MANIFEST_MEDIA_TYPES = (
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json, "
    "application/vnd.oci.image.manifest.v1+json, "
    "application/vnd.docker.distribution.manifest.v2+json"
)


@dataclasses.dataclass
class RegistryTag:
    """
    Published state of an image tag in a registry.

    Attributes:
        last_updated (str): ISO8601 time the tag was last published, or an
            empty string when the registry does not report it.
        platforms (set[str]): Published ``os/arch[/variant]`` platforms.
    """

    last_updated: str
    platforms: set[str]


def format_platform(os_name: str, architecture: str, variant: str | None = "") -> str:
    """
    Format a platform as ``os/arch[/variant]``.

    Args:
        os_name (str): Operating system, e.g. ``linux``.
        architecture (str): CPU architecture, e.g. ``arm64``.
        variant (str, optional): CPU variant, e.g. ``v7``.

    Returns:
        str: Platform string.
    """
    return pathlib.PurePosixPath(os_name, architecture, variant or "").as_posix()


def platform_is_published(requested: str, published: set[str]) -> bool:
    """
    Check whether a requested platform is among the published platforms.

    A requested platform without a variant matches any published variant of
    the same OS and architecture (e.g. ``linux/arm64`` matches ``linux/arm64/v8``).

    Args:
        requested (str): Requested ``os/arch[/variant]`` platform.
        published (set[str]): Published platforms.

    Returns:
        bool: Whether the requested platform is published.
    """
    requested_parts = requested.strip().lower().split("/")
    for platform in published:
        parts = platform.lower().split("/")
        if parts[:2] == requested_parts[:2] and (
            len(requested_parts) < 3 or parts[2:3] == requested_parts[2:3]
        ):
            return True
    return False


def dockerhub_tag_info(
    dockerhub_namespace: str,
    repo_name: str,
    image_tag: str,
    timeout: int = 20,
    session=requests,
) -> RegistryTag | None:
    """
    Get the published state of a Docker Hub tag.

    Args:
        dockerhub_namespace (str): Docker Hub namespace/org.
        repo_name (str): Docker Hub repository name.
        image_tag (str): Docker image tag.
        timeout (int): HTTP timeout in seconds.
        session: Object with a requests-compatible ``get`` method.

    Returns:
        RegistryTag or None: Tag state, or ``None`` when the tag is absent.
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
    platforms = {
        format_platform(
            image.get("os"), image.get("architecture"), image.get("variant")
        )
        for image in payload.get("images") or []
        if image.get("os") and image.get("os") != "unknown"
    }
    return RegistryTag(
        last_updated=(payload.get("last_updated") or "").strip(),
        platforms=platforms,
    )


def dockerhub_tag_last_updated(
    dockerhub_namespace: str,
    repo_name: str,
    image_tag: str,
    timeout: int = 20,
    session=requests,
) -> str | None:
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
    tag = dockerhub_tag_info(
        dockerhub_namespace=dockerhub_namespace,
        repo_name=repo_name,
        image_tag=image_tag,
        timeout=timeout,
        session=session,
    )
    return None if tag is None else tag.last_updated


def ghcr_tag_info(
    ghcr_namespace: str,
    repo_name: str,
    image_tag: str,
    github_token: str = "",
    timeout: int = 20,
    session=requests,
) -> RegistryTag | None:
    """
    Get the published state of a GitHub Container Registry tag.

    The publish time is the oldest image config ``created`` time among the
    tag's platform images, which buildx sets to the build time.

    Args:
        ghcr_namespace (str): GHCR owner or organization.
        repo_name (str): GHCR image repository name.
        image_tag (str): Docker image tag.
        github_token (str): Token for private packages; public packages are
            read anonymously when empty.
        timeout (int): HTTP timeout in seconds.
        session: Object with a requests-compatible ``get`` method.

    Returns:
        RegistryTag or None: Tag state, or ``None`` when the tag is absent.
    """
    repository = f"{ghcr_namespace.lower()}/{repo_name.lower()}"
    token_response = session.get(
        "https://ghcr.io/token",
        params={"scope": f"repository:{repository}:pull", "service": "ghcr.io"},
        auth=("token", github_token) if github_token else None,
        timeout=timeout,
    )
    token_response.raise_for_status()
    headers = {
        "Authorization": f"Bearer {token_response.json()['token']}",
        "Accept": REGISTRY_MANIFEST_MEDIA_TYPES,
    }

    def get_json(path: str) -> dict:
        response = session.get(
            f"https://ghcr.io/v2/{repository}/{path}", headers=headers, timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    response = session.get(
        f"https://ghcr.io/v2/{repository}/manifests/{image_tag}",
        headers=headers,
        timeout=timeout,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    manifest = response.json()

    if "manifests" in manifest:
        image_manifests = [
            get_json(f"manifests/{entry['digest']}")
            for entry in manifest["manifests"]
            if (entry.get("platform") or {}).get("os", "unknown") != "unknown"
        ]
    else:
        image_manifests = [manifest]

    platforms = set()
    created_times = []
    for image_manifest in image_manifests:
        config = get_json(f"blobs/{image_manifest['config']['digest']}")
        platforms.add(
            format_platform(
                config.get("os"), config.get("architecture"), config.get("variant")
            )
        )
        if config.get("created"):
            created_times.append(config["created"])

    last_updated = min(created_times, key=parse_iso_timestamp) if created_times else ""
    return RegistryTag(last_updated=last_updated, platforms=platforms)


def registry_build_reason(
    tag: RegistryTag | None,
    dockerfile_last_commit: str,
    platforms: list[str],
) -> str:
    """
    Explain why a registry tag needs rebuilding.

    Args:
        tag (RegistryTag or None): Published tag state, or ``None`` when absent.
        dockerfile_last_commit (str): ISO8601 time of the Dockerfile's last commit.
        platforms (list[str]): Requested platforms; empty to skip platform checks.

    Returns:
        str: Build reason, or an empty string when the tag is up-to-date.
    """
    if tag is None:
        return "tag_not_found"
    if not tag.last_updated:
        return "tag_missing_last_updated"
    if parse_iso_timestamp(dockerfile_last_commit) > parse_iso_timestamp(
        tag.last_updated
    ):
        return "dockerfile_changed_after_tag"
    missing = [p for p in platforms if not platform_is_published(p, tag.platforms)]
    if missing:
        return f"missing_platforms_{','.join(missing)}"
    return ""


def evaluate_docker_build_staleness(
    dockerfile_path: str,
    image_name: str,
    dockerhub_namespace: str,
    repo_name: str,
    registries: str = "dockerhub",
    ghcr_namespace: str = "",
    platforms: str = "",
    github_token: str = "",
) -> dict[str, str]:
    """
    Decide whether to build a Docker image based on Dockerfile git history and tag freshness.

    The build is skipped only when every selected registry already has the tag,
    the tag is at least as new as the Dockerfile's last commit, and it includes
    every requested platform.

    Args:
        dockerfile_path (str): Path to Dockerfile in repository.
        image_name (str): Target image name, including tag.
        dockerhub_namespace (str): Docker Hub namespace/org.
        repo_name (str): Image repository name.
        registries (str): Comma-separated registries to check (dockerhub, ghcr).
        ghcr_namespace (str): GHCR owner or organization.
        platforms (str): Comma-separated requested platforms; empty to skip
            platform checks.
        github_token (str): Token for reading private GHCR packages.

    Returns:
        dict: Build decision fields suitable for GitHub Action outputs.
    """
    should_build = True
    tag_exists = False
    tag_last_updated = ""
    reason = "default_build"
    registry_list = [r.strip().lower() for r in registries.split(",") if r.strip()]
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]

    dockerfile_last_commit = dockerfile_last_commit_iso(dockerfile_path)
    image_tag = image_tag_from_image_name(image_name)
    if not dockerfile_last_commit:
        reason = "no_git_history_for_dockerfile"
    elif not image_tag:
        reason = "missing_image_tag"
    elif not registry_list:
        reason = "no_registries_selected"
    else:
        reasons = []
        tags = []
        for registry in registry_list:
            try:
                if registry == "dockerhub":
                    tag = dockerhub_tag_info(dockerhub_namespace, repo_name, image_tag)
                elif registry == "ghcr":
                    tag = ghcr_tag_info(
                        ghcr_namespace, repo_name, image_tag, github_token
                    )
                else:
                    raise ValueError(f"Unsupported registry '{registry}'")
                tags.append(tag)
                registry_reason = registry_build_reason(
                    tag, dockerfile_last_commit, platform_list
                )
            except requests.HTTPError as exc:
                tags.append(None)
                status_code = getattr(exc.response, "status_code", "unknown")
                registry_reason = f"http_{status_code}"
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                tags.append(None)
                registry_reason = f"lookup_failed_{type(exc).__name__}"
            if registry_reason:
                reasons.append(f"{registry}:{registry_reason}")

        tag_exists = all(tag is not None for tag in tags)
        published_times = [tag.last_updated for tag in tags if tag and tag.last_updated]
        if published_times:
            tag_last_updated = min(published_times, key=parse_iso_timestamp)
        should_build = bool(reasons)
        reason = ";".join(reasons) if reasons else "tag_is_newer_or_equal_to_dockerfile"

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
    registries: str = "dockerhub",
    ghcr_namespace: str = "",
    platforms: str = "",
    github_token: str = "",
) -> dict[str, str]:
    """
    Evaluate Docker build staleness and set step outputs.

    Args:
        dockerfile_path (str): Path to Dockerfile in repository.
        image_name (str): Target image name, including tag.
        dockerhub_namespace (str): Docker Hub namespace/org.
        repo_name (str): Image repository name.
        registries (str): Comma-separated registries to check (dockerhub, ghcr).
        ghcr_namespace (str): GHCR owner or organization.
        platforms (str): Comma-separated requested platforms.
        github_token (str): Token for reading private GHCR packages.

    Returns:
        dict: Build decision fields written to GitHub Action outputs.
    """
    result = evaluate_docker_build_staleness(
        dockerfile_path=dockerfile_path,
        image_name=image_name,
        dockerhub_namespace=dockerhub_namespace,
        repo_name=repo_name,
        registries=registries,
        ghcr_namespace=ghcr_namespace,
        platforms=platforms,
        github_token=github_token,
    )
    for name, value in result.items():
        set_output(name, value)

    if result["should_build"] == "true":
        print(f"::notice::Will build image. reason={result['reason']}")
    else:
        print(
            f"::notice::Skipping docker build because the {registries} tag is "
            f"up-to-date (dockerfile_last_commit={result['dockerfile_last_commit']}, "
            f"tag_last_updated={result['tag_last_updated']})."
        )

    return result
