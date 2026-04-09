"""AI 用户偏好仓储。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.db.models.ai_user_preference import AIUserPreference


class AIUserPreferenceRepository:
    """AI 长期记忆偏好仓储。"""

    def __init__(self, session: Session):
        self._session = session

    def upsert(
        self,
        user_id: str,
        preference_type: str,
        preference_key: str,
        value: Dict[str, Any],
        weight: float = 1.0,
    ) -> Dict[str, Any]:
        model = (
            self._session.query(AIUserPreference)
            .filter_by(
                user_id=user_id,
                preference_type=preference_type,
                preference_key=preference_key,
            )
            .first()
        )
        if not model:
            model = AIUserPreference(
                user_id=user_id,
                preference_type=preference_type,
                preference_key=preference_key,
                value_json="{}",
                use_count=0,
            )
            self._session.add(model)

        model.value_json = json.dumps(value, ensure_ascii=False)
        model.weight = weight
        model.use_count = int(model.use_count or 0) + 1
        model.last_used_at = datetime.now().isoformat()
        self._session.commit()
        self._session.refresh(model)
        return self._to_dict(model)

    def list_by_user(self, user_id: str, preference_type: Optional[str] = None) -> list[Dict[str, Any]]:
        query = self._session.query(AIUserPreference).filter_by(user_id=user_id)
        if preference_type:
            query = query.filter_by(preference_type=preference_type)
        models = query.order_by(AIUserPreference.weight.desc(), AIUserPreference.updated_at.desc()).all()
        return [self._to_dict(model) for model in models]

    def _to_dict(self, model: AIUserPreference) -> Dict[str, Any]:
        return {
            "id": model.id,
            "user_id": model.user_id,
            "preference_type": model.preference_type,
            "preference_key": model.preference_key,
            "value": json.loads(model.value_json or "{}"),
            "weight": model.weight,
            "use_count": model.use_count,
            "last_used_at": model.last_used_at,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }
