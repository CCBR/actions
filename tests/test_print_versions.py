import pytest
import shutil

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
        shell_run("bash scripts/print_versions.sh --config nonexistent/file.txt")


def test_print_versions_sh_header(data_dir_rel):
    """Test that bash version outputs correct header with config input."""
    config_path = data_dir_rel / "tool_version_commands.txt"
    out = shell_run(f"bash scripts/print_versions.sh --config {config_path}")
    assert "| Tool | Version |" in out
    assert "|---------|---------|" in out


def test_print_versions_sh_legacy_json_option(data_dir_rel):
    """Test that bash version accepts legacy --json option for compatibility."""
    config_path = data_dir_rel / "tool_version_commands.txt"
    out = shell_run(f"bash scripts/print_versions.sh --json {config_path}")
    assert "| Tool | Version |" in out


def test_print_versions_sh_outfile(tmp_path, data_dir_rel):
    """Test that bash version writes to output file correctly."""
    config_path = data_dir_rel / "tool_version_commands.txt"
    filename = tmp_path / "table.md"
    # print to stdout
    out_print = shell_run(f"bash scripts/print_versions.sh --config {config_path}")
    # write to file
    shell_run(
        f"bash scripts/print_versions.sh --config {config_path} --output {filename}"
    )
    with open(filename, "r") as md_file:
        out_file = md_file.read()
    assert out_print.strip() == out_file.strip()


def test_print_versions_sh_append(tmp_path, data_dir_rel):
    """Test that bash version appends to existing file."""
    config_path = data_dir_rel / "tool_version_commands.txt"
    infilename = data_dir_rel / "example_readme.md"
    with open(infilename, "r") as md_file:
        in_text = md_file.read()

    outfilename = tmp_path / "example_readme.md"
    shutil.copyfile(infilename, outfilename)

    shell_run(
        f"bash scripts/print_versions.sh --config {config_path} --output {outfilename}"
    )
    with open(outfilename, "r") as md_file:
        out_text = md_file.read()
    assert out_text.startswith(in_text)
    assert len(out_text) > len(in_text)
