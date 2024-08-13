from cffconvert.cli.create_citation import create_citation
from cffconvert.cli.validate_or_write_output import validate_or_write_output
import yaml

from .util import date_today


def print_citation(
    citation_file="CITATION.cff",
    output_format="bibtex",
):
    citation = create_citation(citation_file, None)
    # click.echo(citation._implementation.cffobj['message'])
    validate_or_write_output(None, output_format, False, citation)


def update_citation(
    citation_file="CITATION.cff",
    version="${{ steps.set-version.output.NEXT_VERSION }}",
    date=date_today(),
    debug=False,
):
    citation = create_citation(citation_file, None)
    citation._implementation.cffobj["version"] = version
    citation._implementation.cffobj["date-released"] = date
    citation_yaml = yaml.dump(
        citation._implementation.cffobj, sort_keys=False, indent=2
    )
    if debug:
        print(citation_yaml)
    else:
        with open(citation_file, "w") as outfile:
            outfile.write(citation_yaml)
