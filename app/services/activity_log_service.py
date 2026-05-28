import structlog

from app.models.database import async_session_factory
from app.models.user import UserActivityLog

log = structlog.get_logger()


async def write_activity_log(
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    before_state: dict = None,
    after_state: dict = None,
    user_email: str = None,
    user_id: str = None,
    ip_address: str = None,
) -> None:
    try:
        async with async_session_factory() as session:
            entry = UserActivityLog(
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                before_state=before_state,
                after_state=after_state,
                user_email=user_email,
                user_id=user_id,
                ip_address=ip_address,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        log.error("activity_log_write_failed", error=str(e), action=action)
