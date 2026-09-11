"""用户概览与类别端点测试。"""

from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from EAW.models import Category, Item, ReviewDay

from .helpers import auth_client, create_item, create_user_with_defaults


class MeTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.client = auth_client(self.user)

    def test_me_returns_user_and_stats(self):
        create_item(self.user, item='apple',
                    input_date=date.today() - timedelta(days=9),
                    init_date=date.today() - timedelta(days=1))
        response = self.client.get('/api/v1/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['username'], 'alice')
        self.assertEqual(response.data['stats']['total_items'], 1)
        self.assertEqual(response.data['stats']['days_since_first_item'], 9)
        # ReviewDay 默认含 day=1,initDate=昨天 → 今天到期
        self.assertEqual(response.data['stats']['today_due'], 1)

    def test_me_empty_stats(self):
        response = self.client.get('/api/v1/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['total_items'], 0)
        self.assertEqual(response.data['stats']['days_since_first_item'], 0)
        self.assertEqual(response.data['stats']['today_due'], 0)

    def test_me_requires_auth(self):
        response = APIClient().get('/api/v1/me/')
        self.assertIn(response.status_code, (401, 403))


class CategoryListTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.other = create_user_with_defaults('bob')
        self.client = auth_client(self.user)

    def test_only_own_categories_with_counts(self):
        create_item(self.user, item='apple')
        create_item(self.user, item='banana')
        Category.objects.create(user=self.other, name='bobs-category')

        response = self.client.get('/api/v1/categories/')
        self.assertEqual(response.status_code, 200)
        names = [c['name'] for c in response.data]
        self.assertIn('单词', names)
        self.assertNotIn('bobs-category', names)

        word = next(c for c in response.data if c['name'] == '单词')
        self.assertEqual(word['item_count'], 2)

    def test_categories_ordering_by_sort_order(self):
        Category.objects.create(user=self.user, name='语法', sort_order=2)
        Category.objects.create(user=self.user, name='短语', sort_order=9)
        response = self.client.get('/api/v1/categories/')
        names = [c['name'] for c in response.data]
        # 单词 sort_order=1(默认),语法 2,短语 9
        self.assertEqual(names, ['单词', '语法', '短语'])
