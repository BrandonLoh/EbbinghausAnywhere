"""认证端点测试:账号密码登录、微信静默登录、首次绑定。"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import WeChatProfile

from .helpers import create_user_with_defaults

LOGIN_URL = '/api/v1/auth/login/'
WECHAT_URL = '/api/v1/auth/wechat/'
BIND_URL = '/api/v1/auth/wechat/bind/'


class LoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user_with_defaults('alice')

    def test_login_success_returns_token_and_user(self):
        response = self.client.post(LOGIN_URL, {
            'username': 'alice',
            'password': 'pass-12345678',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'alice')

    def test_login_wrong_password(self):
        response = self.client.post(LOGIN_URL, {
            'username': 'alice',
            'password': 'wrong',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_login_missing_fields(self):
        response = self.client.post(LOGIN_URL, {'username': 'alice'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_login_returns_stable_token(self):
        """同一用户重复登录应拿到同一个 token(便于小程序多端共用)。"""
        first = self.client.post(LOGIN_URL, {
            'username': 'alice', 'password': 'pass-12345678',
        }, format='json')
        second = self.client.post(LOGIN_URL, {
            'username': 'alice', 'password': 'pass-12345678',
        }, format='json')
        self.assertEqual(first.data['token'], second.data['token'])


class WeChatLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user_with_defaults('alice')

    @patch('api.views.auth._code2session', return_value='openid-aaa')
    def test_unbound_openid_requires_binding(self, mock_code):
        response = self.client.post(WECHAT_URL, {'code': 'js-code'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'bind_required': True})

    @patch('api.views.auth._code2session', return_value='openid-aaa')
    def test_bound_openid_returns_token(self, mock_code):
        WeChatProfile.objects.create(user=self.user, openid='openid-aaa')
        response = self.client.post(WECHAT_URL, {'code': 'js-code'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'alice')

    def test_missing_code_rejected(self):
        response = self.client.post(WECHAT_URL, {}, format='json')
        self.assertEqual(response.status_code, 400)

    @patch('api.views.auth._code2session', return_value=None)
    def test_code2session_failure(self, mock_code):
        response = self.client.post(WECHAT_URL, {'code': 'bad'}, format='json')
        self.assertEqual(response.status_code, 502)


class WeChatBindTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user_with_defaults('alice')

    @patch('api.views.auth._code2session', return_value='openid-new')
    def test_bind_creates_profile_and_returns_token(self, mock_code):
        response = self.client.post(BIND_URL, {
            'code': 'js-code',
            'username': 'alice',
            'password': 'pass-12345678',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        profile = WeChatProfile.objects.get(openid='openid-new')
        self.assertEqual(profile.user, self.user)

    @patch('api.views.auth._code2session', return_value='openid-new')
    def test_bind_wrong_password_rejected(self, mock_code):
        response = self.client.post(BIND_URL, {
            'code': 'js-code',
            'username': 'alice',
            'password': 'wrong',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(WeChatProfile.objects.exists())

    @patch('api.views.auth._code2session', return_value='openid-new')
    def test_rebind_same_openid_moves_to_new_user(self, mock_code):
        """同一微信号换绑账号:绑定关系跟随 openid 更新。"""
        other = create_user_with_defaults('bob')
        WeChatProfile.objects.create(user=self.user, openid='openid-new')

        response = self.client.post(BIND_URL, {
            'code': 'js-code',
            'username': 'bob',
            'password': 'pass-12345678',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WeChatProfile.objects.get(openid='openid-new').user, other)
        self.assertEqual(WeChatProfile.objects.count(), 1)


class TokenAuthenticationTests(TestCase):
    def test_protected_endpoint_requires_token(self):
        response = APIClient().get('/api/v1/me/')
        self.assertIn(response.status_code, (401, 403))
