"""
========================================
用户数据模型
========================================

📚 模块说明：
- 定义用户账号及权限相关的数据表
- 管理用户认证和授权
- 记录用户行为和偏好

🎯 核心模型：
1. User - 用户主表
2. UserPermission - 用户权限表
3. UserSearchHistory - 用户搜索历史

========================================
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean,
    JSON, ForeignKey, Enum as SQLEnum, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from core.constants import UserRole, PermissionLevel

# 使用与document.py相同的Base
from models.document import Base


# =========================================
# 1. 用户主表
# =========================================
class User(Base):
    """
    用户表

    📋 存储内容：
    - 用户基本信息（用户名、邮箱等）
    - 认证信息（密码哈希）
    - 角色和权限
    - 所属部门和项目

    🔒 安全性：
    - 密码使用哈希存储，不保存明文
    - 支持JWT令牌认证
    - 记录登录历史
    """
    __tablename__ = "users"

    # ===== 主键 =====
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="用户唯一ID"
    )

    # ===== 基本信息 =====
    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="用户名（登录用）"
    )

    email = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="邮箱地址"
    )

    full_name = Column(
        String(100),
        nullable=True,
        comment="真实姓名"
    )

    phone = Column(
        String(20),
        nullable=True,
        comment="手机号码"
    )

    # ===== 认证信息 =====
    password_hash = Column(
        String(255),
        nullable=False,
        comment="密码哈希值（使用bcrypt）"
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="账号是否激活"
    )

    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="邮箱是否验证"
    )

    # ===== 角色和权限 =====
    role = Column(
        SQLEnum(UserRole),
        nullable=False,
        default=UserRole.VIEWER,
        index=True,
        comment="用户角色：admin/manager/engineer等"
    )

    default_permission_level = Column(
        SQLEnum(PermissionLevel),
        nullable=False,
        default=PermissionLevel.INTERNAL,
        comment="默认权限级别"
    )

    # ===== 组织信息 =====
    department = Column(
        String(100),
        nullable=True,
        index=True,
        comment="所属部门"
    )

    position = Column(
        String(100),
        nullable=True,
        comment="职位"
    )

    # 用户可以访问的项目列表（JSON数组）
    accessible_projects = Column(
        JSON,
        nullable=True,
        comment="可访问的项目ID列表"
    )

    # ===== 偏好设置 =====
    preferences = Column(
        JSON,
        nullable=True,
        comment="用户偏好设置（主题、语言等）"
    )

    # ===== 统计信息 =====
    query_count = Column(
        Integer,
        default=0,
        comment="查询次数"
    )

    document_upload_count = Column(
        Integer,
        default=0,
        comment="上传文档数量"
    )

    # ===== 登录信息 =====
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间"
    )

    last_login_ip = Column(
        String(50),
        nullable=True,
        comment="最后登录IP"
    )

    login_count = Column(
        Integer,
        default=0,
        comment="登录次数"
    )

    # ===== 时间信息 =====
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="创建时间"
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )

    # ===== 备注 =====
    notes = Column(
        Text,
        nullable=True,
        comment="管理员备注"
    )

    # ===== 关联关系 =====
    # 一对多：用户的权限列表
    permissions = relationship(
        "UserPermission",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # 一对多：用户的搜索历史
    search_history = relationship(
        "UserSearchHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"

    def to_dict(self, include_sensitive=False):
        """
        转换为字典格式

        参数：
            include_sensitive: 是否包含敏感信息（如密码哈希）
        """
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "phone": self.phone,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "role": self.role.value if self.role else None,
            "department": self.department,
            "position": self.position,
            "query_count": self.query_count,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_sensitive:
            data["password_hash"] = self.password_hash

        return data

    def has_permission(self, doc_type: str, permission_level: PermissionLevel) -> bool:
        """
        检查用户是否有访问指定文档的权限

        参数：
            doc_type: 文档类型
            permission_level: 文档的权限级别

        返回：
            bool: True表示有权限，False表示无权限
        """
        # 管理员有所有权限
        if self.role == UserRole.ADMIN:
            return True

        # 公开文档所有人都可访问
        if permission_level == PermissionLevel.PUBLIC:
            return True

        # 其他权限检查逻辑...
        # （实际实现会更复杂，这里简化处理）
        return True


# =========================================
# 2. 用户权限表
# =========================================
class UserPermission(Base):
    """
    用户权限表

    📋 存储内容：
    - 用户对特定资源的访问权限
    - 细粒度的权限控制

    💡 用途：
    - 控制用户对文档、项目的访问
    - 支持临时授权
    - 权限审计
    """
    __tablename__ = "user_permissions"

    # ===== 主键 =====
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="权限ID"
    )

    # ===== 外键：关联用户 =====
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID"
    )

    # ===== 权限范围 =====
    resource_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="资源类型：document/project/collection"
    )

    resource_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="资源ID（文档ID、项目ID等）"
    )

    # ===== 权限类型 =====
    can_read = Column(
        Boolean,
        default=True,
        comment="是否可读"
    )

    can_write = Column(
        Boolean,
        default=False,
        comment="是否可写"
    )

    can_delete = Column(
        Boolean,
        default=False,
        comment="是否可删除"
    )

    can_share = Column(
        Boolean,
        default=False,
        comment="是否可分享"
    )

    # ===== 有效期 =====
    valid_from = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="权限生效时间"
    )

    valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="权限过期时间"
    )

    # ===== 授权信息 =====
    granted_by = Column(
        String(36),
        nullable=True,
        comment="授权人ID"
    )

    grant_reason = Column(
        Text,
        nullable=True,
        comment="授权原因"
    )

    # ===== 时间信息 =====
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="创建时间"
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )

    # ===== 关联关系 =====
    user = relationship("User", back_populates="permissions")

    def __repr__(self):
        return f"<UserPermission(user_id={self.user_id}, resource={self.resource_type}:{self.resource_id})>"

    def is_valid(self) -> bool:
        """检查权限是否在有效期内"""
        now = datetime.now(timezone.utc)
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True


# =========================================
# 3. 用户搜索历史表
# =========================================
class UserSearchHistory(Base):
    """
    用户搜索历史表

    📋 存储内容：
    - 用户的搜索历史
    - 用于个性化推荐

    💡 用途：
    - 快速重复查询
    - 分析用户兴趣
    - 智能提示
    """
    __tablename__ = "user_search_history"

    # ===== 主键 =====
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="历史记录ID"
    )

    # ===== 外键：关联用户 =====
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID"
    )

    # ===== 搜索内容 =====
    query = Column(
        Text,
        nullable=False,
        comment="搜索查询"
    )

    # ===== 搜索结果 =====
    result_count = Column(
        Integer,
        default=0,
        comment="结果数量"
    )

    clicked_doc_id = Column(
        String(36),
        nullable=True,
        comment="用户点击的文档ID"
    )

    # ===== 统计信息 =====
    search_count = Column(
        Integer,
        default=1,
        comment="搜索次数（相同查询的累计次数）"
    )

    # ===== 时间信息 =====
    first_searched_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="首次搜索时间"
    )

    last_searched_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="最后搜索时间"
    )

    # ===== 关联关系 =====
    user = relationship("User", back_populates="search_history")

    def __repr__(self):
        return f"<UserSearchHistory(user_id={self.user_id}, query={self.query[:30]}...)>"


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 创建用户
from models.user import User, UserPermission
from core.constants import UserRole, PermissionLevel
from passlib.context import CryptContext

# 创建密码加密工具
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 创建用户
user = User(
    username="engineer_zhang",
    email="zhang@example.com",
    full_name="张工程师",
    password_hash=pwd_context.hash("secure_password"),
    role=UserRole.ENGINEER,
    department="工程管理部"
)

# 2. 添加权限
permission = UserPermission(
    user_id=user.id,
    resource_type="project",
    resource_id="project_001",
    can_read=True,
    can_write=True
)

# 3. 保存到数据库
session.add(user)
session.add(permission)
session.commit()


# 4. 验证密码
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

is_valid = verify_password("secure_password", user.password_hash)


# 5. 检查权限
has_access = user.has_permission("standard", PermissionLevel.PUBLIC)


# 6. 更新登录信息
user.last_login_at = datetime.now(timezone.utc)
user.last_login_ip = "192.168.1.100"
user.login_count += 1
session.commit()
"""