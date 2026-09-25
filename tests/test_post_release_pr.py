"""
Tests for ccbr_actions.post_release_pr module.
"""

import base64

import pytest
import requests as requests_lib

from ccbr_actions.post_release_pr import (
    POST_RELEASE_PR_TITLE_PATTERN,
    _file_roles,
    _get_file_content,
    _has_pending_human_review_comment,
    _human_review_marker,
    _is_valid_bump_line,
    _release_bump_values,
    _release_dates,
    _split_tokens,
    _validate_changelog_file,
    _validate_citation_file,
    _validate_codemeta_file,
    _validate_description_file,
    _validate_file_bump,
    _validate_readme_file,
    _validate_version_file,
    check_files_are_valid_bumps,
    check_only_allowed_files_changed,
    determine_post_release_reviewer,
    extract_release_tag,
    get_release_by_tag,
    is_allowed_filename,
    is_post_release_pr,
    review_post_release_pr,
)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests_lib.exceptions.HTTPError(f"HTTP {self.status_code}")


class MockSession:
    """Records calls and returns pre-configured payloads keyed by URL."""

    def __init__(self, payloads=None, post_status=200):
        self.payloads = payloads or {}
        self.post_status = post_status
        self.calls = []

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        status = self.post_status if method == "POST" else 200
        default = {"data": {}} if method == "POST" else {}
        return MockResponse(self.payloads.get(url, default), status)


class ContentSession(MockSession):
    """MockSession variant that also serves file contents keyed by (path, ref)."""

    def __init__(self, contents=None, **kwargs):
        super().__init__(**kwargs)
        self.contents = contents or {}
        self.pr_payloads_sequence = None

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        if "contents/" in url and method == "GET":
            path = url.split("contents/", 1)[1]
            ref = (kwargs.get("params") or {}).get("ref")
            text = self.contents.get((path, ref))
            if text is None:
                response = MockResponse({}, 404)
            else:
                encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
                response = MockResponse({"content": encoded})
        elif self.pr_payloads_sequence is not None and url in self.pr_payloads_sequence:
            queue = self.pr_payloads_sequence[url]
            payload = queue.pop(0) if len(queue) > 1 else queue[0]
            response = MockResponse(payload)
        else:
            status = self.post_status if method == "POST" else 200
            default = {"data": {}} if method == "POST" else {}
            response = MockResponse(self.payloads.get(url, default), status)
        return response


class _RaisingSession(MockSession):
    """Always raises a RequestException on GET."""

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs))
        raise requests_lib.exceptions.ConnectionError("boom")


# ---------------------------------------------------------------------------
# Fixture content, based on CCBR/Tools#229
# ---------------------------------------------------------------------------

RELEASE_TAG = "v0.7.1"
RELEASE_VERSION = "0.7.1"
PR_TITLE = f"chore: post-release cleanup for {RELEASE_TAG}"
RELEASE = {
    "tag_name": RELEASE_TAG,
    "published_at": "2026-09-17T00:00:00Z",
    "created_at": "2026-09-17T00:00:00Z",
}
RELEASE_DATES = {"2026-09-17"}

VERSION_OLD = "0.7.0-dev\n"
VERSION_NEW = "0.7.1-dev\n"

CITATION_OLD = """\
cff-version: 1.2.0
message: If you use this software, please cite it as below.
title: Tools
authors:
  - family-names: Sovacool
    given-names: Kelly
identifiers:
  - type: doi
    value: 10.5281/zenodo.13377166
doi: 10.5281/zenodo.13377166
version: v0.7.0
date-released: "2026-06-10"
"""
CITATION_NEW = CITATION_OLD.replace("version: v0.7.0", "version: v0.7.1").replace(
    'date-released: "2026-06-10"', 'date-released: "2026-09-17"'
)

CODEMETA_OLD = '{"version": "0.7.0"}'
CODEMETA_NEW = '{"version": "0.7.1"}'

CHANGELOG_OLD = (
    "## Tools development version\n\n"
    "- minor documentation improvements. (#197, #198, @kelly-sovacool)\n"
)
CHANGELOG_NEW = (
    "## Tools development version\n\n"
    "## Tools 0.7.1\n\n"
    "- minor documentation improvements. (#197, #198, @kelly-sovacool)\n"
)

README_OLD = (
    "> Sovacool K. (2026). CCBR Tools: Utilities (version v0.7.0).\n  month = {6},\n"
)
README_NEW = (
    "> Sovacool K. (2026). CCBR Tools: Utilities (version v0.7.1).\n  month = {9},\n"
)

DESCRIPTION_OLD = "Package: pkg\nVersion: 0.7.0.9000\nTitle: Example\n"
DESCRIPTION_NEW = "Package: pkg\nVersion: 0.7.1.9000\nTitle: Example\n"


def _default_roles():
    return _file_roles("VERSION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION")


