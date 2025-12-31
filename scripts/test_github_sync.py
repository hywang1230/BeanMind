#!/usr/bin/env python3
"""测试新的 GitHub 同步服务

使用纯 Python 的 GitHub API 实现
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.config.settings import settings
from backend.infrastructure.backup.sync_models import SyncConfig
from backend.infrastructure.backup.github_sync_service import GitHubSyncService


def main():
    print("=" * 60)
    print("GitHub 同步服务测试（使用 GitHub API）")
    print("=" * 60)
    print()
    
    # 创建同步配置
    config = SyncConfig(
        github_token=settings.GITHUB_TOKEN,
        github_repo=settings.GITHUB_REPO,
        github_branch=settings.GITHUB_BRANCH
    )
    
    # 创建同步服务
    service = GitHubSyncService(config)
    
    # 检查配置
    print(f"✓ 配置状态: {'已配置' if service.is_configured else '未配置'}")
    if not service.is_configured:
        print("  请在 .env 文件中配置 GITHUB_TOKEN 和 GITHUB_REPO")
        return
    
    print(f"  - 仓库: {config.github_repo}")
    print(f"  - 分支: {config.github_branch}")
    print()
    
    # 测试连接
    print("🔍 测试 GitHub 连接...")
    success, message = service.test_connection()
    if success:
        print(f"  ✓ {message}")
    else:
        print(f"  ✗ {message}")
        return
    print()
    
    # 获取状态
    print("📊 获取同步状态...")
    status = service.get_status()
    print(f"  - 本地变更: {'是' if status.has_local_changes else '否'}")
    print(f"  - 远程变更: {'是' if status.has_remote_changes else '否'}")
    print(f"  - 同步中: {'是' if status.is_syncing else '否'}")
    print()
    
    # 询问是否执行同步
    choice = input("是否执行完整同步？(y/n): ")
    if choice.lower() != 'y':
        print("取消同步")
        return
    
    print()
    print("🔄 执行同步...")
    result = service.sync("Test sync from script")
    
    if result.success:
        print(f"  ✓ {result.message}")
        if result.pulled_files:
            print(f"  - 拉取的文件: {', '.join(result.pulled_files)}")
        if result.pushed_files:
            print(f"  - 推送的文件: {', '.join(result.pushed_files)}")
    else:
        print(f"  ✗ {result.message}")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
