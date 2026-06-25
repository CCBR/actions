import os
import pathlib
from unittest.mock import patch
from click.testing import CliRunner
from ccbr_tools.shell import shell_run
from ccbr_actions.__main__ import cli


def test_citation():
    assert shell_run("ccbr_actions --citation")


def test_version():
    assert shell_run("ccbr_actions --version")


def test_use_example(tmp_path):
    current_wd = pathlib.Path.cwd()
    outfile = tmp_path / ".github" / "workflows" / "build-nextflow.yml"
    try:
        os.chdir(tmp_path)
        shell_run("ccbr_actions use-example build-nextflow")
    finally:
        os.chdir(current_wd)
    assert outfile.exists()


# ---------------------------------------------------------------------------
# list-rulesets CLI
# ---------------------------------------------------------------------------

MOCK_RULESETS = [
    {"id": 1, "name": "Require PR reviews", "enforcement": "active"},
    {"id": 2, "name": "Restrict force push", "enforcement": "evaluate"},
]


def test_list_rulesets_prints_rulesets():
    runner = CliRunner()
    with patch("ccbr_actions.__main__.list_rulesets", return_value=MOCK_RULESETS):
        result = runner.invoke(cli, ["list-rulesets", "CCBR/actions"])

    assert result.exit_code == 0
    assert "Require PR reviews" in result.output
    assert "Restrict force push" in result.output
    assert "active" in result.output
    assert "evaluate" in result.output


def test_list_rulesets_prints_message_when_empty():
    runner = CliRunner()
    with patch("ccbr_actions.__main__.list_rulesets", return_value=[]):
        result = runner.invoke(cli, ["list-rulesets", "CCBR/empty-repo"])

    assert result.exit_code == 0
    assert "No rulesets found" in result.output


def test_list_rulesets_passes_token():
    runner = CliRunner()
    with patch("ccbr_actions.__main__.list_rulesets", return_value=[]) as mock_fn:
        runner.invoke(cli, ["list-rulesets", "CCBR/actions", "--token", "ghp_test"])

    mock_fn.assert_called_once_with(repo="CCBR/actions", token="ghp_test")


def test_list_rulesets_reads_token_from_env():
    runner = CliRunner()
    with patch("ccbr_actions.__main__.list_rulesets", return_value=[]) as mock_fn:
        result = runner.invoke(
            cli, ["list-rulesets", "CCBR/actions"], env={"GH_TOKEN": "ghp_env"}
        )

    assert result.exit_code == 0
    mock_fn.assert_called_once_with(repo="CCBR/actions", token="ghp_env")


# ---------------------------------------------------------------------------
# copy-ruleset CLI
# ---------------------------------------------------------------------------

CREATED_RULESET = {"id": 99, "name": "Require PR reviews"}


def test_copy_ruleset_prints_confirmation():
    runner = CliRunner()
    with patch("ccbr_actions.__main__.copy_ruleset", return_value=CREATED_RULESET):
        result = runner.invoke(
            cli,
            ["copy-ruleset", "CCBR/actions", "CCBR/other-repo", "Require PR reviews"],
        )

    assert result.exit_code == 0
    assert "Require PR reviews" in result.output
    assert "99" in result.output
    assert "CCBR/other-repo" in result.output


def test_copy_ruleset_passes_arguments():
    runner = CliRunner()
    with patch(
        "ccbr_actions.__main__.copy_ruleset", return_value=CREATED_RULESET
    ) as mock_fn:
        runner.invoke(
            cli,
            [
                "copy-ruleset",
                "CCBR/actions",
                "CCBR/other-repo",
                "Require PR reviews",
                "--token",
                "ghp_test",
            ],
        )

    mock_fn.assert_called_once_with(
        source_repo="CCBR/actions",
        target_repo="CCBR/other-repo",
        ruleset_name="Require PR reviews",
        token="ghp_test",
    )


def test_copy_ruleset_reads_token_from_env():
    runner = CliRunner()
    with patch(
        "ccbr_actions.__main__.copy_ruleset", return_value=CREATED_RULESET
    ) as mock_fn:
        runner.invoke(
            cli,
            ["copy-ruleset", "CCBR/actions", "CCBR/other-repo", "Require PR reviews"],
            env={"GH_TOKEN": "ghp_env"},
        )

    mock_fn.assert_called_once_with(
        source_repo="CCBR/actions",
        target_repo="CCBR/other-repo",
        ruleset_name="Require PR reviews",
        token="ghp_env",
    )


def test_copy_ruleset_surfaces_value_error():
    runner = CliRunner()
    with patch(
        "ccbr_actions.__main__.copy_ruleset",
        side_effect=ValueError("'Nonexistent' not found"),
    ):
        result = runner.invoke(
            cli,
            ["copy-ruleset", "CCBR/actions", "CCBR/other-repo", "Nonexistent"],
        )

    assert result.exit_code != 0
