from __future__ import annotations

import json
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from detect.estimate import estimate
from detect.orchestrator import CHANNELS, DetectConfig, run_detection
from detect.packs import load_frozen
from lib.gh_client import API_VERSION, load_tokens
from serve import errors
from serve.detect_spec import DetectSpecError, detect_spec_to_dict, parse_detect_spec
from serve.executor import RunExecutor, Runner, RunPayload, create_run
from serve.pages import (
    _item_count,
    _run_detail_summary,
    validate_csrf,
)
from serve.pages import (
    _templates as templates,
)
from store.models import DetectionEvidence, RunItem, Runs, TracePack
from store.settings import load_run_settings


def build_detect_runner(engine: Engine) -> Runner:
    def runner(run_id: int, spec_doc: dict) -> RunPayload:
        from serve.runner import build_deps

        settings = load_run_settings(engine)
        spec = parse_detect_spec(spec_doc)
        pack = load_frozen(engine, spec.pack_version)
        deps = build_deps(engine, max_concurrent=settings.limiter_max_concurrent)
        try:
            return run_detection(
                deps,
                run_id,
                spec,
                pack,
                config=DetectConfig(
                    deadline_seconds=float(settings.request_deadline_seconds),
                    concurrency=min(settings.limiter_max_concurrent, 32),
                ),
            )
        finally:
            deps.client.close()

    return runner


def _run_row(engine: Engine, run_id: int):
    with engine.connect() as connection:
        return connection.execute(select(Runs).where(Runs.id == run_id)).mappings().one_or_none()


