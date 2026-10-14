from __future__ import annotations

from collections.abc import Mapping

from detect.orchestrator import CHANNELS, DetectOptions

DETECT_SPEC_VERSION = 1
DEFAULT_WINDOWS = {"commits": 100, "prs": 100, "issues": 100}


class DetectSpecError(ValueError):
    def __init__(self, errors: list[str], hints: list[str] | None = None) -> None:
        super().__init__("; ".join(errors))
        self.errors = tuple(errors)
        self.hints = tuple(hints or ())


def parse_detect_spec(doc: Mapping[str, object]) -> DetectOptions:
    if not isinstance(doc, Mapping):
        raise DetectSpecError(["detect spec must be an object"])
    errors: list[str] = []
    hints: list[str] = []
    if doc.get("kind") != "detect":
        errors.append("kind must be 'detect'")
    source = doc.get("source_run_id")
    if not isinstance(source, int) or isinstance(source, bool) or source <= 0:
        errors.append("source_run_id must be a positive integer")
        source = 0
    pack_version = doc.get("pack_version")
    if not isinstance(pack_version, str) or not pack_version:
        errors.append("pack_version is required")
        pack_version = ""
    raw_agents = doc.get("agents")
    agents: frozenset[str] | None
    if raw_agents is None:
        agents = None
    elif (
        isinstance(raw_agents, list)
        and raw_agents
        and all(isinstance(agent, str) and agent for agent in raw_agents)
    ):
        agents = frozenset(str(agent) for agent in raw_agents)
    else:
        errors.append("agents must be null or a non-empty list of agent names")
        agents = None
    raw_channels = doc.get("channels")
    if (
        isinstance(raw_channels, list)
        and raw_channels
        and all(isinstance(channel, str) for channel in raw_channels)
    ):
        unknown = sorted({str(channel) for channel in raw_channels} - set(CHANNELS))
        if unknown:
            errors.append(f"unknown channels: {unknown}")
            hints.append(f"channels must be a subset of: {', '.join(CHANNELS)}")
        channels = frozenset(str(channel) for channel in raw_channels)
    else:
        errors.append("channels must be a non-empty list")
        hints.append(f"channels must be a non-empty subset of: {', '.join(CHANNELS)}")
        channels = frozenset()
    limit = doc.get("limit")
    if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
        errors.append("limit must be null or a positive integer")
        limit = None
    raw_windows = doc.get("windows")
    windows = dict(DEFAULT_WINDOWS)
    if isinstance(raw_windows, Mapping):
        for key, default in DEFAULT_WINDOWS.items():
            value = raw_windows.get(key, default)
            if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 1000:
                windows[key] = value
            else:
                errors.append(f"windows.{key} must be an integer between 1 and 1000")
    if errors:
        raise DetectSpecError(errors, hints)
    return DetectOptions(
        source_run_id=int(source),
        pack_version=str(pack_version),
        agents=agents,
        channels=channels,
        limit=limit,
        windows=windows,
    )


def detect_spec_to_dict(spec: DetectOptions) -> dict:
    return {
        "version": DETECT_SPEC_VERSION,
        "kind": "detect",
        "source_run_id": spec.source_run_id,
        "pack_version": spec.pack_version,
        "agents": sorted(spec.agents) if spec.agents is not None else None,
        "channels": [channel for channel in CHANNELS if channel in spec.channels],
        "limit": spec.limit,
        "windows": dict(spec.windows),
    }
