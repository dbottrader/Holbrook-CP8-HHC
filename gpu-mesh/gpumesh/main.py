"""Coordinator application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from gpumesh import __version__
from gpumesh.api import STATIC, admin, nodes, pages, public
from gpumesh.db import build_database, write_session
from gpumesh.errors import MeshError
from gpumesh.ratelimit import RateLimiter
from gpumesh.settings import Settings
from gpumesh.work import sweep

log = logging.getLogger("gpumesh")


def _resolve_admin_token(settings: Settings) -> tuple[str, bool, str]:
    if settings.admin_token:
        return settings.admin_token, False, ""
    directory = settings.resolved_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "admin.token"
    if path.exists():
        return path.read_text(encoding="utf-8").strip(), False, str(path)
    token = "adm_" + secrets.token_urlsafe(24)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token, True, str(path)


async def _sweep_loop(app: FastAPI) -> None:
    while True:
        try:
            with write_session(app) as session:
                sweep(session, app.state.settings)
        except Exception:
            log.exception("sweep failed")
        await asyncio.sleep(1.0)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_sweep_loop(app))
        log.info("GPU Mesh %s listening, database %s", __version__, settings.database_url.split("://", 1)[0])
        if app.state.admin_token_generated:
            log.warning("generated admin token (stored at %s): %s", app.state.admin_token_path, app.state.settings.admin_token)
        else:
            log.info("admin token loaded")
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    app = FastAPI(
        title="GPU Mesh",
        version=__version__,
        summary="Volunteer GPU network for free open-weight inference.",
        lifespan=lifespan,
    )
    token, generated, path = _resolve_admin_token(settings)
    settings.admin_token = token
    engine, factory = build_database(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.Session = factory
    app.state.ledger_lock = __import__("threading").Lock()
    app.state.limiter = RateLimiter()
    app.state.admin_token_generated = generated
    app.state.admin_token_path = path
    app.state.tarball = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(MeshError)
    async def _mesh_error(_request, exc: MeshError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.body(), headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": message, "type": "server_error", "code": str(exc.status_code)}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"message": "invalid request", "type": "invalid_request_error", "code": "validation"}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "internal error", "type": "server_error", "code": "internal"}},
        )

    app.include_router(public)
    app.include_router(nodes)
    app.include_router(admin)
    app.include_router(pages)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
