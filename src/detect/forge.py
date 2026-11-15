from __future__ import annotations

from enum import StrEnum


class Forge(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE_DEVOPS = "azure_devops"
    LOCAL = "local"


def normalize_forge(value: object, *, default: Forge = Forge.GITHUB) -> Forge:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"azure": Forge.AZURE_DEVOPS, "ado": Forge.AZURE_DEVOPS}
    if text in aliases:
        return aliases[text]
    try:
        return Forge(text)
    except ValueError:
        return default
