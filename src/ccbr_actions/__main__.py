"""
Entry point for CCBR Actions
"""

import click

from ccbr_tools.pkg_util import get_version, CustomClickGroup

from .util import repo_base, print_citation
from .actions import use_github_action


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
    <https://ccbr.github.io/actions/examples.html>
    """
    use_github_action(name)


cli.add_command(use_example)


def main():
    cli()


cli(prog_name="ccbr_actions")

if __name__ == "__main__":
    main()
