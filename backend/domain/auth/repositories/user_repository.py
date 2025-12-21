"""用户仓储接口

定义用户数据访问的抽象接口，遵循 DDD 的仓储模式。
具体实现由基础设施层提供（如 SQLAlchemy）。
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from backend.domain.auth.entities import User


class UserRepository(ABC):
    """
    用户仓储接口
    
    定义所有用户数据访问方法的抽象接口。
    这是领域层的接口，不依赖于任何具体的数据存储技术。
    """
    
    @abstractmethod
    def find_by_id(self, user_id: str) -> Optional[User]:
        """
        根据 ID 查找用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            找到的用户实体，不存在则返回 None
        """
        pass
    
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名查找用户
        
        Args:
            username: 用户名
            
        Returns:
            找到的用户实体，不存在则返回 None
        """
        pass
    
    @abstractmethod
    def find_all(self) -> List[User]:
        """
        查找所有用户
        
        Returns:
            所有用户实体的列表
        """
        pass
    
    @abstractmethod
    def save(self, user: User) -> User:
        """
        保存用户（新增或更新）
        
        如果用户 ID 已存在，则更新；否则创建新用户。
        
        Args:
            user: 用户实体
            
        Returns:
            保存后的用户实体
        """
        pass
    
    @abstractmethod
    def create(self, user: User) -> User:
        """
        创建新用户
        
        Args:
            user: 用户实体
            
        Returns:
            创建后的用户实体
            
        Raises:
            ValueError: 如果用户名已存在
        """
        pass
    
    @abstractmethod
    def update(self, user: User) -> User:
        """
        更新用户
        
        Args:
            user: 用户实体
            
        Returns:
            更新后的用户实体
            
        Raises:
            ValueError: 如果用户不存在
        """
        pass
    
    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """
        删除用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            删除成功返回 True，用户不存在返回 False
        """
        pass
    
    @abstractmethod
    def exists_by_username(self, username: str) -> bool:
        """
        检查用户名是否存在
        
        Args:
            username: 用户名
            
        Returns:
            存在返回 True，否则返回 False
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """
        获取用户总数
        
        Returns:
            用户总数
        """
        pass
