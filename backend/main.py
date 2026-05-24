"""Main application entry point.

Sets up the FastAPI application and configures startup/shutdown via a
lifespan context manager so initialization (like logging) happens at
startup instead of at import time.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analyze import router as analyze_router
from app.core.logging_utils import configure_logging, get_logger
from app.middleware.request_logging import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: configure logging on startup and log shutdown.

    Keeping initialization here ensures side-effects run when the app is
    started (uvicorn/gunicorn) rather than on import, which is helpful for
    tests and tooling.
    """
    configure_logging()
    logger = get_logger(__name__)
    logger.info("app_startup: initializing application")
    try:
        yield
    finally:
        logger.info("app_shutdown: cleaning up application")


app = FastAPI(
    title="Contract Risk Analyzer",
    description=(
        "Autonomous multi-agent pipeline that reads any contract and produces "
        "a structured risk report."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (keep explicit origins for local development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware (adds X-Request-ID and logs requests)
app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(analyze_router, prefix="/api/v1")
