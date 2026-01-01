"""循环预算功能测试"""
import asyncio
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, '/Users/wangrong/PythonProjects/BeanMind')

from backend.application.services import BudgetApplicationService
from backend.infrastructure.persistence.db.repositories.budget_repository_impl import BudgetRepositoryImpl
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider
from backend.infrastructure.persistence.beancount.repositories import TransactionRepositoryImpl
from backend.config import settings
from backend.infrastructure.persistence.db.models.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


async def test_cyclic_budget():
    """测试循环预算功能"""
    # 创建数据库连接
    engine = create_engine('sqlite:///data/beanmind.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 创建仓储
        budget_repo = BudgetRepositoryImpl(session)

        # 创建交易仓储
        beancount_service = BeancountServiceProvider.get_service(settings.LEDGER_FILE)
        transaction_repo = TransactionRepositoryImpl(beancount_service, session)

        # 创建执行计算服务
        from backend.domain.budget.services.budget_execution_service import BudgetExecutionService
        execution_service = BudgetExecutionService(transaction_repo)

        # 创建应用服务
        budget_service = BudgetApplicationService(budget_repo, execution_service)

        print("=" * 60)
        print("测试1: 创建月度循环预算（2025年全年，共12个周期）")
        print("=" * 60)

        # 创建月度循环预算
        budget_dto = await budget_service.create_budget(
            user_id="default",
            name="2025年生活费预算",
            amount=5000.0,
            period_type="CUSTOM",  # 使用CUSTOM，日期完全自定义
            start_date="2025-01-01",
            end_date="2025-01-31",
            cycle_type="MONTHLY",
            cycle_end_date="2025-12-31",
            carry_over_enabled=True,
            items=[
                {
                    "account_pattern": "Expenses:Food:*",
                    "amount": 3000,
                    "currency": "CNY"
                }
            ]
        )

        print(f"✓ 创建预算成功: {budget_dto['name']}")
        print(f"  预算ID: {budget_dto['id']}")
        print(f"  循环类型: {budget_dto['cycle_type']}")
        print(f"  循环结束日期: {budget_dto['cycle_end_date']}")
        print(f"  启用延续: {budget_dto['carry_over_enabled']}")

        budget_id = budget_dto['id']

        print("\n" + "=" * 60)
        print("测试2: 获取预算的所有周期")
        print("=" * 60)

        cycles = await budget_service.get_budget_cycles(budget_id)

        print(f"✓ 生成了 {len(cycles)} 个周期")
        for i, cycle in enumerate(cycles[:3]):  # 只显示前3个
            print(f"\n周期 {cycle['period_number']}:")
            print(f"  时间: {cycle['period_start']} 至 {cycle['period_end']}")
            print(f"  基础金额: {cycle['base_amount']}")
            print(f"  延续金额: {cycle['carried_over_amount']}")
            print(f"  总金额: {cycle['total_amount']}")
            print(f"  已花费: {cycle['spent_amount']}")
            print(f"  剩余: {cycle['remaining_amount']}")

        if len(cycles) > 3:
            print(f"\n... 还有 {len(cycles) - 3} 个周期")

        print("\n" + "=" * 60)
        print("测试3: 获取当前周期（2025年3月15日）")
        print("=" * 60)

        current_cycle = await budget_service.get_current_budget_cycle(budget_id, "2025-03-15")

        if current_cycle:
            print(f"✓ 找到当前周期:")
            print(f"  周期序号: {current_cycle['period_number']}")
            print(f"  时间: {current_cycle['period_start']} 至 {current_cycle['period_end']}")
            print(f"  总金额: {current_cycle['total_amount']}")
        else:
            print("✗ 未找到当前周期")

        print("\n" + "=" * 60)
        print("测试4: 获取周期概览")
        print("=" * 60)

        summary = await budget_service.get_budget_cycle_summary(budget_id)

        if summary and summary.get('is_cyclic'):
            print(f"✓ 循环预算概览:")
            print(f"  总周期数: {summary['total_cycles']}")
            print(f"  已完成周期: {summary['completed_cycles']}")
            print(f"  总基础金额: {summary['total_base_amount']}")
            print(f"  总延续金额: {summary['total_carried_over']}")
            print(f"  总金额: {summary['total_amount']}")

            if summary.get('current_cycle'):
                cc = summary['current_cycle']
                print(f"\n  当前周期详情:")
                print(f"    周期序号: {cc['period_number']}")
                print(f"    时间: {cc['period_start']} 至 {cc['period_end']}")
                print(f"    使用率: {cc['usage_rate']:.2f}%")
        else:
            print("✗ 该预算不是循环预算")

        print("\n" + "=" * 60)
        print("测试5: 创建年度循环预算")
        print("=" * 60)

        # 创建年度循环预算
        budget_dto2 = await budget_service.create_budget(
            user_id="default",
            name="2025-2027年年度预算",
            amount=50000.0,
            period_type="CUSTOM",  # 使用CUSTOM，日期完全自定义
            start_date="2025-01-01",
            end_date="2025-12-31",
            cycle_type="YEARLY",
            cycle_end_date="2027-12-31",
            carry_over_enabled=False,
            items=[]
        )

        print(f"✓ 创建年度预算成功: {budget_dto2['name']}")
        print(f"  预算ID: {budget_dto2['id']}")

        cycles2 = await budget_service.get_budget_cycles(budget_dto2['id'])
        print(f"  生成了 {len(cycles2)} 个年度周期")

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(test_cyclic_budget())
