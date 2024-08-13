from ccbr_actions.citation import print_citation, update_citation
from ccbr_actions.util import exec_in_context, date_today


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
