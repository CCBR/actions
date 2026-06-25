"""
Entry point for CCBR Actions
"""

import click

from ccbr_tools.pkg_util import get_version, CustomClickGroup

from .util import repo_base, print_citation
from .actions import use_github_action
from .github import copy_ruleset, list_rulesets


@click.group(
    cls=CustomClickGroup, context_settings=dict(help_option_names=["-h", "--help"])
)
@click.version_option(get_version(repo_base=repo_base), "-v", "--version", is_flag=True)
@click.option(
    "--citation",
    "-c",
    is_flag=True,
    callback=print_citation,
    expose_value=False,
    is_eager=True,
    help="Print the citation in bibtex format and exit.",
)
def cli():
    """
    GitHub Actions Workflows for CCBR repositories

    For more options, run:
    ccbr_actions [command] --help

    https://ccbr.github.io/actions/
    """
    pass


@click.command()
@click.argument("name")
def use_example(name):
    """
    Use a GitHub Actions workflow file from CCBR/actions.

    \b
    Args:
        name (str): The name of the example workflow file to download.

    \b
    Examples:
        ccbr_actions use-example docs-mkdocs
        ccbr_actions use-example build-nextflow

    See list of workflow files here:
    https://ccbr.github.io/actions/examples.html
    """
    use_github_action(name)


cli.add_command(use_example)


@click.command()
@click.argument("repo")
@click.option(
    "--token",
    "-t",
    envvar="GH_TOKEN",
    default=None,
    help="GitHub token with repo scope. Defaults to the GH_TOKEN environment variable.",
)
def list_rulesets_cmd(repo, token):
    """
    List all rulesets for a GitHub repository.

    \b
    Args:
        repo (str): Repository in owner/repo format.

    \b
    Examples:
        ccbr_actions list-rulesets CCBR/actions
        ccbr_actions list-rulesets CCBR/actions --token ghp_...
    """
    rulesets = list_rulesets(repo=repo, token=token)
    if not rulesets:
        click.echo(f"No rulesets found in {repo}.")
        return
    for r in rulesets:
        click.echo(f"{r['id']:>10}  {r['enforcement']:<12}  {r['name']}")


cli.add_command(list_rulesets_cmd, name="list-rulesets")


@click.command()
@click.argument("source-repo")
@click.argument("target-repo")
@click.argument("ruleset-name")
@click.option(
    "--token",
    "-t",
    envvar="GH_TOKEN",
    default=None,
    help="GitHub token with repo scope. Defaults to the GH_TOKEN environment variable.",
)
def copy_ruleset_cmd(source_repo, target_repo, ruleset_name, token):
    """
    Copy a ruleset from one GitHub repository to another.

    \b
    Args:
        source-repo (str): Source repository in owner/repo format.
        target-repo (str): Target repository in owner/repo format.
        ruleset-name (str): Name of the ruleset to copy.

    \b
    Examples:
        ccbr_actions copy-ruleset CCBR/actions CCBR/other-repo "Require PR reviews"
        ccbr_actions copy-ruleset CCBR/actions CCBR/other-repo "Require PR reviews" --token ghp_...
    """
    result = copy_ruleset(
        source_repo=source_repo,
        target_repo=target_repo,
        ruleset_name=ruleset_name,
        token=token,
    )
    click.echo(
        f"Ruleset '{result['name']}' (id={result['id']}) created in {target_repo}."
    )


cli.add_command(copy_ruleset_cmd, name="copy-ruleset")


def main():
    """Run the Click CLI entry point."""
    cli()


if __name__ == "__main__":
    cli(prog_name="ccbr_actions")
