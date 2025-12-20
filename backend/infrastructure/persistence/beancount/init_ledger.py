"""Beancount 账本初始化脚本

创建初始账本文件
"""
from pathlib import Path
from datetime import datetime


def init_ledger(ledger_path: str = "data/ledger/main.beancount"):
    """初始化 Beancount 账本文件
    
    Args:
        ledger_path: 账本文件路径
    """
    ledger_file = Path(ledger_path)
    
    # 确保目录存在
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 如果文件已存在，不覆盖
    if ledger_file.exists():
        print(f"ℹ️  Ledger file already exists: {ledger_file.absolute()}")
        print("Skipping initialization to avoid data loss.")
        return
    
    # 获取今天的日期
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 账本模板
    template = f""";; ============================================================
;; BeanMind 账本文件
;; 创建时间: {today}
;; ============================================================

;; ------------------------------------------------------------
;; 选项配置
;; ------------------------------------------------------------
option "title" "个人账本"
option "operating_currency" "CNY"
option "operating_currency" "USD"

;; ------------------------------------------------------------
;; 插件
;; ------------------------------------------------------------
plugin "beancount.plugins.auto_accounts"

;; ------------------------------------------------------------
;; 默认账户定义
;; ------------------------------------------------------------

;; 未知账户（用于临时或未分类交易）
{today} open Assets:Unknown
{today} open Equity:OpeningBalances

;; ------------------------------------------------------------
;; 期初余额（示例）
;; ------------------------------------------------------------
;; 取消注释以下行来设置期初余额
;; {today} * "期初余额" "初始化"
;;   Assets:Unknown                        0.00 CNY
;;   Equity:OpeningBalances               -0.00 CNY

;; ------------------------------------------------------------
;; 交易记录
;; ------------------------------------------------------------
;; 你的交易记录将自动添加在这里

"""
    
    # 写入文件
    ledger_file.write_text(template, encoding="utf-8")
    
    print("✅ Ledger file created successfully!")
    print(f"📁 Location: {ledger_file.absolute()}")
    print("\n💡 Tip: You can now start adding transactions through the BeanMind API")
    print("   or manually edit the file following Beancount syntax.\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize BeanMind ledger file")
    parser.add_argument(
        "--ledger-path",
        default="data/ledger/main.beancount",
        help="Ledger file path (default: data/ledger/main.beancount)"
    )
    
    args = parser.parse_args()
    init_ledger(args.ledger_path)
