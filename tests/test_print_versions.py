import pathlib
import pytest
import shutil
import tempfile

from ccbr_tools.shell import shell_run


def test_print_versions_errors():
    with pytest.raises(Exception) as exc_info:
        out = shell_run("print_versions.py")
        assert "error: the following arguments are required: --json" in out


def test_print_versions_header():
    out = shell_run("print_versions.py --json tests/data/tool_version_commands.json")
    assert out.startswith("\n| Tool | Version |\n")


def test_print_versions_outfile():
    with tempfile.TemporaryDirectory() as tmp_dir:
        filename = pathlib.Path(tmp_dir) / "table.md"
        # print
        out_print = shell_run(
            "print_versions.py --json tests/data/tool_version_commands.json"
        )
        # write
        shell_run(
            f"print_versions.py --json tests/data/tool_version_commands.json --output {filename}"
        )
        with open(filename, "r") as md_file:
            out_file = md_file.read()
        assert out_print.strip() == out_file.strip()


def test_print_versions_append():
    with tempfile.TemporaryDirectory() as tmp_dir:
        infilename = pathlib.Path("tests") / "data" / "example_readme.md"
        with open(infilename, "r") as md_file:
            in_text = md_file.read()

        outfilename = pathlib.Path(tmp_dir) / "example_readme.md"
        shutil.copyfile(infilename, outfilename)

        shell_run(
            f"print_versions.py --json tests/data/tool_version_commands.json --output {outfilename}"
        )
        with open(outfilename, "r") as md_file:
            out_text = md_file.read()
        assert all([out_text.startswith(in_text), len(out_text) > len(in_text)])
