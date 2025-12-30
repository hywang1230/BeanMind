"""GitHub 同步服务

提供与 GitHub 仓库的双向同步功能，支持本地优先策略
"""
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from git import Repo, GitCommandError
from git.exc import InvalidGitRepositoryError

from backend.config.settings import settings
from backend.infrastructure.backup.sync_models import (
    SyncStatus, SyncResult, SyncConfig, SyncDirection
)

logger = logging.getLogger(__name__)


class GitHubSyncService:
    """GitHub 同步服务
    
    使用 GitPython 实现本地文件与 GitHub 仓库的同步。
    采用本地优先策略：当发生冲突时，本地变更优先。
    """
    
    def __init__(self, config: SyncConfig):
        """初始化同步服务
        
        Args:
            config: 同步配置
        """
        self.config = config
        self._data_dir = settings.DATA_DIR
        self._repo_dir = self._data_dir / ".git_sync"
        self._repo: Optional[Repo] = None
        self._is_syncing = False
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.config.github_token and self.config.github_repo)
    
    def _get_remote_url(self) -> str:
        """获取远程仓库 URL（带 Token）"""
        return f"https://{self.config.github_token}@github.com/{self.config.github_repo}.git"
    
    def _ensure_repo(self) -> Repo:
        """确保本地仓库存在"""
        if self._repo is not None:
            return self._repo
        
        self._repo_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self._repo = Repo(self._repo_dir)
            # 更新远程 URL
            if "origin" in [r.name for r in self._repo.remotes]:
                self._repo.remotes.origin.set_url(self._get_remote_url())
            else:
                self._repo.create_remote("origin", self._get_remote_url())
        except InvalidGitRepositoryError:
            # 初始化新仓库
            self._repo = Repo.init(self._repo_dir)
            self._repo.create_remote("origin", self._get_remote_url())
            
        return self._repo
    
    def _copy_data_to_repo(self) -> list[str]:
        """复制数据文件到仓库目录
        
        Returns:
            复制的文件列表
        """
        copied_files = []
        
        # 复制 beancount 文件
        ledger_dir = settings.LEDGER_FILE.parent
        repo_ledger_dir = self._repo_dir / "ledger"
        repo_ledger_dir.mkdir(parents=True, exist_ok=True)
        
        for file in ledger_dir.glob("*.beancount"):
            dest = repo_ledger_dir / file.name
            shutil.copy2(file, dest)
            copied_files.append(f"ledger/{file.name}")
        
        # 复制数据库文件
        db_file = settings.DATABASE_FILE
        if db_file.exists():
            repo_db_dir = self._repo_dir / "database"
            repo_db_dir.mkdir(parents=True, exist_ok=True)
            dest = repo_db_dir / db_file.name
            shutil.copy2(db_file, dest)
            copied_files.append(f"database/{db_file.name}")
        
        return copied_files
    
    def _copy_repo_to_data(self) -> list[str]:
        """从仓库目录复制数据到本地
        
        Returns:
            复制的文件列表
        """
        copied_files = []
        
        # 复制 beancount 文件
        repo_ledger_dir = self._repo_dir / "ledger"
        ledger_dir = settings.LEDGER_FILE.parent
        
        if repo_ledger_dir.exists():
            for file in repo_ledger_dir.glob("*.beancount"):
                dest = ledger_dir / file.name
                shutil.copy2(file, dest)
                copied_files.append(f"ledger/{file.name}")
        
        # 复制数据库文件
        repo_db_dir = self._repo_dir / "database"
        if repo_db_dir.exists():
            for file in repo_db_dir.glob("*.db"):
                dest = settings.DATABASE_FILE.parent / file.name
                shutil.copy2(file, dest)
                copied_files.append(f"database/{file.name}")
        
        return copied_files
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试 GitHub 连接
        
        Returns:
            (成功与否, 消息)
        """
        if not self.is_configured:
            return False, "未配置 GitHub Token 或仓库"
        
        try:
            repo = self._ensure_repo()
            # 尝试 fetch 来验证连接
            repo.remotes.origin.fetch()
            return True, "连接成功"
        except GitCommandError as e:
            error_msg = str(e)
            if "Authentication failed" in error_msg:
                return False, "认证失败，请检查 Token 是否正确"
            elif "not found" in error_msg.lower():
                return False, "仓库不存在，请检查仓库名称"
            else:
                return False, f"连接失败: {error_msg}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def get_status(self) -> SyncStatus:
        """获取同步状态"""
        status = SyncStatus(
            is_configured=self.is_configured,
            is_syncing=self._is_syncing,
            repo=self.config.github_repo,
            branch=self.config.github_branch
        )
        
        if not self.is_configured:
            return status
        
        try:
            repo = self._ensure_repo()
            
            # 检查本地变更
            self._copy_data_to_repo()
            if repo.is_dirty() or repo.untracked_files:
                status.has_local_changes = True
            
            # 检查远程变更（需要 fetch）
            try:
                repo.remotes.origin.fetch()
                local_commit = repo.head.commit if repo.head.is_valid() else None
                remote_ref = f"origin/{self.config.github_branch}"
                if remote_ref in [ref.name for ref in repo.refs]:
                    remote_commit = repo.refs[remote_ref].commit
                    if local_commit and local_commit != remote_commit:
                        status.has_remote_changes = True
            except GitCommandError:
                pass  # 忽略 fetch 错误
                
        except Exception as e:
            logger.warning(f"获取同步状态失败: {e}")
        
        return status
    
    def push(self, message: str = "Auto sync from BeanMind") -> SyncResult:
        """推送本地变更到 GitHub
        
        Args:
            message: 提交消息
            
        Returns:
            推送结果
        """
        if not self.is_configured:
            return SyncResult(
                success=False,
                message="未配置 GitHub 同步",
                direction=SyncDirection.PUSH
            )
        
        try:
            self._is_syncing = True
            repo = self._ensure_repo()
            
            # 复制数据到仓库
            copied_files = self._copy_data_to_repo()
            
            # 添加所有文件
            repo.git.add(A=True)
            
            # 检查是否有变更需要提交
            if repo.is_dirty():
                # 提交
                repo.index.commit(message)
            elif not repo.untracked_files:
                # 检查是否需要推送已有提交
                try:
                    repo.remotes.origin.fetch()
                    remote_ref = f"origin/{self.config.github_branch}"
                    if remote_ref in [ref.name for ref in repo.refs]:
                        local_commit = repo.head.commit
                        remote_commit = repo.refs[remote_ref].commit
                        if local_commit == remote_commit:
                            return SyncResult(
                                success=True,
                                message="没有需要同步的变更",
                                direction=SyncDirection.PUSH
                            )
                except Exception:
                    pass
            
            # 推送（本地优先，使用 force-with-lease）
            try:
                repo.remotes.origin.push(self.config.github_branch)
            except GitCommandError as e:
                if "rejected" in str(e) or "non-fast-forward" in str(e):
                    # 远程有变更，使用 force push（本地优先策略）
                    logger.info("远程有更新，使用本地优先策略强制推送")
                    repo.git.push("origin", self.config.github_branch, "--force-with-lease")
                else:
                    raise
            
            return SyncResult(
                success=True,
                message=f"成功推送 {len(copied_files)} 个文件",
                direction=SyncDirection.PUSH,
                pushed_files=copied_files
            )
            
        except Exception as e:
            logger.error(f"推送失败: {e}")
            return SyncResult(
                success=False,
                message=f"推送失败: {str(e)}",
                direction=SyncDirection.PUSH
            )
        finally:
            self._is_syncing = False
    
    def pull(self) -> SyncResult:
        """从 GitHub 拉取更新
        
        Returns:
            拉取结果
        """
        if not self.is_configured:
            return SyncResult(
                success=False,
                message="未配置 GitHub 同步",
                direction=SyncDirection.PULL
            )
        
        try:
            self._is_syncing = True
            repo = self._ensure_repo()
            
            # Fetch
            repo.remotes.origin.fetch()
            
            # 检查远程分支是否存在
            remote_ref = f"origin/{self.config.github_branch}"
            if remote_ref not in [ref.name for ref in repo.refs]:
                return SyncResult(
                    success=True,
                    message="远程仓库为空，无需拉取",
                    direction=SyncDirection.PULL
                )
            
            # 检查本地是否有有效的 HEAD
            has_local_commits = False
            try:
                if repo.head.is_valid():
                    has_local_commits = True
            except Exception:
                pass
            
            if not has_local_commits:
                # 本地没有提交，直接重置到远程
                repo.git.checkout(self.config.github_branch)
                try:
                    repo.git.reset("--hard", remote_ref)
                except GitCommandError:
                    # 可能需要设置跟踪分支
                    repo.git.branch("--set-upstream-to", remote_ref, self.config.github_branch)
                    repo.git.reset("--hard", remote_ref)
            else:
                # 本地优先：使用 rebase 或 merge 策略
                try:
                    # 先保存本地变更
                    stash_result = None
                    if repo.is_dirty() or repo.untracked_files:
                        stash_result = repo.git.stash("push", "-m", "auto-stash before pull")
                    
                    # 尝试 rebase 到远程
                    try:
                        repo.git.rebase(remote_ref)
                    except GitCommandError as e:
                        # rebase 失败，放弃并使用强制策略
                        repo.git.rebase("--abort")
                        # 本地优先：强制使用本地版本覆盖
                        logger.warning(f"Rebase 失败，使用本地优先策略: {e}")
                    
                    # 恢复 stash
                    if stash_result:
                        try:
                            repo.git.stash("pop")
                        except GitCommandError:
                            # 冲突时保留本地版本
                            repo.git.checkout("--ours", ".")
                            repo.git.add(A=True)
                            try:
                                repo.git.stash("drop")
                            except Exception:
                                pass
                            
                except GitCommandError as e:
                    logger.warning(f"Pull 过程出现问题: {e}")
            
            # 复制仓库数据到本地
            copied_files = self._copy_repo_to_data()
            
            return SyncResult(
                success=True,
                message=f"成功拉取 {len(copied_files)} 个文件",
                direction=SyncDirection.PULL,
                pulled_files=copied_files
            )
            
        except Exception as e:
            logger.error(f"拉取失败: {e}")
            return SyncResult(
                success=False,
                message=f"拉取失败: {str(e)}",
                direction=SyncDirection.PULL
            )
        finally:
            self._is_syncing = False
    
    def sync(self, message: str = "Auto sync from BeanMind") -> SyncResult:
        """执行完整同步（先拉取后推送）
        
        Args:
            message: 提交消息
            
        Returns:
            同步结果
        """
        # 先拉取
        pull_result = self.pull()
        if not pull_result.success and "为空" not in pull_result.message:
            return pull_result
        
        # 再推送
        push_result = self.push(message)
        
        # 合并结果
        return SyncResult(
            success=push_result.success,
            message=push_result.message,
            direction=SyncDirection.BOTH,
            pushed_files=push_result.pushed_files,
            pulled_files=pull_result.pulled_files
        )
