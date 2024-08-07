from ccbr_actions.versions import get_releases, get_latest_release_tag


def test_get_releases():
    print(get_releases(limit=1))


def test_get_latest_release_tag():
    print(get_latest_release_tag())
