"""Local-first FastAPI application."""

import os
import mimetypes
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .dependencies import ALLOWED_ORIGINS, DEFAULT_HOST, DEFAULT_PORT
from .branding import OWNER_NAME, PRODUCT_NAME, PRODUCT_TAGLINE
from .routes import cases, enrichment, evidence, graph, indicators, timeline
from darkintel.version import __version__


def create_app() -> FastAPI:
    mimetypes.add_type("image/webp", ".webp")
    application = FastAPI(title=f"{PRODUCT_NAME} API", version=__version__,
                          description=f"{PRODUCT_NAME} — {PRODUCT_TAGLINE}. Local-only; authentication is not implemented.")
    application.state.default_host = DEFAULT_HOST
    application.state.default_port = DEFAULT_PORT
    application.add_middleware(CORSMiddleware, allow_origins=list(ALLOWED_ORIGINS),
                               allow_credentials=False, allow_methods=["GET", "POST"],
                               allow_headers=["Content-Type"])
    for router in (cases.router, evidence.router, indicators.router, enrichment.router,
                   timeline.router, graph.router):
        application.include_router(router, prefix="/api/v1")

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = ("default-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'self'")
        return response

    @application.get("/api/v1/health", tags=["health"])
    def health():
        root = Path(os.environ.get("DARKINTEL_CASES_DIR", "cases"))
        frontend = Path(__file__).parents[1] / "frontend" / "dist" / "index.html"
        return {"status": "ok", "version": __version__, "product": PRODUCT_NAME, "owner": OWNER_NAME,
                "cases_root_accessible": root.is_dir(),
                "frontend_build_available": frontend.is_file()}

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_REQUEST",
                                                                  "message": "Request validation failed."}})

    @application.exception_handler(Exception)
    async def safe_error(_: Request, exc: Exception):
        if isinstance(exc, FileNotFoundError):
            status, code, message = 404, "CASE_NOT_FOUND", "Case does not exist."
        elif isinstance(exc, LookupError):
            status, code, message = 404, "NOT_FOUND", str(exc)
        elif isinstance(exc, (ValueError, KeyError)):
            status, code, message = 400, "INVALID_REQUEST", str(exc)
        else:
            status, code, message = 500, "INTERNAL_ERROR", "The request could not be completed."
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})
    frontend_root = Path(__file__).parents[1] / "frontend" / "dist"
    if frontend_root.is_dir():
        assets = frontend_root / "assets"
        if assets.is_dir():
            application.mount("/assets", StaticFiles(directory=assets), name="assets")

        @application.get("/{spa_path:path}", include_in_schema=False)
        def spa(spa_path: str):
            if spa_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND",
                                                                          "message": "API route does not exist."}})
            return FileResponse(frontend_root / "index.html")
    return application


app = create_app()
