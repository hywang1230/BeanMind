"""AI 会话仓储。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models.ai_session import AISession


class AISessionRepository:
    """AI 会话仓储。"""

    def __init__(self, session: Session):
        self._session = session

    def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        model = self._session.query(AISession).filter_by(session_id=session_id).first()
        return self._to_dict(model) if model else None

    def list_recent(self, limit: int = 50) -> list[Dict[str, Any]]:
        models = (
            self._session.query(AISession)
            .order_by(AISession.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_dict(model) for model in models]

    def upsert(
        self,
        session_id: str,
        title: Optional[str],
        status: str,
        last_message_preview: Optional[str],
        messages: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        model = self._session.query(AISession).filter_by(session_id=session_id).first()
        if not model:
            model = AISession(session_id=session_id, messages_json="[]")
            self._session.add(model)

        model.title = title
        model.status = status
        model.last_message_preview = last_message_preview
        model.messages_json = json.dumps(messages, ensure_ascii=False)
        self._session.commit()
        self._session.refresh(model)
        return self._to_dict(model)

    def delete(self, session_id: str) -> bool:
        model = self._session.query(AISession).filter_by(session_id=session_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    def _to_dict(self, model: AISession) -> Dict[str, Any]:
        return {
            "id": model.id,
            "session_id": model.session_id,
            "title": model.title,
            "status": model.status,
            "last_message_preview": model.last_message_preview,
            "messages": json.loads(model.messages_json or "[]"),
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }
