"""最小 OpenAI-compatible Chat Completions 客户端。"""

from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class LlmUnavailableError(RuntimeError):
    pass


class MonthlyReviewText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    monthly_summary: str = Field(min_length=1)
    next_month_suggestions: list[str] = Field(max_length=3)


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def generate(self, facts: dict) -> MonthlyReviewText:
        if not self.enabled:
            raise LlmUnavailableError("LLM 功能未启用")
        if not self.base_url or not self.api_key or not self.model:
            raise LlmUnavailableError("LLM 配置不完整")
        messages = [
            {
                "role": "system",
                "content": (
                    "你是个人财务复盘助手。只能解释提供的确定性事实，不得重算金额。"
                    "只返回 JSON：monthly_summary 为非空字符串，"
                    "next_month_suggestions 为最多三条字符串。"
                ),
            },
            {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
        ]
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages},
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            payload = json.loads(content)
            return MonthlyReviewText.model_validate(payload)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise LlmUnavailableError(f"月度复盘模型响应不可用: {type(exc).__name__}") from exc
