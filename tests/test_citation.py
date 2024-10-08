import os
import pathlib
import shutil
import tempfile

from ccbr_actions.citation import print_citation, update_citation
from ccbr_tools.shell import exec_in_context


def test_print_citation():
    assert "title = {CCBR actions: GitHub Actions for CCBR repos}," in exec_in_context(
        print_citation
    )


def test_update_citation():
    print_out = exec_in_context(
        update_citation,
        citation_file="CITATION.cff",
        version="v99",
        date="2024-08-13",
        debug=True,
    )
    assert all(
        [
            "version: v99" in print_out,
            "date-released: '2024-08-13'" in print_out,
            "title: 'CCBR actions: GitHub Actions for CCBR repos'" in print_out,
        ]
    )


def test_update_citation_symlink():
    with tempfile.TemporaryDirectory() as tmp_dir:
        shutil.copy("tests/data/CITATION.cff", tmp_dir)
        src_path = pathlib.Path(tmp_dir) / "CITATION.cff"
        link_path = pathlib.Path(tmp_dir) / "citation_link"
        os.symlink(src_path, link_path)
        update_citation(citation_file=link_path, version="v99", date="2024-08-13")
        with open(src_path, "r") as infile:
            citation = infile.read()
    assert all(
        [
            "version: v99" in citation,
            "date-released: '2024-08-13'" in citation,
            "title: 'CCBR actions: GitHub Actions for CCBR repos'" in citation,
        ]
    )
