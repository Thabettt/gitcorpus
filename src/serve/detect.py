from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from detect.estimate import estimate
from detect.git_orchestrator import GitScanConfig, run_git_detection
from detect.orchestrator import CHANNELS, DetectConfig, run_detection
from detect.packs import load_frozen
from enrich.cloner import CloneMode, estimate_clone, free_disk_mb
from lib.deadlines import clone_timeout_seconds
from lib.gh_client import API_VERSION, load_tokens
from serve import errors
from serve.detect_spec import DetectSpecError, detect_spec_to_dict, parse_detect_spec
from serve.executor import RunExecutor, Runner, RunPayload, create_run
from serve.pages import (
    _item_count,
    _run_detail_summary,
    _stamp,
    validate_csrf,
)
from serve.pages import (
    _templates as templates,
)
from serve.repo_import import (
    RepoImportError,
    import_repos_as_run,
    parse_repo_file,
)
from store.models import DetectionEvidence, RunItem, Runs, TracePack
from store.settings import load_run_settings


def build_detect_runner(engine: Engine) -> Runner:
    def runner(run_id: int, spec_doc: dict) -> RunPayload:
        spec = parse_detect_spec(spec_doc)
        settings = load_run_settings(engine)
        pack = load_frozen(engine, spec.pack_version)
        if spec.source == "git":
            return run_git_detection(
                engine,
                run_id,
                spec,
                pack,
                config=GitScanConfig(
                    depth=spec.clone_depth,
                    keep=spec.clone_keep,
                    timeout=clone_timeout_seconds(),
                    workers=min(settings.limiter_max_concurrent, 32),
                ),
            )
        from serve.runner import build_deps

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


def _finished_find_runs(engine: Engine, limit: int = 300) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                Runs.id,
                Runs.filter_hash,
                Runs.status,
                Runs.created_at,
                func.count(RunItem.id).label("item_count"),
            )
            .select_from(Runs)
            .outerjoin(RunItem, RunItem.run_id == Runs.id)
            .where(Runs.kind == "find", Runs.status.in_(("done", "partial")))
            .group_by(Runs.id)
            .order_by(Runs.created_at.desc(), Runs.id.desc())
            .limit(limit)
        ).mappings()
        return [
            {
                "id": row["id"],
                "hash_short": str(row["filter_hash"])[:8],
                "status": row["status"],
                "repos": int(row["item_count"] or 0),
                "when": _stamp(row["created_at"]),
            }
            for row in rows
        ]


def _detect_new_response(request: Request, engine: Engine, *, errors_: list[str], hints: list[str]):
    return templates.TemplateResponse(
        request,
        "detect_new.html",
        {
            "sources": _finished_find_runs(engine),
            "errors": errors_,
            "hints": hints,
            "csrf_token": request.state.csrf_token,
        },
        status_code=400 if errors_ else 200,
    )


def detection_number(engine: Engine, run_id: int) -> int:
    with engine.connect() as connection:
        count = connection.scalar(
            select(func.count()).select_from(Runs).where(Runs.kind == "detect", Runs.id <= run_id)
        )
    return int(count or 0)


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
        "channel_notes": CHANNEL_NOTES,
        "candidate_count": _candidate_count(engine, run_id),
        "errors": errors_,
        "hints": hints,
    }


CHANNEL_NOTES = {
    "file": "Tree + .gitignore + content probes · 2+ REST calls",
    "author": "Commit author/committer identities · shares the history call",
    "branch": "PR head branches · shares the PR call",
    "label": "PR labels · shares the PR call",
    "bot": "Generic CI bots, QA evidence only · shares the history call",
    "commit_trailer": "Co-author / generated-by trailers · shares the history call",
    "pr_metadata": "PR author, body marker, PR→commit propagation · 1 GraphQL call",
    "issue": "Agent users in issues and PR comments · 1 GraphQL call",
}


