"""Application factory. Run with: uvicorn app.main:app"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import config as config_mod
from . import settings as settings_mod
from .db import Database, Setting
from .events import Broker
from .mailer import Mailer
from .routes_admin import router as admin_router
from .routes_auth import build_oauth
from .routes_auth import router as auth_router
from .routes_student import router as student_router
from .routes_teacher import router as teacher_router
from .tokens import TokenSigner
from .web import Redirect, Services, render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def seed_settings(db: Database, seeds: dict[str, str]) -> None:
    with db.session() as s:
        missing = {k: v for k, v in seeds.items() if s.get(Setting, k) is None}
    if missing:
        settings_mod.save(db, missing)


def create_app(config: config_mod.Config | None = None) -> FastAPI:
    config = config or config_mod.load()
    db = Database(config.db_path)
    seed_settings(db, config.seed_settings)
    services = Services(config=config, db=db, mailer=Mailer(config), broker=Broker(),
                        signer=TokenSigner(config.secret_key))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services.broker.bind(asyncio.get_running_loop())
        services.mailer.start()
        yield
        services.mailer.stop()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.svc = services
    app.state.oauth = build_oauth(config)
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key,
        session_cookie="attendance_session",
        max_age=60 * 60 * 24 * 30,
        path=config.base_path or "/",
        same_site="lax",
        https_only=config.cookie_secure,
    )

    root = APIRouter(prefix=config.base_path)
    for r in (auth_router, teacher_router, student_router, admin_router):
        root.include_router(r)

    @root.get("/healthz")
    def healthz():
        return PlainTextResponse("ok")

    app.include_router(root)
    app.mount(config.base_path + "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    if config.base_path:
        @app.get("/")
        def to_base():
            return RedirectResponse(config.base_path + "/")

        @app.get(config.base_path)
        def to_base_slash():
            return RedirectResponse(config.base_path + "/")

    @app.exception_handler(Redirect)
    async def redirect_handler(request: Request, exc: Redirect):
        return RedirectResponse(exc.location, status_code=303)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        wants_json = request.headers.get("x-csrf-token") or "application/json" in request.headers.get("accept", "")
        if wants_json:
            return PlainTextResponse(str(exc.detail), status_code=exc.status_code)
        titles = {403: "Not allowed", 404: "Not found", 400: "Something went wrong"}
        return render(request, "message.html", exc.status_code,
                      title=titles.get(exc.status_code, "Error"), text=str(exc.detail))

    return app


def __getattr__(name):
    # `uvicorn app.main:app` builds the app on first access, so importing the
    # module (e.g. from tests) does not require environment variables.
    if name == "app":
        global app
        app = create_app()
        return app
    raise AttributeError(name)
