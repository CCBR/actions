import subprocess

import requests

from ccbr_actions import docker as docker_module


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.response = self

    def raise_for_status(self):
        if self.status_code >= 400:
            http_error = requests.HTTPError(f"HTTP {self.status_code}")
            http_error.response = self
            raise http_error

    def json(self):
        return self._payload


def test_parse_iso_timestamp():
    """Test ISO timestamp parsing with various formats."""
    dt1 = docker_module.parse_iso_timestamp("2026-01-01T12:00:00Z")
    assert dt1.year == 2026
    assert dt1.month == 1
    assert dt1.day == 1
    assert dt1.hour == 12

    dt2 = docker_module.parse_iso_timestamp("2026-01-01T12:00:00+00:00")
    assert dt2 == dt1

    dt3 = docker_module.parse_iso_timestamp("2026-01-02T00:00:00.000000Z")
    assert dt3.day == 2


def test_parse_iso_timestamp_timezone_normalization():
    """Test that timestamps are normalized to UTC."""
    dt = docker_module.parse_iso_timestamp("2026-01-01T12:00:00Z")
    assert dt.tzinfo is not None
    assert str(dt.tzinfo) == "UTC"


def test_dockerfile_last_commit_iso(monkeypatch):
    """Test getting last commit timestamp from git."""
    expected_commit = "2026-01-15T10:30:45+00:00\n"

    def fake_check_output(*args, **kwargs):
        return expected_commit

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)

    result = docker_module.dockerfile_last_commit_iso("some/Dockerfile.v1")
    assert result == "2026-01-15T10:30:45+00:00"


def test_dockerfile_last_commit_iso_empty(monkeypatch):
    """Test handling when dockerfile has no git history."""

    def fake_check_output(*args, **kwargs):
        return ""

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)

    result = docker_module.dockerfile_last_commit_iso("untracked/Dockerfile.v1")
    assert result == ""


def test_dockerfile_last_commit_iso_called_process_error(monkeypatch):
    """Test that CalledProcessError is handled and returns an empty string."""

    def fake_check_output(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)

    result = docker_module.dockerfile_last_commit_iso("missing/Dockerfile.v1")
    assert result == ""


def test_dockerhub_tag_last_updated_success(monkeypatch):
    """Test successful Docker Hub API call."""

    def fake_get(*args, **kwargs):
        return FakeResponse(
            status_code=200,
            payload={"last_updated": "2026-01-20T14:00:00.000000Z"},
        )

    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.dockerhub_tag_last_updated(
        dockerhub_namespace="nciccbr",
        repo_name="example",
        image_tag="v1",
    )
    assert result == "2026-01-20T14:00:00.000000Z"


def test_dockerhub_tag_last_updated_404(monkeypatch):
    """Test Docker Hub API returning 404 for missing tag."""

    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=404)

    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.dockerhub_tag_last_updated(
        dockerhub_namespace="nciccbr",
        repo_name="example",
        image_tag="nonexistent",
    )
    assert result is None


def test_dockerhub_tag_last_updated_empty_payload(monkeypatch):
    """Test Docker Hub API with missing last_updated field."""

    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=200, payload={})

    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.dockerhub_tag_last_updated(
        dockerhub_namespace="nciccbr",
        repo_name="example",
        image_tag="v1",
    )
    assert result == ""


def test_dockerhub_tag_last_updated_none_value(monkeypatch):
    """Test Docker Hub API with None value for last_updated."""

    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=200, payload={"last_updated": None})

    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.dockerhub_tag_last_updated(
        dockerhub_namespace="nciccbr",
        repo_name="example",
        image_tag="v1",
    )
    assert result == ""


def test_image_tag_from_image_name():
    assert docker_module.image_tag_from_image_name("nciccbr/tool:v1") == "v1"
    assert docker_module.image_tag_from_image_name("nciccbr/tool") == ""
    assert (
        docker_module.image_tag_from_image_name("localhost:5000/myrepo/mytool:latest")
        == "latest"
    )
    # registry with port but no explicit tag should return empty string
    assert docker_module.image_tag_from_image_name("localhost:5000/myrepo/image") == ""


