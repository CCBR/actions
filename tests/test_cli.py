import os
import pathlib
import tempfile
from ccbr_tools.shell import shell_run


def test_citation():
    assert shell_run("ccbr_actions --citation")


def test_version():
    assert shell_run("ccbr_actions --version")


def test_use_example():
    with tempfile.TemporaryDirectory() as tmpdir:
        current_wd = pathlib.Path.cwd()
        os.chdir(tmpdir)
        outfile = pathlib.Path(tmpdir) / ".github" / "workflows" / "build-nextflow.yml"
        shell_run("ccbr_actions use-example build-nextflow")
        os.chdir(current_wd)
        assertions = [outfile.exists()]
    assert all(assertions)
