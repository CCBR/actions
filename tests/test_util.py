import os
import shutil

from ccbr_actions.util import precommit_run, path_resolve


def test_precommit():
    assert "usage: pre-commit run [-h]" in precommit_run("--help")


def test_path_resolve_symlink(data_dir):
    assert path_resolve(data_dir / "file_ln") == (data_dir / "file.txt").resolve()


def test_path_resolve_write(tmp_path, data_dir):
    shutil.copy(data_dir / "file.txt", tmp_path)
    src_path = tmp_path / "file.txt"
    link_path = tmp_path / "file_link"
    os.symlink(src_path, link_path)
    with open(path_resolve(link_path), "w") as outfile:
        outfile.write("hello world")
    with open(src_path, "r") as infile:
        text = infile.read()
    assert text == "hello world"