def test_evaluate_docker_build_staleness_skip_when_tag_is_newer(monkeypatch):
    def fake_check_output(*args, **kwargs):
        return "2026-01-01T00:00:00+00:00\n"

    def fake_get(*args, **kwargs):
        return FakeResponse(
            status_code=200,
            payload={"last_updated": "2026-01-02T00:00:00.000000Z"},
        )

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "false"
    assert result["tag_exists"] == "true"
    assert result["reason"] == "tag_is_newer_or_equal_to_dockerfile"
    assert result["tag_last_updated"] == "2026-01-02T00:00:00.000000Z"


def test_evaluate_docker_build_staleness_build_when_tag_missing(monkeypatch):
    def fake_check_output(*args, **kwargs):
        return "2026-01-01T00:00:00+00:00\n"

    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=404)

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "true"
    assert result["tag_exists"] == "false"
    assert result["reason"] == "dockerhub:tag_not_found"
    assert result["tag_last_updated"] == ""


def test_evaluate_docker_build_staleness_build_when_dockerfile_newer(monkeypatch):
    """Test that build proceeds when Dockerfile is newer than tag."""

    def fake_check_output(*args, **kwargs):
        return "2026-01-03T00:00:00+00:00\n"

    def fake_get(*args, **kwargs):
        return FakeResponse(
            status_code=200,
            payload={"last_updated": "2026-01-02T00:00:00.000000Z"},
        )

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "true"
    assert result["tag_exists"] == "true"
    assert result["reason"] == "dockerhub:dockerfile_changed_after_tag"
    assert result["dockerfile_last_commit"] == "2026-01-03T00:00:00+00:00"


def test_evaluate_docker_build_staleness_no_git_history(monkeypatch):
    """Test when Dockerfile has no git history."""

    def fake_check_output(*args, **kwargs):
        return ""

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="untracked/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "true"
    assert result["reason"] == "no_git_history_for_dockerfile"
    assert result["dockerfile_last_commit"] == ""


def test_evaluate_docker_build_staleness_no_image_tag(monkeypatch):
    """Test when image name has no tag."""

    def fake_check_output(*args, **kwargs):
        return "2026-01-01T00:00:00+00:00\n"

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "true"
    assert result["reason"] == "missing_image_tag"


def test_evaluate_docker_build_staleness_missing_last_updated(monkeypatch):
    """Test when Docker Hub tag exists but has no last_updated."""

    def fake_check_output(*args, **kwargs):
        return "2026-01-01T00:00:00+00:00\n"

    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=200, payload={})

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "true"
    assert result["reason"] == "dockerhub:tag_missing_last_updated"


def test_evaluate_docker_build_staleness_http_error(monkeypatch):
    """Test handling of Docker Hub HTTP errors."""

    def fake_check_output(*args, **kwargs):
        return "2026-01-01T00:00:00+00:00\n"

    def fake_get(*args, **kwargs):
        response = FakeResponse(status_code=500)
        return response

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "true"
    assert result["reason"] == "dockerhub:http_500"


