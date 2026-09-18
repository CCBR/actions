"""Meta-test asserting every composite action has CI test coverage.

See Further Considerations #1 in the coverage plan (issue #50): every
`*/action.yml` must either have a sibling `test/action.yml` (invoked by the
shared `.github/actions/integration-tests` fixture or directly by a workflow)
or be explicitly listed here with a reason it cannot be.
"""

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ACTION_USAGE = re.compile(r"uses:\s*\./([^\s@]+)")
SEARCHED_FILES = (
    REPOSITORY_ROOT / ".github/workflows/build-python.yml",
    REPOSITORY_ROOT / ".github/actions/integration-tests/action.yml",
)

# Actions intentionally excluded from per-action integration tests, with reasons.
UNTESTED_ACTIONS = {
    # Pure API callers with no workspace dependency (see plan Decisions).
    "review-pre-commit-pr": "pure API caller; no workspace dependency",
    "copy-ruleset": "pure API caller; no workspace dependency",
    "user-projects": "pure API caller; no workspace dependency",
    "add-issue-label-list": "pure API caller; no workspace dependency",
    "label-issue-repo-name": "pure API caller; no workspace dependency",
    # Side-effecting actions that require secrets or push to real branches,
    # and have no dry-run/debug hook to make them safely testable.
    "sync-copilot-instructions": "requires a GitHub App token and targets an external repository",
}


def _action_directories():
    """Yield directories directly containing an action.yml file."""
    return sorted(
        path.parent.name
        for path in REPOSITORY_ROOT.glob("*/action.yml")
        if path.is_file()
    )


def _actions_invoked_locally():
    """Return the top-level action names referenced via `uses: ./<action>[/...]`."""
    invoked = set()
    for filepath in SEARCHED_FILES:
        for match in LOCAL_ACTION_USAGE.findall(filepath.read_text()):
            invoked.add(match.split("/")[0])
    return invoked


def test_every_action_has_a_sibling_test_action_or_documented_exclusion():
    invoked = _actions_invoked_locally()
    untested = [
        action_name
        for action_name in _action_directories()
        if action_name not in UNTESTED_ACTIONS
        and (
            action_name not in invoked
            or not (REPOSITORY_ROOT / action_name / "test/action.yml").is_file()
        )
    ]
    assert not untested, (
        f"Add a {untested}/test/action.yml invoked from "
        ".github/actions/integration-tests/action.yml, or document why it is "
        "excluded in tests/test_action_test_coverage.py:UNTESTED_ACTIONS"
    )


def test_documented_exclusions_are_still_untested():
    """Excluded actions should not silently gain a test action without pruning the list."""
    invoked = _actions_invoked_locally()
    stale_exclusions = sorted(set(UNTESTED_ACTIONS) & invoked)
    assert not stale_exclusions, (
        f"Remove {stale_exclusions} from UNTESTED_ACTIONS since they now have test coverage"
    )
