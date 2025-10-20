import json
import os
import pathlib
import shutil
import tempfile

from ccbr_actions.citation import print_citation, update_citation, write_citation
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


def test_write_citation_codemeta():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # codemeta_filename = pathlib.Path(tmp_dir) / "codemeta.json"
        codemeta_filename = "test.codemeta.json"
        write_citation(
            citation_file=pathlib.Path("tests") / "data" / "CITATION.cff",
            output_file=codemeta_filename,
            output_format="codemeta",
        )
        with open(codemeta_filename, "r") as infile:
            codemeta_content = json.load(infile)
    assert codemeta_content == {
        "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
        "@type": "SoftwareSourceCode",
        "author": [
            {
                "@id": "https://orcid.org/0000-0003-3283-829X",
                "@type": "Person",
                "affiliation": {
                    "@type": "Organization",
                    "name": "Advanced Biomedical Computational Science, Frederick National Laboratory for Cancer Research, Frederick, MD 21702, USA",
                },
                "familyName": "Sovacool",
                "givenName": "Kelly",
            },
            {
                "@id": "https://orcid.org/0000-0001-8978-8495",
                "@type": "Person",
                "affiliation": {
                    "@type": "Organization",
                    "name": "Advanced Biomedical Computational Science, Frederick National Laboratory for Cancer Research, Frederick, MD 21702, USA",
                },
                "familyName": "Koparde",
                "givenName": "Vishal",
            },
        ],
        "codeRepository": "https://github.com/CCBR/actions",
        "license": "https://spdx.org/licenses/MIT",
        "name": "CCBR actions: GitHub Actions for CCBR repos",
        "url": "https://ccbr.github.io/actions/",
    }
