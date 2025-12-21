"""用户领域实体"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """
    用户领域实体
    
    遵循 DDD 原则，领域实体不包含任何与基础设施相关的依赖，
    仅包含业务属性和业务规则。
    
    Attributes:
        id: 用户唯一标识符（UUID）
        username: 用户名（唯一）
        password_hash: 密码哈希值（无鉴权模式可选）
        display_name: 显示名称
        created_at: 创建时间
        updated_at: 更新时间
    """
    
    id: str
    username: str
    password_hash: Optional[str] = None
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """验证业务规则"""
        self._validate_username()
    
    def _validate_username(self):
        """验证用户名格式"""
        if not self.username:
            raise ValueError("用户名不能为空")
        
        if len(self.username) < 3:
            raise ValueError("用户名长度不能少于3个字符")
        
        if len(self.username) > 50:
            raise ValueError("用户名长度不能超过50个字符")
        
        # 用户名只能包含字母、数字、下划线和中划线
        if not all(c.isalnum() or c in ('_', '-') for c in self.username):
            raise ValueError("用户名只能包含字母、数字、下划线和中划线")
    
    def has_password(self) -> bool:
        """检查是否设置了密码"""
        return self.password_hash is not None and len(self.password_hash) > 0
    
    def update_display_name(self, new_name: str) -> None:
        """更新显示名称"""
        if new_name and len(new_name) > 100:
            raise ValueError("显示名称长度不能超过100个字符")
        self.display_name = new_name
        self.updated_at = datetime.now()
    
    def update_password_hash(self, new_hash: str) -> None:
        """更新密码哈希"""
        if not new_hash:
            raise ValueError("密码哈希不能为空")
        self.password_hash = new_hash
        self.updated_at = datetime.now()
    
    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return {
            "id": self.id,
            "username": self.username,
            "password_hash": self.password_hash,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """从字典创建用户实体"""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"]
        
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"]) if isinstance(data["updated_at"], str) else data["updated_at"]
        
        return cls(
            id=data["id"],
            username=data["username"],
            password_hash=data.get("password_hash"),
            display_name=data.get("display_name"),
            created_at=created_at,
            updated_at=updated_at,
        )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<User(id={self.id}, username={self.username})>"
