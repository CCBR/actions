import os
import pathlib
import shutil
import tempfile

from ccbr_actions.util import date_today, precommit_run, path_resolve


def test_precommit():
    assert "usage: pre-commit run [-h]" in precommit_run("--help")


def test_path_resolve_symlink():
    assert str(path_resolve("tests/data/file_ln")).endswith("tests/data/file.txt")


def test_path_resolve_write():
    with tempfile.TemporaryDirectory() as tmp_dir:
        shutil.copy("tests/data/file.txt", tmp_dir)
        src_path = pathlib.Path(tmp_dir) / "file.txt"
        link_path = pathlib.Path(tmp_dir) / "file_link"
        os.symlink(src_path, link_path)
        with open(path_resolve(link_path), "w") as outfile:
            outfile.write("hello world")
        with open(src_path, "r") as infile:
            text = infile.read()
    assert text == "hello world"
