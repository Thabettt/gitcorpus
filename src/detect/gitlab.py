from __future__ import annotations

import os
from collections.abc import Mapping
from contextlib import nullcontext
from urllib.parse import quote

import httpx

from detect.attribution import (
    Hit,
    dedupe_hits,
    match_branches,
    match_issue_participants,
    match_pr_authors,
    match_pr_metadata,
)
from detect.channels import ChannelResult, FailureKind
from detect.packs import Pack

DEFAULT_GITLAB_API = "https://gitlab.com/api/v4"
MAX_MERGE_REQUESTS = 100
MAX_NOTED_MERGE_REQUESTS = 20
MAX_NOTES_PER_MERGE_REQUEST = 50


def _client() -> httpx.Client:
    headers: dict[str, str] = {"User-Agent": "gitcorpus/lifecycle-trace-v2"}
    token = os.environ.get("GITLAB_TOKEN", "").strip()
    if token:
        headers["PRIVATE-TOKEN"] = token
    return httpx.Client(headers=headers, timeout=30.0, follow_redirects=True)


def _get(client: httpx.Client, url: str, *, params: Mapping[str, object]) -> object:
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _identity(value: object) -> str:
    if not isinstance(value, Mapping):
        return ""
    return str(value.get("username") or value.get("name") or "")


def _merge_requests(
    client: httpx.Client,
    base: str,
    *,
    include_note_bodies: bool,
) -> list[dict[str, object]]:
    raw = _get(
        client,
        f"{base}/merge_requests",
        params={"scope": "all", "state": "all", "per_page": MAX_MERGE_REQUESTS},
    )
    if not isinstance(raw, list):
        return []
    prs: list[dict[str, object]] = []
    for item in raw[:MAX_MERGE_REQUESTS]:
        if not isinstance(item, Mapping):
            continue
        iid = item.get("iid")
        comments: list[dict[str, object]] = []
        if include_note_bodies and len(prs) < MAX_NOTED_MERGE_REQUESTS and iid is not None:
            notes = _get(
                client,
                f"{base}/merge_requests/{iid}/notes",
                params={"per_page": MAX_NOTES_PER_MERGE_REQUEST},
            )
            if isinstance(notes, list):
                comments = [
                    {
                        "login": _identity(note.get("author")),
                        "body": str(note.get("body") or "")[:20_000],
                    }
                    for note in notes[:MAX_NOTES_PER_MERGE_REQUEST]
                    if isinstance(note, Mapping)
                ]
        prs.append(
            {
                "number": iid,
                "createdAt": str(item.get("created_at") or ""),
                "headRefName": str(item.get("source_branch") or ""),
                "body": str(item.get("description") or "")[:20_000],
                "author": _identity(item.get("author")),
                "labels": [str(label) for label in item.get("labels") or []],
                "comments": comments,
                "reviews": [
                    {"login": _identity(reviewer), "body": "", "state": "reviewer"}
                    for reviewer in item.get("reviewers") or []
                ],
                "commits": [],
            }
        )
    return prs


def collect_gitlab_repository(
    project: str,
    pack: Pack,
    *,
    client: httpx.Client | None = None,
    api_base: str | None = None,
    agents: frozenset[str] | None = None,
) -> dict[str, ChannelResult]:
    """Collect GitLab-native branch and MR participation without GitHub conventions."""

    own_client = client is None
    session = client or _client()
    context = session if own_client else nullcontext(session)
    base_url = (api_base or os.environ.get("GITLAB_API_URL") or DEFAULT_GITLAB_API).rstrip("/")
    project_url = f"{base_url}/projects/{quote(project, safe='')}"
    try:
        with context as active:
            branches_raw = _get(
                active,
                f"{project_url}/repository/branches",
                params={"per_page": 100},
            )
            branches = (
                [
                    {"branch": str(item.get("name") or ""), "role": "branch_head"}
                    for item in branches_raw
                    if isinstance(item, Mapping) and item.get("name")
                ]
                if isinstance(branches_raw, list)
                else []
            )
            prs = _merge_requests(
                active,
                project_url,
                include_note_bodies=pack.requires_comment_bodies,
            )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        kind = FailureKind.PERMANENT if status in {401, 403, 404} else FailureKind.RETRYABLE
        result = ChannelResult(
            status="unavailable" if status == 404 else "partial",
            note=f"GitLab HTTP {status}",
            failure_kind=kind,
        )
        return {"branch": result, "pr_metadata": result, "issue": result}
    except (httpx.HTTPError, ValueError) as exc:
        result = ChannelResult(
            status="partial",
            note=f"GitLab {type(exc).__name__}: {str(exc)[:160]}",
            failure_kind=FailureKind.RETRYABLE,
        )
        return {"branch": result, "pr_metadata": result, "issue": result}

    branch_hits = match_branches(pack, branches, agents, forge="gitlab")
    pr_hits = match_pr_metadata(pack, prs, agents, forge="gitlab") + match_pr_authors(
        pack, prs, agents, forge="gitlab"
    )
    participants: list[dict[str, object]] = []
    for pr in prs:
        for comment in pr.get("comments") or []:
            if isinstance(comment, Mapping) and comment.get("login"):
                participants.append(
                    {
                        "login": comment["login"],
                        "body": comment.get("body"),
                        "number": pr.get("number"),
                        "role": "pr_commenter",
                        "observed_at": pr.get("createdAt"),
                    }
                )
        for review in pr.get("reviews") or []:
            if isinstance(review, Mapping) and review.get("login"):
                participants.append(
                    {
                        "login": review["login"],
                        "number": pr.get("number"),
                        "role": "pr_reviewer",
                        "observed_at": pr.get("createdAt"),
                    }
                )
    participant_hits: list[Hit] = match_issue_participants(
        pack, participants, agents, forge="gitlab"
    )
    return {
        "branch": ChannelResult(
            hits=tuple(dedupe_hits(branch_hits)),
            note="GitLab repository branches; first 100",
            stats={"branches": len(branches)},
        ),
        "pr_metadata": ChannelResult(
            hits=tuple(dedupe_hits(pr_hits)),
            note="GitLab merge requests; most recent 100",
            stats={"merge_requests": len(prs)},
        ),
        "issue": ChannelResult(
            hits=tuple(dedupe_hits(participant_hits)),
            note="GitLab MR reviewers/notes; bodies bounded and rule-gated",
            stats={"participants": len(participants)},
        ),
    }
