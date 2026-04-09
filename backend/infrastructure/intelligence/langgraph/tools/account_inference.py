"""账户推断工具。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Optional


GENERIC_MESSAGE_TOKENS = (
    "帮我",
    "记一笔",
    "记账",
    "记录",
    "今天",
    "昨天",
    "今日",
    "刚刚",
    "花了",
    "消费",
    "支付",
    "付款",
    "付了",
    "支出",
    "收入",
    "收到",
    "收了",
    "转账",
    "转给",
    "转到",
    "账户",
)

LIQUIDITY_EXCLUDE_TERMS = (
    "investment",
    "broker",
    "stock",
    "stocks",
    "fund",
    "funds",
    "security",
    "securities",
    "equity",
    "loan",
    "receivable",
    "payable",
    "投资",
    "基金",
    "股票",
    "证券",
    "理财",
    "应收",
    "应付",
    "预付",
    "预付款",
)


@dataclass(frozen=True)
class InferenceDecision:
    """账户推断结果。"""

    selected_account: Optional[str]
    candidates: List[str]
    confidence: float
    source: str


@dataclass(frozen=True)
class DescriptionDecision:
    """描述推断结果。"""

    text: str
    confidence: float
    source: str


class AccountInferenceEngine:
    """基于账户树、历史交易和用户偏好做最小推断。"""

    def __init__(
        self,
        account_names: List[str],
        preferences: Optional[Dict[str, Any]] = None,
        recent_transactions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.account_names = account_names
        self.preferences = preferences or {}
        self.recent_transactions = recent_transactions or []

    def infer_funding_account(self, message: str) -> InferenceDecision:
        liability_candidates = self._filter_accounts("Liabilities:")
        asset_candidates = self._filter_accounts("Assets:")

        liability_matches = self._score_accounts(liability_candidates, message)
        asset_matches = self._score_accounts(asset_candidates, message)
        if liability_matches:
            return InferenceDecision(
                selected_account=liability_matches[0]["account"],
                candidates=[item["account"] for item in liability_matches[:3]],
                confidence=self._score_to_confidence(liability_matches[0]["score"]),
                source="account_name_match",
            )
        if asset_matches:
            return InferenceDecision(
                selected_account=asset_matches[0]["account"],
                candidates=[item["account"] for item in asset_matches[:3]],
                confidence=self._score_to_confidence(asset_matches[0]["score"]),
                source="account_name_match",
            )

        preferred_asset_account = self.preferences.get("preferred_asset_account")
        if preferred_asset_account in asset_candidates:
            return InferenceDecision(
                selected_account=preferred_asset_account,
                candidates=[preferred_asset_account],
                confidence=0.84,
                source="preference",
            )

        recent_candidates = self._recent_accounts_by_prefix(("Assets:", "Liabilities:"))
        if recent_candidates:
            candidate = next(
                (account for account in recent_candidates if account in liability_candidates),
                None,
            ) or next((account for account in recent_candidates if account in asset_candidates), None)
            if candidate:
                return InferenceDecision(
                    selected_account=candidate,
                    candidates=[account for account in recent_candidates if account in liability_candidates or account in asset_candidates][:3],
                    confidence=0.72,
                    source="recent_history",
                )

        primary_candidates = self._rank_liquid_assets(asset_candidates)
        if primary_candidates:
            return InferenceDecision(
                selected_account=primary_candidates[0],
                candidates=primary_candidates[:3],
                confidence=0.45,
                source="fallback",
            )

        return InferenceDecision(
            selected_account=None,
            candidates=[],
            confidence=0.0,
            source="missing_account",
        )

    def infer_counterparty_account(
        self,
        message: str,
        txn_kind: str,
        payee: Optional[str] = None,
    ) -> InferenceDecision:
        root = "Income:" if txn_kind == "income" else "Expenses:"
        candidates = self._filter_accounts(root)
        payee_map = self.preferences.get("payee_account_map") or {}

        if payee:
            mapped = payee_map.get(payee)
            if mapped in candidates:
                return InferenceDecision(
                    selected_account=mapped,
                    candidates=[mapped],
                    confidence=0.92,
                    source="payee_preference",
                )

        account_matches = self._score_accounts(candidates, message)
        if account_matches:
            return InferenceDecision(
                selected_account=account_matches[0]["account"],
                candidates=[item["account"] for item in account_matches[:3]],
                confidence=self._score_to_confidence(account_matches[0]["score"]),
                source="account_name_match",
            )

        recent_candidates = self._recent_accounts_by_prefix((root,))
        if recent_candidates:
            return InferenceDecision(
                selected_account=recent_candidates[0],
                candidates=recent_candidates[:3],
                confidence=0.68,
                source="recent_history",
            )

        if candidates:
            return InferenceDecision(
                selected_account=candidates[0],
                candidates=candidates[:3],
                confidence=0.38,
                source="fallback",
            )

        fallback_account = "Income:Other" if txn_kind == "income" else "Expenses:Other"
        return InferenceDecision(
            selected_account=fallback_account,
            candidates=[fallback_account],
            confidence=0.2,
            source="missing_account",
        )

    def infer_description(
        self,
        message: str,
        txn_kind: str,
        payee: Optional[str],
        related_accounts: Iterable[str],
    ) -> DescriptionDecision:
        if payee:
            suffix = "收入" if txn_kind == "income" else ""
            return DescriptionDecision(
                text=f"{payee}{suffix}",
                confidence=0.9,
                source="payee",
            )

        cleaned = self._strip_known_tokens(message, related_accounts)
        if cleaned:
            return DescriptionDecision(
                text=cleaned,
                confidence=0.72,
                source="message_crop",
            )

        fallback_text = "收入" if txn_kind == "income" else "支出"
        return DescriptionDecision(
            text=fallback_text,
            confidence=0.35,
            source="fallback",
        )

    def _filter_accounts(self, prefix: str) -> List[str]:
        return [
            account
            for account in self.account_names
            if account.startswith(prefix) and not self._is_test_account(account)
        ]

    def _recent_accounts_by_prefix(self, prefixes: tuple[str, ...]) -> List[str]:
        ranked: List[str] = []
        for account in self.preferences.get("recent_accounts", []):
            if isinstance(account, str) and account.startswith(prefixes) and account not in ranked:
                ranked.append(account)

        usage_count: Dict[str, int] = {}
        for txn in self.recent_transactions:
            for posting in txn.get("postings", []):
                account = posting.get("account")
                if isinstance(account, str) and account.startswith(prefixes):
                    usage_count[account] = usage_count.get(account, 0) + 1

        for account, _ in sorted(usage_count.items(), key=lambda item: (-item[1], item[0])):
            if account not in ranked:
                ranked.append(account)
        return ranked

    def _rank_liquid_assets(self, account_names: List[str]) -> List[str]:
        def _score(account: str) -> tuple[int, str]:
            lower = account.lower()
            penalty = 1 if any(term in lower for term in LIQUIDITY_EXCLUDE_TERMS) else 0
            return (penalty, account)

        return [account for account in sorted(account_names, key=_score)]

    def _score_accounts(self, account_names: List[str], message: str) -> List[Dict[str, Any]]:
        normalized_message = self._normalize_message(message)
        scored_matches: List[Dict[str, Any]] = []
        recent_rank = {
            account: index
            for index, account in enumerate(self._recent_accounts_by_prefix(("Assets:", "Liabilities:", "Expenses:", "Income:")))
        }

        for account in account_names:
            score = 0
            for token in self._extract_account_tokens(account):
                if token in normalized_message:
                    score += max(len(token), 2)
                    if token.isdigit():
                        score += 2
            if score == 0:
                continue
            score += max(0, 3 - recent_rank.get(account, 99))
            scored_matches.append({"account": account, "score": score})

        scored_matches.sort(key=lambda item: (-item["score"], item["account"]))
        return scored_matches

    def _extract_account_tokens(self, account_name: str) -> List[str]:
        tokens = set()
        for part in [segment for segment in account_name.split(":") if segment]:
            part_lower = part.lower()
            if len(part_lower) >= 2:
                tokens.add(part_lower)
            for token in re.findall(r"[a-z]{2,}|\d{2,}|[\u4e00-\u9fff]{2,}", part_lower):
                tokens.add(token)
        return sorted(tokens, key=len, reverse=True)

    def _strip_known_tokens(self, message: str, related_accounts: Iterable[str]) -> str:
        cleaned = message
        cleaned = re.sub(r"\d+(?:\.\d+)?\s*(?:元|块|rmb|cny|usd|eur)?", " ", cleaned, flags=re.IGNORECASE)
        for token in GENERIC_MESSAGE_TOKENS:
            cleaned = cleaned.replace(token, " ")
        for account in related_accounts:
            for token in self._extract_account_tokens(account):
                cleaned = re.sub(re.escape(token), " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[，。,.\-_/：:]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:24] if cleaned else ""

    def _normalize_message(self, message: str) -> str:
        normalized = message.lower()
        normalized = normalized.replace(" ", "")
        for token in ("账户支出", "账户收入", "账户", "支付", "付款", "消费", "刷卡", "用了", "支出", "收入"):
            normalized = normalized.replace(token, "")
        return normalized

    def _score_to_confidence(self, score: int) -> float:
        return min(0.95, max(0.45, 0.45 + score / 40))

    def _is_test_account(self, account_name: str) -> bool:
        return "AITest" in account_name or account_name.startswith("Assets:AITest")
