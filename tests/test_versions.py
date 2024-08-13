import pytest

from ccbr_actions.versions import (
    get_releases,
    get_latest_release_tag,
    match_semver,
    check_version_increments_by_one,
)


def test_get_releases():
    assert match_semver(get_releases(limit=1)[0]["tagName"], with_leading_v=True)


def test_get_latest_release_tag():
    assert match_semver(get_latest_release_tag(), with_leading_v=True)


def test_version_increment():
    assert all(
        [
            check_version_increments_by_one("v0.1.0", "v0.2.0", with_leading_v=True),
            check_version_increments_by_one("0.1.0", "0.1.1", with_leading_v=False),
            check_version_increments_by_one(
                "v1.9.10", "v1.10.0", with_leading_v=True, debug=True
            ),
        ]
    )


def test_version_increment_error():
    messages = []
    with pytest.raises(ValueError) as exc_info:
        check_version_increments_by_one("v0.1.0", "v0.2.1", with_leading_v=True)
    messages.append(
        "Next version must only increment one number at a time." in str(exc_info.value)
    )
    with pytest.raises(ValueError) as exc_info:
        check_version_increments_by_one("v0.1.0", "v0.0.1", with_leading_v=True)
    messages.append(
        "Next version must only increment one number at a time." in str(exc_info.value)
    )
    with pytest.raises(ValueError) as exc_info:
        check_version_increments_by_one("0.1.0", "3.0.0", with_leading_v=False)
    messages.append(
        "Next version must only increment one number at a time." in str(exc_info.value)
    )
    with pytest.raises(ValueError) as exc_info:
        check_version_increments_by_one("v1", "v10", with_leading_v=True)
    messages.append(
        "Tag v10 does not match semantic versioning guidelines." in str(exc_info.value)
    )
    assert all(messages)
