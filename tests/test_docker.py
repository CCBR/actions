import datetime
import os
import pathlib
import subprocess
import tempfile

import pytest

from ccbr_actions.docker import prepare_docker_build_variables


def parse_env_file(env_path):
    values = {}
    with open(env_path, "r") as handle:
        for line in handle.read().splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
    return values


def run_bash_prepare(script_path, dockerfile, suffix, dockerhub_account, env_path):
    env = os.environ.copy()
    env["GITHUB_ENV"] = str(env_path)
    subprocess.run(
        [str(script_path), str(dockerfile), suffix, dockerhub_account],
        check=True,
        env=env,
        text=True,
        capture_output=True,
    )
    return parse_env_file(env_path)


@pytest.mark.parametrize("suffix", ["dev", "main", "", "feature"])
def test_prepare_docker_build_variables_matches_bash(suffix):
    script_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_docker_build_variables.sh"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = pathlib.Path(tmpdir) / "myrepo"
        repo_dir.mkdir()
        dockerfile = repo_dir / "Dockerfile.v2"
        dockerfile.write_text("FROM ubuntu:22.04\n")

        bash_env_path = pathlib.Path(tmpdir) / "bash.env"
        bash_values = run_bash_prepare(
            script_path=script_path,
            dockerfile=dockerfile,
            suffix=suffix,
            dockerhub_account="nciccbr",
            env_path=bash_env_path,
        )

        now = datetime.datetime.strptime(bash_values["BUILD_DATE"], "%Y-%m-%d_%H:%M:%S")
        py_env_path = pathlib.Path(tmpdir) / "py.env"
        py_values = prepare_docker_build_variables(
            dockerfile=str(dockerfile),
            suffix=suffix,
            dockerhub_account="nciccbr",
            github_env=str(py_env_path),
            now=now,
        )
        py_file_values = parse_env_file(py_env_path)

    assert py_values == bash_values
    assert py_file_values == bash_values