def test_evaluate_docker_build_staleness_generic_exception(monkeypatch):
    """Test handling of generic exceptions during Docker Hub lookup."""

    def fake_check_output(*args, **kwargs):
        return "2026-01-01T00:00:00+00:00\n"

    def fake_get(*args, **kwargs):
        raise ValueError("Network error")

    monkeypatch.setattr(docker_module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(docker_module.requests, "get", fake_get)

    result = docker_module.evaluate_docker_build_staleness(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    assert result["should_build"] == "true"
    assert result["reason"] == "dockerhub:lookup_failed_ValueError"


def test_evaluate_docker_build_staleness_and_set_outputs(
    monkeypatch, github_output_file
):
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output_file))

    def fake_evaluate(*args, **kwargs):
        return {
            "should_build": "false",
            "tag_exists": "true",
            "dockerfile_last_commit": "2026-01-01T00:00:00+00:00",
            "tag_last_updated": "2026-01-02T00:00:00.000000Z",
            "reason": "tag_is_newer_or_equal_to_dockerfile",
        }

    monkeypatch.setattr(docker_module, "evaluate_docker_build_staleness", fake_evaluate)

    result = docker_module.evaluate_docker_build_staleness_and_set_outputs(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    output_text = github_output_file.read_text()
    assert result["should_build"] == "false"
    assert "should_build<<" in output_text
    assert "tag_exists<<" in output_text
    assert "tag_is_newer_or_equal_to_dockerfile" in output_text


def test_evaluate_docker_build_staleness_and_set_outputs_build_true(
    monkeypatch, github_output_file
):
    """Test wrapper with should_build=true (build needed)."""
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output_file))

    def fake_evaluate(*args, **kwargs):
        return {
            "should_build": "true",
            "tag_exists": "false",
            "dockerfile_last_commit": "2026-01-03T00:00:00+00:00",
            "tag_last_updated": "",
            "reason": "tag_not_found",
        }

    monkeypatch.setattr(docker_module, "evaluate_docker_build_staleness", fake_evaluate)

    result = docker_module.evaluate_docker_build_staleness_and_set_outputs(
        dockerfile_path="dockers2/example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
    )

    output_text = github_output_file.read_text()
    assert result["should_build"] == "true"
    assert "should_build<<" in output_text
    assert "reason<<" in output_text
    assert "tag_not_found" in output_text


GHCR_INDEX = {
    "manifests": [
        {"digest": "sha256:amd", "platform": {"os": "linux", "architecture": "amd64"}},
        {"digest": "sha256:arm", "platform": {"os": "linux", "architecture": "arm64"}},
        {
            "digest": "sha256:att",
            "platform": {"os": "unknown", "architecture": "unknown"},
        },
    ]
}
GHCR_DOCUMENTS = {
    "manifests/v1": GHCR_INDEX,
    "manifests/sha256:amd": {"config": {"digest": "sha256:amdcfg"}},
    "manifests/sha256:arm": {"config": {"digest": "sha256:armcfg"}},
    "blobs/sha256:amdcfg": {
        "os": "linux",
        "architecture": "amd64",
        "created": "2026-01-02T00:05:00Z",
    },
    "blobs/sha256:armcfg": {
        "os": "linux",
        "architecture": "arm64",
        "variant": "v8",
        "created": "2026-01-02T00:00:00Z",
    },
}


def fake_registry_get(dockerhub=None, ghcr=None, calls=None):
    """Build a fake ``requests.get`` serving Docker Hub and GHCR documents."""

    def fake_get(url, **kwargs):
        if calls is not None:
            calls.append((url, kwargs))
        if url.startswith("https://hub.docker.com/"):
            return dockerhub or FakeResponse(status_code=404)
        if url == "https://ghcr.io/token":
            return FakeResponse(payload={"token": "registry-token"})
        path = url.split("/ccbr/example/", 1)[1]
        documents = GHCR_DOCUMENTS if ghcr is None else ghcr
        if path not in documents:
            return FakeResponse(status_code=404)
        return FakeResponse(payload=documents[path])

    return fake_get


def evaluate(monkeypatch, fake_get, last_commit="2026-01-01T00:00:00+00:00", **kwargs):
    monkeypatch.setattr(
        docker_module.subprocess, "check_output", lambda *a, **k: last_commit + "\n"
    )
    monkeypatch.setattr(docker_module.requests, "get", fake_get)
    return docker_module.evaluate_docker_build_staleness(
        dockerfile_path="example/Dockerfile.v1",
        image_name="nciccbr/example:v1",
        dockerhub_namespace="nciccbr",
        repo_name="example",
        **kwargs,
    )


