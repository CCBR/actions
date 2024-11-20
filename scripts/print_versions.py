#!/usr/bin/env python
import json
import subprocess
import argparse
import shutil
import os

# Set up argument parsing
parser = argparse.ArgumentParser(
    description="Generate a Markdown table of command versions from a JSON file."
)
parser.add_argument(
    "--json",
    required=True,
    type=str,
    help="Path to the JSON file containing commands and their version commands.",
)
parser.add_argument(
    "--output",
    required=False,
    type=str,
    help="Output file path. If not specified, output will be printed to stdout.",
)


def create_table(args):
    """
    Generates a Markdown table with tool versions based on a JSON configuration file.

    Args:
        args: An object containing the following attributes:
            - json (str): Path to the JSON file containing tool version commands.

    Returns:
        list: A list of strings representing the Markdown table with tool names and their versions.
    """
    # Load JSON data
    with open(args.json, "r") as file:
        commands = json.load(file)

    # Prepare table header
    output_list = ["", "| Tool | Version |", "|---------|---------|"]

    # Run each command and capture output
    version_info = ""
    for tool, details in commands.items():
        # Extract command name, version text file path, and version command from details
        command_name = details.get("command_in_path", "")
        version_txt = details.get("version_txt", "")
        version_command = details.get("version_command", "")

        # Determine version information based on the available details
        if command_name == "" and version_txt == "":
            version_info = "NOTINDOCKER"
        elif not version_txt == "":  # version is saved in this txt file
            if os.path.exists(version_txt):
                # Open the file and read the first line
                with open(version_txt, "r") as file:
                    version_info = file.readline().strip()
            else:
                version_info = "NOTINDOCKER"
        else:
            if shutil.which(command_name):
                try:
                    # Run the command and capture its output
                    result = subprocess.run(
                        version_command,
                        shell=True,
                        check=True,
                        text=True,
                        capture_output=True,
                    )
                    # Extract and clean the version information from the command output
                    version_info = (
                        result.stdout.strip()
                        if result.stdout
                        else result.stderr.strip()
                    )
                    version_info = (
                        version_info.strip()
                        .replace('"', "")
                        .replace("'", "")
                        .replace("(", "")
                        .replace(")", "")
                    )
                    version_info = version_info.strip() or "VERSIONUNKNOWN"
                except subprocess.CalledProcessError:
                    # If the command fails, handle the exception
                    version_info = "NOTINDOCKER"
            else:
                version_info = "NOTINDOCKER"

        # Print in Markdown table format
        output_list.append(f"| {tool} | {version_info} |")

    # Add empty lines to the output list
    output_list.append("")
    output_list.append("")

    return output_list


def main(args):
    output_list = create_table(args)
    output_str = "\n".join(output_list)

    if args.output:
        with open(args.output, "a") as outfile:
            outfile.write(output_str)
    else:
        print(output_str, end="")


if __name__ == "__main__":
    args = parser.parse_args()
    main(args)

# test json should look like this:
# {
#     "python3": {
#       "command_in_path": "python3",
#       "version_txt": "",
#       "version_command": "python3 --version 2>&1 | awk '{print $NF}'"
#     },
#     "samtools": {
#       "command_in_path": "samtools",
#       "version_txt": "",
#       "version_command": "samtools --version 2>&1 | head -n1 | awk '{print $NF}'"
#     },
#     "picard": {
#       "command_in_path": "",
#       "version_txt": "/path/to/picard_version.txt",
#       "version_command": ""
#     }
#   }
