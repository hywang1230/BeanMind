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
    
    def _calculate_content_hash(self, content: bytes) -> str:
        """计算文件内容的 hash 值（与 GitHub blob SHA 兼容）
        
        GitHub 使用 git blob SHA 格式: sha1("blob {size}\0{content}")
        """
        import hashlib
        # Git blob SHA 计算方式
        header = f"blob {len(content)}\0".encode()
        return hashlib.sha1(header + content).hexdigest()
    
    def _get_remote_file_info(self, repo, file_path: str) -> Optional[Tuple[str, str]]:
        """获取远程文件信息
        
        Returns:
            (sha, content_hash) 或 None（文件不存在）
        """
        try:
            content_file = repo.get_contents(file_path, ref=self.config.github_branch)
            if isinstance(content_file, list):
                return None
            return (content_file.sha, content_file.sha)  # GitHub 的 SHA 就是 blob SHA
        except UnknownObjectException:
            return None
        except Exception as e:
            logger.warning(f"获取远程文件信息失败 {file_path}: {e}")
            return None
    
    def push(self, message: str = "Auto sync from BeanMind") -> SyncResult:
        """推送本地变更到 GitHub
        
        使用逐文件更新方式（参考 beancount-web 实现）：
        - 先检查远程文件是否存在
        - 比较内容 hash，只更新有变化的文件
        - 使用 update_file/create_file API
        
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
            
            pushed_files = []
            skipped_files = []
            failed_files = []
            
            for file_path, content in local_files.items():
                try:
                    # 计算本地文件的 blob SHA
                    local_blob_sha = self._calculate_content_hash(content)
                    
                    # 获取远程文件信息
                    remote_info = self._get_remote_file_info(repo, file_path)
                    
                    # 解码内容为字符串（GitHub API 需要字符串）
                    try:
                        content_str = content.decode('utf-8')
                    except UnicodeDecodeError:
                        # 二进制文件使用 base64
                        content_str = base64.b64encode(content).decode('utf-8')
                    
                    if remote_info:
                        remote_sha, remote_blob_sha = remote_info
                        
                        # 比较 SHA，如果相同则跳过
                        if local_blob_sha == remote_blob_sha:
                            skipped_files.append(file_path)
                            logger.debug(f"文件未变更，跳过: {file_path}")
                            continue
                        
                        # 更新已存在的文件
                        repo.update_file(
                            path=file_path,
                            message=f"{message}: {file_path}",
                            content=content_str,
                            sha=remote_sha,
                            branch=self.config.github_branch
                        )
                        logger.info(f"更新文件: {file_path}")
                    else:
                        # 创建新文件
                        repo.create_file(
                            path=file_path,
                            message=f"{message}: {file_path}",
                            content=content_str,
                            branch=self.config.github_branch
                        )
                        logger.info(f"创建文件: {file_path}")
                    
                    pushed_files.append(file_path)
                    
                except GithubException as e:
                    logger.error(f"推送文件失败 {file_path}: {e}")
                    failed_files.append(file_path)
                except Exception as e:
                    logger.error(f"处理文件失败 {file_path}: {e}")
                    failed_files.append(file_path)
            
            # 构建结果消息
            if pushed_files:
                msg_parts = [f"成功推送 {len(pushed_files)} 个文件"]
                if skipped_files:
                    msg_parts.append(f"跳过 {len(skipped_files)} 个未变更文件")
                if failed_files:
                    msg_parts.append(f"{len(failed_files)} 个文件失败")
                result_message = "，".join(msg_parts)
                success = True
            elif skipped_files and not failed_files:
                result_message = f"所有 {len(skipped_files)} 个文件均未变更"
                success = True
            else:
                result_message = f"推送失败，{len(failed_files)} 个文件出错"
                success = False
            
            return SyncResult(
                success=success,
                message=result_message,
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
    
    def pull(self, force: bool = False) -> SyncResult:
        """从 GitHub 拉取更新
        
        智能拉取：只拉取本地不存在或远程有更新的文件。
        如果本地文件有变更（与远程不同），不会覆盖，除非 force=True。
        
        Args:
            force: 是否强制覆盖本地文件（危险操作）
        
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
            
            # 获取本地和远程文件
            local_files = self._get_local_files()
            github_files = self._get_github_files()
            
            if not github_files:
                return SyncResult(
                    success=True,
                    message="远程仓库为空，无需拉取",
                    direction=SyncDirection.PULL
                )
            
            # 智能拉取：只拉取需要更新的文件
            pulled_files = []
            skipped_files = []
            conflict_files = []
            failed_files = []
            
            for file_path, remote_sha in github_files.items():
                # 检查本地是否存在该文件
                if file_path in local_files:
                    # 计算本地文件的 blob SHA
                    local_content = local_files[file_path]
                    local_blob_sha = self._calculate_content_hash(local_content)
                    
                    # 如果本地和远程 SHA 相同，跳过
                    if local_blob_sha == remote_sha:
                        skipped_files.append(file_path)
                        logger.debug(f"文件未变更，跳过拉取: {file_path}")
                        continue
                    
                    # 本地和远程不同，这是一个潜在冲突
                    if not force:
                        # 非强制模式下，跳过有本地修改的文件，避免数据丢失
                        conflict_files.append(file_path)
                        logger.warning(f"文件存在本地修改，跳过拉取以保护数据: {file_path}")
                        continue
                
                # 下载文件（本地不存在，或强制模式）
                content = self._download_file_from_github(file_path)
                if content is None:
                    failed_files.append(file_path)
                    continue
                
                # 保存到本地
                if self._save_local_file(file_path, content):
                    pulled_files.append(file_path)
                    logger.info(f"拉取文件: {file_path}")
                else:
                    failed_files.append(file_path)
            
            if failed_files:
                logger.warning(f"部分文件拉取失败: {failed_files}")
            
            # 构建结果消息
            msg_parts = []
            if pulled_files:
                msg_parts.append(f"拉取 {len(pulled_files)} 个文件")
            if skipped_files:
                msg_parts.append(f"跳过 {len(skipped_files)} 个未变更文件")
            if conflict_files:
                msg_parts.append(f"保护 {len(conflict_files)} 个本地修改文件")
            if failed_files:
                msg_parts.append(f"{len(failed_files)} 个文件失败")
            
            if not msg_parts:
                result_message = "无需拉取"
            else:
                result_message = "，".join(msg_parts)
            
            # 如果有冲突文件，提醒用户
            if conflict_files:
                result_message += "（建议先推送本地变更）"
            
            return SyncResult(
                success=True,
                message=result_message,
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
        """执行完整同步（先推送后拉取）
        
        正确的同步顺序：
        1. 先推送本地变更到远程（保护本地数据）
        2. 再拉取远程新增的文件（只拉取本地不存在的文件）
        
        这样可以确保：
        - 本地修改的数据不会被远程覆盖
        - 远程新增的文件会被同步到本地
        
        Args:
            message: 提交消息
            
        Returns:
            同步结果
        """
        # 1. 先推送本地变更（保护本地数据）
        push_result = self.push(message)
        if not push_result.success:
            return push_result
        
        # 2. 再拉取远程新文件（智能拉取，不覆盖本地已有文件）
        pull_result = self.pull()
        
        # 合并结果消息
        msg_parts = []
        if push_result.pushed_files:
            msg_parts.append(f"推送 {len(push_result.pushed_files)} 个文件")
        if pull_result.pulled_files:
            msg_parts.append(f"拉取 {len(pull_result.pulled_files)} 个文件")
        
        if not msg_parts:
            result_message = "所有文件已同步，无需更新"
        else:
            result_message = "，".join(msg_parts)
        
        return SyncResult(
            success=True,
            message=result_message,
            direction=SyncDirection.BOTH,
            pushed_files=push_result.pushed_files,
            pulled_files=pull_result.pulled_files
        )