def _default_contents():
    return {
        ("VERSION", "base-sha"): VERSION_OLD,
        ("VERSION", "head-sha"): VERSION_NEW,
        ("CITATION.cff", "base-sha"): CITATION_OLD,
        ("CITATION.cff", "head-sha"): CITATION_NEW,
        ("codemeta.json", "base-sha"): CODEMETA_OLD,
        ("codemeta.json", "head-sha"): CODEMETA_NEW,
        ("CHANGELOG.md", "base-sha"): CHANGELOG_OLD,
        ("CHANGELOG.md", "head-sha"): CHANGELOG_NEW,
        ("README.md", "base-sha"): README_OLD,
        ("README.md", "head-sha"): README_NEW,
    }


def _default_filenames():
    return ["VERSION", "CITATION.cff", "codemeta.json", "CHANGELOG.md", "README.md"]


# ---------------------------------------------------------------------------
# is_post_release_pr / extract_release_tag
# ---------------------------------------------------------------------------


def test_post_release_pr_title_pattern_matches_expected_title():
    assert POST_RELEASE_PR_TITLE_PATTERN.match(PR_TITLE)


def test_is_post_release_pr_returns_true_for_matching_pr():
    assert is_post_release_pr(PR_TITLE, "Bot") is True


def test_is_post_release_pr_returns_false_for_wrong_title():
    assert is_post_release_pr("chore: bump deps", "Bot") is False


def test_is_post_release_pr_returns_false_for_non_bot_sender():
    assert is_post_release_pr(PR_TITLE, "User") is False


def test_extract_release_tag_returns_tag():
    assert extract_release_tag(PR_TITLE) == RELEASE_TAG


def test_extract_release_tag_returns_none_for_wrong_title():
    assert extract_release_tag("chore: bump deps") is None


# ---------------------------------------------------------------------------
# get_release_by_tag
# ---------------------------------------------------------------------------


def test_get_release_by_tag_returns_release_when_found():
    session = MockSession(
        {"https://api.github.com/repos/CCBR/Tools/releases/tags/v0.7.1": RELEASE}
    )
    assert get_release_by_tag("CCBR/Tools", "v0.7.1", session=session) == RELEASE


def test_get_release_by_tag_returns_none_when_missing():
    assert get_release_by_tag("CCBR/Tools", "v9.9.9", session=_RaisingSession()) is None


# ---------------------------------------------------------------------------
# _file_roles / is_allowed_filename / check_only_allowed_files_changed
# ---------------------------------------------------------------------------


def test_file_roles_assigns_expected_roles():
    roles = _default_roles()
    assert roles == {
        "VERSION": "version",
        "CITATION.cff": "citation",
        "codemeta.json": "codemeta",
        "CHANGELOG.md": "changelog",
        "NEWS.md": "changelog",
        "NEWS": "changelog",
        "DESCRIPTION": "description",
    }


def test_is_allowed_filename_matches_basename_regardless_of_path():
    roles = _default_roles()
    assert is_allowed_filename("src/ccbr_tools/VERSION", roles) is True


def test_is_allowed_filename_matches_readme_case_insensitively():
    roles = _default_roles()
    assert is_allowed_filename("Readme.qmd", roles) is True


def test_is_allowed_filename_returns_false_for_disallowed_file():
    roles = _default_roles()
    assert is_allowed_filename("src/main.py", roles) is False


def test_check_only_allowed_files_changed_returns_true_for_pr_files():
    roles = _default_roles()
    pr_files = [{"filename": name} for name in _default_filenames()]
    assert check_only_allowed_files_changed(pr_files, roles) is True


def test_check_only_allowed_files_changed_returns_false_when_extra_file():
    roles = _default_roles()
    pr_files = [{"filename": name} for name in _default_filenames()] + [
        {"filename": "src/main.py"}
    ]
    assert check_only_allowed_files_changed(pr_files, roles) is False


def test_check_only_allowed_files_changed_returns_false_when_empty():
    roles = _default_roles()
    assert check_only_allowed_files_changed([], roles) is False


# ---------------------------------------------------------------------------
# _release_bump_values / _split_tokens / _is_valid_bump_line
# ---------------------------------------------------------------------------


def test_release_bump_values_includes_version_and_date_tokens():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert "v0.7.1" in values
    assert "0.7.1" in values
    assert "0.7.1-dev" in values
    assert "2026-09-17" in values
    assert "9" in values


def test_release_dates_extracts_published_and_created_dates():
    assert _release_dates(RELEASE) == RELEASE_DATES


def test_release_dates_ignores_missing_or_malformed_dates():
    assert _release_dates({"published_at": "", "created_at": "not-a-date"}) == set()


def test_split_tokens_separates_text_and_numeric_tokens():
    text, tokens = _split_tokens("version: v0.7.0")
    assert tokens == ["0.7.0"]
    assert text == ["version: v", ""]


def test_is_valid_bump_line_accepts_version_bump():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _is_valid_bump_line("(version v0.7.0).", "(version v0.7.1).", values) is True


def test_is_valid_bump_line_rejects_non_matching_version():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _is_valid_bump_line("v0.7.0", "v9.9.9", values) is False


def test_is_valid_bump_line_rejects_changed_surrounding_text():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _is_valid_bump_line("version: v0.7.0", "ver: v0.7.1", values) is False


# ---------------------------------------------------------------------------
# _get_file_content
# ---------------------------------------------------------------------------


