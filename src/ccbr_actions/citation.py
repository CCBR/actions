"""Print and update citation files in CFF format."""

from cffconvert.cli.create_citation import create_citation
from cffconvert.cli.validate_or_write_output import validate_or_write_output
import yaml

from .util import date_today, path_resolve


def print_citation(
    citation_file="CITATION.cff",
    output_format="bibtex",
):
    """
    Print the citation in the specified format.

    This function reads a citation file in CFF format and prints it in the specified
    output format using the cffconvert library.

    Args:
        citation_file (str): The path to the citation file (default is "CITATION.cff").
        output_format (str): The format to print the citation in (default is "bibtex").

    Examples:
        >>> print_citation()
        @article{...
    """
    citation = create_citation(citation_file, None)
    # click.echo(citation._implementation.cffobj['message'])
    validate_or_write_output(None, output_format, False, citation)


def write_citation(
    citation_file="CITATION.cff",
    output_file="codemeta.json",
    output_format="codemeta",
):
    """
    Generates a citation metadata file in the specified format.

    Reads citation information from a CITATION.cff file, converts it to the desired output format (default: codemeta),
    and writes it to the specified output file.

    Args:
        citation_file (str): Path to the input CITATION.cff file. (Default: "CITATION.cff").
        output_file (str): Path to the output file where the citation metadata will be written. (Default: "codemeta.json").
        output_format (str): Format of the output citation metadata. See [](`~cffconvert.cli.validate_or_write_output` for options). (Default: "codemeta").

    Returns:
        None
    """
    citation = create_citation(citation_file, None)
    validate_or_write_output(output_file, output_format, False, citation)


def update_citation(
    citation_file="CITATION.cff",
    version="${{ steps.set-version.output.NEXT_VERSION }}",
    date=date_today(),
    debug=False,
):
    """
    Update the citation file with the specified version and date.

    This function updates the version and date-released fields in the citation file
    and writes the updated content back to the file.

    Args:
        citation_file (str): The path to the citation file (default is "CITATION.cff").
        version (str): The version to set in the citation file (default is "${{ steps.set-version.output.NEXT_VERSION }}").
        date (str): The release date to set in the citation file (default is today's date).
        debug (bool): If True, print the updated citation content instead of writing to the file (default is False).

    Examples:
        >>> update_citation(version="1.0.1", date="2023-10-01")
    """
    citation = create_citation(citation_file, None)
    citation._implementation.cffobj["version"] = version
    citation._implementation.cffobj["date-released"] = date
    citation_yaml = yaml.dump(
        citation._implementation.cffobj, sort_keys=False, indent=2
    )
    if debug:
        print(citation_yaml)
    else:
        with open(path_resolve(citation_file), "w") as outfile:
            outfile.write(citation_yaml)
