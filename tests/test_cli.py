import os
import pathlib
from ccbr_tools.shell import shell_run


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
        assertions = [outfile.exists()]
    finally:
        os.chdir(current_wd)
    assert all(assertions)