def _first_signal_label(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def _ratio_label(value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "—"
    return f"{float(value) * 100:.1f}%"


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
    result_summary = row["result_summary"] or {}
    return templates.TemplateResponse(
        request,
        "detect_detail.html",
        {
            "run": summary,
            "detection": {
                "number": detection_number(engine, run_id),
                "source_run_id": row["source_run_id"],
                "summary": result_summary,
                "first_signal_label": _first_signal_label(result_summary.get("first_signal_at")),
                "ratio_label": _ratio_label(result_summary.get("commit_ratio")),
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
    clone_disk_free: Callable[[str], float] | None = None,
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
            numbers = {
                int(numbered_id): int(number)
                for numbered_id, number in connection.execute(
                    select(Runs.id, func.row_number().over(order_by=Runs.id)).where(
                        Runs.kind == "detect"
                    )
                )
            }
        return templates.TemplateResponse(
            request,
            "detect_list.html",
            {
                "detections": [
                    {
                        "id": row["id"],
                        "number": numbers.get(int(row["id"])),
                        "status": row["status"],
                        "source_run_id": row["source_run_id"],
                        "started": _stamp(row["created_at"]),
                        "summary": row["result_summary"] or {},
                    }
                    for row in rows
                ],
                "csrf_token": request.state.csrf_token,
            },
        )

    @application.get("/detections/new", response_class=HTMLResponse)
    def detect_new_page(request: Request):
        engine = engine_factory()
        return _detect_new_response(request, engine, errors_=[], hints=[])

    @application.post("/detections/new")
    async def detect_new_submit(request: Request):
        if not await validate_csrf(request):
            return errors.csrf_error_page(request)
        form = await request.form()
        engine = engine_factory()
        upload = form.get("import_file")
        if upload is not None and getattr(upload, "filename", ""):
            raw = await upload.read()
            try:
                parsed = parse_repo_file(str(upload.filename), raw)
            except RepoImportError as exc:
                return _detect_new_response(
                    request,
                    engine,
                    errors_=[exc.message],
                    hints=[exc.hint] if exc.hint else [],
                )
            run_id = await run_in_threadpool(
                import_repos_as_run, engine, parsed, name=str(upload.filename)
            )
            return RedirectResponse(f"/detections/from/{run_id}", status_code=303)
        source = str(form.get("source") or "").strip()
        if not source.isdigit():
            return _detect_new_response(
                request,
                engine,
                errors_=["pick a finished search or upload a CSV"],
                hints=[],
            )
        row = await run_in_threadpool(_run_row, engine, int(source))
        if row is None or row["kind"] != "find" or row["status"] not in ("done", "partial"):
            return _detect_new_response(
                request,
                engine,
                errors_=[f"search #{source} is not a finished search"],
                hints=["only searches that finished (done or partial) can be detected"],
            )
        return RedirectResponse(f"/detections/from/{row['id']}", status_code=303)

    @application.get("/detections/from/{run_id}", response_class=HTMLResponse)
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

    @application.post("/detections/from/{run_id}")
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
        raw_depth = str(form.get("clone_depth") or "").strip()
        clone_depth: int | None = None
        if raw_depth:
            try:
                clone_depth = int(raw_depth)
            except ValueError:
                clone_depth = 0
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
            "source": str(form.get("source") or "api").strip(),
            "clone": {
                "depth": clone_depth if clone_depth is not None else 100,
                "keep": form.get("clone_keep") is not None,
            },
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
        return RedirectResponse(f"/detections/{new_id}", status_code=303)

    @application.get("/detections/{run_id}", response_class=HTMLResponse)
    def detect_page(request: Request, run_id: int):
        engine = engine_factory()
        row = _run_row(engine, run_id)
        if row is None or row["kind"] != "detect":
            return templates.TemplateResponse(
                request, "detect_detail.html", {"run": None}, status_code=404
            )
        return detect_detail_response(request, engine, row)

    @application.get("/partials/detections/{run_id}/estimate", response_class=HTMLResponse)
    def detect_estimate_partial(request: Request, run_id: int):
        engine = engine_factory()
        raw_channels = request.query_params.getlist("channels")
        if len(raw_channels) == 1 and "," in raw_channels[0]:
            raw_channels = raw_channels[0].split(",")
        channels = [channel for channel in raw_channels if channel in CHANNELS] or list(CHANNELS)
        raw_limit = request.query_params.get("limit", "").strip()
        candidates = _candidate_count(engine, run_id)
        limit_value = int(raw_limit) if raw_limit.isdigit() and int(raw_limit) > 0 else None
        repos = min(candidates, limit_value) if limit_value is not None else candidates
        settings = load_run_settings(engine)
        api_estimate = estimate(
            repos,
            channels,
            tokens=max(1, len(load_tokens())),
            concurrency=settings.limiter_max_concurrent,
            deadline_seconds=float(settings.request_deadline_seconds),
        )
        free_mb = (
            clone_disk_free("clones") if clone_disk_free is not None else free_disk_mb("clones")
        )
        clone_estimate = estimate_clone(
            engine,
            run_id,
            limit=repos,
            mode=CloneMode.DETECT,
            disk_free_mb=free_mb,
        )
        workers = max(1, min(settings.limiter_max_concurrent, 32))
        git_estimate = {
            "repos": clone_estimate.repos,
            "estimated_mb": round(clone_estimate.estimated_mb, 1),
            "free_mb": round(free_mb, 1),
            "workers": workers,
            "minutes_low": round(clone_estimate.repos * 1.0 / workers / 60, 1),
            "minutes_high": round(clone_estimate.repos * 4.0 / workers / 60, 1),
            "warnings": list(clone_estimate.warnings),
        }
        return templates.TemplateResponse(
            request,
            "partials/detect_estimate.html",
            {
                "selected": (request.query_params.get("source") or "api").strip(),
                "repos": repos,
                "api": api_estimate,
                "git": git_estimate,
            },
        )

    @application.get("/partials/detections/{run_id}/status", response_class=HTMLResponse)
    def detect_status_partial(request: Request, run_id: int):
        engine = engine_factory()
        row = _run_row(engine, run_id)
        if row is None:
            return HTMLResponse("run not found", status_code=404)
        summary = _run_detail_summary(row, _item_count(engine, run_id))
        response = templates.TemplateResponse(
            request,
            "partials/detect_status.html",
            {
                "run": summary,
                "result_summary": row["result_summary"] or {},
                "csrf_token": request.state.csrf_token,
            },
        )
        if request.headers.get("HX-Request") == "true" and not summary["polling"]:
            response.headers["HX-Refresh"] = "true"
        return response
