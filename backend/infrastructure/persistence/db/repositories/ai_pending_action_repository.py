"""AI 待确认动作仓储。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models.ai_pending_action import AIPendingAction


class AIPendingActionRepository:
    """AI 待确认动作仓储。"""

    def __init__(self, session: Session):
        self._session = session

    def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        model = self._session.query(AIPendingAction).filter_by(session_id=session_id).first()
        return self._to_dict(model) if model else None

    def upsert(
        self,
        session_id: str,
        action_type: str,
        draft: Dict[str, Any],
        missing_fields: list[str],
        assumptions: Dict[str, Any],
        confidence: Optional[float],
        status: str = "PENDING",
    ) -> Dict[str, Any]:
        model = self._session.query(AIPendingAction).filter_by(session_id=session_id).first()
        if not model:
            model = AIPendingAction(
                session_id=session_id,
                action_type=action_type,
                draft_json="{}",
                missing_fields_json="[]",
                assumptions_json="{}",
            )
            self._session.add(model)

        model.action_type = action_type
        model.status = status
        model.draft_json = json.dumps(draft, ensure_ascii=False)
        model.missing_fields_json = json.dumps(missing_fields, ensure_ascii=False)
        model.assumptions_json = json.dumps(assumptions, ensure_ascii=False)
        model.confidence = confidence
        self._session.commit()
        self._session.refresh(model)
        return self._to_dict(model)

    def delete(self, session_id: str) -> bool:
        model = self._session.query(AIPendingAction).filter_by(session_id=session_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    def update_status(self, session_id: str, status: str) -> bool:
        model = self._session.query(AIPendingAction).filter_by(session_id=session_id).first()
        if not model:
            return False
        model.status = status
        self._session.commit()
        return True

    def _to_dict(self, model: AIPendingAction) -> Dict[str, Any]:
        return {
            "id": model.id,
            "session_id": model.session_id,
            "action_type": model.action_type,
            "status": model.status,
            "draft": json.loads(model.draft_json or "{}"),
            "missing_fields": json.loads(model.missing_fields_json or "[]"),
            "assumptions": json.loads(model.assumptions_json or "{}"),
            "confidence": model.confidence,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }
