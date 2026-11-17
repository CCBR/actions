"""Test registry source-tag checks and stable image promotion."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "promote_docker_image.py"


def install_fake_docker(tmp_path):
    """Install a Docker CLI stub that records inspections and tag copies."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "docker.jsonl"
    log.unlink(missing_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["DOCKER_LOG"], "a", encoding="utf-8") as log:
    print(json.dumps(args), file=log)
if args[:3] == ["buildx", "imagetools", "inspect"]:
    ref = args[3]
    if os.environ.get("MOCK_ERROR") and os.environ["MOCK_ERROR"] in ref:
        print("unauthorized", file=sys.stderr)
        raise SystemExit(1)
    if os.environ.get("MOCK_MISSING") and os.environ["MOCK_MISSING"] in ref:
        print("no such manifest", file=sys.stderr)
        raise SystemExit(1)
"""
    )
    docker.chmod(0o755)
    return bin_dir, log


def run_script(tmp_path, command, **variables):
    output = tmp_path / "github_output"
    output.unlink(missing_ok=True)
    env = os.environ.copy()
    env.update(GITHUB_OUTPUT=str(output), **variables)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), command],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = (
        dict(line.split("=", 1) for line in output.read_text().splitlines())
        if output.exists()
        else {}
    )
    return result, outputs


def docker_env(tmp_path, **variables):
    bin_dir, log = install_fake_docker(tmp_path)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_LOG": str(log),
        "SOURCE_REFS": "nciccbr/tool:context-tree\nghcr.io/ccbr/tool:context-tree",
        "TARGET_REFS": "nciccbr/tool:v2\nghcr.io/ccbr/tool:v2",
    }
    env.update(variables)
    return env, log


def test_check_confirms_source_tag_in_each_registry(tmp_path):
    env, log = docker_env(tmp_path)
    result, output = run_script(tmp_path, "check", **env)

    assert result.returncode == 0, result.stderr
    assert output == {"available": "true"}
    assert [json.loads(line)[-1] for line in log.read_text().splitlines()] == [
        "nciccbr/tool:context-tree",
        "ghcr.io/ccbr/tool:context-tree",
    ]


def test_check_falls_back_only_for_missing_source_tags(tmp_path):
    env, _ = docker_env(tmp_path, MOCK_MISSING="ghcr.io/ccbr/tool")
    result, output = run_script(tmp_path, "check", **env)

    assert result.returncode == 0, result.stderr
    assert output == {"available": "false"}
    assert "::notice::" in result.stdout

    env, _ = docker_env(tmp_path, MOCK_ERROR="ghcr.io/ccbr/tool")
    result, output = run_script(tmp_path, "check", **env)
    assert result.returncode != 0
    assert "::error::" in result.stderr
    assert not output


def test_promote_retags_source_images_and_reports_success(tmp_path):
    env, log = docker_env(tmp_path)
    result, output = run_script(tmp_path, "promote", **env)

    assert result.returncode == 0, result.stderr
    assert output == {"promoted": "true"}
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls[-2:] == [
        [
            "buildx",
            "imagetools",
            "create",
            "--tag",
            "nciccbr/tool:v2",
            "nciccbr/tool:context-tree",
        ],
        [
            "buildx",
            "imagetools",
            "create",
            "--tag",
            "ghcr.io/ccbr/tool:v2",
            "ghcr.io/ccbr/tool:context-tree",
        ],
    ]


def test_promote_falls_back_when_source_tag_disappears(tmp_path):
    env, log = docker_env(tmp_path, MOCK_MISSING="nciccbr/tool")
    result, output = run_script(tmp_path, "promote", **env)

    assert result.returncode == 0, result.stderr
    assert output == {"promoted": "false"}
    assert "::notice::" in result.stdout
    assert not any(
        json.loads(line)[2] == "create" for line in log.read_text().splitlines()
    )


def test_promote_requires_matching_source_and_target_refs(tmp_path):
    env, _ = docker_env(tmp_path, TARGET_REFS="nciccbr/tool:v2")
    result, output = run_script(tmp_path, "promote", **env)

    assert result.returncode != 0
    assert "::error::" in result.stderr
    assert not output


@pytest.mark.parametrize("command", ["check", "promote"])
def test_script_rejects_empty_refs(tmp_path, command):
    env, _ = docker_env(tmp_path, SOURCE_REFS="")
    result, output = run_script(tmp_path, command, **env)

    assert result.returncode != 0
    assert "::error::" in result.stderr
    assert not output
