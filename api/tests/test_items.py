"""条目端点测试:列表分页/搜索/筛选、详情隔离、新建拆分规则。"""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from EAW.models import Category, Item

from .helpers import auth_client, create_item, create_user_with_defaults

ITEMS_URL = '/api/v1/items/'


class ItemListTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.other = create_user_with_defaults('bob')
        self.client = auth_client(self.user)

    def test_list_only_own_items_with_pagination_meta(self):
        create_item(self.user, item='apple')
        create_item(self.other, item='bobs-word')

        response = self.client.get(ITEMS_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['num_pages'], 1)
        items = [r['item'] for r in response.data['results']]
        self.assertEqual(items, ['apple'])

    def test_search_filters_by_name(self):
        create_item(self.user, item='apple')
        create_item(self.user, item='banana')

        response = self.client.get(ITEMS_URL, {'q': 'app'})
        self.assertEqual([r['item'] for r in response.data['results']], ['apple'])

    def test_filter_by_category(self):
        grammar = Category.objects.create(user=self.user, name='语法')
        create_item(self.user, item='apple')  # 默认类别"单词"
        create_item(self.user, item='过去时', category=grammar)

        response = self.client.get(ITEMS_URL, {'category': grammar.pk})
        self.assertEqual([r['item'] for r in response.data['results']], ['过去时'])

    def test_pagination(self):
        for i in range(55):
            create_item(self.user, item=f'word-{i:03d}')
        response = self.client.get(ITEMS_URL)
        self.assertEqual(response.data['count'], 55)
        self.assertEqual(response.data['num_pages'], 2)
        self.assertEqual(len(response.data['results']), 50)

    def test_requires_auth(self):
        response = APIClient().get(ITEMS_URL)
        self.assertIn(response.status_code, (401, 403))


class ItemDetailTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.other = create_user_with_defaults('bob')
        self.client = auth_client(self.user)

    def test_detail_returns_full_fields(self):
        item = create_item(self.user, item='apple', content='苹果\nn. 苹果',
                           init_date=date(2025, 6, 1))
        response = self.client.get(f'{ITEMS_URL}{item.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['item'], 'apple')
        self.assertEqual(response.data['content'], '苹果\nn. 苹果')
        self.assertEqual(response.data['category_name'], '单词')
        for field in ('src_tts', 'us_phonetic', 'uk_phonetic', 'inputDate',
                      'initDate', 'proficiency', 'proficiency_label'):
            self.assertIn(field, response.data)

    def test_others_item_returns_404(self):
        bobs = create_item(self.other, item='secret')
        response = self.client.get(f'{ITEMS_URL}{bobs.pk}/')
        self.assertEqual(response.status_code, 404)


class ItemCreateTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.client = auth_client(self.user)
        self.word = Category.objects.get(user=self.user, name='单词')

    def _post(self, **payload):
        body = {
            'item_text': 'apple:苹果',
            'input_date': '2026-01-01',
            'category_id': self.word.pk,
        }
        body.update(payload)
        return self.client.post(ITEMS_URL, body, format='json')

    def test_create_with_colon_split(self):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        created = response.data['created'][0]
        self.assertEqual(created['item'], 'apple')
        self.assertEqual(created['content'], '苹果')
        self.assertEqual(created['inputDate'], '2026-01-01')
        self.assertEqual(created['initDate'], '2026-01-01')
        # 主键已回填,可再次按 id 取回
        self.assertIsNotNone(created['id'])
        self.assertTrue(Item.objects.filter(pk=created['id'], user=self.user).exists())

    def test_create_with_chinese_colon(self):
        response = self._post(item_text='苹果：水果')
        self.assertEqual(response.data['created'][0]['item'], '苹果')
        self.assertEqual(response.data['created'][0]['content'], '水果')

    def test_create_without_colon_uses_whole_line(self):
        response = self._post(item_text='plain-word')
        self.assertEqual(response.data['created'][0]['item'], 'plain-word')
        self.assertEqual(response.data['created'][0]['content'], '')

    def test_create_multiline_bulk(self):
        response = self._post(item_text='apple:苹果\r\nbanana:香蕉\ncherry')
        self.assertEqual(response.status_code, 201)
        names = [c['item'] for c in response.data['created']]
        self.assertEqual(names, ['apple', 'banana', 'cherry'])

    def test_empty_text_rejected(self):
        response = self._post(item_text=' \r\n ')
        self.assertEqual(response.status_code, 400)

    def test_other_users_category_rejected(self):
        """不能把条目建到别人的类别里。"""
        other = create_user_with_defaults('bob')
        bobs_category = Category.objects.get(user=other, name='单词')
        response = self._post(category_id=bobs_category.pk)
        self.assertEqual(response.status_code, 400)

    def test_invalid_date_rejected(self):
        response = self._post(input_date='not-a-date')
        self.assertEqual(response.status_code, 400)

    def test_requires_auth(self):
        response = APIClient().post(ITEMS_URL, {'item_text': 'x',
                                                'input_date': '2026-01-01',
                                                'category_id': self.word.pk}, format='json')
        self.assertIn(response.status_code, (401, 403))