def test_ghcr_tag_info_reads_index_platforms_and_oldest_build_time(monkeypatch):
    calls = []
    monkeypatch.setattr(docker_module.requests, "get", fake_registry_get(calls=calls))

    tag = docker_module.ghcr_tag_info("CCBR", "Example", "v1", github_token="secret")

    assert tag.platforms == {"linux/amd64", "linux/arm64/v8"}
    assert tag.last_updated == "2026-01-02T00:00:00Z"
    token_url, token_kwargs = calls[0]
    assert token_url == "https://ghcr.io/token"
    assert token_kwargs["params"]["scope"] == "repository:ccbr/example:pull"
    assert token_kwargs["auth"] == ("token", "secret")
    assert not any("sha256:att" in url for url, _ in calls)


def test_ghcr_tag_info_preserves_descriptor_variant_when_config_omits_it(monkeypatch):
    documents = {
        "manifests/v1": {
            "manifests": [
                {
                    "digest": "sha256:arm",
                    "platform": {
                        "os": "linux",
                        "architecture": "arm",
                        "variant": "v7",
                    },
                }
            ]
        },
        "manifests/sha256:arm": {"config": {"digest": "sha256:armcfg"}},
        "blobs/sha256:armcfg": {
            "os": "linux",
            "architecture": "arm",
            "created": "2026-01-02T00:00:00Z",
        },
    }

    monkeypatch.setattr(
        docker_module.requests, "get", fake_registry_get(ghcr=documents)
    )
    tag = docker_module.ghcr_tag_info("ccbr", "example", "v1")

    assert tag.platforms == {"linux/arm/v7"}


def test_ghcr_tag_info_single_platform_manifest(monkeypatch):
    documents = {
        "manifests/v1": {"config": {"digest": "sha256:cfg"}},
        "blobs/sha256:cfg": {
            "os": "linux",
            "architecture": "amd64",
            "created": "2026-01-02T00:00:00Z",
        },
    }
    calls = []
    monkeypatch.setattr(
        docker_module.requests, "get", fake_registry_get(ghcr=documents, calls=calls)
    )

    tag = docker_module.ghcr_tag_info("ccbr", "example", "v1")

    assert tag == docker_module.RegistryTag("2026-01-02T00:00:00Z", {"linux/amd64"})
    assert calls[0][1]["auth"] is None


def test_ghcr_tag_info_missing_tag(monkeypatch):
    monkeypatch.setattr(docker_module.requests, "get", fake_registry_get(ghcr={}))
    assert docker_module.ghcr_tag_info("ccbr", "example", "v1") is None


def test_dockerhub_tag_info_reads_platforms(monkeypatch):
    payload = {
        "last_updated": "2026-01-02T00:00:00Z",
        "images": [
            {"os": "linux", "architecture": "amd64"},
            {"os": "linux", "architecture": "arm", "variant": "v7"},
            {"os": "unknown", "architecture": "unknown"},
        ],
    }
    monkeypatch.setattr(
        docker_module.requests, "get", lambda *a, **k: FakeResponse(payload=payload)
    )

    tag = docker_module.dockerhub_tag_info("nciccbr", "example", "v1")

    assert tag.platforms == {"linux/amd64", "linux/arm/v7"}


def test_platform_is_published_matches_variants():
    published = {"linux/amd64", "linux/arm64/v8", "linux/arm/v7"}
    assert docker_module.platform_is_published("linux/arm64", published)
    assert docker_module.platform_is_published("linux/arm/v7", published)
    assert not docker_module.platform_is_published("linux/arm/v6", published)
    assert not docker_module.platform_is_published("linux/ppc64le", published)


DOCKERHUB_CURRENT = FakeResponse(
    payload={
        "last_updated": "2026-01-03T00:00:00Z",
        "images": [
            {"os": "linux", "architecture": "amd64"},
            {"os": "linux", "architecture": "arm64"},
        ],
    }
)


def test_staleness_skips_when_all_registries_current(monkeypatch):
    result = evaluate(
        monkeypatch,
        fake_registry_get(dockerhub=DOCKERHUB_CURRENT),
        registries="dockerhub,ghcr",
        ghcr_namespace="CCBR",
        platforms="linux/amd64,linux/arm64",
    )

    assert result["should_build"] == "false"
    assert result["tag_exists"] == "true"
    assert result["reason"] == "tag_is_newer_or_equal_to_dockerfile"
    assert result["tag_last_updated"] == "2026-01-02T00:00:00Z"


