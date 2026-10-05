"""通用依赖：当前用户解析与服务端权限检查（不信任前端传入的角色）。"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RoleName, User
from app.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少认证凭据")
    try:
        payload = decode_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "认证无效或已过期")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


def require_roles(*roles: RoleName) -> Callable:
    allowed = set(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"权限不足：需要 {'/'.join(r.value for r in allowed)}，当前为 {user.role.value}",
            )
        return user

    return checker


# 便捷别名
require_editor = require_roles(RoleName.admin, RoleName.editor)
require_admin = require_roles(RoleName.admin)
require_viewer = require_roles(RoleName.admin, RoleName.editor, RoleName.viewer)
