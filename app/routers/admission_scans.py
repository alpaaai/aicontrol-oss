"""POST/GET /admission-scans — admission-time scanning of skills/tools before enrollment.

Off the hot path (enroll-time, not the runtime /intercept path) — scanners
run synchronously per request but each ScannerPort.scan() call is already
non-blocking (dispatches its subprocess via asyncio.to_thread internally),
so this router never blocks the event loop even though it awaits directly.
"""
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.schemas import AdmissionScan
from app.services.scanners import registry as scanner_registry

router = APIRouter(prefix="/admission-scans", tags=["admission-scans"])
logger = get_logger("admission_scans_api")


class AdmissionScanRequest(BaseModel):
    target_type: str
    target_ref: str
    agent_id: Optional[uuid.UUID] = None
    scanners: list[str] = ["skill_scanner"]


class AdmissionScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: Optional[uuid.UUID]
    target_type: str
    target_ref: str
    scanner_name: str
    status: str
    findings: list[dict]
    severity_summary: dict
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: Optional[datetime]


@router.post("", response_model=list[AdmissionScanResponse], status_code=201)
async def create_admission_scan(
    body: AdmissionScanRequest,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[AdmissionScan]:
    """Run each requested scanner against the target, persisting one row per scanner."""
    results = []
    for scanner_name in body.scanners:
        scanner = scanner_registry.SCANNER_REGISTRY[scanner_name]
        row = AdmissionScan(
            id=uuid.uuid4(),
            agent_id=body.agent_id,
            target_type=body.target_type,
            target_ref=body.target_ref,
            scanner_name=scanner_name,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(row)
        await db.flush()

        try:
            findings = await scanner.scan(Path(body.target_ref))
            row.status = "completed"
            row.findings = [f.model_dump() for f in findings]
            row.severity_summary = dict(Counter(f.severity for f in findings))
        except Exception as exc:
            logger.error("admission_scan_failed", scanner_name=scanner_name, error=str(exc))
            row.status = "failed"
            row.findings = []
            row.severity_summary = {}
        row.completed_at = datetime.utcnow()

        await db.flush()
        results.append(row)

    await db.commit()
    for row in results:
        await db.refresh(row)
    return results


@router.get("", response_model=list[AdmissionScanResponse])
async def list_admission_scans(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[AdmissionScan]:
    rows = (await db.execute(
        select(AdmissionScan).order_by(AdmissionScan.created_at.desc()).limit(500)
    )).scalars().all()
    return rows


@router.get("/{scan_id}", response_model=AdmissionScanResponse)
async def get_admission_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> AdmissionScan:
    row = await db.get(AdmissionScan, scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Admission scan not found")
    return row
