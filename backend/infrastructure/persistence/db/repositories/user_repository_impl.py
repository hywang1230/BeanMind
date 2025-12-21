"""用户仓储 SQLAlchemy 实现

实现用户仓储接口，使用 SQLAlchemy 进行数据持久化。
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.domain.auth.entities import User as UserEntity
from backend.domain.auth.repositories import UserRepository
from backend.infrastructure.persistence.db.models.user import User as UserModel


class UserRepositoryImpl(UserRepository):
    """
    用户仓储的 SQLAlchemy 实现
    
    负责将领域实体与数据库 ORM 模型之间进行转换。
    """
    
    def __init__(self, db: Session):
        """
        初始化仓储
        
        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db
    
    def _to_entity(self, model: UserModel) -> UserEntity:
        """
        将 ORM 模型转换为领域实体
        
        Args:
            model: 用户 ORM 模型
            
        Returns:
            用户领域实体
        """
        return UserEntity(
            id=model.id,
            username=model.username,
            password_hash=model.password_hash,
            display_name=model.display_name,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: UserEntity) -> UserModel:
        """
        将领域实体转换为 ORM 模型
        
        Args:
            entity: 用户领域实体
            
        Returns:
            用户 ORM 模型
        """
        model = UserModel()
        model.id = entity.id
        model.username = entity.username
        model.password_hash = entity.password_hash
        model.display_name = entity.display_name
        if entity.created_at:
            model.created_at = entity.created_at
        if entity.updated_at:
            model.updated_at = entity.updated_at
        return model
    
    def _update_model_from_entity(self, model: UserModel, entity: UserEntity) -> None:
        """
        用领域实体的数据更新 ORM 模型
        
        Args:
            model: 要更新的 ORM 模型
            entity: 源领域实体
        """
        model.username = entity.username
        model.password_hash = entity.password_hash
        model.display_name = entity.display_name
        if entity.created_at:
            model.created_at = entity.created_at
        if entity.updated_at:
            model.updated_at = entity.updated_at
    
    def find_by_id(self, user_id: str) -> Optional[UserEntity]:
        """
        根据 ID 查找用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            找到的用户实体，不存在则返回 None
        """
        model = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_entity(model) if model else None
    
    def find_by_username(self, username: str) -> Optional[UserEntity]:
        """
        根据用户名查找用户
        
        Args:
            username: 用户名
            
        Returns:
            找到的用户实体，不存在则返回 None
        """
        model = self.db.query(UserModel).filter(UserModel.username == username).first()
        return self._to_entity(model) if model else None
    
    def find_all(self) -> List[UserEntity]:
        """
        查找所有用户
        
        Returns:
            所有用户实体的列表
        """
        models = self.db.query(UserModel).all()
        return [self._to_entity(model) for model in models]
    
    def save(self, user: UserEntity) -> UserEntity:
        """
        保存用户（新增或更新）
        
        如果用户 ID 已存在，则更新；否则创建新用户。
        
        Args:
            user: 用户实体
            
        Returns:
            保存后的用户实体
        """
        existing = self.db.query(UserModel).filter(UserModel.id == user.id).first()
        if existing:
            return self.update(user)
        else:
            return self.create(user)
    
    def create(self, user: UserEntity) -> UserEntity:
        """
        创建新用户
        
        Args:
            user: 用户实体
            
        Returns:
            创建后的用户实体
            
        Raises:
            ValueError: 如果用户名已存在
        """
        try:
            model = self._to_model(user)
            self.db.add(model)
            self.db.commit()
            self.db.refresh(model)
            return self._to_entity(model)
        except IntegrityError as e:
            self.db.rollback()
            if "username" in str(e).lower():
                raise ValueError(f"用户名 '{user.username}' 已存在")
            raise ValueError(f"创建用户失败: {str(e)}")
    
    def update(self, user: UserEntity) -> UserEntity:
        """
        更新用户
        
        Args:
            user: 用户实体
            
        Returns:
            更新后的用户实体
            
        Raises:
            ValueError: 如果用户不存在或用户名冲突
        """
        model = self.db.query(UserModel).filter(UserModel.id == user.id).first()
        if not model:
            raise ValueError(f"用户 ID '{user.id}' 不存在")
        
        try:
            self._update_model_from_entity(model, user)
            self.db.commit()
            self.db.refresh(model)
            return self._to_entity(model)
        except IntegrityError as e:
            self.db.rollback()
            if "username" in str(e).lower():
                raise ValueError(f"用户名 '{user.username}' 已存在")
            raise ValueError(f"更新用户失败: {str(e)}")
    
    def delete(self, user_id: str) -> bool:
        """
        删除用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            删除成功返回 True，用户不存在返回 False
        """
        model = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not model:
            return False
        
        self.db.delete(model)
        self.db.commit()
        return True
    
    def exists_by_username(self, username: str) -> bool:
        """
        检查用户名是否存在
        
        Args:
            username: 用户名
            
        Returns:
            存在返回 True，否则返回 False
        """
        count = self.db.query(UserModel).filter(UserModel.username == username).count()
        return count > 0
    
    def count(self) -> int:
        """
        获取用户总数
        
        Returns:
            用户总数
        """
        return self.db.query(UserModel).count()