def test_staleness_skips_when_ghcr_descriptor_has_requested_variant(monkeypatch):
    documents = {
        "manifests/v1": {
            "manifests": [
                {
                    "digest": "sha256:arm",
                    "platform": {
                        "os": "linux",
                        "architecture": "arm",
                        "variant": "v7",
                    },
                }
            ]
        },
        "manifests/sha256:arm": {"config": {"digest": "sha256:armcfg"}},
        "blobs/sha256:armcfg": {
            "os": "linux",
            "architecture": "arm",
            "created": "2026-01-02T00:00:00Z",
        },
    }
    result = evaluate(
        monkeypatch,
        fake_registry_get(ghcr=documents),
        registries="ghcr",
        ghcr_namespace="ccbr",
        platforms="linux/arm/v7",
    )

    assert result["should_build"] == "false"
    assert result["reason"] == "tag_is_newer_or_equal_to_dockerfile"


def test_staleness_builds_when_dockerhub_timestamp_is_invalid(monkeypatch):
    result = evaluate(
        monkeypatch,
        fake_registry_get(
            dockerhub=FakeResponse(
                payload={
                    "last_updated": "not-a-timestamp",
                    "images": [{"os": "linux", "architecture": "amd64"}],
                }
            )
        ),
        registries="dockerhub",
    )

    assert result["should_build"] == "true"
    assert result["tag_exists"] == "false"
    assert result["reason"] == "dockerhub:lookup_failed_ValueError"
    assert result["tag_last_updated"] == ""


def test_staleness_builds_when_ghcr_tag_missing(monkeypatch):
    result = evaluate(
        monkeypatch,
        fake_registry_get(dockerhub=DOCKERHUB_CURRENT, ghcr={}),
        registries="dockerhub,ghcr",
        ghcr_namespace="ccbr",
    )

    assert result["should_build"] == "true"
    assert result["tag_exists"] == "false"
    assert result["reason"] == "ghcr:tag_not_found"


def test_staleness_builds_when_ghcr_older_than_dockerfile(monkeypatch):
    result = evaluate(
        monkeypatch,
        fake_registry_get(dockerhub=DOCKERHUB_CURRENT),
        last_commit="2026-01-02T00:01:00+00:00",
        registries="dockerhub,ghcr",
        ghcr_namespace="ccbr",
    )

    assert result["should_build"] == "true"
    assert result["reason"] == "ghcr:dockerfile_changed_after_tag"


def test_staleness_builds_when_platform_missing(monkeypatch):
    result = evaluate(
        monkeypatch,
        fake_registry_get(dockerhub=DOCKERHUB_CURRENT),
        registries="dockerhub,ghcr",
        ghcr_namespace="ccbr",
        platforms="linux/amd64,linux/ppc64le",
    )

    assert result["should_build"] == "true"
    assert result["reason"] == (
        "dockerhub:missing_platforms_linux/ppc64le;ghcr:missing_platforms_linux/ppc64le"
    )


def test_staleness_builds_when_ghcr_inaccessible(monkeypatch):
    def fake_get(url, **kwargs):
        if url.startswith("https://ghcr.io/v2/"):
            return FakeResponse(status_code=403)
        return fake_registry_get(dockerhub=DOCKERHUB_CURRENT)(url, **kwargs)

    result = evaluate(monkeypatch, fake_get, registries="ghcr", ghcr_namespace="ccbr")

    assert result["should_build"] == "true"
    assert result["reason"] == "ghcr:http_403"


def test_staleness_checks_only_selected_registries(monkeypatch):
    calls = []
    result = evaluate(
        monkeypatch,
        fake_registry_get(dockerhub=DOCKERHUB_CURRENT, calls=calls),
        registries="dockerhub",
    )

    assert result["should_build"] == "false"
    assert all(url.startswith("https://hub.docker.com/") for url, _ in calls)
