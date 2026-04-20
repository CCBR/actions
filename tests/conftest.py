import os
import pathlib

import pytest


@pytest.fixture
def github_output_file(tmp_path):
    output_file = tmp_path / "github_output.txt"
    previous_value = os.environ.get("GITHUB_OUTPUT")
    os.environ["GITHUB_OUTPUT"] = str(output_file)
    try:
        yield output_file
    finally:
        if previous_value is None:
            os.environ.pop("GITHUB_OUTPUT", None)
        else:
            os.environ["GITHUB_OUTPUT"] = previous_value


@pytest.fixture
def data_dir():
    return pathlib.Path(__file__).resolve().parent / "data"
