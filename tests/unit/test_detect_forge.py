from __future__ import annotations

import pytest

from detect.forge import Forge, normalize_forge


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("github", Forge.GITHUB),
        ("GitLab", Forge.GITLAB),
        ("azure-devops", Forge.AZURE_DEVOPS),
        ("ado", Forge.AZURE_DEVOPS),
        ("local", Forge.LOCAL),
        (None, Forge.GITHUB),
        ("sourcehut", Forge.GITHUB),
    ],
)
def test_normalize_forge(raw, expected):
    assert normalize_forge(raw) is expected


def test_normalize_forge_honours_an_explicit_default():
    assert normalize_forge("unknown", default=Forge.LOCAL) is Forge.LOCAL
