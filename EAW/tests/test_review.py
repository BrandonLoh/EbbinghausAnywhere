"""复习视图与复习反馈测试。"""

import json
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from EAW.models import Item, Proficiency

from .factories import create_item, create_user_with_defaults


class ReviewViewTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.client.login(username='alice', password='pass-12345678')
        self.today = date(2026, 1, 10)

    def _url(self, d=None):
        d = d or self.today
        return reverse('review-view', args=[d.year, d.month, d.day])

    def test_item_due_today_by_interval(self):
        # initDate = today - 1 天,恰好命中 day=1 的复习间隔
        create_item(self.user, item='due-word', init_date=self.today - timedelta(days=1))
        response = self.client.get(self._url())
        self.assertContains(response, 'due-word')
        self.assertContains(response, 'Day 1')

    def test_item_not_due(self):
        create_item(self.user, item='future-word', init_date=self.today - timedelta(days=3))
        response = self.client.get(self._url())
        self.assertNotContains(response, 'future-word')

    def test_other_users_items_not_shown(self):
        other = create_user_with_defaults('bob')
        create_item(other, item='bobs-word', init_date=self.today - timedelta(days=1))
        response = self.client.get(self._url())
        self.assertNotContains(response, 'bobs-word')

    def test_ajax_returns_fragment_with_markdown_hook(self):
        create_item(self.user, item='due-word', init_date=self.today - timedelta(days=1),
                    content='# 标题\n\n**加粗**')
        response = self.client.get(
            self._url(), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-markdown')
        self.assertContains(response, 'due-word')

    def test_direct_get_renders_full_page(self):
        """非 AJAX 直连 /review/<日期>/ 时渲染继承 base 的完整页面。"""
        create_item(self.user, item='due-word', init_date=self.today - timedelta(days=1))
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        # base 模板包含 markdown 渲染脚本
        self.assertContains(response, 'markdown_render.js')


class ReviewFeedbackTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.client.login(username='alice', password='pass-12345678')
        self.item = create_item(self.user, item='word', proficiency=Proficiency.UNFAMILIAR)

    def _post(self, url_name, item_id=None):
        return self.client.post(
            reverse(url_name),
            data=json.dumps({'id': item_id if item_id is not None else self.item.pk}),
            content_type='application/json',
        )

    def test_feedback_yes_sets_mastered(self):
        response = self._post('review-feedback-yes')
        self.assertTrue(response.json()['success'])
        self.item.refresh_from_db()
        self.assertEqual(self.item.proficiency, Proficiency.MASTERED)

    def test_feedback_no_sets_unfamiliar(self):
        self.item.proficiency = Proficiency.MASTERED
        self.item.save()
        response = self._post('review-feedback-no')
        self.assertTrue(response.json()['success'])
        self.item.refresh_from_db()
        self.assertEqual(self.item.proficiency, Proficiency.UNFAMILIAR)

    def test_feedback_reset_restarts_cycle(self):
        old_init = date(2025, 1, 1)
        self.item.initDate = old_init
        self.item.proficiency = Proficiency.MASTERED
        self.item.save()

        response = self._post('review-feedback-reset')
        self.assertTrue(response.json()['success'])
        self.item.refresh_from_db()
        self.assertEqual(self.item.initDate, date.today())
        self.assertEqual(self.item.proficiency, Proficiency.UNFAMILIAR)
        self.assertEqual(self.item.inputDate, old_init)  # inputDate 不应被重置

    def test_feedback_cannot_touch_others_items(self):
        other = create_user_with_defaults('bob')
        bobs_item = create_item(other, item='bobs-word')
        response = self._post('review-feedback-yes', item_id=bobs_item.pk)
        self.assertFalse(response.json()['success'])
        bobs_item.refresh_from_db()
        self.assertEqual(bobs_item.proficiency, Proficiency.UNFAMILIAR)

    def test_feedback_get_method_rejected(self):
        """回归测试:GET 请求过去会隐式返回 None 导致 500。"""
        response = self.client.get(reverse('review-feedback-yes'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['success'])

    def test_feedback_invalid_json(self):
        response = self.client.post(
            reverse('review-feedback-yes'),
            data='not-json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['success'])
