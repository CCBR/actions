from ccbr_actions.versions import get_releases, get_latest_release_tag, match_semver


def test_get_releases():
    assert match_semver(get_releases(limit=1)[0]["tagName"], with_leading_v=True)


def test_get_latest_release_tag():
    assert match_semver(get_latest_release_tag(), with_leading_v=True)