def test_get_file_content_returns_decoded_text():
    encoded = base64.b64encode(b"hello world").decode("ascii")
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/Tools/contents/VERSION": {
                "content": encoded
            }
        }
    )
    result = _get_file_content("CCBR/Tools", "VERSION", "abc", session=session)
    assert result == "hello world"


def test_get_file_content_returns_none_when_missing():
    result = _get_file_content(
        "CCBR/Tools", "VERSION", "abc", session=_RaisingSession()
    )
    assert result is None


def test_get_file_content_returns_none_for_invalid_base64():
    session = MockSession(
        {
            "https://api.github.com/repos/CCBR/Tools/contents/VERSION": {
                "content": "not-valid-base64!!"
            }
        }
    )
    result = _get_file_content("CCBR/Tools", "VERSION", "abc", session=session)
    assert result is None


# ---------------------------------------------------------------------------
# _validate_version_file
# ---------------------------------------------------------------------------


def test_validate_version_file_accepts_exact_dev_bump():
    assert _validate_version_file(VERSION_NEW, RELEASE_VERSION) is True


def test_validate_version_file_rejects_wrong_version():
    assert _validate_version_file("9.9.9-dev\n", RELEASE_VERSION) is False


def test_validate_version_file_rejects_missing_content():
    assert _validate_version_file(None, RELEASE_VERSION) is False


# ---------------------------------------------------------------------------
# _validate_description_file
# ---------------------------------------------------------------------------


def test_validate_description_file_accepts_valid_r_dev_bump():
    assert (
        _validate_description_file(DESCRIPTION_OLD, DESCRIPTION_NEW, RELEASE_VERSION)
        is True
    )


def test_validate_description_file_rejects_other_field_changes():
    tampered = DESCRIPTION_NEW.replace("Title: Example", "Title: Tampered")
    assert (
        _validate_description_file(DESCRIPTION_OLD, tampered, RELEASE_VERSION) is False
    )


def test_validate_description_file_rejects_wrong_version():
    tampered = DESCRIPTION_OLD.replace("Version: 0.7.0.9000", "Version: 9.9.9.9000")
    assert (
        _validate_description_file(DESCRIPTION_OLD, tampered, RELEASE_VERSION) is False
    )


def test_validate_description_file_rejects_missing_content():
    assert _validate_description_file(None, DESCRIPTION_NEW, RELEASE_VERSION) is False


def test_validate_description_file_rejects_non_semver_release_version():
    assert (
        _validate_description_file(DESCRIPTION_OLD, DESCRIPTION_NEW, "not-semver")
        is False
    )


def test_validate_description_file_rejects_line_count_mismatch():
    new_with_extra_line = DESCRIPTION_NEW + "Extra: field\n"
    assert (
        _validate_description_file(
            DESCRIPTION_OLD, new_with_extra_line, RELEASE_VERSION
        )
        is False
    )


# ---------------------------------------------------------------------------
# _validate_citation_file
# ---------------------------------------------------------------------------


def test_validate_citation_file_accepts_valid_bump():
    assert (
        _validate_citation_file(CITATION_OLD, CITATION_NEW, RELEASE_TAG, RELEASE_DATES)
        is True
    )


def test_validate_citation_file_rejects_other_field_changes():
    tampered = CITATION_NEW.replace("title: Tools", "title: Tampered")
    assert (
        _validate_citation_file(CITATION_OLD, tampered, RELEASE_TAG, RELEASE_DATES)
        is False
    )


def test_validate_citation_file_rejects_version_not_matching_release():
    tampered = CITATION_NEW.replace("version: v0.7.1", "version: v9.9.9")
    assert (
        _validate_citation_file(CITATION_OLD, tampered, RELEASE_TAG, RELEASE_DATES)
        is False
    )


def test_validate_citation_file_rejects_malformed_date():
    tampered = CITATION_NEW.replace(
        'date-released: "2026-09-17"', 'date-released: "not-a-date"'
    )
    assert (
        _validate_citation_file(CITATION_OLD, tampered, RELEASE_TAG, RELEASE_DATES)
        is False
    )


def test_validate_citation_file_rejects_date_not_matching_release():
    # Well-formed date, but not the actual release date.
    tampered = CITATION_NEW.replace(
        'date-released: "2026-09-17"', 'date-released: "2099-01-01"'
    )
    assert (
        _validate_citation_file(CITATION_OLD, tampered, RELEASE_TAG, RELEASE_DATES)
        is False
    )


def test_validate_citation_file_rejects_invalid_yaml():
    assert (
        _validate_citation_file(
            CITATION_OLD, "not: valid: yaml: [", RELEASE_TAG, RELEASE_DATES
        )
        is False
    )


# ---------------------------------------------------------------------------
# _validate_codemeta_file
# ---------------------------------------------------------------------------


def test_validate_codemeta_file_accepts_matching_version():
    assert (
        _validate_codemeta_file(
            CODEMETA_OLD, CODEMETA_NEW, RELEASE_VERSION, RELEASE_TAG, RELEASE_DATES
        )
        is True
    )


