"""Conversational agent endpoints (LangChain)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.rbac import Action, Module
from app.models.system import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.system import (
    AgentAnswer,
    AgentCapability,
    ChatMessageOut,
    ChatRequest,
    ChatSessionDetail,
    ChatSessionOut,
)
from app.services.agent import ask, capabilities
from app.services.audit import write_audit

router = APIRouter(prefix="/agent", tags=["Agente conversacional"])

AGENT_USE = Depends(require_permission(Module.AGENT, Action.USE))


@router.get("/capabilities", response_model=list[AgentCapability], summary="Capacidades del agente")
def agent_capabilities(_: User = AGENT_USE) -> list[AgentCapability]:
    return [AgentCapability(**item) for item in capabilities()]


@router.post("/chat", response_model=AgentAnswer, summary="Consultar al agente")
def chat(payload: ChatRequest, db: DbSession, user: User = AGENT_USE) -> AgentAnswer:
    result = ask(db, user=user, message=payload.message, session_id=payload.session_id)
    write_audit(
        db,
        module="agent",
        action="use",
        user=user,
        resource_type="chat_session",
        resource_id=result["session_id"],
        detail={"intent": result["intent"], "tools": result["tools_used"]},
    )
    return AgentAnswer(**result)


@router.get("/sessions", response_model=list[ChatSessionOut], summary="Conversaciones del usuario")
def sessions(db: DbSession, user: CurrentUser) -> list[ChatSessionOut]:
    rows = db.execute(
        select(ChatSession).where(ChatSession.user_id == user.id).order_by(ChatSession.updated_at.desc()).limit(50)
    ).scalars().all()
    return [ChatSessionOut.model_validate(row) for row in rows]


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail, summary="Detalle de conversación")
def session_detail(session_id: int, db: DbSession, user: CurrentUser) -> ChatSessionDetail:
    session = db.get(ChatSession, session_id)
    if session is None or (session.user_id not in (None, user.id) and user.role.code != "ADMIN"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")
    messages = db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.id)
    ).scalars().all()
    payload = ChatSessionDetail.model_validate(session)
    payload.messages = [ChatMessageOut.model_validate(message) for message in messages]
    return payload


@router.delete("/sessions/{session_id}", summary="Eliminar conversación")
def delete_session(session_id: int, db: DbSession, user: CurrentUser) -> dict[str, str]:
    session = db.get(ChatSession, session_id)
    if session is None or (session.user_id not in (None, user.id) and user.role.code != "ADMIN"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")
    db.delete(session)
    db.commit()
    return {"message": "Conversación eliminada"}
