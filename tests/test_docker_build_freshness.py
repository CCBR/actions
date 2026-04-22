import requests

from ccbr_actions import docker as docker_module


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            http_error = requests.HTTPError(f"HTTP {self.status_code}")
            http_error.response = self
            raise http_error

    def json(self):
        return self._payload


def test_image_tag_from_image_name():
    assert docker_module.image_tag_from_image_name("nciccbr/tool:v1") == "v1"
    assert docker_module.image_tag_from_image_name("nciccbr/tool") == ""


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