def test_validate_codemeta_file_accepts_missing_version_field():
    assert (
        _validate_codemeta_file("{}", "{}", RELEASE_VERSION, RELEASE_TAG, RELEASE_DATES)
        is True
    )


def test_validate_codemeta_file_rejects_mismatched_version():
    assert (
        _validate_codemeta_file(
            CODEMETA_OLD,
            '{"version": "9.9.9"}',
            RELEASE_VERSION,
            RELEASE_TAG,
            RELEASE_DATES,
        )
        is False
    )


def test_validate_codemeta_file_rejects_invalid_json():
    assert (
        _validate_codemeta_file(
            CODEMETA_OLD, "not json", RELEASE_VERSION, RELEASE_TAG, RELEASE_DATES
        )
        is False
    )


def test_validate_codemeta_file_rejects_unrelated_field_replacement():
    # A completely different JSON object must not pass just because the old
    # content is ignored and the version happens to be absent.
    tampered = '{"name": "Totally different metadata", "license": "MIT"}'
    assert (
        _validate_codemeta_file(
            CODEMETA_OLD, tampered, RELEASE_VERSION, RELEASE_TAG, RELEASE_DATES
        )
        is False
    )


# ---------------------------------------------------------------------------
# _validate_changelog_file
# ---------------------------------------------------------------------------


def test_validate_changelog_file_accepts_expected_heading_insertion():
    assert (
        _validate_changelog_file(
            CHANGELOG_OLD, CHANGELOG_NEW, RELEASE_VERSION, "development version"
        )
        is True
    )


def test_validate_changelog_file_rejects_unrelated_bullet_insertion():
    tampered = CHANGELOG_OLD + "- an unrelated bullet\n"
    assert (
        _validate_changelog_file(
            CHANGELOG_OLD, tampered, RELEASE_VERSION, "development version"
        )
        is False
    )


def test_validate_changelog_file_rejects_missing_dev_header():
    old_without_header = "- a bullet\n"
    new_with_insertion = "## Tools 0.7.1\n\n- a bullet\n"
    assert (
        _validate_changelog_file(
            old_without_header,
            new_with_insertion,
            RELEASE_VERSION,
            "development version",
        )
        is False
    )


def test_validate_changelog_file_rejects_heading_without_release_version():
    tampered = CHANGELOG_NEW.replace("## Tools 0.7.1", "## Tools 9.9.9")
    assert (
        _validate_changelog_file(
            CHANGELOG_OLD, tampered, RELEASE_VERSION, "development version"
        )
        is False
    )


def test_validate_changelog_file_rejects_missing_content():
    assert (
        _validate_changelog_file(
            None, CHANGELOG_NEW, RELEASE_VERSION, "development version"
        )
        is False
    )


# ---------------------------------------------------------------------------
# _validate_readme_file
# ---------------------------------------------------------------------------


def test_validate_readme_file_accepts_token_bumps():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _validate_readme_file(README_OLD, README_NEW, values) is True


def test_validate_readme_file_rejects_inserted_lines():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    tampered = README_NEW + "Imports: unsafe-package (>= 0.7.1)\n"
    assert _validate_readme_file(README_OLD, tampered, values) is False


def test_validate_readme_file_rejects_unrelated_line_change():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    tampered = README_NEW.replace("Sovacool K.", "Someone Else.")
    assert _validate_readme_file(README_OLD, tampered, values) is False


def test_validate_readme_file_rejects_missing_content():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert _validate_readme_file(None, README_NEW, values) is False


def test_validate_readme_file_rejects_bump_outside_citation_context():
    # "9" happens to equal the release month, but this line has nothing to do
    # with the citation snippet (e.g. an issue reference), so it must not
    # pass just because the token is individually valid.
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    old = "Fixes #6 for details.\n" + README_OLD
    new = "Fixes #9 for details.\n" + README_OLD
    assert _validate_readme_file(old, new, values) is False


# ---------------------------------------------------------------------------
# _validate_file_bump dispatch
# ---------------------------------------------------------------------------


def test_validate_file_bump_dispatches_to_version_validator():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert (
        _validate_file_bump(
            "version",
            VERSION_OLD,
            VERSION_NEW,
            RELEASE_TAG,
            RELEASE_VERSION,
            RELEASE_DATES,
            "development version",
            values,
        )
        is True
    )


def test_validate_file_bump_dispatches_to_readme_validator_by_default():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert (
        _validate_file_bump(
            "readme",
            README_OLD,
            README_NEW,
            RELEASE_TAG,
            RELEASE_VERSION,
            RELEASE_DATES,
            "development version",
            values,
        )
        is True
    )


def test_validate_file_bump_dispatches_to_description_validator():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert (
        _validate_file_bump(
            "description",
            DESCRIPTION_OLD,
            DESCRIPTION_NEW,
            RELEASE_TAG,
            RELEASE_VERSION,
            RELEASE_DATES,
            "development version",
            values,
        )
        is True
    )


def test_validate_file_bump_dispatches_to_citation_validator():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert (
        _validate_file_bump(
            "citation",
            CITATION_OLD,
            CITATION_NEW,
            RELEASE_TAG,
            RELEASE_VERSION,
            RELEASE_DATES,
            "development version",
            values,
        )
        is True
    )


