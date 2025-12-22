"""Beancount 账本数据同步脚本

从现有的 Beancount 账本文件解析数据，并写入 SQLite 数据库的对应表中。

运行方式:
    从项目根目录运行: 
    source venv/bin/activate && python scripts/sync_beancount.py
    
    或使用 make 命令（如已配置）:
    make sync-beancount

支持的同步内容：
    - 交易元数据 (TransactionMetadata)
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
import argparse
import sys

# 确保项目根目录在 Python 路径中
# scripts/sync_beancount.py -> 向上一层到 BeanMind
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 现在可以安全导入项目模块
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.infrastructure.persistence.db.models import (
    Base,
    TransactionMetadata,
    User,
)


def get_beancount_data(ledger_path: Path) -> tuple:
    """
    使用 beancount 库直接加载账本数据
    
    通过在导入前临时修改 sys.path 来避免与本地 beancount 目录的命名冲突。
    
    Args:
        ledger_path: 账本文件路径
        
    Returns:
        (entries, errors, options, Transaction, Open) 元组
    """
    import importlib
    
    # 保存当前的 sys.path 和已导入的模块
    original_path = sys.path.copy()
    
    # 查找是否有冲突的 beancount 模块
    conflicting_modules = [key for key in sys.modules.keys() if key.startswith('beancount')]
    for mod in conflicting_modules:
        del sys.modules[mod]
    
    try:
        # 创建一个只包含 site-packages 的干净路径
        clean_path = []
        for p in sys.path:
            # 保留 site-packages 和标准库路径
            if 'site-packages' in p or 'lib/python' in p or p == '':
                clean_path.append(p)
        
        sys.path = clean_path
        
        # 导入 beancount 库
        from beancount import loader
        from beancount.core.data import Transaction, Open
        
        # 加载账本
        entries, errors, options = loader.load_file(str(ledger_path))
        
        return entries, errors, options, Transaction, Open
        
    finally:
        # 恢复 sys.path
        sys.path = original_path


class BeancountSyncService:
    """Beancount 账本数据同步服务
    
    负责解析 Beancount 账本文件，将数据同步到 SQLite 数据库。
    """
    
    DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"
    
    def __init__(self, ledger_path: str, db_path: str):
        """
        初始化同步服务
        
        Args:
            ledger_path: Beancount 账本文件路径
            db_path: SQLite 数据库文件路径
        """
        self.ledger_path = Path(ledger_path)
        self.db_path = db_path
        
        # 验证账本文件存在
        if not self.ledger_path.exists():
            raise FileNotFoundError(f"账本文件不存在: {self.ledger_path}")
        
        # 初始化数据库连接
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # 加载 Beancount 数据
        print(f"📂 正在加载账本文件: {self.ledger_path}")
        result = get_beancount_data(self.ledger_path)
        self.entries, self.errors, self.options, self.Transaction, self.Open = result
        
        if self.errors:
            print(f"⚠️  账本解析警告: 发现 {len(self.errors)} 个问题")
            for error in self.errors[:5]:
                print(f"   - {error}")
        
        # 统计交易数量
        transaction_count = self._count_transactions()
        print(f"✅ 账本加载完成，共发现 {transaction_count} 笔交易")
    
    def _count_transactions(self) -> int:
        """统计交易数量"""
        return sum(1 for e in self.entries if isinstance(e, self.Transaction))
    
    def _count_accounts(self) -> int:
        """统计账户数量"""
        return sum(1 for e in self.entries if isinstance(e, self.Open))
    
    def _generate_transaction_id(self, txn_date, description: str) -> str:
        """
        生成交易 ID
        
        使用 UUID5 基于日期和描述生成确定性的唯一 ID。
        
        Args:
            txn_date: 交易日期
            description: 交易描述
            
        Returns:
            唯一的交易 ID
        """
        unique_str = f"{txn_date.isoformat()}_{description}_{uuid.uuid4().hex[:8]}"
        return uuid.uuid5(uuid.NAMESPACE_DNS, unique_str).hex
    
    def sync_transaction_metadata(
        self, 
        user_id: Optional[str] = None,
        clear_existing: bool = False
    ) -> dict:
        """
        同步交易元数据到数据库
        
        Args:
            user_id: 用户 ID（默认使用默认用户）
            clear_existing: 是否清除现有数据后再同步
            
        Returns:
            同步统计信息
        """
        user_id = user_id or self.DEFAULT_USER_ID
        
        print(f"\n📝 开始同步交易元数据...")
        print(f"   用户 ID: {user_id}")
        
        # 检查用户是否存在
        user = self.session.query(User).filter_by(id=user_id).first()
        if not user:
            print(f"⚠️  用户 {user_id} 不存在，创建默认用户...")
            user = User(
                id=user_id,
                username="default",
                display_name="默认用户",
                password_hash=None
            )
            self.session.add(user)
            self.session.commit()
        
        # 如果需要清除现有数据
        if clear_existing:
            deleted_count = self.session.query(TransactionMetadata).filter_by(
                user_id=user_id
            ).delete()
            self.session.commit()
            print(f"   已清除 {deleted_count} 条现有交易元数据")
        
        # 同步交易
        stats = {
            "total": 0,
            "synced": 0,
            "skipped": 0,
            "errors": 0
        }
        
        now = datetime.now()
        
        for entry in self.entries:
            if not isinstance(entry, self.Transaction):
                continue
            
            stats["total"] += 1
            
            try:
                # 生成交易 ID
                description = entry.narration or ""
                beancount_id = self._generate_transaction_id(entry.date, description)
                
                # 提取元数据中的 notes
                notes = ""
                if entry.meta:
                    notes = entry.meta.get("notes", "")
                
                # 从 payee 和 narration 组合提取更多信息
                payee = entry.payee or ""
                if payee:
                    notes = f"[{payee}] {notes}".strip()
                
                # 创建元数据记录
                metadata = TransactionMetadata(
                    user_id=user_id,
                    beancount_id=beancount_id,
                    sync_at=now,
                    notes=notes or None
                )
                
                self.session.add(metadata)
                stats["synced"] += 1
                
                # 每 100 条提交一次
                if stats["synced"] % 100 == 0:
                    self.session.commit()
                    print(f"   已同步 {stats['synced']} 条...")
                    
            except Exception as e:
                stats["errors"] += 1
                print(f"   ❌ 同步失败: {entry.date} - {entry.narration}: {e}")
        
        # 最终提交
        self.session.commit()
        
        print(f"\n📊 交易元数据同步完成:")
        print(f"   总交易数: {stats['total']}")
        print(f"   成功同步: {stats['synced']}")
        print(f"   跳过: {stats['skipped']}")
        print(f"   错误: {stats['errors']}")
        
        return stats
    
    def get_sync_summary(self) -> dict:
        """
        获取同步摘要
        
        显示 Beancount 账本和数据库的当前状态。
        
        Returns:
            摘要信息
        """
        # 数据库统计
        db_metadata_count = self.session.query(TransactionMetadata).count()
        db_user_count = self.session.query(User).count()
        
        summary = {
            "beancount": {
                "file": str(self.ledger_path),
                "transactions": self._count_transactions(),
                "accounts": self._count_accounts(),
                "errors": len(self.errors),
            },
            "database": {
                "file": self.db_path,
                "transaction_metadata": db_metadata_count,
                "users": db_user_count,
            }
        }
        
        return summary
    
    def print_summary(self):
        """打印同步摘要"""
        summary = self.get_sync_summary()
        
        print("\n" + "=" * 60)
        print("📊 同步摘要")
        print("=" * 60)
        
        print("\n📁 Beancount 账本:")
        print(f"   文件: {summary['beancount']['file']}")
        print(f"   交易数: {summary['beancount']['transactions']}")
        print(f"   账户数: {summary['beancount']['accounts']}")
        print(f"   解析错误: {summary['beancount']['errors']}")
        
        print("\n🗄️  SQLite 数据库:")
        print(f"   文件: {summary['database']['file']}")
        print(f"   交易元数据: {summary['database']['transaction_metadata']}")
        print(f"   用户数: {summary['database']['users']}")
        
        print("\n" + "=" * 60)
    
    def close(self):
        """关闭数据库连接"""
        self.session.close()


def sync_beancount_to_db(
    ledger_path: str = "data/ledger/main.beancount",
    db_path: str = "data/beanmind.db",
    user_id: Optional[str] = None,
    clear_existing: bool = False
) -> dict:
    """
    将 Beancount 账本数据同步到 SQLite 数据库
    
    这是对外提供的主要接口函数。
    
    Args:
        ledger_path: Beancount 账本文件路径
        db_path: SQLite 数据库文件路径
        user_id: 用户 ID（可选）
        clear_existing: 是否清除现有数据
        
    Returns:
        同步统计信息
    """
    sync_service = BeancountSyncService(ledger_path, db_path)
    
    try:
        # 打印初始摘要
        sync_service.print_summary()
        
        # 同步交易元数据
        stats = sync_service.sync_transaction_metadata(
            user_id=user_id,
            clear_existing=clear_existing
        )
        
        # 打印最终摘要
        sync_service.print_summary()
        
        return stats
        
    finally:
        sync_service.close()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="Beancount 账本数据同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 默认同步（增量模式）
    python scripts/sync_beancount.py
    
    # 清除现有数据后重新同步
    python scripts/sync_beancount.py --clear
    
    # 仅查看摘要
    python scripts/sync_beancount.py --summary-only
    
    # 指定自定义路径
    python scripts/sync_beancount.py \\
        --ledger data/ledger/main.beancount \\
        --db data/beanmind.db
        """
    )
    
    parser.add_argument(
        "--ledger",
        default="data/ledger/main.beancount",
        help="Beancount 账本文件路径（默认: data/ledger/main.beancount）"
    )
    
    parser.add_argument(
        "--db",
        default="data/beanmind.db",
        help="SQLite 数据库文件路径（默认: data/beanmind.db）"
    )
    
    parser.add_argument(
        "--user-id",
        default=None,
        help="用户 ID（默认使用系统默认用户）"
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="清除现有数据后重新同步"
    )
    
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="仅显示同步摘要，不执行同步"
    )
    
    args = parser.parse_args()
    
    print("\n🚀 Beancount 数据同步工具")
    print("=" * 60)
    
    if args.summary_only:
        # 仅显示摘要
        sync_service = BeancountSyncService(args.ledger, args.db)
        try:
            sync_service.print_summary()
        finally:
            sync_service.close()
    else:
        # 执行同步
        sync_beancount_to_db(
            ledger_path=args.ledger,
            db_path=args.db,
            user_id=args.user_id,
            clear_existing=args.clear
        )
    
    print("\n🎉 完成!")


if __name__ == "__main__":
    main()
