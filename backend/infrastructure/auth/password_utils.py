"""密码加密工具

使用 bcrypt 进行密码哈希和验证
"""
import bcrypt


class PasswordUtils:
    """密码加密工具类"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        加密密码
        
        Args:
            password: 明文密码
        
        Returns:
            加密后的密码哈希
        
        Example:
            hashed = PasswordUtils.hash_password("my_password")
            # 返回: $2b$12$xxxxx...
        """
        # 将密码转换为 bytes
        password_bytes = password.encode('utf-8')
        # 生成盐值
        salt = bcrypt.gensalt()
        # 生成哈希
        hashed = bcrypt.hashpw(password_bytes, salt)
        # 返回字符串形式
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        验证密码
        
        Args:
            plain_password: 明文密码
            hashed_password: 加密后的密码哈希
        
        Returns:
            True 如果密码匹配，False 如果不匹配
        
        Example:
            is_valid = PasswordUtils.verify_password("my_password", hashed)
        """
        # 将密码和哈希转换为 bytes
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        # 验证
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    
    @staticmethod
    def needs_update(hashed_password: str) -> bool:
        """
        检查密码哈希是否需要更新
        
        Args:
            hashed_password: 加密后的密码哈希
        
        Returns:
            始终返回 False（bcrypt 哈希格式稳定）
        
        Note:
            bcrypt 哈希格式非常稳定，除非手动升级成本因子(cost factor)，
            否则不需要重新哈希。此方法保留用于未来扩展。
        """
        # bcrypt 哈希通常不需要更新
        # 如果将来需要增加工作因子，可以在这里检查
        return False


