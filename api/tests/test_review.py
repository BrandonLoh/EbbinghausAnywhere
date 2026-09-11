"""复习端点测试:分组、排序、日期解析、反馈。"""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from EAW.models import Category, Proficiency

from .helpers import auth_client, create_item, create_user_with_defaults

REVIEW_URL = '/api/v1/review/'
FEEDBACK_URL = '/api/v1/review/feedback/'


class ReviewListTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.other = create_user_with_defaults('bob')
        self.client = auth_client(self.user)

    def _due_item(self, name, days_ago, **kwargs):
        """initDate = 今天 - days_ago,命中 ReviewDay 中 day=days_ago 的间隔。"""
        return create_item(
            self.user, item=name,
            init_date=timezone.localdate() - timedelta(days=days_ago),
            **kwargs,
        )

    def test_due_item_grouped_by_category_with_review_day(self):
        self._due_item('apple', days_ago=1)
        response = self.client.get(REVIEW_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['review_date'], timezone.localdate().isoformat())

        category = response.data['categories'][0]
        self.assertEqual(category['name'], '单词')
        item = category['items'][0]
        self.assertEqual(item['item'], 'apple')
        self.assertEqual(item['review_day'], 1)
        self.assertIn('content', item)
        self.assertIn('proficiency_label', item)

    def test_not_due_item_absent(self):
        self._due_item('future-word', days_ago=3)  # 默认曲线没有 day=3
        response = self.client.get(REVIEW_URL)
        self.assertEqual(response.data['categories'], [])

    def test_other_users_items_absent(self):
        create_item(self.other, item='bobs-word',
                    init_date=timezone.localdate() - timedelta(days=1))
        response = self.client.get(REVIEW_URL)
        self.assertEqual(response.data['categories'], [])

    def test_items_sorted_by_review_day_asc(self):
        """回归测试:组内按间隔天数升序(与 Web 端 review.py 的排序一致)。"""
        self._due_item('day15-word', days_ago=15)
        self._due_item('day1-word', days_ago=1)
        self._due_item('day7-word', days_ago=7)

        response = self.client.get(REVIEW_URL)
        items = response.data['categories'][0]['items']
        self.assertEqual([i['review_day'] for i in items], [1, 7, 15])
        self.assertEqual([i['item'] for i in items], ['day1-word', 'day7-word', 'day15-word'])

    def test_categories_ordered_by_sort_order(self):
        Category.objects.create(user=self.user, name='语法', sort_order=2)
        grammar = Category.objects.get(user=self.user, name='语法')
        self._due_item('word', days_ago=1)
        create_item(self.user, item='过去时', category=grammar,
                    init_date=timezone.localdate() - timedelta(days=1))

        response = self.client.get(REVIEW_URL)
        names = [c['name'] for c in response.data['categories']]
        self.assertEqual(names, ['单词', '语法'])

    def test_explicit_date_parameter(self):
        target = date(2026, 3, 10)
        create_item(self.user, item='apple', init_date=target - timedelta(days=1))
        response = self.client.get(REVIEW_URL, {'date': '2026-03-10'})
        self.assertEqual(response.data['review_date'], '2026-03-10')
        self.assertEqual(response.data['categories'][0]['items'][0]['item'], 'apple')

    def test_invalid_date_rejected(self):
        response = self.client.get(REVIEW_URL, {'date': '2026/03/10'})
        self.assertEqual(response.status_code, 400)

    def test_requires_auth(self):
        response = APIClient().get(REVIEW_URL)
        self.assertIn(response.status_code, (401, 403))


class ReviewFeedbackTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.other = create_user_with_defaults('bob')
        self.client = auth_client(self.user)
        self.item = create_item(self.user, item='apple',
                                proficiency=Proficiency.UNFAMILIAR)

    def _post(self, item_id, action):
        return self.client.post(FEEDBACK_URL,
                                {'id': item_id, 'action': action}, format='json')

    def test_yes_sets_mastered(self):
        response = self._post(self.item.pk, 'yes')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.item.refresh_from_db()
        self.assertEqual(self.item.proficiency, Proficiency.MASTERED)

    def test_no_sets_unfamiliar(self):
        self.item.proficiency = Proficiency.MASTERED
        self.item.save()
        response = self._post(self.item.pk, 'no')
        self.assertTrue(response.data['success'])
        self.item.refresh_from_db()
        self.assertEqual(self.item.proficiency, Proficiency.UNFAMILIAR)

    def test_reset_restarts_cycle(self):
        self.item.initDate = date(2025, 1, 1)
        self.item.save()
        response = self._post(self.item.pk, 'reset')
        self.assertTrue(response.data['success'])
        self.item.refresh_from_db()
        self.assertEqual(self.item.initDate, timezone.localdate())
        self.assertEqual(self.item.proficiency, Proficiency.UNFAMILIAR)

    def test_other_users_item_not_found(self):
        bobs = create_item(self.other, item='bobs-word')
        response = self._post(bobs.pk, 'yes')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['success'])

    def test_invalid_action_rejected(self):
        response = self._post(self.item.pk, 'maybe')
        self.assertEqual(response.status_code, 400)

    def test_requires_auth(self):
        response = APIClient().post(FEEDBACK_URL,
                                    {'id': self.item.pk, 'action': 'yes'}, format='json')
        self.assertIn(response.status_code, (401, 403))
