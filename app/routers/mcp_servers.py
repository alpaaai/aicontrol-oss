"""MCP server registration CRUD — admin only, manual registration only
(Decision 2, plans/2026-09-07-gateway-pivot.md). No discovery logic here or
anywhere else in this codebase: every row is created by an explicit admin
call to this router. No credential field exists on the request or response
model (Decision 9) — see app/models/mcp_server.py for why."""
import uuid
from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.mcp_server import MCPServer
from app.services.activity_log_service import write_activity_log

router = APIRouter(prefix="/mcp-servers", tags=["mcp_servers"])
logger = get_logger("mcp_servers_api")


class MCPServerCreate(BaseModel):
    name: str
    base_url: str
    approved_tools: list[str] = []

    @field_validator("base_url")
    @classmethod
    def _base_url_must_be_http_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("base_url must be an absolute http(s) URL, e.g. https://mcp.example.com/mcp")
        return v


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_url: str
    status: str
    approved_tools: list
    created_at: Optional[datetime]


@router.post("", response_model=MCPServerResponse, status_code=201)
async def register_mcp_server(
    body: MCPServerCreate,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> MCPServer:
    server = MCPServer(
        id=uuid.uuid4(), name=body.name, base_url=body.base_url,
        approved_tools=body.approved_tools,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    logger.info("mcp_server_registered", server_id=str(server.id), name=server.name)
    await write_activity_log(
        action="mcp_server.create",
        resource_type="mcp_server",
        resource_id=str(server.id),
        after_state={"name": server.name, "base_url": server.base_url},
        user_email=_token.get("email"),
    )
    return server


@router.get("", response_model=list[MCPServerResponse])
async def list_mcp_servers(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[MCPServer]:
    result = await db.execute(select(MCPServer).order_by(MCPServer.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> MCPServer:
    server = await db.get(MCPServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return server


class MCPServerUpdate(BaseModel):
    status: Optional[Literal["pending_review", "active", "blocked"]] = None
    approved_tools: Optional[list[str]] = None


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: uuid.UUID,
    body: MCPServerUpdate,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> MCPServer:
    server = await db.get(MCPServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    before = {"status": server.status, "approved_tools": server.approved_tools, "name": server.name}
    if body.status is not None:
        server.status = body.status
    if body.approved_tools is not None:
        server.approved_tools = body.approved_tools
    await db.commit()
    await db.refresh(server)
    logger.info("mcp_server_updated", server_id=str(server_id), status=server.status)
    await write_activity_log(
        action="mcp_server.update",
        resource_type="mcp_server",
        resource_id=str(server_id),
        before_state=before,
        after_state={"status": server.status, "approved_tools": server.approved_tools},
        user_email=_token.get("email"),
    )
    return server


@router.delete("/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> None:
    server = await db.get(MCPServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    name = server.name
    await db.delete(server)
    await db.commit()
    logger.info("mcp_server_deleted", server_id=str(server_id))
    await write_activity_log(
        action="mcp_server.delete",
        resource_type="mcp_server",
        resource_id=str(server_id),
        before_state={"name": name},
        user_email=_token.get("email"),
    )