def test_validate_file_bump_dispatches_to_codemeta_validator():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert (
        _validate_file_bump(
            "codemeta",
            CODEMETA_OLD,
            CODEMETA_NEW,
            RELEASE_TAG,
            RELEASE_VERSION,
            RELEASE_DATES,
            "development version",
            values,
        )
        is True
    )


def test_validate_file_bump_dispatches_to_changelog_validator():
    values = _release_bump_values(RELEASE_TAG, RELEASE)
    assert (
        _validate_file_bump(
            "changelog",
            CHANGELOG_OLD,
            CHANGELOG_NEW,
            RELEASE_TAG,
            RELEASE_VERSION,
            RELEASE_DATES,
            "development version",
            values,
        )
        is True
    )


# ---------------------------------------------------------------------------
# check_files_are_valid_bumps
# ---------------------------------------------------------------------------


def test_check_files_are_valid_bumps_returns_true_for_valid_pr():
    session = ContentSession(contents=_default_contents())
    result = check_files_are_valid_bumps(
        "CCBR/Tools",
        _default_filenames(),
        _default_roles(),
        RELEASE_TAG,
        RELEASE,
        "development version",
        "base-sha",
        "head-sha",
        "VERSION",
        "DESCRIPTION",
        session=session,
    )
    assert result is True


def test_check_files_are_valid_bumps_returns_false_when_version_file_not_changed():
    filenames = ["README.md"]
    session = ContentSession(contents=_default_contents())
    result = check_files_are_valid_bumps(
        "CCBR/Tools",
        filenames,
        _default_roles(),
        RELEASE_TAG,
        RELEASE,
        "development version",
        "base-sha",
        "head-sha",
        "VERSION",
        "DESCRIPTION",
        session=session,
    )
    assert result is False


def test_check_files_are_valid_bumps_returns_false_when_one_file_invalid():
    contents = _default_contents()
    contents[("CHANGELOG.md", "head-sha")] = CHANGELOG_OLD + "- unrelated bullet\n"
    session = ContentSession(contents=contents)
    result = check_files_are_valid_bumps(
        "CCBR/Tools",
        _default_filenames(),
        _default_roles(),
        RELEASE_TAG,
        RELEASE,
        "development version",
        "base-sha",
        "head-sha",
        "VERSION",
        "DESCRIPTION",
        session=session,
    )
    assert result is False


def test_check_files_are_valid_bumps_counts_r_description_bump_as_version_bump():
    # For an R package, version-filepath and description-filepath are both
    # DESCRIPTION; a validated description bump must satisfy the version-bump
    # audit even though no basename maps to the "version" role.
    roles = _file_roles("DESCRIPTION", "CITATION.cff", "CHANGELOG.md", "DESCRIPTION")
    contents = {
        ("DESCRIPTION", "base-sha"): DESCRIPTION_OLD,
        ("DESCRIPTION", "head-sha"): DESCRIPTION_NEW,
    }
    session = ContentSession(contents=contents)
    result = check_files_are_valid_bumps(
        "CCBR/Tools",
        ["DESCRIPTION"],
        roles,
        RELEASE_TAG,
        RELEASE,
        "development version",
        "base-sha",
        "head-sha",
        "DESCRIPTION",
        "DESCRIPTION",
        session=session,
    )
    assert result is True


# ---------------------------------------------------------------------------
# determine_post_release_reviewer
# ---------------------------------------------------------------------------


def test_determine_post_release_reviewer_prefers_explicit_reviewer():
    session = MockSession({})
    result = determine_post_release_reviewer(
        "CCBR/Tools", reviewer="explicit-user", token="tok", session=session
    )
    assert result == "explicit-user"
    assert session.calls == []


def test_determine_post_release_reviewer_uses_last_draft_release_actor():
    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    session = MockSession(
        {runs_url: {"workflow_runs": [{"triggering_actor": {"login": "actor-user"}}]}}
    )
    result = determine_post_release_reviewer("CCBR/Tools", token="tok", session=session)
    assert result == "actor-user"


def test_determine_post_release_reviewer_falls_back_to_default_codeowner():
    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    content = "* @default-owner\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    session = MockSession(
        {
            runs_url: {"workflow_runs": []},
            "https://api.github.com/repos/CCBR/Tools/contents/CODEOWNERS": {
                "content": encoded
            },
        }
    )
    result = determine_post_release_reviewer("CCBR/Tools", token="tok", session=session)
    assert result == "default-owner"


def test_determine_post_release_reviewer_returns_none_when_nothing_resolves():
    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    session = MockSession({runs_url: {"workflow_runs": []}})
    result = determine_post_release_reviewer("CCBR/Tools", token="tok", session=session)
    assert result is None


# ---------------------------------------------------------------------------
# _human_review_marker / _has_pending_human_review_comment
# ---------------------------------------------------------------------------


def test_human_review_marker_embeds_commit_sha():
    marker = _human_review_marker("abc123")
    assert (
        marker
        == "<!-- ccbr-actions:review-post-release-pr:needs-human-review:abc123 -->"
    )


