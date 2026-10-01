from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import select

from app.core.config import settings as _settings
from app.core.license_gate import has_enterprise_license
from app.core.logging import configure_logging, get_logger
from app.models.database import async_session_factory
from app.models.user import OrgSettings
from app.routers.auth import router as auth_router
from app.routers.audit_events import router as audit_events_router
from app.routers.dashboard import router as dashboard_router
from app.routers.policies import router as policies_router
from app.routers.agents import router as agents_router
from app.routers.coverage import router as coverage_router
from app.routers.reviews import router as reviews_router
from app.routers.sessions import router as sessions_router
from app.routers.slack_actions import router as slack_router
from app.routers.tokens import router as tokens_router
from app.routers.license import router as license_router
from app.routers.billing import router as billing_router
from app.routers.users import router as users_router
from app.routers.setup import router as setup_router
from app.routers.org_settings import router as org_settings_router
from app.routers.org_settings import settings_router
from app.routers.mcp_gateway import router as mcp_gateway_router
from app.routers.mcp_servers import router as mcp_servers_router
from app.services.cedar_client import invalidate_policy_set_cache
from app.services.license_sync import LicenseSync
from app.services.policy_loader import load_all
from app.services.retention_purger import RetentionPurger
from app.services.wal import default_wal_writer
from app.services.wal_shipper import WalShipper

# enterprise/ is proprietary and physically absent from the public OSS
# mirror (.github/workflows/mirror-oss.yml runs `rm -rf enterprise/` before
# pushing to github.com/alpaaai/aicontrol-oss) — these imports must stay
# optional so every OSS deployment can still boot.
try:
    from enterprise.compliance.router import router as compliance_router
    from enterprise.app.routers.policy_authoring import router as policy_authoring_router
    from enterprise.app.routers.audit_export_config import router as audit_export_config_router
    from enterprise.app.routers.warnings import router as warnings_router
    from enterprise.app.services.drift_detector import DriftDetector
except ImportError:
    compliance_router = None
    policy_authoring_router = None
    audit_export_config_router = None
    warnings_router = None
    DriftDetector = None

configure_logging(env=_settings.app_env)
logger = get_logger("main")


async def _safe_has_enterprise_license() -> bool:
    """has_enterprise_license() raises HTTPException(402) for a set-but-invalid/
    expired key -- correct for a request handler, but here it is called outside
    a request (startup) and inside /health, neither of which should 402 or crash
    over a bad license key. An unusable key is treated the same as no key: not
    enterprise."""
    try:
        async with async_session_factory() as session:
            return await has_enterprise_license(session)
    except HTTPException:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run policy loader on startup and start the drift detector."""
    logger.info("aicontrol_starting")
    async with async_session_factory() as session:
        await load_all(session)

    _http_client = httpx.AsyncClient()

    wal_shipper = WalShipper(wal_path=default_wal_writer.wal_path, session_factory=async_session_factory)
    await wal_shipper.replay_and_start()
    app.state.wal_shipper = wal_shipper

    # DriftDetector — enterprise only, and only importable when enterprise/ is present.
    # Gated on the decoded plan (has_enterprise_license), not bare key presence: a
    # Business-tier or invalid/expired key would otherwise start the background scan
    # even though GET /warnings (require_enterprise_license) can never show its results.
    if DriftDetector is not None and await _safe_has_enterprise_license():
        drift_detector = DriftDetector(
            session_factory=async_session_factory,
            interval_hours=_settings.drift_scan_interval_hours,
            unseen_tool_lookback_days=_settings.drift_unseen_tool_lookback_days,
        )
        drift_detector.start()
        app.state.drift_detector = drift_detector
    else:
        app.state.drift_detector = None

    # Retention purge — every tier (unlike DriftDetector, this isn't
    # enterprise-gated: Community's 7-day window needs enforcement too).
    retention_purger = RetentionPurger(
        session_factory=async_session_factory,
        interval_hours=_settings.retention_purge_interval_hours,
    )
    retention_purger.start()
    app.state.retention_purger = retention_purger

    # License sync -- only started when an activation code is on file at
    # boot (community installs, and business/enterprise installs not yet
    # activated, skip it entirely). Checked once here, same pattern as
    # DriftDetector's has_enterprise_license gate above.
    async with async_session_factory() as session:
        has_activation_code = (
            await session.execute(select(OrgSettings.activation_code).where(OrgSettings.activation_code.isnot(None)))
        ).first() is not None

    if has_activation_code:
        license_sync = LicenseSync(
            session_factory=async_session_factory,
        )
        license_sync.start()
        app.state.license_sync = license_sync
    else:
        app.state.license_sync = None

    logger.info("aicontrol_ready")

    yield

    if app.state.drift_detector is not None:
        await app.state.drift_detector.stop()
    if app.state.license_sync is not None:
        await app.state.license_sync.stop()
    await app.state.retention_purger.stop()
    await app.state.wal_shipper.stop()
    await _http_client.aclose()
    logger.info("aicontrol_stopping")


app = FastAPI(
    title="AIControl",
    description="Enterprise AI agent governance middleware",
    version="0.1.0",
    lifespan=lifespan,
)

# ADD HERE — before any include_router calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(license_router)
app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(audit_events_router)
app.include_router(dashboard_router)
app.include_router(policies_router)
app.include_router(agents_router)
app.include_router(coverage_router)
app.include_router(reviews_router)
app.include_router(sessions_router)
app.include_router(slack_router)
app.include_router(tokens_router)
app.include_router(billing_router)
app.include_router(users_router)
app.include_router(org_settings_router)
app.include_router(settings_router)
if _settings.DEMO_MODE:
    app.include_router(demo_router)
app.include_router(mcp_gateway_router)
app.include_router(mcp_servers_router)
if compliance_router is not None:
    app.include_router(compliance_router)
if policy_authoring_router is not None:
    app.include_router(policy_authoring_router)
if audit_export_config_router is not None:
    app.include_router(audit_export_config_router)
if warnings_router is not None:
    app.include_router(warnings_router)


@app.get("/health")
async def health(request: Request) -> dict:
    """Liveness check — returns ok when the app process is running."""
    drift_detector = getattr(request.app.state, "drift_detector", None)
    is_enterprise = await _safe_has_enterprise_license()
    return {
        "status": "ok",
        "service": "aicontrol",
        # Cedar evaluates in this process, so there is no sidecar that can be
        # unreachable and nothing to poll. The field is kept so existing health
        # consumers do not break on a missing key.
        "policy_engine_status": "in_process",
        "drift_detector_status": (
            (drift_detector.status if drift_detector else "unknown")
            if is_enterprise
            else "enterprise_only"
        ),
    }
