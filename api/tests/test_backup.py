"""快照端点测试:权限边界(重点:is_staff 不等于 superuser)与内容完整性。"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from api.models import WeChatProfile

from .helpers import auth_client, create_item, create_user_with_defaults

SNAPSHOT_URL = '/api/v1/backup/snapshot/'


class SnapshotPermissionTests(TestCase):
    def setUp(self):
        # 普通注册用户:is_staff=True(与 register 视图行为一致)但非 superuser
        self.staff_user = create_user_with_defaults('alice')
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'root-pass-123',
        )

    def test_anonymous_denied(self):
        response = APIClient().get(SNAPSHOT_URL)
        self.assertIn(response.status_code, (401, 403))

    def test_staff_non_superuser_denied(self):
        """关键回归:注册用户都是 is_staff,绝不能拿到全站快照。"""
        self.assertTrue(self.staff_user.is_staff)
        self.assertFalse(self.staff_user.is_superuser)
        response = auth_client(self.staff_user).get(SNAPSHOT_URL)
        self.assertEqual(response.status_code, 403)

    def test_superuser_allowed(self):
        response = auth_client(self.superuser).get(SNAPSHOT_URL)
        self.assertEqual(response.status_code, 200)


class SnapshotContentTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'root-pass-123',
        )
        self.user = create_user_with_defaults('alice')
        self.client = auth_client(self.superuser)

    def test_snapshot_structure(self):
        create_item(self.user, item='apple', content='苹果',
                    input_date=date(2026, 2, 1), init_date=date(2026, 2, 1))
        WeChatProfile.objects.create(user=self.user, openid='openid-aaa')

        response = self.client.get(SNAPSHOT_URL)
        data = response.data

        self.assertEqual(data['meta']['format'], 1)
        self.assertIn('created_at', data['meta'])
        self.assertIn('source', data['meta'])  # 服务方主机名,便于确认数据来源
        for key in ('users', 'categories', 'review_days', 'items', 'wechat_profiles'):
            self.assertIn(key, data)

        # 用户:含密码哈希(isinstance str 且非明文),不含 token 字段
        user_row = next(u for u in data['users'] if u['id'] == self.user.pk)
        self.assertTrue(user_row['password'].startswith('pbkdf2_'))
        self.assertNotIn('token', user_row)
        self.assertNotIn('authtoken', data)

        # 条目:保留主键与外键,日期为 ISO 字符串
        item_row = next(i for i in data['items'] if i['item'] == 'apple')
        self.assertEqual(item_row['user_id'], self.user.pk)
        self.assertEqual(item_row['content'], '苹果')
        self.assertEqual(item_row['inputDate'], '2026-02-01')
        self.assertEqual(item_row['category_id'],
                         self.user.category_set.get(is_default=True).pk)

        # 绑定关系随快照带走
        profile_row = data['wechat_profiles'][0]
        self.assertEqual(profile_row['openid'], 'openid-aaa')
        self.assertEqual(profile_row['user_id'], self.user.pk)

    def test_snapshot_includes_all_users(self):
        create_user_with_defaults('bob')
        response = self.client.get(SNAPSHOT_URL)
        usernames = {u['username'] for u in response.data['users']}
        self.assertIn('alice', usernames)
        self.assertIn('bob', usernames)
        self.assertIn('root', usernames)
