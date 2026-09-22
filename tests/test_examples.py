"""Validate the published example workflow contracts."""

import re
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted(
    list((REPOSITORY_ROOT / "examples").glob("*.yml"))
    + list((REPOSITORY_ROOT / "examples").glob("*.yaml"))
)
CURRENT_VERSION = (REPOSITORY_ROOT / "VERSION").read_text().strip()
CURRENT_RELEASE = f"v{CURRENT_VERSION.removesuffix('-dev')}"
ACTION_REFERENCE = re.compile(r"CCBR/actions/([^@\s]+)@([^\s]+)")


def _iter_steps(value):
    """Yield workflow step mappings from nested workflow data."""
    if isinstance(value, dict):
        if "uses" in value:
            yield value
        for nested_value in value.values():
            yield from _iter_steps(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from _iter_steps(nested_value)


def test_examples_use_current_release_refs():
    """Examples should use the current release rather than a moving ref."""
    references = [
        match.group(2)
        for example in EXAMPLES
        for match in ACTION_REFERENCE.finditer(example.read_text())
    ]
    assert references
    assert set(references) == {CURRENT_RELEASE}


def test_examples_reference_declared_inputs_and_required_values():
    """Every example input should be declared and satisfy required metadata."""
    for example in EXAMPLES:
        workflow = yaml.safe_load(example.read_text())
        steps = list(_iter_steps(workflow))
        for action_name, action_ref in ACTION_REFERENCE.findall(example.read_text()):
            action_path = REPOSITORY_ROOT / action_name / "action.yml"
            assert action_path.is_file(), f"{example}: {action_name}@{action_ref}"
            action = yaml.safe_load(action_path.read_text())
            action_inputs = action.get("inputs", {})
            matching_steps = [
                step
                for step in steps
                if step.get("uses") == f"CCBR/actions/{action_name}@{action_ref}"
            ]
            assert matching_steps
            for step in matching_steps:
                supplied_inputs = step.get("with", {})
                unknown_inputs = set(supplied_inputs) - set(action_inputs)
                assert not unknown_inputs, (
                    f"{example}: unknown inputs for {action_name}: {unknown_inputs}"
                )
                for input_name, metadata in action_inputs.items():
                    if metadata.get("required") and "default" not in metadata:
                        assert input_name in supplied_inputs, (
                            f"{example}: missing required input {input_name}"
                        )


def test_docs_examples_glob_both_workflow_extensions():
    """The examples page must include both supported workflow extensions."""
    docs_source = (REPOSITORY_ROOT / "docs/examples.qmd").read_text()
    assert 'glob("../examples/*.yml")' in docs_source
    assert 'glob("../examples/*.yaml")' in docs_source
