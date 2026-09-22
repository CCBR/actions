"""Tests for the scripts used by the build-docker composite action."""

from ccbr_tools.shell import shell_run


def test_prepare_docker_build_variables_script(tmp_path, monkeypatch):
    """The preparation script writes the expected GitHub environment values."""
    docker_dir = tmp_path / "example"
    docker_dir.mkdir()
    dockerfile = docker_dir / "Dockerfile.v1"
    dockerfile.write_text("FROM python:3.14-slim\n")
    github_env = tmp_path / "github_env"
    monkeypatch.setenv("GITHUB_ENV", str(github_env))

    shell_run(
        f"python scripts/prepare_docker_build_variables.py {dockerfile} dev nciccbr"
    )

    values = github_env.read_text()
    assert f"DOCKERFILE_PATH={dockerfile}" in values
    assert "IMAGENAME=nciccbr/example:v1-dev" in values
    assert f"MDFILE={docker_dir}/v1-dev.README.md" in values


def test_check_docker_build_staleness_script_force_build(tmp_path, monkeypatch):
    """The staleness script honors force-build and emits step outputs."""
    github_output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setenv("INPUT_FORCE_BUILD", "true")

    shell_run(
        "python scripts/check_docker_build_staleness.py "
        "Dockerfile nciccbr/actions:v1 nciccbr actions"
    )

    outputs = github_output.read_text()
    assert "should_build<<" in outputs
    assert "\ntrue\n" in outputs
    assert "reason<<" in outputs
    assert "\nforce_build_requested\n" in outputs
