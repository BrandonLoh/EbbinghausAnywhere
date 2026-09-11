"""API 测试共享辅助。"""

from rest_framework.authtoken.models import Token

from EAW.tests.factories import create_item, create_user_with_defaults  # noqa: F401  供各测试模块复用


def get_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token


def auth_client(user):
    """返回已带 Token 认证头的 APIClient。"""
    from rest_framework.test import APIClient

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {get_token(user).key}')
    return client