def test_has_pending_human_review_comment_returns_true_for_matching_marker():
    comments_url = "https://api.github.com/repos/CCBR/Tools/issues/9/comments"
    session = MockSession(
        {comments_url: [{"body": f"hello\n\n{_human_review_marker('abc123')}"}]}
    )
    assert (
        _has_pending_human_review_comment(
            "CCBR/Tools", 9, "abc123", token="tok", session=session
        )
        is True
    )


def test_has_pending_human_review_comment_returns_false_for_different_commit():
    comments_url = "https://api.github.com/repos/CCBR/Tools/issues/9/comments"
    session = MockSession(
        {comments_url: [{"body": f"hello\n\n{_human_review_marker('old-sha')}"}]}
    )
    assert (
        _has_pending_human_review_comment(
            "CCBR/Tools", 9, "abc123", token="tok", session=session
        )
        is False
    )


def test_has_pending_human_review_comment_returns_false_on_request_error():
    assert (
        _has_pending_human_review_comment(
            "CCBR/Tools", 9, "abc123", token="tok", session=_RaisingSession()
        )
        is False
    )


# ---------------------------------------------------------------------------
# review_post_release_pr
# ---------------------------------------------------------------------------


def _make_review_session(
    *,
    pr_files=None,
    pr_node_payload=None,
    graphql_payload=None,
    release_payload=None,
    existing_reviews=None,
    existing_comments=None,
    action_required_runs=None,
    contents=None,
    second_pr_node_payload=None,
):
    """Build a ContentSession suitable for review_post_release_pr tests."""
    if pr_files is None:
        pr_files = [{"filename": name} for name in _default_filenames()]
    if pr_node_payload is None:
        pr_node_payload = {
            "node_id": "PR_NODE_9",
            "title": PR_TITLE,
            "user": {"type": "Bot"},
            "head": {"ref": "release/v0.7.1", "sha": "head-sha"},
            "base": {"sha": "base-sha"},
            "changed_files": len(pr_files),
        }
    if graphql_payload is None:
        graphql_payload = {
            "data": {
                "enablePullRequestAutoMerge": {
                    "pullRequest": {"autoMergeRequest": {"enabledAt": "2026-09-17"}}
                }
            }
        }
    if release_payload is None:
        release_payload = RELEASE
    if contents is None:
        contents = _default_contents()

    pr_files_url = "https://api.github.com/repos/CCBR/Tools/pulls/9/files"
    pr_node_url = "https://api.github.com/repos/CCBR/Tools/pulls/9"
    graphql_url = "https://api.github.com/graphql"
    reviews_url = "https://api.github.com/repos/CCBR/Tools/pulls/9/reviews"
    reviewers_url = (
        "https://api.github.com/repos/CCBR/Tools/pulls/9/requested_reviewers"
    )
    comments_url = "https://api.github.com/repos/CCBR/Tools/issues/9/comments"
    release_url = f"https://api.github.com/repos/CCBR/Tools/releases/tags/{RELEASE_TAG}"
    runs_url = "https://api.github.com/repos/CCBR/Tools/actions/runs"
    draft_runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )

    payloads = {
        pr_files_url: pr_files,
        pr_node_url: pr_node_payload,
        graphql_url: graphql_payload,
        reviews_url: existing_reviews if existing_reviews is not None else [],
        reviewers_url: {},
        comments_url: existing_comments if existing_comments is not None else [],
        release_url: release_payload,
        runs_url: {"workflow_runs": action_required_runs or []},
        draft_runs_url: {"workflow_runs": []},
    }
    session = ContentSession(contents=contents, payloads=payloads)
    if second_pr_node_payload is not None:
        session.pr_payloads_sequence = {
            pr_node_url: [pr_node_payload, second_pr_node_payload]
        }
    return session


def test_review_post_release_pr_approves_when_conditions_met():
    session = _make_review_session()
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert any("reviews" in u for u in posted_urls)
    assert any("graphql" in u for u in posted_urls)
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)
    assert any(body.get("commit_id") == "head-sha" for body in review_bodies)


