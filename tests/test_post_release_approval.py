"""Tests for post-release workflow-run approval orchestration."""

import pytest

from ccbr_actions import post_release_approval


def test_approve_post_release_workflow_runs_uses_pr_number(monkeypatch):
    calls = []

    def _approve_pending_runs(repo, pr_number, token):
        calls.append((repo, pr_number, token))
        return [101]

    monkeypatch.setattr(
        post_release_approval,
        "approve_pending_workflow_runs_for_pr",
        _approve_pending_runs,
    )

    result = post_release_approval.approve_post_release_workflow_runs(
        "https://github.com/CCBR/actions/pull/42",
        "CCBR/actions",
        "token",
    )

    assert result == [101]
    assert calls == [("CCBR/actions", "42", "token")]


def test_approve_post_release_workflow_runs_rejects_invalid_pr_url():
    with pytest.raises(ValueError, match="Invalid post-release PR URL"):
        post_release_approval.approve_post_release_workflow_runs(
            "https://github.com/CCBR/actions/pull/not-a-number",
            "CCBR/actions",
            "token",
        )
