import pytest

from ccbr_actions.versions import (
    get_releases,
    get_latest_release_tag,
    get_latest_release_hash,
    match_semver,
    check_version_increments_by_one,
    get_major_minor_version,
    is_ancestor,
)


def test_get_releases():
    assert match_semver(get_releases(limit=1)[0]["tagName"], with_leading_v=True)


def test_get_latest_release_tag():
    assert match_semver(get_latest_release_tag(), with_leading_v=True)


def test_get_latest_release_hash():
    assert all(
        [
            len(get_latest_release_hash()) > 7,
            get_latest_release_hash(args="--repo CCBR/CCBR_NextflowTemplate") == "",
        ]
    )


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
    with pytest.raises(ValueError) as exc_info:
        check_version_increments_by_one("v1", "10", with_leading_v=True)
    messages.append("The tag does not start with 'v'." in str(exc_info.value))
    assert all(messages)


def test_get_major_minor():
    assert all(
        [
            get_major_minor_version("1.0.0") == "1.0",
            get_major_minor_version("2.1.3-alpha") == "2.1",
            get_major_minor_version("v1.0.0", with_leading_v=True) == "v1.0",
            get_major_minor_version("invalid_version") == None,
        ]
    )


def test_is_ancestor():
    assert all(
        [
            is_ancestor("v0.1.0", "v0.1.1"),
            is_ancestor("d620b61", "6cf677a"),
            is_ancestor("d620b61\n", "\n6cf677a"),
        ]
    )
