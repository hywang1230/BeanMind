"""OpenAI-compatible Chat Completions 客户端（月度复盘）。"""

from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class LlmUnavailableError(RuntimeError):
    pass


class MonthlyReviewText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    monthly_summary: str = Field(min_length=1)
    highlights: list[str] = Field(default_factory=list, max_length=5)
    next_month_suggestions: list[str] = Field(min_length=1, max_length=5)


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
                    "你是个人财务月度复盘助手。只能解释用户提供的确定性事实，"
                    "不得重算、估算或编造任何金额、比例、排名或预算状态。"
                    "只能引用事实中已给出的数字、分类名与风险标签。"
                    "输出必须是单个 JSON 对象，不要 Markdown 代码块，不要额外说明。"
                    "字段要求："
                    "1) monthly_summary：非空字符串，使用多个自然段（用 \\n 分隔），"
                    "覆盖收支总览、环比变化、结构亮点、预算风险与分类重点；"
                    "2) highlights：字符串数组，最多 5 条关键发现短句，无内容时可为 []；"
                    "3) next_month_suggestions：1 到 5 条具体可执行建议。"
                    "禁止返回金额字段或其它财务结构。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于以下 JSON 事实撰写本月复盘。金额已由系统折算到主币种，请直接引用。\n"
                    f"{json.dumps(facts, ensure_ascii=False)}"
                ),
            },
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
