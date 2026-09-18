"""Tests for the draft-release composite action workflow contract."""

from pathlib import Path

import yaml

ACTION_PATH = Path(__file__).resolve().parents[1] / "draft-release" / "action.yml"


def _load_action():
    """Load the draft-release action metadata and steps."""
    return yaml.safe_load(ACTION_PATH.read_text())


def test_draft_release_allows_missing_semver_metadata():
    action = _load_action()
    semver_step = next(
        step for step in action["runs"]["steps"] if step.get("id") == "semver"
    )

    assert semver_step["continue-on-error"] is True


def test_draft_release_forwards_release_file_inputs():
    action = _load_action()
    prepare_step = next(
        step for step in action["runs"]["steps"] if step.get("id") == "set-version"
    )

    assert 'version_filepath="${{ inputs.version-filepath }}"' in prepare_step["run"]
    assert (
        'description_filepath="${{ inputs.description-filepath }}"'
        in prepare_step["run"]
    )
    assert (
        'changelog_filepath="${{ inputs.changelog-filepath }}"' in prepare_step["run"]
    )
    assert (
        'citation_filepath = "${{ inputs.citation-filepath }}"' in prepare_step["run"]
    )


def test_draft_release_r_setup_requires_description_file():
    action = _load_action()
    setup_steps = [
        step
        for step in action["runs"]["steps"]
        if step.get("uses", "").startswith("r-lib/actions/setup-r")
    ]

    assert len(setup_steps) == 2
    assert all(
        "hashFiles(inputs.description-filepath) != ''" in step["if"]
        for step in setup_steps
    )


def test_draft_release_exposes_dry_run_to_release_helper():
    action = _load_action()
    assert action["inputs"]["dry-run"]["default"] == "false"
    prepare_step = next(
        step for step in action["runs"]["steps"] if step.get("id") == "set-version"
    )

    assert "debug=${{ inputs.dry-run == 'true' }}" in prepare_step["run"]
