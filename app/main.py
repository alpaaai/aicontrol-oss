from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from app.core.config import settings as _settings
from app.core.logging import configure_logging, get_logger
from app.models.database import async_session_factory
from app.routers.auth import router as auth_router
from app.routers.audit_events import router as audit_events_router
from app.routers.dashboard import router as dashboard_router
from app.routers.debug import router as debug_router
from app.routers.intercept import router as intercept_router
from app.routers.policies import router as policies_router
from app.routers.agents import router as agents_router
from app.routers.reviews import router as reviews_router
from app.routers.sessions import router as sessions_router
from app.routers.slack_actions import router as slack_router
from app.routers.tokens import router as tokens_router
from app.routers.warnings import router as warnings_router
from enterprise.compliance.router import router as compliance_router
from app.services.drift_detector import DriftDetector
from app.services.opa_health_watcher import OpaHealthWatcher
from app.services.policy_loader import load_all, push_rego_to_opa

configure_logging(env=_settings.app_env)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run policy loader on startup, start OPA health watcher and drift detector."""
    logger.info("aicontrol_starting")
    async with async_session_factory() as session:
        await load_all(session)

    _http_client = httpx.AsyncClient()
    opa_watcher = OpaHealthWatcher(
        push_fn=push_rego_to_opa,
        http_client=_http_client,
    )
    opa_watcher.start()
    app.state.opa_watcher = opa_watcher

    # DriftDetector — enterprise only
    if _settings.AICONTROL_LICENSE_KEY:
        drift_detector = DriftDetector(
            session_factory=async_session_factory,
            interval_hours=_settings.drift_scan_interval_hours,
        )
        drift_detector.start()
        app.state.drift_detector = drift_detector
    else:
        app.state.drift_detector = None

    logger.info("aicontrol_ready")

    yield

    if app.state.drift_detector is not None:
        await app.state.drift_detector.stop()
    await opa_watcher.stop()  # task fully cancelled before client closes
    await _http_client.aclose()
    logger.info("aicontrol_stopping")


app = FastAPI(
    title="AIControl",
    description="Enterprise AI agent governance middleware",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(audit_events_router)
app.include_router(dashboard_router)
app.include_router(debug_router)
app.include_router(intercept_router)
app.include_router(policies_router)
app.include_router(agents_router)
app.include_router(reviews_router)
app.include_router(sessions_router)
app.include_router(slack_router)
app.include_router(tokens_router)
app.include_router(warnings_router)
app.include_router(compliance_router)


@app.get("/health")
async def health(request: Request) -> dict:
    """Liveness check — returns ok when the app process is running."""
    watcher = getattr(request.app.state, "opa_watcher", None)
    drift_detector = getattr(request.app.state, "drift_detector", None)
    has_license = bool(_settings.AICONTROL_LICENSE_KEY)
    return {
        "status": "ok",
        "service": "aicontrol",
        "opa_status": (
            (watcher.opa_status if watcher else "unknown")
            if has_license
            else "enterprise_only"
        ),
        "drift_detector_status": (
            (drift_detector.status if drift_detector else "unknown")
            if has_license
            else "enterprise_only"
        ),
    }
