from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from serve.pages import _templates


def register_compare(app: FastAPI) -> None:
    @app.get("/compare", response_class=HTMLResponse)
    def compare_page(request: Request):
        return _templates.TemplateResponse(
            request,
            "compare.html",
            {"csrf_token": request.state.csrf_token},
        )
