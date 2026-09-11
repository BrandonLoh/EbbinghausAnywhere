"""API 权限类。

注意:本应用在注册时会给所有用户 is_staff=True(以便使用 Django admin
作为个人数据管理台),因此**不能**使用 DRF 自带的 IsAdminUser——
它只检查 is_staff,会让任何注册用户拿到全站数据。需要管理权限时
一律使用下面的 IsSuperUser。
"""

from rest_framework.permissions import BasePermission


class IsSuperUser(BasePermission):
    """仅超级用户可访问(用于快照导出等运维端点)。"""

    message = '仅超级用户可访问。'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )
