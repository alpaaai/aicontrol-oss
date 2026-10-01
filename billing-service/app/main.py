from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.database import async_session_factory
from app.routers.billing import router as billing_router
from app.services.trial_expiry import TrialExpiry

configure_logging(env=settings.app_env)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("billing_service_starting")
    trial_expiry = TrialExpiry(session_factory=async_session_factory)
    trial_expiry.start()
    app.state.trial_expiry = trial_expiry

    logger.info("billing_service_ready")

    yield

    await app.state.trial_expiry.stop()
    logger.info("billing_service_stopping")


app = FastAPI(title="AIControl Billing Service", lifespan=lifespan)

# Only POST /billing/checkout and POST /billing/reissue-activation are ever
# called from a browser (aicontrol-site's Pricing page and a "lost my code"
# link). The webhook (Stripe server-to-server) and /license/sync,
# /billing/portal (customer-instance server-to-server) don't need browser
# CORS -- restricting the origin list to aictl.io covers the only real
# browser caller rather than opening this globally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aictl.io"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(billing_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
