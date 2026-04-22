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
    assert result["reason"] == "tag_not_found"
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
    assert result["reason"] == "dockerfile_changed_after_tag"
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
    assert result["reason"] == "tag_missing_last_updated"


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
    assert "dockerhub_http_500" in result["reason"]


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
    assert "dockerhub_lookup_failed_ValueError" in result["reason"]


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
