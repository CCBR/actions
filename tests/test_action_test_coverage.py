"""Meta-test asserting every composite action has CI test coverage.

See Further Considerations #1 in the coverage plan (issue #50): every
`*/action.yml` must either be exercised by a job in `build-python.yml`
(`uses: ./<action>`) or be explicitly listed here with a reason it cannot be.
"""

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/build-python.yml"
LOCAL_ACTION_USAGE = re.compile(r"uses:\s*\./([^\s@]+)")

# Actions intentionally excluded from per-action integration jobs, with reasons.
UNTESTED_ACTIONS = {
    # Pure API callers with no workspace dependency (see plan Decisions).
    "review-pre-commit-pr": "pure API caller; no workspace dependency",
    "copy-ruleset": "pure API caller; no workspace dependency",
    "maintain-milestones": "pure API caller; no workspace dependency",
    "user-projects": "pure API caller; no workspace dependency",
    "add-issue-label-list": "pure API caller; no workspace dependency",
    "label-issue-repo-name": "pure API caller; no workspace dependency",
    # Side-effecting actions that require secrets or push to real branches,
    # and have no dry-run/debug hook to make them safely testable.
    "mkdocs-mike": "pushes to gh-pages via `mike deploy --push`; no dry-run hook",
    "sync-copilot-instructions": "requires a GitHub App token and targets an external repository",
}


def _action_directories():
    """Yield directories directly containing an action.yml file."""
    return sorted(
        path.parent.name
        for path in REPOSITORY_ROOT.glob("*/action.yml")
        if path.is_file()
    )


def _actions_used_in_build_workflow():
    """Return the set of local action names referenced via `uses: ./<action>`."""
    return set(LOCAL_ACTION_USAGE.findall(BUILD_WORKFLOW.read_text()))


def test_every_action_has_a_test_job_or_documented_exclusion():
    tested_actions = _actions_used_in_build_workflow()
    untested = [
        action_name
        for action_name in _action_directories()
        if action_name not in tested_actions and action_name not in UNTESTED_ACTIONS
    ]
    assert not untested, (
        f"Add a build-python.yml job for {untested}, or document why it is "
        "excluded in tests/test_action_test_coverage.py:UNTESTED_ACTIONS"
    )


def test_documented_exclusions_are_still_untested():
    """Excluded actions should not silently gain a test job without pruning the list."""
    tested_actions = _actions_used_in_build_workflow()
    stale_exclusions = sorted(set(UNTESTED_ACTIONS) & tested_actions)
    assert not stale_exclusions, (
        f"Remove {stale_exclusions} from UNTESTED_ACTIONS since they now have test jobs"
    )
