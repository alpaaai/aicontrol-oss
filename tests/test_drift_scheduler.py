"""Tests for P1-5: DriftDetector scheduler."""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.drift_detector import (
    AgentSnapshot,
    DriftDetector,
    PolicySnapshot,
    WarningRecord,
)


def _warning_record(warning_type, agent_id=None, agent_name=None,
                    policy_id=None, policy_name=None, tool_name="tool_x",
                    message="test msg"):
    return WarningRecord(
        warning_type=warning_type, agent_id=agent_id, agent_name=agent_name,
        policy_id=policy_id, policy_name=policy_name,
        tool_name=tool_name, message=message,
    )


@pytest.fixture
def db_session_factory_mock():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=mock_session)
    return factory


@pytest.mark.asyncio
async def test_run_once_calls_reconcile(db_session_factory_mock):
    """run_once() calls _reconcile with output of detect_drift."""
    with patch("app.services.drift_detector._load_agents", new_callable=AsyncMock,
               return_value=[]), \
         patch("app.services.drift_detector._load_policies", new_callable=AsyncMock,
               return_value=[]), \
         patch("app.services.drift_detector._reconcile", new_callable=AsyncMock) as mock_rec:
        detector = DriftDetector(db_session_factory_mock, interval_hours=6)
        await detector.run_once()
        mock_rec.assert_called_once()


@pytest.mark.asyncio
async def test_run_once_sets_status_healthy_on_success(db_session_factory_mock):
    with patch("app.services.drift_detector._load_agents", new_callable=AsyncMock,
               return_value=[]), \
         patch("app.services.drift_detector._load_policies", new_callable=AsyncMock,
               return_value=[]), \
         patch("app.services.drift_detector._reconcile", new_callable=AsyncMock):
        detector = DriftDetector(db_session_factory_mock, interval_hours=6)
        await detector.run_once()
        assert detector.status == "healthy"


@pytest.mark.asyncio
async def test_run_once_sets_status_degraded_on_exception(db_session_factory_mock):
    with patch("app.services.drift_detector._load_agents",
               new_callable=AsyncMock, side_effect=Exception("DB error")):
        detector = DriftDetector(db_session_factory_mock, interval_hours=6)
        await detector.run_once()
        assert detector.status == "degraded"


@pytest.mark.asyncio
async def test_stop_cancels_task(db_session_factory_mock):
    with patch("app.services.drift_detector._load_agents", new_callable=AsyncMock,
               return_value=[]), \
         patch("app.services.drift_detector._load_policies", new_callable=AsyncMock,
               return_value=[]), \
         patch("app.services.drift_detector._reconcile", new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        detector = DriftDetector(db_session_factory_mock, interval_hours=6)
        detector.start()
        await asyncio.sleep(0)   # yield to let _task be created
        await detector.stop()
        assert detector._task is None or detector._task.cancelled()
