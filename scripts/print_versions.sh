#!/usr/bin/env bash
#
# Generate a Markdown table of command versions from a config file.
# Usage: ./print_versions.sh --config <path_to_config> [--output <output_file>]
#
# Config file format (delimiter is ::):
# tool_name::command_in_path::version_txt::version_command
#

set -euo pipefail

config_file=""
output_file=""

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            config_file="$2"
            shift 2
            ;;
        --json)
            # Legacy option, treat as --config
            config_file="$2"
            shift 2
            ;;
        --output)
            output_file="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$config_file" ]]; then
    echo "Error: --config argument is required" >&2
    exit 1
fi

if [[ ! -f "$config_file" ]]; then
    echo "Error: Config file not found: $config_file" >&2
    exit 1
fi

# Initialize output
output_lines=()
output_lines+=("")
output_lines+=("| Tool | Version |")
output_lines+=("|---------|---------|")

# Read config file and process each tool
while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue

    # Split on :: delimiter
    # We need to handle the case where version_command contains pipes
    # So we split only the first 3 delimiters
    tool=$(echo "$line" | cut -d':' -f1-2 | sed 's/:$//')
    command_name=$(echo "$line" | cut -d':' -f3-4 | sed 's/:$//')
    version_txt=$(echo "$line" | cut -d':' -f5-6 | sed 's/:$//')
    version_command=$(echo "$line" | cut -d':' -f7- | sed 's/^://')

    version_info="NOTINDOCKER"

    # Determine version information based on available details
    if [[ -n "$version_txt" && -f "$version_txt" ]]; then
        version_info=$(head -n 1 "$version_txt" | xargs)
    elif [[ -n "$command_name" ]] && command -v "$command_name" &> /dev/null; then
        if version_output=$(eval "$version_command" 2>/dev/null); then
            # Clean up the version output
            version_info=$(echo "$version_output" \
                | xargs \
                | sed 's/"//g' \
                | sed "s/'//g" \
                | sed 's/(//g' \
                | sed 's/)//g' \
                | xargs)
            [[ -z "$version_info" ]] && version_info="VERSIONUNKNOWN"
        else
            version_info="NOTINDOCKER"
        fi
    fi

    output_lines+=("| $tool | $version_info |")
done < "$config_file"

# Add empty lines
output_lines+=("")

# Output to file or stdout
output_str=$(printf '%s\n' "${output_lines[@]}")
if [[ -n "$output_file" ]]; then
    printf '%s' "$output_str" >> "$output_file"
else
    printf '%s' "$output_str"
fi
