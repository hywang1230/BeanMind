"""基于 LangGraph 的月报 Agent"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


class MonthlyReportAgentError(RuntimeError):
    """月报 Agent 调用失败"""


@dataclass(frozen=True)
class MonthlyReportModelConfig:
    """月报模型配置"""

    provider: str
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.2


class MonthlyReportAgent:
    """LangGraph 月报单 Agent"""

    def __init__(self, config: MonthlyReportModelConfig):
        self._config = config

    @property
    def model_config(self) -> MonthlyReportModelConfig:
        return self._config

    def generate(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from langgraph.graph import END, START, StateGraph
        except ModuleNotFoundError as exc:
            raise MonthlyReportAgentError("未安装 langgraph，无法生成 AI 月报") from exc

        prompt = self._build_prompt(facts)
        facts_payload = json.dumps(facts, ensure_ascii=False, indent=2)

        def render_node(state: Dict[str, Any]) -> Dict[str, Any]:
            report = self._invoke_llm(state["facts"], state["prompt"], state["facts_payload"])
            return {
                "facts": state["facts"],
                "prompt": state["prompt"],
                "facts_payload": state["facts_payload"],
                "report": report,
            }

        graph = StateGraph(dict)
        graph.add_node("render", render_node)
        graph.add_edge(START, "render")
        graph.add_edge("render", END)

        app = graph.compile()
        result = app.invoke(
            {
                "facts": facts,
                "prompt": prompt,
                "facts_payload": facts_payload,
            }
        )
        return result["report"]

    def _build_prompt(self, facts: Dict[str, Any]) -> str:
        return (
            "你是 BeanMind 的财务月报助手。"
            "只能基于提供的结构化事实输出月报，不允许编造金额、交易、分类或趋势。"
            "你只负责生成文字总结和下月建议，金额、指标、支出结构、异常、现金流、投资字段必须原样使用事实数据。"
            "输出必须是 JSON，且只能包含 monthly_summary 和 next_month_suggestions 两个字段。"
            "monthly_summary 需要 1 到 3 句话，中文，结论优先。"
            "next_month_suggestions 最多 3 条，必须具体、可执行，禁止空泛。"
            f" 当前月份：{facts['report_month']}"
        )

    def _invoke_llm(
        self,
        facts: Dict[str, Any],
        prompt: str,
        facts_payload: str,
    ) -> Dict[str, Any]:
        llm = self._create_chat_model()
        messages = self._build_messages(prompt, facts_payload)
        response = llm.invoke(messages)
        generated = self._parse_llm_response(response)

        summary = generated.get("monthly_summary")
        if not isinstance(summary, str) or not summary.strip():
            raise MonthlyReportAgentError("月报模型返回的 monthly_summary 无效")

        suggestions = generated.get("next_month_suggestions")
        if not isinstance(suggestions, list):
            raise MonthlyReportAgentError("月报模型返回的 next_month_suggestions 无效")

        normalized_suggestions = [
            str(item).strip()
            for item in suggestions
            if str(item).strip()
        ][:3]
        if not normalized_suggestions:
            normalized_suggestions = ["当前数据不足以给出更具体建议。"]

        return {
            "prompt": prompt,
            "monthly_summary": summary.strip(),
            "core_metrics": facts["summary_metrics"],
            "spending_structure": facts["spending_structure"],
            "income_structure": facts["income_structure"],
            "change_analysis": facts["change_analysis"],
            "anomalies": facts["anomalies"],
            "cash_flow": facts["cash_flow"],
            "investment": facts["investment"],
            "next_month_suggestions": normalized_suggestions,
        }

    def _create_chat_model(self):
        try:
            from langchain_openai import ChatOpenAI
        except ModuleNotFoundError as exc:
            raise MonthlyReportAgentError(
                "未安装 langchain-openai，无法调用 LLM 生成 AI 月报"
            ) from exc

        return ChatOpenAI(
            model=self._config.model,
            api_key=self._config.api_key or None,
            base_url=self._config.base_url or None,
            temperature=self._config.temperature,
        )

    @staticmethod
    def _build_messages(prompt: str, facts_payload: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    "以下是本月结构化财务事实，请严格基于这些数据生成 JSON：\n"
                    f"{facts_payload}"
                ),
            },
        ]

    def _parse_llm_response(self, response: Any) -> Dict[str, Any]:
        content = self._response_text(response)
        if not content:
            raise MonthlyReportAgentError("月报模型未返回内容")

        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            if normalized.startswith("json"):
                normalized = normalized[4:].strip()

        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise MonthlyReportAgentError("月报模型返回的内容不是有效 JSON") from exc

        if not isinstance(parsed, dict):
            raise MonthlyReportAgentError("月报模型返回的 JSON 结构无效")
        return parsed

    @staticmethod
    def _response_text(response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
            return "".join(parts)
        return str(content or "")
