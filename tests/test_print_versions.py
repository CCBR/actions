import pathlib
import pytest
import shutil
import tempfile

from ccbr_tools.shell import shell_run


# Tests for Bash version (print_versions.sh)
def test_print_versions_sh_errors():
    """Test that bash version requires --config argument."""
    with pytest.raises(Exception):
        out = shell_run("bash scripts/print_versions.sh")
        assert "error: --config argument is required" in out


def test_print_versions_sh_missing_file():
    """Test that bash version errors on missing config file."""
    with pytest.raises(Exception):
        shell_run("bash scripts/print_versions.sh --config /nonexistent/file.txt")


def test_print_versions_sh_header():
    """Test that bash version outputs correct header with config input."""
    out = shell_run(
        "bash scripts/print_versions.sh --config tests/data/tool_version_commands.txt"
    )
    assert "| Tool | Version |" in out
    assert "|---------|---------|" in out


def test_print_versions_sh_legacy_json_option():
    """Test that bash version accepts legacy --json option for compatibility."""
    out = shell_run(
        "bash scripts/print_versions.sh --json tests/data/tool_version_commands.txt"
    )
    assert "| Tool | Version |" in out


def test_print_versions_sh_outfile():
    """Test that bash version writes to output file correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        filename = pathlib.Path(tmp_dir) / "table.md"
        # print to stdout
        out_print = shell_run(
            "bash scripts/print_versions.sh --config tests/data/tool_version_commands.txt"
        )
        # write to file
        shell_run(
            f"bash scripts/print_versions.sh --config tests/data/tool_version_commands.txt --output {filename}"
        )
        with open(filename, "r") as md_file:
            out_file = md_file.read()
        assert out_print.strip() == out_file.strip()


def test_print_versions_sh_append():
    """Test that bash version appends to existing file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        infilename = pathlib.Path("tests") / "data" / "example_readme.md"
        with open(infilename, "r") as md_file:
            in_text = md_file.read()

        outfilename = pathlib.Path(tmp_dir) / "example_readme.md"
        shutil.copyfile(infilename, outfilename)

        shell_run(
            f"bash scripts/print_versions.sh --config tests/data/tool_version_commands.txt --output {outfilename}"
        )
        with open(outfilename, "r") as md_file:
            out_text = md_file.read()
        assert all([out_text.startswith(in_text), len(out_text) > len(in_text)])
