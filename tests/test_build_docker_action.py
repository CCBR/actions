"""Tests for the build-docker composite action's registry and platform inputs."""

import os
import pathlib
import subprocess

import pytest
import yaml

ACTION_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "build-docker" / "action.yml"
)


def load_action():
    """Load the composite action metadata."""
    with ACTION_PATH.open() as action_file:
        return yaml.safe_load(action_file)


def find_step(action, step_id):
    """Find a composite action step by its ID."""
    return next(step for step in action["runs"]["steps"] if step.get("id") == step_id)


def run_step(step, tmp_path, **step_env):
    """Run a shell step from the action with the supplied step environment."""
    output_path = tmp_path / "github_output"
    env = os.environ.copy()
    env.update(step_env)
    env["GITHUB_OUTPUT"] = str(output_path)
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    return result, output_path.read_text() if output_path.exists() else ""


def parse_outputs(output_text):
    """Parse the single-line GitHub Actions outputs used by these steps."""
    outputs = {}
    for line in output_text.splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            outputs[name] = value
    return outputs


def test_build_docker_defaults_to_both_registries_and_supports_platforms():
    action = load_action()

    assert action["inputs"]["registries"]["default"] == "dockerhub,ghcr"
    assert action["inputs"]["platforms"]["default"] == ""

    build_step = next(
        step
        for step in action["runs"]["steps"]
        if step.get("uses") == "docker/build-push-action@v7"
    )
    assert build_step["with"]["platforms"] == "${{ inputs.platforms }}"
    assert any(
        step.get("uses") == "docker/setup-qemu-action@v4"
        and step["if"] == "${{ inputs.platforms != '' }}"
        for step in action["runs"]["steps"]
    )


@pytest.mark.parametrize(
    ("registries", "dockerhub_username", "dockerhub_token", "github_token", "expected"),
    [
        (
            "dockerhub,ghcr",
            "user",
            "token",
            "github-token",
            {
                "push_enabled": "true",
                "push_dockerhub": "true",
                "push_ghcr": "true",
            },
        ),
        (
            "ghcr",
            "",
            "",
            "github-token",
            {
                "push_enabled": "true",
                "push_dockerhub": "false",
                "push_ghcr": "true",
            },
        ),
        (
            "dockerhub,ghcr",
            "",
            "",
            "github-token",
            {
                "push_enabled": "true",
                "push_dockerhub": "false",
                "push_ghcr": "true",
            },
        ),
        (
            "dockerhub",
            "",
            "",
            "",
            {
                "push_enabled": "false",
                "push_dockerhub": "false",
                "push_ghcr": "false",
            },
        ),
    ],
)
def test_resolve_push_selects_registries_and_credentials(
    tmp_path,
    registries,
    dockerhub_username,
    dockerhub_token,
    github_token,
    expected,
):
    step = find_step(load_action(), "resolve_push")
    result, output_text = run_step(
        step,
        tmp_path,
        INPUT_PUSH="true",
        INPUT_REGISTRIES=registries,
        INPUT_DOCKERHUB_USERNAME=dockerhub_username,
        INPUT_DOCKERHUB_TOKEN=dockerhub_token,
        INPUT_GITHUB_TOKEN=github_token,
    )

    assert result.returncode == 0
    assert parse_outputs(output_text) == expected


def test_prepare_image_tags_includes_selected_registries(tmp_path):
    step = find_step(load_action(), "prepare_image_tags")
    _, output_text = run_step(
        step,
        tmp_path,
        PUSH_ENABLED="true",
        PUSH_DOCKERHUB="true",
        PUSH_GHCR="true",
        GHCR_NAMESPACE_INPUT="",
        GITHUB_REPOSITORY_OWNER="CCBR",
        IMAGENAME="nciccbr/tool:v1",
        REPONAME="Tool",
        BUILD_TAG="v1",
    )

    tags = output_text.split("tags<<EOF\n", 1)[1].split("\nEOF", 1)[0].splitlines()
    assert tags == ["nciccbr/tool:v1", "ghcr.io/ccbr/tool:v1"]


def test_prepare_image_tags_uses_repository_name_for_root_dockerfile(tmp_path):
    step = find_step(load_action(), "prepare_image_tags")
    _, output_text = run_step(
        step,
        tmp_path,
        PUSH_ENABLED="true",
        PUSH_DOCKERHUB="false",
        PUSH_GHCR="true",
        GHCR_NAMESPACE_INPUT="",
        GITHUB_REPOSITORY_OWNER="CCBR",
        GITHUB_REPOSITORY="CCBR/Example",
        IMAGENAME="nciccbr/:v1",
        REPONAME="",
        BUILD_TAG="v1",
    )

    tags = output_text.split("tags<<EOF\n", 1)[1].split("\nEOF", 1)[0].splitlines()
    assert tags == ["ghcr.io/ccbr/example:v1"]


def test_resolve_push_rejects_unknown_registry(tmp_path):
    step = find_step(load_action(), "resolve_push")
    result, _ = run_step(
        step,
        tmp_path,
        INPUT_PUSH="true",
        INPUT_REGISTRIES="unknown",
        INPUT_DOCKERHUB_USERNAME="",
        INPUT_DOCKERHUB_TOKEN="",
        INPUT_GITHUB_TOKEN="",
    )

    assert result.returncode != 0