def test_review_post_release_pr_defers_to_active_changes_requested_review():
    # Even though the file checks would otherwise pass, an active human
    # CHANGES_REQUESTED review must block automatic approval.
    session = _make_review_session(
        existing_reviews=[{"user": {"login": "human"}, "state": "CHANGES_REQUESTED"}]
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert not any(body.get("event") == "APPROVE" for body in review_bodies)
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "changes requested" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_approves_pending_workflow_runs():
    session = _make_review_session(
        action_required_runs=[{"id": 555, "head_sha": "head-sha"}]
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    approve_run_urls = [
        c[1]
        for c in session.calls
        if c[0] == "POST" and "actions/runs/555/approve" in c[1]
    ]
    assert approve_run_urls


def test_review_post_release_pr_does_not_approve_workflow_runs_for_other_commits():
    session = _make_review_session(
        action_required_runs=[{"id": 555, "head_sha": "unrelated-sha"}]
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    approve_run_urls = [
        c[1]
        for c in session.calls
        if c[0] == "POST" and "actions/runs/555/approve" in c[1]
    ]
    assert not approve_run_urls


def test_review_post_release_pr_skips_when_current_review_is_approved():
    session = _make_review_session(
        existing_reviews=[
            {
                "user": {"login": "ccbr-bot"},
                "state": "APPROVED",
                "commit_id": "head-sha",
            }
        ]
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert not posted_urls


def test_review_post_release_pr_revalidates_when_approval_is_stale():
    # Approval exists but was left on an earlier commit (e.g. before an
    # auto-format push), so it must not count and the PR must be re-validated.
    session = _make_review_session(
        existing_reviews=[
            {"user": {"login": "ccbr-bot"}, "state": "APPROVED", "commit_id": "old-sha"}
        ]
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)


def test_review_post_release_pr_reviews_again_when_force_review_is_enabled():
    session = _make_review_session(
        existing_reviews=[
            {
                "user": {"login": "ccbr-bot"},
                "state": "APPROVED",
                "commit_id": "head-sha",
            }
        ]
    )
    result = review_post_release_pr(
        "CCBR/Tools", 9, force_review=True, token="tok", session=session
    )
    assert result is True
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    assert any(c[2]["json"].get("event") == "APPROVE" for c in review_calls)


def test_review_post_release_pr_requests_human_review_when_extra_file_changed():
    pr_files = [{"filename": name} for name in _default_filenames()] + [
        {"filename": "src/main.py"}
    ]
    session = _make_review_session(pr_files=pr_files)
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert not any(body.get("event") == "APPROVE" for body in review_bodies)
    assert any("issues/9/comments" in u for u in posted_urls)


def test_review_post_release_pr_skips_duplicate_human_review_comment_for_same_commit():
    pr_files = [{"filename": name} for name in _default_filenames()] + [
        {"filename": "src/main.py"}
    ]
    existing_comments = [
        {
            "body": (
                "This post-release cleanup PR requires human review.\n\n"
                "<!-- ccbr-actions:review-post-release-pr:needs-human-review:head-sha -->"
            )
        }
    ]
    session = _make_review_session(
        pr_files=pr_files, existing_comments=existing_comments
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert not any("issues/9/comments" in u for u in posted_urls)
    assert not any("requested_reviewers" in u for u in posted_urls)


def test_review_post_release_pr_reposts_comment_for_different_commit_marker():
    pr_files = [{"filename": name} for name in _default_filenames()] + [
        {"filename": "src/main.py"}
    ]
    existing_comments = [
        {
            "body": "<!-- ccbr-actions:review-post-release-pr:needs-human-review:old-sha -->"
        }
    ]
    session = _make_review_session(
        pr_files=pr_files, existing_comments=existing_comments
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert any("issues/9/comments" in u for u in posted_urls)


def test_review_post_release_pr_reposts_duplicate_comment_when_force_review_enabled():
    pr_files = [{"filename": name} for name in _default_filenames()] + [
        {"filename": "src/main.py"}
    ]
    existing_comments = [
        {
            "body": "<!-- ccbr-actions:review-post-release-pr:needs-human-review:head-sha -->"
        }
    ]
    session = _make_review_session(
        pr_files=pr_files, existing_comments=existing_comments
    )
    result = review_post_release_pr(
        "CCBR/Tools", 9, force_review=True, token="tok", session=session
    )
    assert result is False
    posted_urls = [c[1] for c in session.calls if c[0] == "POST"]
    assert any("issues/9/comments" in u for u in posted_urls)


def test_review_post_release_pr_requests_human_review_when_file_count_mismatched():
    pr_node_payload = {
        "node_id": "PR_NODE_9",
        "title": PR_TITLE,
        "user": {"type": "Bot"},
        "head": {"ref": "release/v0.7.1", "sha": "head-sha"},
        "base": {"sha": "base-sha"},
        "changed_files": 99,
    }
    session = _make_review_session(pr_node_payload=pr_node_payload)
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "pagination mismatch" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_requests_human_review_when_version_not_bumped():
    pr_files = [{"filename": "README.md"}]
    session = _make_review_session(pr_files=pr_files)
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "version file must be bumped" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_requests_human_review_when_release_not_found():
    session = _make_review_session()
    original_request = session.request

    def _patched_request(method, url, headers=None, **kwargs):
        if "releases/tags/" in url:
            raise requests_lib.exceptions.HTTPError("404")
        return original_request(method, url, headers=headers, **kwargs)

    session.request = _patched_request
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "no matching GitHub release tag" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_requests_human_review_when_title_or_sender_mismatch():
    session = _make_review_session(
        pr_node_payload={
            "node_id": "PR_NODE_9",
            "title": "chore: bump deps",
            "user": {"type": "User"},
            "head": {"ref": "some-branch", "sha": "head-sha"},
            "base": {"sha": "base-sha"},
            "changed_files": 5,
        }
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "post-release cleanup pattern" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_requests_resolved_reviewer_successfully():
    runs_url = (
        "https://api.github.com/repos/CCBR/Tools/actions/workflows/"
        "draft-release.yml/runs"
    )
    session = _make_review_session(
        pr_node_payload={
            "node_id": "PR_NODE_9",
            "title": "chore: bump deps",
            "user": {"type": "User"},
            "head": {"ref": "some-branch", "sha": "head-sha"},
            "base": {"sha": "base-sha"},
            "changed_files": 5,
        }
    )
    session.payloads[runs_url] = {
        "workflow_runs": [{"triggering_actor": {"login": "kelly-sovacool"}}]
    }
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    reviewer_calls = [
        c for c in session.calls if c[0] == "POST" and "requested_reviewers" in c[1]
    ]
    assert reviewer_calls
    assert reviewer_calls[0][2]["json"]["reviewers"] == ["kelly-sovacool"]


def test_review_post_release_pr_aborts_approval_when_head_changes_concurrently():
    pr_node_payload = {
        "node_id": "PR_NODE_9",
        "title": PR_TITLE,
        "user": {"type": "Bot"},
        "head": {"ref": "release/v0.7.1", "sha": "head-sha"},
        "base": {"sha": "base-sha"},
        "changed_files": len(_default_filenames()),
    }
    second_pr_node_payload = dict(pr_node_payload)
    second_pr_node_payload["head"] = {"ref": "release/v0.7.1", "sha": "new-head-sha"}
    session = _make_review_session(
        pr_node_payload=pr_node_payload,
        second_pr_node_payload=second_pr_node_payload,
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False
    review_bodies = [
        c[2]["json"] for c in session.calls if c[0] == "POST" and "reviews" in c[1]
    ]
    assert not any(body.get("event") == "APPROVE" for body in review_bodies)
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "head commit changed" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_keeps_approval_when_auto_merge_api_fails():
    session = _make_review_session(
        graphql_payload={
            "errors": [{"message": "Resource not accessible by integration"}]
        }
    )
    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
    review_calls = [c for c in session.calls if c[0] == "POST" and "reviews" in c[1]]
    review_bodies = [c[2]["json"] for c in review_calls]
    assert any(body.get("event") == "APPROVE" for body in review_bodies)
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    assert "GraphQL errors" in comment_calls[0][2]["json"]["body"]


def test_review_post_release_pr_comments_when_approval_fails(monkeypatch):
    session = _make_review_session()

    def _fail_approval(*args, **kwargs):
        raise RuntimeError("approval is not allowed")

    monkeypatch.setattr("ccbr_actions.post_release_pr.approve_pr", _fail_approval)

    result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)

    assert result is False
    comment_calls = [
        c for c in session.calls if c[0] == "POST" and "issues/9/comments" in c[1]
    ]
    assert comment_calls
    comment_body = comment_calls[0][2]["json"]["body"]
    assert "automatic approval could not be completed" in comment_body


def test_review_post_release_pr_warns_when_reviewer_request_fails(monkeypatch):
    pr_files = [{"filename": name} for name in _default_filenames()] + [
        {"filename": "src/main.py"}
    ]
    session = _make_review_session(pr_files=pr_files)

    def _fail_request(*args, **kwargs):
        raise RuntimeError("reviewer not allowed on PR")

    monkeypatch.setattr("ccbr_actions.post_release_pr.request_reviewer", _fail_request)
    monkeypatch.setattr(
        "ccbr_actions.post_release_pr.determine_post_release_reviewer",
        lambda *args, **kwargs: "dave",
    )

    with pytest.warns(UserWarning, match="Could not request reviewer"):
        result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False


def test_review_post_release_pr_warns_when_human_review_comment_fails(monkeypatch):
    pr_files = [{"filename": name} for name in _default_filenames()] + [
        {"filename": "src/main.py"}
    ]
    session = _make_review_session(pr_files=pr_files)

    def _fail_comment(*args, **kwargs):
        raise RuntimeError("comment is not allowed")

    monkeypatch.setattr("ccbr_actions.post_release_pr.post_pr_comment", _fail_comment)

    with pytest.warns(UserWarning, match="Could not post human-review comment"):
        result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is False


def test_review_post_release_pr_warns_when_auto_merge_comment_fails(monkeypatch):
    session = _make_review_session(
        graphql_payload={"errors": [{"message": "auto-merge unavailable"}]}
    )

    def _fail_comment(*args, **kwargs):
        raise RuntimeError("comment is not allowed")

    monkeypatch.setattr("ccbr_actions.post_release_pr.post_pr_comment", _fail_comment)

    with pytest.warns(UserWarning, match="Could not post auto-merge failure comment"):
        result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)

    assert result is True


def test_review_post_release_pr_warns_when_workflow_run_approval_fails(monkeypatch):
    session = _make_review_session()

    def _fail_approve_runs(*args, **kwargs):
        raise RuntimeError("actions: write permission required")

    monkeypatch.setattr(
        "ccbr_actions.post_release_pr.approve_pending_workflow_runs",
        _fail_approve_runs,
    )

    with pytest.warns(UserWarning, match="Could not approve pending workflow runs"):
        result = review_post_release_pr("CCBR/Tools", 9, token="tok", session=session)
    assert result is True
