import pytest

from scripts.version_guard import check_base, is_new_release, read_version


def test_rejects_the_reported_branch_downgrade():
    with pytest.raises(ValueError, match='downgrade'):
        check_base('3.0.0', '3.2.0')


@pytest.mark.parametrize('candidate,base', [('3.5.0', '3.2.0'), ('3.2.0', '3.2.0'),
                                          ('3.10.0', '3.9.0')])
def test_allows_unchanged_or_newer_branch_versions(candidate, base):
    check_base(candidate, base)


@pytest.mark.parametrize('candidate,latest,releases,expected', [
    ('3.0.0', '3.2.0', ['3.2.0'], False),  # Unpublished does not mean newer.
    ('3.2.0', '3.2.0', ['3.2.0'], False),
    ('3.5.0', '3.2.0', ['3.2.0'], True),
    ('3.10.0', '3.9.0', ['3.9.0'], True),
    ('3.5.0', '3.2.0', ['3.2.0', '3.5'], False),  # Normalized duplicate.
    ('3.5.0rc1', '3.5.0', ['3.5.0'], False),
])
def test_publication_policy(candidate, latest, releases, expected):
    assert is_new_release(candidate, latest, releases) is expected


def test_reads_version_without_executing_module():
    assert str(read_version('raise RuntimeError("do not execute")\n__version__ = "3.5.0"')) == '3.5.0'


def test_missing_version_fails_closed():
    with pytest.raises(ValueError, match='missing'):
        read_version('name = "No version"')
