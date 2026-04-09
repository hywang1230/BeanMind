"""模型注册表。"""

from __future__ import annotations

import json
import logging
from typing import Dict

from backend.config import settings
from backend.infrastructure.intelligence.langgraph.models.profiles import ModelProfile

logger = logging.getLogger(__name__)


class ModelRegistry:
    """统一管理模型 profile。"""

    def __init__(self) -> None:
        self._profiles = self._build_profiles()

    def _build_profiles(self) -> Dict[str, ModelProfile]:
        base = {
            "provider": settings.AI_MODEL_PROVIDER,
            "base_url": settings.AI_BASE_URL,
            "temperature": settings.AI_TEMPERATURE,
        }
        profiles = {
            "default": ModelProfile("default", model_name=settings.AI_MODEL_DEFAULT, **base),
            "fast": ModelProfile("fast", model_name=settings.AI_MODEL_FAST, **base),
            "reasoning": ModelProfile("reasoning", model_name=settings.AI_MODEL_REASONING, **base),
            "structured": ModelProfile("structured", model_name=settings.AI_MODEL_STRUCTURED, **base),
            "long_context": ModelProfile("long_context", model_name=settings.AI_MODEL_LONG_CONTEXT, **base),
            "guardrail": ModelProfile("guardrail", model_name=settings.AI_MODEL_GUARDRAIL, **base),
        }

        if settings.AI_AGENT_MODEL_OVERRIDES:
            try:
                overrides = json.loads(settings.AI_AGENT_MODEL_OVERRIDES)
                for profile_id, model_name in overrides.items():
                    if profile_id in profiles and isinstance(model_name, str) and model_name:
                        current = profiles[profile_id]
                        profiles[profile_id] = ModelProfile(
                            profile_id=current.profile_id,
                            provider=current.provider,
                            model_name=model_name,
                            base_url=current.base_url,
                            temperature=current.temperature,
                            max_tokens=current.max_tokens,
                            timeout=current.timeout,
                            supports_tool_call=current.supports_tool_call,
                            supports_json_mode=current.supports_json_mode,
                        )
            except Exception as exc:
                logger.warning("解析 AI_AGENT_MODEL_OVERRIDES 失败: %s", exc)

        return profiles

    def get(self, profile_id: str) -> ModelProfile:
        return self._profiles.get(profile_id, self._profiles["default"])

    def list_profiles(self) -> list[ModelProfile]:
        return list(self._profiles.values())
