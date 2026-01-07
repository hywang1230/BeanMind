"""交易工具

用于查询交易信息并格式化为 beancount 格式。
"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List
import logging

from backend.domain.transaction.entities import Transaction
from backend.infrastructure.persistence.beancount.repositories.transaction_repository_impl import TransactionRepositoryImpl
from backend.config.dependencies import get_beancount_service, get_db


logger = logging.getLogger(__name__)


class TransactionToolInput(BaseModel):
    """交易工具输入参数"""
    start_date: str = Field(description="开始日期，格式为 YYYY-MM-DD")
    end_date: str = Field(description="结束日期，格式为 YYYY-MM-DD")


@tool(args_schema=TransactionToolInput)
def transaction_tool(start_date: str, end_date: str) -> str:
    """
    查询指定日期范围内的交易信息，并格式化为 beancount 格式文本。
    
    调用示例：{"start_date": "2025-12-01", "end_date": "2025-12-31"}
    """
    try:
        # 解析日期
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        # 获取交易仓储
        beancount_service = get_beancount_service()
        db_session = next(get_db())
        try:
            transaction_repo = TransactionRepositoryImpl(beancount_service, db_session)
            
            # 查询交易
            transactions = transaction_repo.find_by_date_range(start, end)
            
            # 格式化为 beancount 文本
            return _format_transactions_to_beancount(transactions)
        finally:
            db_session.close()
            
    except Exception as e:
        logger.error(f"查询交易失败: {e}")
        return f"查询交易失败: {str(e)}"


def _format_transactions_to_beancount(transactions: List[Transaction]) -> str:
    """
    将交易列表格式化为 beancount 格式文本
    
    Args:
        transactions: 交易列表
        
    Returns:
        beancount 格式文本
    """
    if not transactions:
        return "未找到符合条件的交易记录"
    
    # 按日期排序
    transactions.sort(key=lambda t: t.date)
    
    lines = []
    lines.append(f"; 共找到 {len(transactions)} 笔交易\n")
    
    for txn in transactions:
        # 交易头部：日期 标记 "收付款方" "描述"
        flag = txn.flag.value if txn.flag else "*"
        payee = f'"{txn.payee}"' if txn.payee else ""
        description = f'"{txn.description}"' if txn.description else '""'
        
        # 组装交易头部
        if payee:
            header = f"{txn.date.isoformat()} {flag} {payee} {description}"
        else:
            header = f"{txn.date.isoformat()} {flag} {description}"
        
        lines.append(header)
        
        # 添加标签
        if txn.tags:
            tags_str = " ".join(f"#{tag}" for tag in sorted(txn.tags))
            lines.append(f"  ; tags: {tags_str}")
        
        # 添加链接
        if txn.links:
            links_str = " ".join(f"^{link}" for link in sorted(txn.links))
            lines.append(f"  ; links: {links_str}")
        
        # 添加 postings
        for posting in txn.postings:
            # 格式：  账户  金额 货币
            posting_line = f"  {posting.account:<50} {posting.amount:>15.2f} {posting.currency}"
            
            # 添加成本信息
            if posting.has_cost():
                posting_line += f" {{{posting.cost:.2f} {posting.cost_currency}}}"
            
            # 添加价格信息
            if posting.has_price():
                posting_line += f" @ {posting.price:.2f} {posting.price_currency}"
            
            lines.append(posting_line)
        
        # 添加空行分隔
        lines.append("")
    
    return "\n".join(lines)