def _pack_versions(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return [
            str(row[0])
            for row in connection.execute(
                select(TracePack.version).order_by(TracePack.frozen_at.desc(), TracePack.version)
            )
        ]


def _latest_pack(engine: Engine):
    versions = _pack_versions(engine)
    if not versions:
        return None
    return load_frozen(engine, versions[0])


def _candidate_count(engine: Engine, run_id: int) -> int:
    with engine.connect() as connection:
        count = connection.scalar(
            select(func.count()).select_from(RunItem).where(RunItem.run_id == run_id)
        )
    return int(count or 0)


def latest_detect_for_run(engine: Engine, run_id: int):
    with engine.connect() as connection:
        return (
            connection.execute(
                select(Runs)
                .where(Runs.kind == "detect", Runs.source_run_id == run_id)
                .order_by(Runs.created_at.desc(), Runs.id.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )


def _options_context(engine: Engine, run_id: int, *, errors_: list[str], hints: list[str]) -> dict:
    pack = _latest_pack(engine)
    return {
        "source": {"id": run_id, "eligible": True, "status": "done"},
        "packs": _pack_versions(engine),
        "roster": pack.roster() if pack is not None else (),
        "channels": CHANNELS,
        "candidate_count": _candidate_count(engine, run_id),
        "errors": errors_,
        "hints": hints,
    }


def _evidence_summary(evidence: dict) -> str:
    if "path" in evidence:
        suffix = " (hidden via .gitignore)" if evidence.get("source") == "gitignore" else ""
        return f"{evidence['path']}{suffix}"
    if "commit" in evidence and "snippet" in evidence:
        return f"{evidence['commit']}: {evidence['snippet']}"
    if "commit" in evidence and evidence.get("propagated"):
        return f"PR #{evidence.get('pr')} → commit {evidence['commit']}"
    if "pr" in evidence and "head" in evidence:
        return f"PR #{evidence['pr']} branch {evidence['head']}"
    if "pr" in evidence and "label" in evidence:
        return f"PR #{evidence['pr']} label {evidence['label']}"
    if "pr" in evidence and "snippet" in evidence:
        return f"PR #{evidence['pr']} body marker"
    if "pr" in evidence and "author" in evidence:
        return f"PR #{evidence['pr']} author {evidence['author']}"
    if "login" in evidence and "number" in evidence:
        return f"{evidence.get('role')} of #{evidence['number']} ({evidence['login']})"
    if "commit" in evidence and "field" in evidence:
        return f"commit {evidence['commit']} ({evidence['field']} match)"
    return json.dumps(evidence, sort_keys=True)[:120]


def detect_detail_response(request: Request, engine: Engine, row) -> HTMLResponse:
    run_id = int(row["id"])
    summary = _run_detail_summary(row, _item_count(engine, run_id))
    with engine.connect() as connection:
        item_rows = list(
            connection.execute(
                select(RunItem)
                .where(RunItem.run_id == run_id)
                .order_by(RunItem.stargazers.desc().nullslast(), RunItem.repo_id)
            ).mappings()
        )
        evidence_rows = list(
            connection.execute(
                select(DetectionEvidence)
                .where(DetectionEvidence.run_id == run_id)
                .order_by(
                    DetectionEvidence.repo_id,
                    DetectionEvidence.agent,
                    DetectionEvidence.channel,
                )
            ).mappings()
        )
    by_repo: dict[int, list] = {}
    for evidence in evidence_rows:
        by_repo.setdefault(evidence["repo_id"], []).append(evidence)
    repos = []
    for item in item_rows:
        rollup = item["detection"] or {}
        grouped: dict[str, list] = {}
        for evidence in by_repo.get(item["repo_id"], []):
            grouped.setdefault(evidence["channel"], []).append(
                {"agent": evidence["agent"], "summary": _evidence_summary(evidence["evidence"])}
            )
        repos.append(
            {
                "repo_id": item["repo_id"],
                "full_name": item["full_name"],
                "agents": rollup.get("agents", []),
                "unavailable": bool(rollup.get("unavailable")),
                "notes": rollup.get("notes", []),
                "channels": grouped,
                "channel_names": sorted(grouped),
            }
        )
    spec = row["filter_spec"] or {}
    return templates.TemplateResponse(
        request,
        "detect_detail.html",
        {
            "run": summary,
            "detection": {
                "source_run_id": row["source_run_id"],
                "summary": row["result_summary"] or {},
                "windows": spec.get("windows") or {"commits": 100, "prs": 100, "issues": 100},
                "repos": repos,
                "filter_agents": sorted({agent for repo in repos for agent in repo["agents"]}),
                "filter_channels": sorted(
                    {channel for repo in repos for channel in repo["channels"]}
                ),
            },
            "csrf_token": request.state.csrf_token,
        },
    )


def register_detect(
    application: FastAPI,
    *,
    engine_factory: Callable[[], Engine],
    executor_factory: Callable[[], RunExecutor],
    runner_factory: Callable[[], Runner],
) -> None:
    @application.get("/detections", response_class=HTMLResponse)
    def detections_page(request: Request):
        engine = engine_factory()
        with engine.connect() as connection:
            rows = list(
                connection.execute(
                    select(Runs)
                    .where(Runs.kind == "detect")
                    .order_by(Runs.created_at.desc(), Runs.id.desc())
                    .limit(200)
                ).mappings()
            )
        return templates.TemplateResponse(
            request,
            "detect_list.html",
            {
                "detections": [
                    {
                        "id": row["id"],
                        "status": row["status"],
                        "source_run_id": row["source_run_id"],
                        "created_at": row["created_at"],
                        "summary": row["result_summary"] or {},
                    }
                    for row in rows
                ],
                "csrf_token": request.state.csrf_token,
            },
        )

    @application.get("/runs/{run_id}/detect", response_class=HTMLResponse)
    def detect_options_page(request: Request, run_id: int):
        engine = engine_factory()
        row = _run_row(engine, run_id)
        if row is None:
            return templates.TemplateResponse(
                request, "detect_options.html", {"source": None}, status_code=404
            )
        if row["kind"] != "find" or row["status"] not in ("done", "partial"):
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {"source": {"id": run_id, "eligible": False, "status": row["status"]}},
                status_code=400,
            )
        return templates.TemplateResponse(
            request,
            "detect_options.html",
            {
                **_options_context(engine, run_id, errors_=[], hints=[]),
                "csrf_token": request.state.csrf_token,
            },
        )

    @application.post("/runs/{run_id}/detect")
    async def detect_start(request: Request, run_id: int):
        if not await validate_csrf(request):
            return errors.csrf_error_page(request)
        form = await request.form()
        raw_limit = str(form.get("limit") or "").strip()
        limit: int | None = None
        if raw_limit:
            try:
                limit = int(raw_limit)
            except ValueError:
                limit = 0
        doc = {
            "version": 1,
            "kind": "detect",
            "source_run_id": run_id,
            "pack_version": str(form.get("pack_version") or "").strip(),
            "agents": [str(value) for value in form.getlist("agents") if str(value).strip()]
            or None,
            "channels": [str(value) for value in form.getlist("channels") if str(value).strip()],
            "limit": limit,
            "windows": {"commits": 100, "prs": 100, "issues": 100},
        }
        engine = engine_factory()
        try:
            spec = parse_detect_spec(doc)
        except DetectSpecError as exc:
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {
                    **_options_context(
                        engine, run_id, errors_=list(exc.errors), hints=list(exc.hints)
                    ),
                    "csrf_token": request.state.csrf_token,
                },
                status_code=400,
            )
        row = await run_in_threadpool(_run_row, engine, run_id)
        if row is None or row["kind"] != "find" or row["status"] not in ("done", "partial"):
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {
                    "source": {
                        "id": run_id,
                        "eligible": False,
                        "status": row["status"] if row else "missing",
                    }
                },
                status_code=400,
            )
        if await run_in_threadpool(_candidate_count, engine, run_id) == 0:
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {
                    **_options_context(
                        engine,
                        run_id,
                        errors_=["source run has no saved results to detect"],
                        hints=[
                            "Detection needs a finished search with saved results;"
                            " run a search first or pick another."
                        ],
                    ),
                    "csrf_token": request.state.csrf_token,
                },
                status_code=400,
            )
        try:
            pack = await run_in_threadpool(load_frozen, engine, spec.pack_version)
        except KeyError:
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {
                    **_options_context(
                        engine,
                        run_id,
                        errors_=[f"unknown pack version {spec.pack_version!r}"],
                        hints=[],
                    ),
                    "csrf_token": request.state.csrf_token,
                },
                status_code=400,
            )
        if spec.agents is not None:
            unknown = sorted(set(spec.agents) - set(pack.roster()))
            if unknown:
                return templates.TemplateResponse(
                    request,
                    "detect_options.html",
                    {
                        **_options_context(
                            engine,
                            run_id,
                            errors_=[
                                f"unknown agents for pack {spec.pack_version!r}:"
                                f" {', '.join(unknown)}"
                            ],
                            hints=[
                                "Pick agents from the selected pack's roster; the options"
                                " list may belong to a different pack version."
                            ],
                        ),
                        "csrf_token": request.state.csrf_token,
                    },
                    status_code=400,
                )
        new_id = await run_in_threadpool(
            create_run,
            engine,
            detect_spec_to_dict(spec),
            api_version=API_VERSION,
            kind="detect",
            source_run_id=run_id,
        )
        executor_factory().submit(new_id, runner_factory())
        return RedirectResponse(f"/runs/{new_id}", status_code=303)

    @application.get("/runs/{run_id}/detect-estimate", response_class=HTMLResponse)
    def detect_estimate_partial(request: Request, run_id: int):
        engine = engine_factory()
        raw_channels = request.query_params.getlist("channels")
        if len(raw_channels) == 1 and "," in raw_channels[0]:
            raw_channels = raw_channels[0].split(",")
        channels = [channel for channel in raw_channels if channel in CHANNELS] or list(CHANNELS)
        raw_limit = request.query_params.get("limit", "").strip()
        candidates = _candidate_count(engine, run_id)
        if raw_limit.isdigit() and int(raw_limit) > 0:
            candidates = min(candidates, int(raw_limit))
        settings = load_run_settings(engine)
        result = estimate(
            candidates,
            channels,
            tokens=max(1, len(load_tokens())),
            concurrency=settings.limiter_max_concurrent,
            deadline_seconds=float(settings.request_deadline_seconds),
        )
        return templates.TemplateResponse(
            request, "partials/detect_estimate.html", {"estimate": result}
        )

    @application.get("/partials/runs/{run_id}/detect-status", response_class=HTMLResponse)
    def detect_status_partial(request: Request, run_id: int):
        engine = engine_factory()
        row = _run_row(engine, run_id)
        if row is None:
            return HTMLResponse("run not found", status_code=404)
        return templates.TemplateResponse(
            request,
            "partials/detect_status.html",
            {
                "run": _run_detail_summary(row, _item_count(engine, run_id)),
                "result_summary": row["result_summary"] or {},
                "csrf_token": request.state.csrf_token,
            },
        )
