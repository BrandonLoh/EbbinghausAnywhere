"""API 层数据模型。目前只有微信绑定关系,业务数据全部复用 EAW 的模型。"""

from django.contrib.auth.models import User
from django.db import models


class WeChatProfile(models.Model):
    """微信 openid 与 Web 账号的绑定关系(1:1)。

    用户首次在小程序输入 Web 端账号密码后建立绑定;
    之后 wx.login 的 code 静默换取 token,无需再次输入密码。
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wechat_profile')
    openid = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.openid[:8]}…)"
