"""Tests for the build-docker composite action's registry and platform inputs."""

import os
import pathlib
import subprocess
import sys

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


@pytest.mark.parametrize("dockerfile", ["Dockerfile.v1", "./Dockerfile.v1"])
def test_root_dockerfile_preparation_and_reporting(tmp_path, dockerfile):
    action = load_action()
    (tmp_path / "Dockerfile.v1").write_text("FROM ubuntu:22.04\n")
    (tmp_path / "tool_version_commands.txt").write_text("")
    github_env = tmp_path / "github_env"

    stale_package = tmp_path / "old-package" / "ccbr_actions"
    stale_package.mkdir(parents=True)
    (stale_package / "__init__.py").write_text('raise RuntimeError("stale package")\n')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        '#!/bin/bash\nprintf "%s|%s\\n" "$DOCKER_DEFAULT_PLATFORM" "$*" >> "$DOCKER_LOG"\n'
    )
    docker.chmod(0o755)
    (bin_dir / "print_versions.sh").write_text("#!/bin/bash\n")
    (bin_dir / "print_versions.sh").chmod(0o755)
    executable_path = os.pathsep.join(
        [str(bin_dir), str(pathlib.Path(sys.executable).parent), os.environ["PATH"]]
    )

    result, _ = run_step(
        find_step(action, "prepare_vars"),
        tmp_path,
        GITHUB_WORKSPACE=str(tmp_path),
        GITHUB_ACTION_PATH=str(ACTION_PATH.parent),
        GITHUB_REPOSITORY="CCBR/My.Example_Repo",
        GITHUB_ENV=str(github_env),
        DOCKERFILE_INPUT=dockerfile,
        SUFFIX_INPUT="dev",
        DOCKERHUB_NAMESPACE_INPUT="nciccbr",
        PYTHONPATH=str(stale_package.parent),
        PATH=executable_path,
    )
    assert result.returncode == 0, result.stderr
    values = parse_outputs(github_env.read_text())
    assert values["REPONAME"] == "my-example-repo"
    assert values["IMAGENAME"] == "nciccbr/my-example-repo:v1-dev"
    assert values["MDFILE"] == "v1-dev.README.md"
    assert values["CONTEXT"] == "."
    assert values["DOCKERFILE_PATH"] == "Dockerfile.v1"
    subprocess.run(
        ["git", "check-ref-format", "--branch", f"auto-pr/{values['DOCKERFILE_PATH']}"],
        check=True,
        capture_output=True,
        text=True,
    )

    result, output = run_step(
        find_step(action, "prepare_image_tags"),
        tmp_path,
        **values,
        PUSH_ENABLED="true",
        PUSH_DOCKERHUB="true",
        PUSH_GHCR="true",
        GHCR_NAMESPACE_INPUT="",
        GITHUB_REPOSITORY_OWNER="CCBR",
        GITHUB_REPOSITORY="CCBR/My.Example_Repo",
    )
    assert result.returncode == 0, result.stderr
    assert "nciccbr/my-example-repo:v1-dev" in output
    assert "ghcr.io/ccbr/my-example-repo:v1-dev" in output

    readme_step = find_step(action, "check_and_create_readme").copy()
    readme_step["run"] = (
        readme_step["run"]
        .replace("${{ github.repository }}", "CCBR/My.Example_Repo")
        .replace("${{ github.sha }}", "abc123")
        .replace("${{ inputs.dockerfile }}", dockerfile)
    )
    result, _ = run_step(
        readme_step,
        tmp_path,
        **values,
        GITHUB_WORKSPACE=str(tmp_path),
        INPUT_PLATFORMS="linux/arm64,linux/amd64",
    )
    assert result.returncode == 0, result.stderr
    readme = (tmp_path / "v1-dev.README.md").read_text()
    assert "nciccbr/my-example-repo:v1-dev" in readme
    assert "Platforms: linux/arm64, linux/amd64" in readme

    report_step = find_step(action, "run_script_in_container").copy()
    report_step["run"] = (
        report_step["run"]
        .replace("${{ inputs.config-file }}", "tool_version_commands.txt")
        .replace("${{ github.workspace }}", str(tmp_path))
        .replace("${{ env.MDFILE }}", values["MDFILE"])
    )
    result, _ = run_step(
        report_step,
        tmp_path,
        **values,
        GITHUB_WORKSPACE=str(tmp_path),
        GITHUB_REPOSITORY="CCBR/My.Example_Repo",
        GITHUB_REPOSITORY_OWNER="CCBR",
        GHCR_NAMESPACE_INPUT="",
        IMAGE_NAME_INPUT=values["IMAGENAME"],
        INPUT_PLATFORMS="linux/arm64,linux/amd64",
        PUSH_ENABLED="true",
        PUSH_GHCR="true",
        PATH=executable_path,
        DOCKER_LOG=str(docker_log),
    )
    assert result.returncode == 0, result.stderr
    calls = docker_log.read_text().splitlines()
    assert calls[0] == "linux/arm64|pull ghcr.io/ccbr/my-example-repo:v1-dev"
    assert calls[1].startswith("linux/arm64|run ")
    assert "ghcr.io/ccbr/my-example-repo:v1-dev" in calls[1]
    assert f"--output {os.path.join(os.sep, 'ws', values['MDFILE'])}" in calls[1]


@pytest.mark.parametrize(
    ("platforms", "docker_platform", "expected"),
    [
        (" linux/amd64, linux/arm64 ", "linux/amd64", "linux/amd64, linux/arm64"),
        ("", "linux/amd64", "linux/amd64"),
        ("", "", "runner default"),
    ],
)
def test_readme_lists_platforms(tmp_path, platforms, docker_platform, expected):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        f"#!/bin/bash\n[[ -n '{docker_platform}' ]] && echo '{docker_platform}'\n"
    )
    docker.chmod(0o755)
    readme_step = find_step(load_action(), "check_and_create_readme").copy()
    readme_step["run"] = (
        readme_step["run"]
        .replace("${{ github.repository }}", "CCBR/example")
        .replace("${{ github.sha }}", "abc123")
        .replace("${{ inputs.dockerfile }}", "Dockerfile.v1")
    )

    result, _ = run_step(
        readme_step,
        tmp_path,
        GITHUB_WORKSPACE=str(tmp_path),
        MDFILE="v1.README.md",
        INPUT_PLATFORMS=platforms,
        PATH=os.pathsep.join([str(bin_dir), os.environ["PATH"]]),
    )

    assert result.returncode == 0, result.stderr
    assert f"Platforms: {expected} \n" in (tmp_path / "v1.README.md").read_text()


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


@pytest.mark.parametrize(
    ("push_ghcr", "platforms", "force_build", "expected_force"),
    [
        ("true", "", "false", "true"),
        ("false", "linux/arm64", "false", "true"),
        ("true", "linux/arm64", "false", "true"),
        ("false", "", "false", "false"),
        ("false", "", "true", "true"),
    ],
)
def test_staleness_check_bypasses_dockerhub_when_needed(
    tmp_path, push_ghcr, platforms, force_build, expected_force
):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text("#!/bin/bash\nexit 0\n")
    git.chmod(0o755)
    python = bin_dir / "python"
    python.write_text('#!/bin/bash\nprintf "force=%s\\n" "$INPUT_FORCE_BUILD"\n')
    python.chmod(0o755)

    result, _ = run_step(
        find_step(load_action(), "check_tag_staleness"),
        tmp_path,
        GITHUB_WORKSPACE=str(tmp_path),
        GITHUB_ACTION_PATH=str(ACTION_PATH.parent),
        INPUT_FORCE_BUILD=force_build,
        INPUT_PUSH_GHCR=push_ghcr,
        INPUT_PLATFORMS=platforms,
        DOCKERFILE_PATH_INPUT="Dockerfile.v1",
        IMAGE_NAME_INPUT="nciccbr/example:v1",
        DOCKERHUB_NAMESPACE_INPUT="nciccbr",
        REPO_NAME_INPUT="example",
        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"force={expected_force}\n"
