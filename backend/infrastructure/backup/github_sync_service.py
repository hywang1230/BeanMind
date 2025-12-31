"""GitHub 同步服务

提供与 GitHub 仓库的双向同步功能，使用 GitHub API 实现
避免本地 Git 仓库，解决文件权限问题
"""
import base64
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List

from github import Github, Repository, GithubException, UnknownObjectException
from github.GithubException import RateLimitExceededException

from backend.config.settings import settings
from backend.infrastructure.backup.sync_models import (
    SyncStatus, SyncResult, SyncConfig, SyncDirection
)

logger = logging.getLogger(__name__)


class GitHubSyncService:
    """GitHub 同步服务
    
    使用 GitHub API (PyGithub) 实现本地文件与 GitHub 仓库的同步。
    优点：
    - 无需本地 Git 仓库，避免权限问题
    - 纯 Python 实现，无需安装 Git
    - 直接通过 API 操作，代码更简洁
    """
    
    # 需要同步的文件路径配置
    SYNC_PATHS = {
        "ledger": {
            "local_dir": lambda: settings.LEDGER_FILE.parent,
            "github_dir": "ledger",
            "pattern": "*.beancount"
        },
        "database": {
            "local_dir": lambda: settings.DATABASE_FILE.parent,
            "github_dir": "database",
            "pattern": "*.db"
        }
    }
    
    def __init__(self, config: SyncConfig):
        """初始化同步服务
        
        Args:
            config: 同步配置
        """
        self.config = config
        self._github: Optional[Github] = None
        self._repo: Optional[Repository.Repository] = None
        self._is_syncing = False
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.config.github_token and self.config.github_repo)
    
    def _get_github_client(self) -> Github:
        """获取 GitHub 客户端"""
        if self._github is None:
            self._github = Github(self.config.github_token)
        return self._github
    
    def _get_repository(self) -> Repository.Repository:
        """获取 GitHub 仓库对象"""
        if self._repo is None:
            github = self._get_github_client()
            self._repo = github.get_repo(self.config.github_repo)
        return self._repo
    
    def _get_local_files(self) -> Dict[str, bytes]:
        """获取所有需要同步的本地文件
        
        Returns:
            {相对路径: 文件内容(bytes)} 的字典
        """
        files = {}
        
        for category, path_config in self.SYNC_PATHS.items():
            local_dir = path_config["local_dir"]()
            github_dir = path_config["github_dir"]
            pattern = path_config["pattern"]
            
            if not local_dir.exists():
                logger.warning(f"本地目录不存在: {local_dir}")
                continue
            
            # 查找匹配的文件
            for file_path in local_dir.glob(pattern):
                if file_path.is_file():
                    relative_path = f"{github_dir}/{file_path.name}"
                    try:
                        with open(file_path, 'rb') as f:
                            files[relative_path] = f.read()
                        logger.debug(f"读取本地文件: {relative_path}")
                    except Exception as e:
                        logger.error(f"读取文件失败 {file_path}: {e}")
        
        return files
    
    def _get_github_files(self) -> Dict[str, str]:
        """获取 GitHub 仓库中的文件列表
        
        Returns:
            {相对路径: SHA} 的字典
        """
        files = {}
        
        try:
            repo = self._get_repository()
            
            # 检查分支是否存在
            try:
                branch = repo.get_branch(self.config.github_branch)
            except UnknownObjectException:
                logger.info(f"分支 {self.config.github_branch} 不存在，仓库可能为空")
                return files
            
            # 获取分支的树
            commit = branch.commit
            tree = repo.get_git_tree(commit.sha, recursive=True)
            
            # 只保留我们关心的文件
            for item in tree.tree:
                if item.type == "blob":  # 只处理文件，不处理目录
                    # 检查是否在我们的同步路径中
                    for category, path_config in self.SYNC_PATHS.items():
                        github_dir = path_config["github_dir"]
                        if item.path.startswith(f"{github_dir}/"):
                            files[item.path] = item.sha
                            logger.debug(f"发现远程文件: {item.path}")
            
            return files
            
        except Exception as e:
            logger.error(f"获取 GitHub 文件列表失败: {e}")
            return files
    
    def _download_file_from_github(self, file_path: str) -> Optional[bytes]:
        """从 GitHub 下载文件内容
        
        Args:
            file_path: 文件在仓库中的相对路径
            
        Returns:
            文件内容（bytes），失败返回 None
        """
        try:
            repo = self._get_repository()
            content_file = repo.get_contents(file_path, ref=self.config.github_branch)
            
            # GitHub API 返回的内容是 base64 编码的
            if isinstance(content_file, list):
                logger.error(f"{file_path} 是目录，无法下载")
                return None
            
            content = base64.b64decode(content_file.content)
            logger.debug(f"从 GitHub 下载文件: {file_path}")
            return content
            
        except Exception as e:
            logger.error(f"下载文件失败 {file_path}: {e}")
            return None
    
    def _save_local_file(self, file_path: str, content: bytes) -> bool:
        """保存文件到本地
        
        Args:
            file_path: GitHub 中的相对路径（如 "ledger/main.beancount"）
            content: 文件内容
            
        Returns:
            是否成功
        """
        try:
            # 解析路径，找到对应的本地目录
            parts = file_path.split('/', 1)
            if len(parts) != 2:
                logger.error(f"无效的文件路径: {file_path}")
                return False
            
            category_dir, filename = parts
            
            # 查找对应的配置
            local_dir = None
            for category, path_config in self.SYNC_PATHS.items():
                if path_config["github_dir"] == category_dir:
                    local_dir = path_config["local_dir"]()
                    break
            
            if local_dir is None:
                logger.error(f"未找到对应的本地目录配置: {category_dir}")
                return False
            
            # 确保目录存在
            local_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            local_file_path = local_dir / filename
            with open(local_file_path, 'wb') as f:
                f.write(content)
            
            logger.debug(f"保存本地文件: {local_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存本地文件失败 {file_path}: {e}")
            return False
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试 GitHub 连接
        
        Returns:
            (成功与否, 消息)
        """
        if not self.is_configured:
            return False, "未配置 GitHub Token 或仓库"
        
        try:
            repo = self._get_repository()
            # 尝试获取仓库信息来验证连接
            _ = repo.name
            return True, "连接成功"
        except RateLimitExceededException:
            return False, "GitHub API 速率限制，请稍后再试"
        except UnknownObjectException:
            return False, "仓库不存在，请检查仓库名称"
        except GithubException as e:
            if e.status == 401:
                return False, "认证失败，请检查 Token 是否正确"
            elif e.status == 403:
                return False, "权限不足，请检查 Token 权限"
            else:
                return False, f"GitHub API 错误: {e.data.get('message', str(e))}"
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
            # 获取本地和远程文件
            local_files = self._get_local_files()
            github_files = self._get_github_files()
            
            # 检查本地变更（本地有但远程没有，或内容不同）
            for file_path in local_files.keys():
                if file_path not in github_files:
                    status.has_local_changes = True
                    break
            
            # 检查远程变更（远程有但本地没有）
            for file_path in github_files.keys():
                if file_path not in local_files:
                    status.has_remote_changes = True
                    break
                    
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
            repo = self._get_repository()
            
            # 获取本地文件
            local_files = self._get_local_files()
            if not local_files:
                return SyncResult(
                    success=True,
                    message="没有需要同步的文件",
                    direction=SyncDirection.PUSH
                )
            
            # 获取当前分支的最新 commit
            try:
                branch = repo.get_branch(self.config.github_branch)
                base_tree_sha = branch.commit.commit.tree.sha
            except UnknownObjectException:
                # 分支不存在，创建初始提交
                base_tree_sha = None
            
            # 创建 blob 对象和树
            tree_elements = []
            for file_path, content in local_files.items():
                # 创建 blob
                blob = repo.create_git_blob(base64.b64encode(content).decode(), "base64")
                tree_elements.append({
                    "path": file_path,
                    "mode": "100644",  # 普通文件
                    "type": "blob",
                    "sha": blob.sha
                })
            
            # 创建树
            if base_tree_sha:
                tree = repo.create_git_tree(tree_elements, base_tree=base_tree_sha)
            else:
                tree = repo.create_git_tree(tree_elements)
            
            # 创建提交
            if base_tree_sha:
                parent = branch.commit
                commit = repo.create_git_commit(message, tree, [parent.commit])
            else:
                commit = repo.create_git_commit(message, tree, [])
            
            # 更新分支引用
            try:
                ref = repo.get_git_ref(f"heads/{self.config.github_branch}")
                ref.edit(commit.sha, force=True)  # force=True 实现本地优先策略
            except UnknownObjectException:
                # 分支不存在，创建新分支
                repo.create_git_ref(f"refs/heads/{self.config.github_branch}", commit.sha)
            
            pushed_files = list(local_files.keys())
            return SyncResult(
                success=True,
                message=f"成功推送 {len(pushed_files)} 个文件",
                direction=SyncDirection.PUSH,
                pushed_files=pushed_files
            )
            
        except RateLimitExceededException:
            return SyncResult(
                success=False,
                message="GitHub API 速率限制，请稍后再试",
                direction=SyncDirection.PUSH
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
            
            # 获取远程文件列表
            github_files = self._get_github_files()
            
            if not github_files:
                return SyncResult(
                    success=True,
                    message="远程仓库为空，无需拉取",
                    direction=SyncDirection.PULL
                )
            
            # 下载并保存所有文件
            pulled_files = []
            failed_files = []
            
            for file_path in github_files.keys():
                # 下载文件
                content = self._download_file_from_github(file_path)
                if content is None:
                    failed_files.append(file_path)
                    continue
                
                # 保存到本地
                if self._save_local_file(file_path, content):
                    pulled_files.append(file_path)
                else:
                    failed_files.append(file_path)
            
            if failed_files:
                logger.warning(f"部分文件拉取失败: {failed_files}")
            
            if not pulled_files:
                return SyncResult(
                    success=False,
                    message="所有文件拉取失败",
                    direction=SyncDirection.PULL
                )
            
            message = f"成功拉取 {len(pulled_files)} 个文件"
            if failed_files:
                message += f"，{len(failed_files)} 个文件失败"
            
            return SyncResult(
                success=True,
                message=message,
                direction=SyncDirection.PULL,
                pulled_files=pulled_files
            )
            
        except RateLimitExceededException:
            return SyncResult(
                success=False,
                message="GitHub API 速率限制，请稍后再试",
                direction=SyncDirection.PULL
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
