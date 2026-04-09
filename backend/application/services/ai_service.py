"""AI 应用服务

协调 AI 领域服务，管理会话状态，提供面向接口层的操作。
"""
import logging
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from time import perf_counter
from typing import Any, Dict, Optional, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import desc

from backend.config import settings
from backend.config.dependencies import engine, get_beancount_service, get_db_session
from backend.domain.ai.entities import ChatMessage, ChatSession
from backend.application.services import AccountApplicationService, BudgetApplicationService
from backend.application.services.transaction_service import TransactionApplicationService
from backend.domain.budget.services.budget_execution_service import BudgetExecutionService
from backend.infrastructure.intelligence.langgraph import LangGraphRuntime
from backend.infrastructure.persistence.beancount.repositories import (
    AccountRepositoryImpl,
    TransactionRepositoryImpl,
)
from backend.infrastructure.persistence.db.models import (
    AIActionAudit,
    AIAgentInvocation,
    AIPendingAction,
    AISession,
    AISkillInvocation,
    AIToolInvocation,
    AIUserPreference,
    Base,
)
from backend.infrastructure.persistence.db.models.recurring import RecurringRule
from backend.infrastructure.persistence.db.models.user import User
from backend.infrastructure.persistence.db.repositories.ai_pending_action_repository import (
    AIPendingActionRepository,
)
from backend.infrastructure.persistence.db.repositories.ai_session_repository import (
    AISessionRepository,
)
from backend.infrastructure.persistence.db.repositories.ai_user_preference_repository import (
    AIUserPreferenceRepository,
)
from backend.infrastructure.persistence.db.repositories.budget_repository_impl import BudgetRepositoryImpl
from backend.interfaces.dto.request.transaction import CreateTransactionRequest
from backend.interfaces.dto.request.budget import CreateBudgetRequest

logger = logging.getLogger(__name__)

AI_USER_FACING_ERROR = "AI 服务暂时不可用，请稍后重试"




# 预定义的快捷问题
QUICK_QUESTIONS = [
    {"id": "q1", "text": "本月支出分析", "icon": "chart_pie"},
    {"id": "q2", "text": "最近消费趋势", "icon": "graph_square"},
    {"id": "q3", "text": "上月账单总结", "icon": "doc_text"},
    {"id": "q4", "text": "今日消费情况", "icon": "calendar"},
    {"id": "q5", "text": "本周支出最多的类别", "icon": "list_bullet"},
    {"id": "q6", "text": "账户余额概览", "icon": "creditcard"},
]


class AIApplicationService:
    """
    AI 应用服务
    
    负责：
    - 管理聊天会话
    - 协调 AI 领域服务
    - 提供对话接口
    - 管理对话历史
    """
    
    def __init__(self):
        """初始化 AI 应用服务"""
        # 会话存储（实例级内存缓存，生产环境可改为 Redis）
        self._sessions: Dict[str, ChatSession] = {}
        self._graph_runtime = LangGraphRuntime()
        Base.metadata.create_all(
            bind=engine,
            tables=[
                AISession.__table__,
                AIPendingAction.__table__,
                AIActionAudit.__table__,
                AISkillInvocation.__table__,
                AIAgentInvocation.__table__,
                AIToolInvocation.__table__,
                AIUserPreference.__table__,
            ],
        )
    
    def get_quick_questions(self) -> List[Dict]:
        """
        获取快捷问题列表
        
        Returns:
            快捷问题列表
        """
        return QUICK_QUESTIONS

    def get_capabilities(self) -> Dict:
        """返回当前 AI 能力摘要。"""
        memory_summary = self._get_user_memory_summary()
        return {
            "ai_enabled": True,
            "graph_enabled": True,
            "skills_enabled": True,
            "subagents_enabled": True,
            "memory_enabled": True,
            "tool_observability_enabled": True,
            "skills": self._graph_runtime.list_skills(),
            "agents": self._graph_runtime.list_agents(),
            "models": self._graph_runtime.list_models(),
            "memory_summary": memory_summary,
        }

    def list_skills(self) -> List[Dict]:
        return self._graph_runtime.list_skills()

    def list_agents(self) -> List[Dict]:
        return self._graph_runtime.list_agents()

    def list_models(self) -> List[Dict]:
        return self._graph_runtime.list_models()
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> ChatSession:
        """
        获取或创建会话
        
        Args:
            session_id: 会话 ID，如果为 None 则创建新会话
            
        Returns:
            会话实体
        """
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        if session_id:
            persisted = self._load_session(session_id)
            if persisted:
                self._sessions[session_id] = persisted
                return persisted
        
        # 创建新会话
        new_id = session_id or str(uuid.uuid4())
        session = ChatSession(id=new_id)
        self._sessions[new_id] = session
        self._save_session(session)
        return session

    def create_session(self) -> Dict[str, Any]:
        """创建空白会话。"""
        session = self.get_or_create_session()
        return session.to_dict()
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        获取会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            会话实体，不存在返回 None
        """
        session = self._sessions.get(session_id)
        if session:
            return session
        persisted = self._load_session(session_id)
        if persisted:
            self._sessions[session_id] = persisted
        return persisted
    
    def clear_session(self, session_id: str) -> bool:
        """
        清空会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否成功
        """
        session = self.get_session(session_id)
        if session:
            session.clear_messages()
            self._save_session(session)
            self._delete_pending_action(session_id)
            return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否成功
        """
        existed = False
        if session_id in self._sessions:
            del self._sessions[session_id]
            existed = True
        deleted = self._delete_session(session_id)
        self._delete_pending_action(session_id)
        return existed or deleted
    
    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ) -> Dict:
        """
        对话
        
        Args:
            message: 用户消息
            session_id: 会话 ID
            history: 外部传入的历史（可选）
            
        Returns:
            对话响应 DTO
        """
        # 获取或创建会话
        session = self.get_or_create_session(session_id)
        
        # 添加用户消息
        user_message = ChatMessage.user_message(message, session.id)
        session.add_message(user_message)
        self._save_session(session)
        
        # 获取聊天历史
        chat_history = self._prepare_chat_history(history, session, message)

        delete_pending = self._build_delete_pending_action(session.id, message)
        if delete_pending:
            self._save_pending_action(session.id, delete_pending)
            self._record_action_audit(
                session_id=session.id,
                action_type=delete_pending["action_type"],
                draft_payload=delete_pending["draft"],
                status="DRAFTED",
            )
            assistant_message = ChatMessage.assistant_message(
                self._build_draft_reply(delete_pending),
                session.id
            )
            session.add_message(assistant_message)
            self._save_session(session)
            return {
                "session_id": session.id,
                "message": assistant_message.to_dict()
            }
        
        plan = None
        plan_started = perf_counter()
        try:
            plan = self._graph_runtime.plan(
                message=message,
                session_id=session.id,
                history=chat_history,
                context=context or {},
            )
            plan_duration_ms = int((perf_counter() - plan_started) * 1000)
            logger.info(
                "AI graph plan: session=%s intent=%s skills=%s agents=%s",
                session.id,
                plan.intent,
                plan.selected_skills,
                plan.selected_agents,
            )

            runtime_context = self._build_runtime_context(context or {})
            tool_started = perf_counter()
            tool_results = self._graph_runtime.execute_readonly_skills(
                message=message,
                plan=plan,
                context=runtime_context,
            )
            tool_duration_ms = int((perf_counter() - tool_started) * 1000)
            self._record_plan_invocations(session.id, plan, duration_ms=plan_duration_ms)
            self._record_tool_invocations(session.id, tool_results, duration_ms=tool_duration_ms)
            pending_draft = self._extract_pending_transaction_draft(tool_results)
            if pending_draft:
                self._save_pending_action(session.id, pending_draft)
                self._record_action_audit(
                    session_id=session.id,
                    action_type=pending_draft["action_type"],
                    draft_payload=pending_draft["draft"],
                    status="DRAFTED",
                )
                assistant_message = ChatMessage.assistant_message(
                    self._build_draft_reply(pending_draft),
                    session.id
                )
                session.add_message(assistant_message)
                self._save_session(session)
                return {
                    "session_id": session.id,
                    "message": assistant_message.to_dict()
                }
            chat_history = self._apply_system_context(
                chat_history,
                self._graph_runtime.build_system_context(tool_results, context=context or {}),
            )

            # 调用当前模型 profile
            try:
                response = self._invoke_model_response(
                    chat_history=chat_history,
                    model_profile_id=plan.model_profiles[0] if plan.model_profiles else "default",
                )
            except Exception as exc:
                logger.warning("AI 模型调用失败，降级为工具结果总结: %s", exc)
                response = self._build_tool_fallback_reply(message, tool_results)
            
            # 添加 AI 回复消息
            assistant_message = ChatMessage.assistant_message(response, session.id)
            session.add_message(assistant_message)
            self._save_session(session)
            
            return {
                "session_id": session.id,
                "message": assistant_message.to_dict()
            }
            
        except Exception as e:
            try:
                if plan is not None:
                    self._record_plan_invocations(session.id, plan, error=str(e))
            except Exception:
                logger.warning("记录 AI plan 审计失败", exc_info=True)
            logger.error("AI 对话失败: %s", e, exc_info=True)
            raise
    
    async def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ):
        """
        流式对话
        
        Args:
            message: 用户消息
            session_id: 会话 ID
            history: 外部传入的历史（可选）
            
        Yields:
            SSE 格式的数据块
        """
        import json
        
        # 获取或创建会话
        session = self.get_or_create_session(session_id)
        
        # 添加用户消息
        user_message = ChatMessage.user_message(message, session.id)
        session.add_message(user_message)
        self._save_session(session)
        
        # 获取聊天历史
        chat_history = self._prepare_chat_history(history, session, message)

        delete_pending = self._build_delete_pending_action(session.id, message)
        if delete_pending:
            self._save_pending_action(session.id, delete_pending)
            yield f"data: {json.dumps({'type': 'session', 'session_id': session.id})}\n\n"
            yield (
                f"data: {json.dumps({'type': 'interrupt', 'session_id': session.id, 'action_type': delete_pending['action_type'], 'draft': delete_pending['draft'], 'missing_fields': delete_pending['missing_fields'], 'confidence': delete_pending['confidence']}, ensure_ascii=False)}\n\n"
            )
            assistant_message = ChatMessage.assistant_message(
                self._build_draft_reply(delete_pending),
                session.id
            )
            session.add_message(assistant_message)
            self._save_session(session)
            yield f"data: {json.dumps({'type': 'done', 'message': assistant_message.to_dict()}, ensure_ascii=False)}\n\n"
            return
        
        # 收集完整响应
        full_response = ""
        
        plan = None
        plan_started = perf_counter()
        try:
            # 首先发送 session_id
            yield f"data: {json.dumps({'type': 'session', 'session_id': session.id})}\n\n"

            runtime_context = self._build_runtime_context(context or {})

            async for event in self._graph_runtime.plan_stream(
                message=message,
                session_id=session.id,
                history=chat_history,
                context=runtime_context,
            ):
                if event.get("type") == "session":
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            plan = self._graph_runtime.plan(
                message=message,
                session_id=session.id,
                history=chat_history,
                context=context or {},
            )
            plan_duration_ms = int((perf_counter() - plan_started) * 1000)
            tool_started = perf_counter()
            tool_results = self._graph_runtime.execute_readonly_skills(
                message=message,
                plan=plan,
                context=runtime_context,
            )
            tool_duration_ms = int((perf_counter() - tool_started) * 1000)
            self._record_plan_invocations(session.id, plan, duration_ms=plan_duration_ms)
            self._record_tool_invocations(session.id, tool_results, duration_ms=tool_duration_ms)
            pending_draft = self._extract_pending_transaction_draft(tool_results)
            for result in tool_results:
                yield (
                    f"data: {json.dumps({'type': 'tool', 'tool_name': result.tool_name, 'skill_id': result.skill_id, 'payload': result.payload}, ensure_ascii=False)}\n\n"
                )
            if pending_draft:
                self._save_pending_action(session.id, pending_draft)
                yield (
                    f"data: {json.dumps({'type': 'interrupt', 'session_id': session.id, 'action_type': pending_draft['action_type'], 'draft': pending_draft['draft'], 'missing_fields': pending_draft['missing_fields'], 'confidence': pending_draft['confidence']}, ensure_ascii=False)}\n\n"
                )
                assistant_message = ChatMessage.assistant_message(
                    self._build_draft_reply(pending_draft),
                    session.id
                )
                session.add_message(assistant_message)
                self._save_session(session)
                yield f"data: {json.dumps({'type': 'done', 'message': assistant_message.to_dict()}, ensure_ascii=False)}\n\n"
                return
            chat_history = self._apply_system_context(
                chat_history,
                self._graph_runtime.build_system_context(tool_results, context=context or {}),
            )
            
            # 流式输出 AI 回复
            try:
                async for token in self._astream_model_response(
                    chat_history=chat_history,
                    model_profile_id=plan.model_profiles[0] if plan.model_profiles else "default",
                ):
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            except Exception as exc:
                logger.warning("AI 流式模型调用失败，降级为工具结果总结: %s", exc)
                full_response = self._build_tool_fallback_reply(message, tool_results)
                yield f"data: {json.dumps({'type': 'token', 'content': full_response}, ensure_ascii=False)}\n\n"
            
            # 添加 AI 回复消息到会话
            assistant_message = ChatMessage.assistant_message(full_response, session.id)
            session.add_message(assistant_message)
            self._save_session(session)
            
            # 发送完成消息
            yield f"data: {json.dumps({'type': 'done', 'message': assistant_message.to_dict()})}\n\n"
            
        except Exception as e:
            try:
                if plan is not None:
                    self._record_plan_invocations(session.id, plan, error=str(e))
            except Exception:
                logger.warning("记录 AI stream plan 审计失败", exc_info=True)
            logger.error("AI 流式对话失败: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': AI_USER_FACING_ERROR}, ensure_ascii=False)}\n\n"
            return
    
    def get_session_history(self, session_id: str) -> Optional[Dict]:
        """
        获取会话历史
        
        Args:
            session_id: 会话 ID
            
        Returns:
            会话 DTO，不存在返回 None
        """
        session = self.get_session(session_id)
        if not session:
            return None

        session_data = session.to_dict()
        session_data["pending_action"] = self._get_pending_action(session_id)
        return session_data

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        db = get_db_session()
        try:
            repo = AISessionRepository(db)
            rows = repo.list_recent(limit=limit)
        finally:
            db.close()

        result = []
        for row in rows:
            result.append(
                {
                    "id": row["session_id"],
                    "title": row.get("title"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "message_count": len(row.get("messages", [])),
                    "last_message_preview": row.get("last_message_preview"),
                }
            )
        return result

    def _build_runtime_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        runtime_context = dict(context)
        runtime_context["ai_preferences"] = self._get_user_memory_summary()
        return runtime_context

    def _apply_system_context(
        self,
        history: Optional[List[Dict[str, Any]]],
        system_context: Optional[str],
    ) -> List[Dict[str, Any]]:
        prepared_history = list(history or [])
        if not system_context:
            return prepared_history
        return [{"role": "system", "content": system_context}, *prepared_history]

    def _prepare_chat_history(
        self,
        history: Optional[List[Dict[str, Any]]],
        session: ChatSession,
        message: str,
    ) -> List[Dict[str, Any]]:
        prepared_history = list(history or session.get_history_for_context())
        if prepared_history and prepared_history[-1].get("role") == "user" and prepared_history[-1].get("content") == message:
            return prepared_history
        prepared_history.append({"role": "user", "content": message})
        return prepared_history

    def _looks_like_delete_request(self, message: str) -> bool:
        normalized = message.strip().lower()
        return (
            any(keyword in normalized for keyword in ["删除", "删掉", "删了", "移除", "去掉"])
            and any(keyword in normalized for keyword in ["这条", "这笔", "上一条", "上条", "刚才", "记录", "交易"])
        )

    def _build_delete_pending_action(self, session_id: str, message: str) -> Optional[Dict[str, Any]]:
        if not self._looks_like_delete_request(message):
            return None

        db = get_db_session()
        try:
            audit = (
                db.query(AIActionAudit)
                .filter(
                    AIActionAudit.session_id == session_id,
                    AIActionAudit.action_type == "transaction.record",
                    AIActionAudit.status == "CONFIRMED",
                )
                .order_by(desc(AIActionAudit.created_at))
                .first()
            )
        finally:
            db.close()

        if not audit or not audit.final_payload:
            return None

        try:
            final_payload = json.loads(audit.final_payload)
        except Exception:
            logger.warning("解析最近交易审计失败: session=%s", session_id, exc_info=True)
            return None

        transaction_id = final_payload.get("id")
        if not transaction_id:
            return None

        return {
            "action_type": "transaction.delete",
            "draft": {
                "transaction_id": transaction_id,
                "date": final_payload.get("date"),
                "description": final_payload.get("description"),
                "payee": final_payload.get("payee"),
            },
            "missing_fields": [],
            "confidence": 0.92,
            "assumptions": {
                "source": "last_confirmed_transaction_in_session",
                "original_action_audit_id": audit.id,
            },
            "status": "draft_only_not_committed",
        }

    def _extract_pending_transaction_draft(self, tool_results) -> Optional[Dict[str, Any]]:
        for result in tool_results:
            if result.skill_id != "transaction.record":
                if result.skill_id == "budget.plan":
                    payload = result.payload
                    return {
                        "action_type": "budget.plan",
                        "draft": payload.get("draft", {}),
                        "missing_fields": payload.get("missing_fields", []),
                        "confidence": 0.7,
                        "assumptions": {"basis": payload.get("basis"), "suggestions": payload.get("suggestions", [])},
                        "status": payload.get("status"),
                    }
                if result.skill_id == "recurring.manage" and result.tool_name == "draft_recurring_rule":
                    payload = result.payload
                    return {
                        "action_type": "recurring.manage",
                        "draft": payload.get("draft", {}),
                        "missing_fields": payload.get("missing_fields", []),
                        "confidence": 0.7,
                        "assumptions": payload.get("assumptions", {}),
                        "status": payload.get("status"),
                    }
                if result.skill_id == "account.manage" and result.tool_name == "draft_account_action":
                    payload = result.payload
                    assumptions = payload.get("assumptions", {})
                    draft = payload.get("draft", {})
                    if draft.get("action") == "close":
                        assumptions = {
                            **assumptions,
                            "required_confirmations": 2,
                            "confirmed_count": 0,
                            "risk_message": "关闭账户属于高风险操作，需要二次确认。",
                        }
                    return {
                        "action_type": "account.manage",
                        "draft": draft,
                        "missing_fields": payload.get("missing_fields", []),
                        "confidence": 0.7,
                        "assumptions": assumptions,
                        "status": payload.get("status"),
                    }
                continue
            payload = result.payload
            return {
                "action_type": "transaction.record",
                "draft": payload.get("draft", {}),
                "missing_fields": payload.get("missing_fields", []),
                "confidence": payload.get("confidence"),
                "assumptions": payload.get("assumptions", {}),
                "status": payload.get("status"),
            }
        return None

    def _build_draft_reply(self, pending_draft: Dict[str, Any]) -> str:
        if pending_draft.get("action_type") == "transaction.delete":
            draft = pending_draft["draft"]
            missing_fields = pending_draft.get("missing_fields") or []
            if missing_fields:
                return (
                    "我识别到了删除交易的请求，但还无法定位要删除的交易，当前不会执行删除。\n"
                    f"草稿：{draft}\n"
                    f"缺失字段：{missing_fields}\n"
                    "请明确指定交易后再确认。"
                )
            return (
                "我已经生成了一份删除交易草稿，当前还没有执行。\n"
                f"草稿：{draft}\n"
                f"假设：{pending_draft.get('assumptions', {})}\n"
                "如需删除这笔交易，请调用 resume 接口执行 confirm；如需取消，请用 cancel。"
            )
        if pending_draft.get("action_type") == "budget.plan":
            draft = pending_draft["draft"]
            missing_fields = pending_draft.get("missing_fields") or []
            if missing_fields:
                return (
                    "我已经生成了一份预算草稿，但信息还不完整，当前不会写入数据库。\n"
                    f"草稿：{draft}\n"
                    f"缺失字段：{missing_fields}\n"
                    "请补充后再确认。"
                )
            return (
                "我已经生成了一份预算草稿，当前还没有写入数据库。\n"
                f"草稿：{draft}\n"
                f"假设：{pending_draft.get('assumptions', {})}\n"
                "如需创建预算，请调用 resume 接口执行 confirm；如需修改草稿，请用 edit。"
            )
        if pending_draft.get("action_type") == "recurring.manage":
            draft = pending_draft["draft"]
            missing_fields = pending_draft.get("missing_fields") or []
            if missing_fields:
                return (
                    "我已经生成了一份周期规则草稿，但信息还不完整，当前不会写入数据库。\n"
                    f"草稿：{draft}\n"
                    f"缺失字段：{missing_fields}\n"
                    "请补充后再确认。"
                )
            return (
                "我已经生成了一份周期规则草稿，当前还没有写入数据库。\n"
                f"草稿：{draft}\n"
                f"假设：{pending_draft.get('assumptions', {})}\n"
                "如需创建周期规则，请调用 resume 接口执行 confirm；如需修改草稿，请用 edit。"
            )
        if pending_draft.get("action_type") == "account.manage":
            draft = pending_draft["draft"]
            missing_fields = pending_draft.get("missing_fields") or []
            assumptions = pending_draft.get("assumptions", {})
            if missing_fields:
                return (
                    "我已经生成了一份账户操作草稿，但信息还不完整，当前不会写入账本。\n"
                    f"草稿：{draft}\n"
                    f"缺失字段：{missing_fields}\n"
                    "请补充后再确认。"
                )
            if assumptions.get("required_confirmations", 1) > 1:
                return (
                    "我已经生成了一份账户操作草稿，当前还没有执行。\n"
                    f"草稿：{draft}\n"
                    f"假设：{assumptions}\n"
                    "这是高风险操作，确认时需要再次确认。"
                )
            return (
                "我已经生成了一份账户操作草稿，当前还没有执行。\n"
                f"草稿：{draft}\n"
                f"假设：{assumptions}\n"
                "如需执行账户操作，请调用 resume 接口执行 confirm；如需修改草稿，请用 edit。"
            )
        draft = pending_draft["draft"]
        missing_fields = pending_draft.get("missing_fields") or []
        if missing_fields:
            return (
                "我已经生成了一份记账草稿，但信息还不完整，当前不会写入账本。\n"
                f"草稿：{draft}\n"
                f"缺失字段：{missing_fields}\n"
                "请补充后再确认。"
            )
        return (
            "我已经生成了一份记账草稿，当前还没有写入账本。\n"
            f"草稿：{draft}\n"
            f"假设：{pending_draft.get('assumptions', {})}\n"
            "如需落账，请调用 resume 接口执行 confirm；如需修改草稿，请用 edit。"
        )

    def _build_cancel_reply(self, action_type: str) -> str:
        if action_type == "transaction.delete":
            return "已取消本次 AI 删除交易草稿，不会执行删除。"
        if action_type == "budget.plan":
            return "已取消本次 AI 预算草稿，不会写入数据库。"
        if action_type == "recurring.manage":
            return "已取消本次 AI 周期规则草稿，不会写入数据库。"
        if action_type == "account.manage":
            return "已取消本次 AI 账户操作草稿，不会执行。"
        return "已取消本次 AI 记账草稿，不会写入账本。"

    def _build_transaction_service(self) -> tuple[TransactionApplicationService, Any]:
        db = get_db_session()
        beancount_service = get_beancount_service()
        transaction_repo = TransactionRepositoryImpl(beancount_service, db)
        account_repo = AccountRepositoryImpl(beancount_service)
        return TransactionApplicationService(transaction_repo, account_repo), db

    def _build_budget_service(self) -> tuple[BudgetApplicationService, Any]:
        db = get_db_session()
        budget_repo = BudgetRepositoryImpl(db)
        beancount_service = get_beancount_service()
        transaction_repo = TransactionRepositoryImpl(beancount_service, db)
        execution_service = BudgetExecutionService(transaction_repo)
        return BudgetApplicationService(budget_repo, execution_service), db

    def _build_account_service(self) -> AccountApplicationService:
        beancount_service = get_beancount_service()
        account_repo = AccountRepositoryImpl(beancount_service)
        return AccountApplicationService(account_repo)

    def _run_async_safely(self, coroutine):
        """在独立线程中执行协程，避免当前线程事件循环状态影响同步调用链。"""
        import asyncio

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coroutine)
            return future.result()

    def _load_session(self, session_id: str) -> Optional[ChatSession]:
        db = get_db_session()
        try:
            repo = AISessionRepository(db)
            data = repo.get_by_session_id(session_id)
            if not data:
                return None
            return ChatSession.from_dict(
                {
                    "id": data["session_id"],
                    "title": data.get("title"),
                    "messages": data.get("messages", []),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                }
            )
        finally:
            db.close()

    def _save_session(self, session: ChatSession) -> Dict[str, Any]:
        db = get_db_session()
        try:
            repo = AISessionRepository(db)
            last_message = session.get_last_message()
            preview = last_message.content[:255] if last_message else None
            return repo.upsert(
                session_id=session.id,
                title=session.title,
                status="ACTIVE",
                last_message_preview=preview,
                messages=[message.to_dict() for message in session.messages],
            )
        finally:
            db.close()

    def _delete_session(self, session_id: str) -> bool:
        db = get_db_session()
        try:
            repo = AISessionRepository(db)
            return repo.delete(session_id)
        finally:
            db.close()

    def _build_tool_fallback_reply(self, message: str, tool_results: List[Any]) -> str:
        if not tool_results:
            return "暂时无法连接 AI 模型，也没有可用的账本结果可以总结。"

        lines: List[str] = []
        wants_detail = any(keyword in message for keyword in ["具体", "详细", "展开", "分析下", "深入", "怎么看", "说明"])
        for result in tool_results:
            payload = result.payload
            if result.skill_id == "transaction.query":
                lines.append(
                    f"已查询到 {payload.get('total', 0)} 笔交易，时间范围 "
                    f"{payload.get('date_range', {}).get('start_date')} 到 {payload.get('date_range', {}).get('end_date')}。"
                )
            elif result.skill_id == "analysis.spending":
                lines.append(self._build_spending_fallback_reply(payload, wants_detail))
            elif result.skill_id == "budget.inspect":
                lines.append(
                    f"当前命中 {payload.get('budget_count', 0)} 个活跃预算，"
                    f"摘要 {payload.get('budgets', [])[:3]}。"
                )
            elif result.skill_id == "budget.plan":
                lines.append(
                    f"已生成预算建议草稿，依据：{payload.get('basis')}，"
                    f"建议项 {payload.get('suggestions', [])[:3]}。"
                )
            elif result.skill_id == "report.explain":
                if payload.get("report_type") == "balance_sheet":
                    lines.append(
                        f"截至 {payload.get('as_of_date')}，总资产 {payload.get('total_assets_cny', 0)} CNY，"
                        f"总负债 {payload.get('total_liabilities_cny', 0)} CNY，净资产 {payload.get('net_worth_cny', 0)} CNY。"
                    )
                else:
                    lines.append(
                        f"时间范围 {payload.get('start_date')} 到 {payload.get('end_date')}，"
                        f"收入 {payload.get('income_total_cny', 0)} CNY，支出 {payload.get('expense_total_cny', 0)} CNY，"
                        f"净利润 {payload.get('net_profit_cny', 0)} CNY。"
                    )
            elif result.skill_id == "recurring.manage":
                lines.append(
                    f"截至 {payload.get('check_date')}，启用周期规则 {payload.get('active_rule_count', 0)} 个，"
                    f"待执行 {payload.get('pending_rule_count', 0)} 个，待执行规则 {payload.get('pending_rules', [])[:3]}。"
                )
            elif result.skill_id == "account.classify":
                lines.append(
                    f"推荐账户 {payload.get('suggested_account')}，"
                    f"原因：{payload.get('reason')}，相关账户 {payload.get('related_accounts', [])[:5]}。"
                )

        return "\n".join(lines) if lines else "暂时无法连接 AI 模型，但已拿到账本结果，当前没有可展示的摘要。"

    def _build_spending_fallback_reply(self, payload: Dict[str, Any], wants_detail: bool) -> str:
        date_range = payload.get("date_range", {})
        start_date = date_range.get("start_date")
        end_date = date_range.get("end_date")
        transaction_count = payload.get("transaction_count", 0)
        total_expense = float(payload.get("total_expense", 0) or 0)
        top_categories = payload.get("top_categories", []) or []
        average_expense = total_expense / transaction_count if transaction_count else 0

        if not top_categories:
            return (
                f"{start_date} 到 {end_date} 一共记录了 {transaction_count} 笔支出，"
                f"合计 {total_expense:.2f} CNY。当前没有可用的分类明细。"
            )

        top_category = top_categories[0]
        top_category_name = top_category.get("category", "其他")
        top_category_amount = float(top_category.get("amount", 0) or 0)
        top_category_percentage = float(top_category.get("percentage", 0) or 0)
        category_summary = "、".join(
            f"{item.get('category', '其他')} {float(item.get('amount', 0) or 0):.2f} 元（{float(item.get('percentage', 0) or 0):.1f}%）"
            for item in top_categories[:3]
        )

        if wants_detail:
            return (
                f"从 {start_date} 到 {end_date}，你一共有 {transaction_count} 笔支出，合计 {total_expense:.2f} CNY，"
                f"平均每笔约 {average_expense:.2f} CNY。\n"
                f"支出最集中的类别是“{top_category_name}”，金额 {top_category_amount:.2f} 元，占比 {top_category_percentage:.1f}%。\n"
                f"前几项主要支出分别是：{category_summary}。\n"
                f"如果你愿意，我可以继续按时间、商户或具体交易逐条展开。"
            )

        return (
            f"从 {start_date} 到 {end_date}，你一共有 {transaction_count} 笔支出，合计 {total_expense:.2f} CNY。"
            f"目前支出主要集中在“{top_category_name}”，金额 {top_category_amount:.2f} 元，占比 {top_category_percentage:.1f}%。"
            f"如果你想看更细的拆分，我可以继续展开。"
        )

    def _build_llm(self, model_profile_id: str) -> ChatOpenAI:
        profile = self._graph_runtime.model_registry.get(model_profile_id)
        return ChatOpenAI(
            model=profile.model_name,
            temperature=profile.temperature,
            api_key=settings.AI_API_KEY,
            base_url=profile.base_url,
            timeout=profile.timeout,
            max_tokens=profile.max_tokens,
        )

    def _to_langchain_messages(self, chat_history: List[Dict[str, Any]]) -> List[Any]:
        messages: List[Any] = []
        for item in chat_history:
            role = item.get("role")
            content = item.get("content", "")
            if role == "system":
                messages.append(SystemMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))
        return messages

    def _invoke_model_response(self, chat_history: List[Dict[str, Any]], model_profile_id: str) -> str:
        llm = self._build_llm(model_profile_id)
        result = llm.invoke(self._to_langchain_messages(chat_history))
        return result.content if hasattr(result, "content") else str(result)

    async def _astream_model_response(self, chat_history: List[Dict[str, Any]], model_profile_id: str):
        llm = self._build_llm(model_profile_id)
        async for chunk in llm.astream(self._to_langchain_messages(chat_history)):
            content = chunk.content if hasattr(chunk, "content") else ""
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                    else:
                        text = str(item)
                    if text:
                        yield text
            elif content:
                yield content

    def _record_plan_invocations(
        self,
        session_id: str,
        plan: Any,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        status = "FAILED" if error else "SUCCESS"
        for skill_id in plan.selected_skills:
            self._record_skill_invocation(session_id, skill_id, status, duration_ms, error)
        for index, agent_id in enumerate(plan.selected_agents):
            profile = plan.model_profiles[index] if index < len(plan.model_profiles) else None
            self._record_agent_invocation(session_id, agent_id, profile, status, duration_ms, error)

    def _record_skill_invocation(
        self,
        session_id: str,
        skill_id: str,
        status: str,
        duration_ms: Optional[int],
        error: Optional[str],
    ) -> None:
        db = get_db_session()
        try:
            db.add(
                AISkillInvocation(
                    session_id=session_id,
                    skill_id=skill_id,
                    status=status,
                    duration_ms=duration_ms,
                    error=error,
                )
            )
            db.commit()
        finally:
            db.close()

    def _record_agent_invocation(
        self,
        session_id: str,
        agent_id: str,
        model_profile: Optional[str],
        status: str,
        duration_ms: Optional[int],
        error: Optional[str],
    ) -> None:
        db = get_db_session()
        try:
            db.add(
                AIAgentInvocation(
                    session_id=session_id,
                    agent_id=agent_id,
                    model_profile=model_profile,
                    status=status,
                    duration_ms=duration_ms,
                    error=error,
                )
            )
            db.commit()
        finally:
            db.close()

    def _record_action_audit(
        self,
        session_id: str,
        action_type: str,
        draft_payload: Optional[Dict[str, Any]],
        status: str,
        final_payload: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        db = get_db_session()
        try:
            serialize = lambda payload: json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else None
            db.add(
                AIActionAudit(
                    session_id=session_id,
                    action_type=action_type,
                    draft_payload=serialize(draft_payload),
                    final_payload=serialize(final_payload),
                    status=status,
                    executed_at=datetime.now().isoformat() if status != "DRAFTED" else None,
                    error=error,
                )
            )
            db.commit()
        finally:
            db.close()

    def _record_tool_invocations(
        self,
        session_id: str,
        tool_results: List[Any],
        duration_ms: Optional[int] = None,
    ) -> None:
        if not tool_results:
            return
        per_tool_duration = max(int(duration_ms / len(tool_results)), 1) if duration_ms else None
        db = get_db_session()
        try:
            for result in tool_results:
                payload_preview = json.dumps(result.payload, ensure_ascii=False, default=str)[:1000]
                db.add(
                    AIToolInvocation(
                        session_id=session_id,
                        skill_id=result.skill_id,
                        tool_name=result.tool_name,
                        status="SUCCESS",
                        duration_ms=per_tool_duration,
                        payload_preview=payload_preview,
                    )
                )
            db.commit()
        finally:
            db.close()

    def _get_user_memory_summary(self, user_id: str = "default") -> Dict[str, Any]:
        db = get_db_session()
        try:
            repo = AIUserPreferenceRepository(db)
            preferences = repo.list_by_user(user_id)
        finally:
            db.close()

        summary: Dict[str, Any] = {
            "preferred_asset_account": None,
            "preferred_currency": None,
            "payee_account_map": {},
            "recent_accounts": [],
        }

        for item in preferences:
            pref_type = item["preference_type"]
            value = item["value"]
            if pref_type == "preferred_asset_account" and summary["preferred_asset_account"] is None:
                summary["preferred_asset_account"] = value.get("account")
            elif pref_type == "preferred_currency" and summary["preferred_currency"] is None:
                summary["preferred_currency"] = value.get("currency")
            elif pref_type == "payee_account_map":
                payee = value.get("payee")
                account = value.get("account")
                if payee and account and payee not in summary["payee_account_map"]:
                    summary["payee_account_map"][payee] = account
            elif pref_type == "recent_account" and len(summary["recent_accounts"]) < 5:
                account = value.get("account")
                if account:
                    summary["recent_accounts"].append(account)

        return summary

    def _remember_user_preferences(
        self,
        action_type: str,
        committed: Dict[str, Any],
        draft: Dict[str, Any],
        user_id: str = "default",
    ) -> None:
        db = get_db_session()
        try:
            repo = AIUserPreferenceRepository(db)

            if action_type == "transaction.record":
                postings = committed.get("postings") or draft.get("postings") or []
                asset_account = next(
                    (posting.get("account") for posting in postings if str(posting.get("account", "")).startswith("Assets:")),
                    None,
                )
                if asset_account:
                    repo.upsert(
                        user_id=user_id,
                        preference_type="preferred_asset_account",
                        preference_key=asset_account,
                        value={"account": asset_account},
                        weight=1.0,
                    )
                    repo.upsert(
                        user_id=user_id,
                        preference_type="recent_account",
                        preference_key=asset_account,
                        value={"account": asset_account},
                        weight=0.8,
                    )

                currency = next((posting.get("currency") for posting in postings if posting.get("currency")), None)
                if currency:
                    repo.upsert(
                        user_id=user_id,
                        preference_type="preferred_currency",
                        preference_key=str(currency),
                        value={"currency": currency},
                        weight=1.0,
                    )

                payee = committed.get("payee") or draft.get("payee")
                counterparty_account = next(
                    (
                        posting.get("account")
                        for posting in postings
                        if str(posting.get("account", "")).startswith(("Expenses:", "Income:"))
                    ),
                    None,
                )
                if payee and counterparty_account:
                    repo.upsert(
                        user_id=user_id,
                        preference_type="payee_account_map",
                        preference_key=str(payee),
                        value={"payee": payee, "account": counterparty_account},
                        weight=1.1,
                    )

            if action_type == "account.manage":
                account_name = committed.get("name") or committed.get("account_name") or draft.get("name") or draft.get("account_name")
                if account_name:
                    repo.upsert(
                        user_id=user_id,
                        preference_type="recent_account",
                        preference_key=str(account_name),
                        value={"account": account_name},
                        weight=0.7,
                    )
        finally:
            db.close()

    def _get_pending_action(self, session_id: str) -> Optional[Dict[str, Any]]:
        db = get_db_session()
        try:
            repo = AIPendingActionRepository(db)
            return repo.get_by_session_id(session_id)
        finally:
            db.close()

    def _save_pending_action(self, session_id: str, pending_draft: Dict[str, Any]) -> Dict[str, Any]:
        db = get_db_session()
        try:
            repo = AIPendingActionRepository(db)
            return repo.upsert(
                session_id=session_id,
                action_type=pending_draft["action_type"],
                draft=pending_draft.get("draft", {}),
                missing_fields=pending_draft.get("missing_fields", []),
                assumptions=pending_draft.get("assumptions", {}),
                confidence=pending_draft.get("confidence"),
                status="PENDING",
            )
        finally:
            db.close()

    def _delete_pending_action(self, session_id: str) -> bool:
        db = get_db_session()
        try:
            repo = AIPendingActionRepository(db)
            return repo.delete(session_id)
        finally:
            db.close()

    def _validate_draft_missing_fields(self, draft: Dict[str, Any]) -> List[str]:
        missing = []
        if not draft.get("date"):
            missing.append("date")
        if not draft.get("postings"):
            missing.append("postings")
        elif len(draft["postings"]) < 2:
            missing.append("postings")
        return missing

    def _validate_transaction_draft(self, draft: Dict[str, Any]) -> None:
        CreateTransactionRequest.model_validate(
            {
                "date": draft.get("date"),
                "description": draft.get("description"),
                "postings": draft.get("postings"),
                "payee": draft.get("payee"),
                "tags": draft.get("tags"),
                "links": draft.get("links"),
            }
        )

    def _validate_budget_draft(self, draft: Dict[str, Any]) -> None:
        CreateBudgetRequest.model_validate(
            {
                "name": draft.get("name"),
                "amount": draft.get("amount"),
                "period_type": draft.get("period_type"),
                "start_date": draft.get("start_date"),
                "end_date": draft.get("end_date"),
                "items": draft.get("items") or [],
                "cycle_type": draft.get("cycle_type", "NONE"),
                "carry_over_enabled": draft.get("carry_over_enabled", False),
            }
        )

    def _validate_recurring_draft(self, draft: Dict[str, Any]) -> None:
        if not draft.get("name"):
            raise ValueError("周期规则名称不能为空")
        frequency = (draft.get("frequency") or "").upper()
        if frequency not in {"DAILY", "WEEKLY", "BIWEEKLY", "MONTHLY", "YEARLY"}:
            raise ValueError("周期频率仅支持 daily/weekly/biweekly/monthly/yearly")
        frequency_config = draft.get("frequency_config") or {}
        if frequency in {"WEEKLY", "BIWEEKLY"} and not frequency_config.get("weekdays"):
            raise ValueError("周频率必须指定 weekdays")
        if frequency == "MONTHLY" and not frequency_config.get("month_days"):
            raise ValueError("月频率必须指定 month_days")
        transaction_template = draft.get("transaction_template") or {}
        CreateTransactionRequest.model_validate(
            {
                "date": draft.get("start_date"),
                "description": transaction_template.get("description"),
                "postings": transaction_template.get("postings"),
                "payee": transaction_template.get("payee"),
                "tags": transaction_template.get("tags"),
                "links": [],
            }
        )

    def _validate_account_draft(self, draft: Dict[str, Any]) -> None:
        action = draft.get("action")
        if action not in {"create", "close"}:
            raise ValueError("账户操作仅支持 create/close")
        account_service = self._build_account_service()
        if action == "create":
            if not draft.get("name"):
                raise ValueError("账户名称不能为空")
            if not draft.get("account_type"):
                raise ValueError("账户类型不能为空")
            if not account_service.is_valid_account_name(draft["name"]):
                raise ValueError(f"无效的账户名称: {draft['name']}")
        else:
            if not draft.get("account_name"):
                raise ValueError("关闭账户必须指定 account_name")

    def _execute_confirmed_pending_action(self, pending: Dict[str, Any]) -> tuple[str, Dict[str, Any], str]:
        action_type = pending.get("action_type") or "unknown"
        draft = pending["draft"]

        if action_type == "transaction.delete":
            transaction_id = draft.get("transaction_id")
            if not transaction_id:
                raise ValueError("删除交易必须指定 transaction_id")
            service, db = self._build_transaction_service()
            try:
                existing = service.get_transaction_by_id(transaction_id)
                if not existing:
                    raise ValueError(f"交易 '{transaction_id}' 不存在")
                service.delete_transaction(transaction_id)
            finally:
                db.close()
            committed = {
                "id": transaction_id,
                "date": existing.get("date"),
                "description": existing.get("description"),
                "payee": existing.get("payee"),
            }
            message = f"已确认并删除交易，交易 ID：{transaction_id}，描述：{committed.get('description') or ''}"
            return action_type, committed, message

        if action_type == "budget.plan":
            self._validate_budget_draft(draft)
            service, db = self._build_budget_service()
            try:
                committed = self._run_async_safely(
                    service.create_budget(
                        user_id="default",
                        name=draft["name"],
                        amount=draft["amount"],
                        period_type=draft["period_type"],
                        start_date=draft["start_date"],
                        end_date=draft.get("end_date"),
                        items=draft.get("items"),
                        cycle_type=draft.get("cycle_type", "NONE"),
                        carry_over_enabled=draft.get("carry_over_enabled", False),
                    )
                )
            finally:
                db.close()
            message = f"已确认并创建预算，预算 ID：{committed['id']}，名称：{committed['name']}，开始日期：{committed['start_date']}"
            return action_type, committed, message

        if action_type == "recurring.manage":
            self._validate_recurring_draft(draft)
            db = get_db_session()
            try:
                default_user = db.query(User).filter(User.username == "default").first()
                if not default_user:
                    raise ValueError("默认用户不存在，无法创建周期规则")
                rule = RecurringRule(
                    user_id=default_user.id,
                    name=draft["name"],
                    frequency=draft["frequency"].upper(),
                    frequency_config=json.dumps(draft.get("frequency_config") or {}, ensure_ascii=False),
                    transaction_template=json.dumps(draft.get("transaction_template") or {}, ensure_ascii=False),
                    start_date=date.fromisoformat(draft["start_date"]),
                    end_date=date.fromisoformat(draft["end_date"]) if draft.get("end_date") else None,
                    is_active=draft.get("is_active", True),
                )
                db.add(rule)
                db.commit()
                db.refresh(rule)
            finally:
                db.close()
            committed = {"id": rule.id, "name": rule.name, "frequency": rule.frequency.lower()}
            message = f"已确认并创建周期规则，规则 ID：{rule.id}，名称：{rule.name}，频率：{rule.frequency.lower()}"
            return action_type, committed, message

        if action_type == "account.manage":
            self._validate_account_draft(draft)
            service = self._build_account_service()
            if draft["action"] == "create":
                committed = service.create_account(
                    name=draft["name"],
                    account_type=draft["account_type"],
                    currencies=draft.get("currencies"),
                    open_date=draft.get("open_date"),
                )
                message = f"已确认并创建账户，账户名称：{committed['name']}，类型：{committed['account_type']}"
                return action_type, committed, message

            service.close_account(
                account_name=draft["account_name"],
                close_date=draft.get("close_date"),
            )
            committed = {"account_name": draft["account_name"]}
            message = f"已确认并关闭账户：{draft['account_name']}"
            return action_type, committed, message

        self._validate_transaction_draft(draft)
        service, db = self._build_transaction_service()
        try:
            committed = service.create_transaction(
                txn_date=draft["date"],
                description=draft.get("description") or "",
                postings=draft["postings"],
                payee=draft.get("payee"),
                tags=draft.get("tags"),
                links=draft.get("links"),
            )
        finally:
            db.close()

        message = f"已确认并写入账本，交易 ID：{committed['id']}，日期：{committed['date']}，描述：{committed.get('description') or ''}"
        return "transaction.record", committed, message

    def resume_session_action(
        self,
        session_id: str,
        action: str,
        draft: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = self.get_or_create_session(session_id)
        pending = self._get_pending_action(session_id)
        if not pending:
            return None

        normalized_action = action.lower().strip()
        if normalized_action not in {"confirm", "cancel", "edit"}:
            raise ValueError("action 仅支持 confirm/cancel/edit")

        if normalized_action == "cancel":
            self._delete_pending_action(session_id)
            self._record_action_audit(
                session_id=session_id,
                action_type=pending.get("action_type", "unknown"),
                draft_payload=pending.get("draft"),
                status="CANCELLED",
            )
            assistant_message = ChatMessage.assistant_message(
                self._build_cancel_reply(pending.get("action_type", "")),
                session_id
            )
            session.add_message(assistant_message)
            self._save_session(session)
            return {"session_id": session_id, "message": assistant_message.to_dict()}

        if normalized_action == "edit":
            if not draft:
                raise ValueError("edit 操作必须提供 draft")
            pending["draft"] = draft
            pending["missing_fields"] = self._validate_draft_missing_fields(draft)
            if not pending["missing_fields"] and pending.get("action_type") == "transaction.record":
                self._validate_transaction_draft(draft)
            if pending.get("action_type") == "budget.plan":
                pending["missing_fields"] = []
                if not draft.get("name"):
                    pending["missing_fields"].append("name")
                if not draft.get("amount"):
                    pending["missing_fields"].append("amount")
                if not draft.get("items"):
                    pending["missing_fields"].append("items")
                if not draft.get("start_date"):
                    pending["missing_fields"].append("start_date")
                if not pending["missing_fields"]:
                    self._validate_budget_draft(draft)
            if pending.get("action_type") == "recurring.manage":
                pending["missing_fields"] = []
                if not draft.get("name"):
                    pending["missing_fields"].append("name")
                if not draft.get("frequency"):
                    pending["missing_fields"].append("frequency")
                if not draft.get("start_date"):
                    pending["missing_fields"].append("start_date")
                if not (draft.get("transaction_template") or {}).get("postings"):
                    pending["missing_fields"].append("transaction_template.postings")
                if not pending["missing_fields"]:
                    self._validate_recurring_draft(draft)
            if pending.get("action_type") == "account.manage":
                pending["missing_fields"] = []
                if draft.get("action") == "create" and not draft.get("name"):
                    pending["missing_fields"].append("name")
                if draft.get("action") == "close" and not draft.get("account_name"):
                    pending["missing_fields"].append("account_name")
                if not pending["missing_fields"]:
                    self._validate_account_draft(draft)
            if pending.get("action_type") == "transaction.delete":
                pending["missing_fields"] = []
                if not draft.get("transaction_id"):
                    pending["missing_fields"].append("transaction_id")
            pending = self._save_pending_action(session_id, pending)
            self._record_action_audit(
                session_id=session_id,
                action_type=pending.get("action_type", "unknown"),
                draft_payload=pending.get("draft"),
                status="EDITED",
            )
            assistant_message = ChatMessage.assistant_message(
                self._build_draft_reply(pending),
                session_id
            )
            session.add_message(assistant_message)
            self._save_session(session)
            return {"session_id": session_id, "message": assistant_message.to_dict()}

        if pending.get("missing_fields"):
            raise ValueError(f"草稿仍缺少字段，不能确认：{pending['missing_fields']}")

        if pending.get("action_type") == "account.manage":
            assumptions = pending.get("assumptions") or {}
            draft_payload = pending.get("draft") or {}
            required_confirmations = int(assumptions.get("required_confirmations", 1) or 1)
            confirmed_count = int(assumptions.get("confirmed_count", 0) or 0)
            if draft_payload.get("action") == "close" and confirmed_count < required_confirmations - 1:
                assumptions["confirmed_count"] = confirmed_count + 1
                pending["assumptions"] = assumptions
                self._save_pending_action(session_id, pending)
                self._record_action_audit(
                    session_id=session_id,
                    action_type="account.manage",
                    draft_payload=pending.get("draft"),
                    status="GUARDRAIL_PENDING",
                )
                assistant_message = ChatMessage.assistant_message(
                    assumptions.get("risk_message") or "这是高风险操作，请再次确认后再执行。",
                    session_id,
                )
                session.add_message(assistant_message)
                self._save_session(session)
                return {"session_id": session_id, "message": assistant_message.to_dict()}
        action_type, committed, message = self._execute_confirmed_pending_action(pending)

        self._delete_pending_action(session_id)
        self._remember_user_preferences(action_type, committed, pending["draft"])
        self._record_action_audit(
            session_id=session_id,
            action_type=action_type,
            draft_payload=pending["draft"],
            final_payload=committed,
            status="CONFIRMED",
        )
        assistant_message = ChatMessage.assistant_message(message, session_id)
        session.add_message(assistant_message)
        self._save_session(session)
        return {"session_id": session_id, "message": assistant_message.to_dict()}
