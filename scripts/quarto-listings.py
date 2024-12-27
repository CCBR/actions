#!/usr/bin/env python
""" Create quarto listing for custom CCBR actions """
import pathlib
from ruamel.yaml import YAML

yaml = YAML(typ="rt")
yaml_str = YAML(typ=["rt", "string"])


def create_actions_listing():
    listing_subdir = pathlib.Path("docs/actions/")
    for action_yml in get_yaml_glob():
        f = action_yml["filename"]
        action_subdir = listing_subdir / f.parent
        action_subdir.mkdir(exist_ok=True, parents=True)

        qmd_meta = {
            "title": action_yml["name"],
            "subtitle": action_yml["description"],
            "author": action_yml["author"],
            "execute": {"echo": False, "output": "asis"},
        }
        with open(f.parent / "README.md", "r") as infile:
            readme_body = (
                infile.read()
                .replace(
                    "/examples/", "https://github.com/CCBR/actions/blob/main/examples/"
                )
                .replace(f"# {action_yml['name']}\n", "")
            )
        with open(action_subdir / "index.qmd", "w") as outfile:
            outfile.write("---\n")
            yaml_str.dump(qmd_meta, outfile)
            outfile.write("---\n")
            outfile.write(readme_body)


def get_yaml_glob():
    for filename in pathlib.Path().glob("*/action.yml"):
        with open(filename, "r") as infile:
            yaml_meta = yaml.load(infile)
            yaml_meta["filename"] = filename
            yield yaml_meta


def write_yaml_object(object, outfilename):
    with open(outfilename, "w") as outfile:
        yaml.dump(object, outfile)


if __name__ == "__main__":
    create_actions_listing()
