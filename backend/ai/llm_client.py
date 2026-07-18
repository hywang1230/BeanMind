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
                    "你是个人财务月度复盘助手。只解释用户提供的确定性事实，"
                    "不得重算、估算或编造任何金额、比例、排名、预算状态或未给出的交易/资产负债数据。"
                    "只能引用事实中的数字、分类名与风险状态；事实没有的内容用中文写「数据不足」，不要脑补。"
                    "语气务实、简练，给优先级和建议，不要道德说教。"
                    "文案语言：正文必须是自然中文。"
                    "严禁在用户可见文案中出现 JSON 键名、字段名或英文技术词，"
                    "例如 risk_items、missing_exchange_rates、change_rate、share、usage_rate、"
                    "top_expense_categories、top_income_categories、currency、budget、items、NORMAL 等；"
                    "应改写为「预算风险项」「缺失汇率」「变化率」「占比」「使用率」「主要支出分类」"
                    "「主要收入分类」「币种」「预算」「预算明细」「正常」等中文。"
                    "风险标签若为英文，写成中文：NORMAL=正常，WARNING=预警，OVER=超支（或事实中的实际含义）。"
                    "数字格式："
                    "1) 事实里的变化率/占比/使用率是小数比例（0.2787=27.87%），"
                    "文中必须写成百分比并保留 1 位小数（如 -27.9%、42.2%），禁止粘贴长小数；"
                    "2) 金额可四舍五入到分（2 位小数），并带上币种代码（如 CNY）。"
                    "输出必须是单个 JSON 对象，不要 Markdown 代码块，不要额外说明。"
                    "字段要求（仅 JSON 键名使用英文，键值内容用中文）："
                    "1) monthly_summary：非空，多自然段（用 \\n 分隔），按以下顺序写，缺数据就跳过并标注数据不足——"
                    "首段一句话结论（健康度：好/中/差 + 主要原因，结合净额、环比与预算风险）；"
                    "收入结构（稳定性、是否偏单一分类或偶发感，仅据主要收入分类与环比判断）；"
                    "支出结构（大类占比、环比、是否触达预算风险；仅据主要支出分类、收支变动、预算与风险项）；"
                    "风险与数据缺口（预算风险项、缺失汇率；无则用中文简述无预算风险、无缺失汇率）。"
                    "不要分析逐笔异常交易、净资产/现金缓冲倍数等事实中不存在的维度。"
                    "2) highlights：最多 5 条短句关键发现，优先写结论性事实（净额/变化率/高占比分类/预算风险），无内容可为 []；"
                    "3) next_month_suggestions：1 到 5 条可执行行动，按优先级排序，"
                    "具体到可操作项（如压降某分类、调整某预算项、补记/补汇率、继续定额投入等），避免空泛口号。"
                    "禁止返回金额字段或其它财务结构。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于以下 JSON 事实撰写本月复盘。"
                    "金额与比例已由账本/系统计算并折算到主币种，请直接引用，勿重算。\n"
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
