"""Machine-to-machine authentication for orchestration tools (n8n)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_service_token(x_n8n_token: str | None = Header(default=None, alias="X-N8N-Token")) -> None:
    """Validate the shared service token used by n8n webhooks."""
    if not x_n8n_token or x_n8n_token != settings.n8n_webhook_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de servicio inválido")
