"""录入视图与 split_string 测试。"""

import re
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from EAW.models import Category, Item
from EAW.views.input import split_string

from .factories import create_user_with_defaults


class SplitStringTests(TestCase):
    def test_no_colon(self):
        self.assertEqual(split_string('apple'), ('apple', ''))

    def test_english_colon(self):
        self.assertEqual(split_string('apple:苹果'), ('apple', '苹果'))

    def test_chinese_colon(self):
        self.assertEqual(split_string('苹果：水果'), ('苹果', '水果'))

    def test_earlier_colon_wins(self):
        self.assertEqual(split_string('a:b：c'), ('a', 'b：c'))

    def test_colon_at_start(self):
        self.assertEqual(split_string(':content'), ('', 'content'))


class InputViewTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.client.login(username='alice', password='pass-12345678')
        # 表单中 category 为 ModelChoiceField,提交的是主键
        self.word_category = Category.objects.get(user=self.user, name='单词')

    def _post_input(self, text, category=None, **extra):
        payload = {
            'input_date': '2026-01-01',
            'category': (category or self.word_category).pk,
            'input': text,
        }
        payload.update(extra)
        return self.client.post(reverse('input-view'), payload)

    def test_multi_line_input_creates_items(self):
        response = self._post_input('apple:苹果\r\nbanana:香蕉')
        self.assertRedirects(response, reverse('item-list'))
        self.assertEqual(Item.objects.filter(user=self.user).count(), 2)
        apple = Item.objects.get(user=self.user, item='apple')
        self.assertEqual(apple.content, '苹果')
        self.assertEqual(apple.inputDate, date(2026, 1, 1))
        self.assertEqual(apple.initDate, date(2026, 1, 1))

    def test_line_without_colon_uses_whole_line(self):
        self._post_input('plain-word')
        item = Item.objects.get(user=self.user, item='plain-word')
        self.assertEqual(item.content, '')

    def test_input_without_translate_does_not_call_baidu(self):
        with patch('EAW.views.input.baidu_translate') as mock_translate:
            self._post_input('apple:苹果')
            mock_translate.assert_not_called()

    def test_translate_checkbox_fills_dictionary_fields(self):
        fake_result = {
            'phonetic': ['ˈæpl', 'ˈæpəl'],
            'parts_and_means': ['词性: n.\n释义: 苹果'],
            'simple_meaning': [],
            'src_tts': 'https://tsn.baidu.com/voice.mp3',
        }
        with patch('EAW.views.input.baidu_translate', return_value=fake_result):
            self._post_input('apple', translate='on')

        item = Item.objects.get(user=self.user, item='apple')
        self.assertEqual(item.us_phonetic, 'ˈæpəl')
        self.assertEqual(item.uk_phonetic, 'ˈæpl')
        self.assertEqual(item.src_tts, 'https://tsn.baidu.com/voice.mp3')
        self.assertIn('苹果', item.content)

    def test_translate_failure_still_creates_item(self):
        with patch('EAW.views.input.baidu_translate', return_value={}):
            response = self._post_input('apple', translate='on')
        self.assertRedirects(response, reverse('item-list'))
        item = Item.objects.get(user=self.user, item='apple')
        self.assertEqual(item.content, '')
        self.assertIsNone(item.src_tts)

    def test_translate_not_applied_to_non_word_category(self):
        """非"单词"类别即使勾选翻译也不调用百度 API。"""
        grammar = Category.objects.create(user=self.user, name='语法')
        with patch('EAW.views.input.baidu_translate') as mock_translate:
            self._post_input('过去时', category=grammar, translate='on')
            mock_translate.assert_not_called()
        item = Item.objects.get(user=self.user, item='过去时')
        self.assertEqual(item.content, '')


class InputDuplicateSubmitTests(TestCase):
    """录入页防重复提交:一次性令牌 + 空行过滤。"""

    def setUp(self):
        self.user = create_user_with_defaults('bob')
        self.client.login(username='bob', password='pass-12345678')
        self.word_category = Category.objects.get(user=self.user, name='单词')

    def _get_submit_token(self):
        response = self.client.get(reverse('input-view'))
        match = re.search(r'name="submit_token" value="([^"]+)"', response.content.decode())
        self.assertIsNotNone(match, '录入页应下发一次性提交令牌')
        return match.group(1)

    def _post_input(self, text, **extra):
        payload = {
            'input_date': '2026-01-01',
            'category': self.word_category.pk,
            'input': text,
        }
        payload.update(extra)
        return self.client.post(reverse('input-view'), payload)

    def _count_items(self):
        return Item.objects.filter(user=self.user).count()

    def test_replayed_submit_is_ignored(self):
        """同一令牌重复提交(双击/网络中断后重试)只录入一次。"""
        token = self._get_submit_token()
        self._post_input('apple\r\nbanana', submit_token=token)
        self.assertEqual(self._count_items(), 2)

        response = self._post_input('apple\r\nbanana', submit_token=token)
        self.assertRedirects(response, reverse('item-list'))
        self.assertEqual(self._count_items(), 2, '重复提交不得重复建条目')

    def test_replayed_submit_shows_message(self):
        token = self._get_submit_token()
        self._post_input('apple', submit_token=token)
        response = self.client.post(
            reverse('input-view'),
            {
                'input_date': '2026-01-01',
                'category': self.word_category.pk,
                'input': 'apple',
                'submit_token': token,
            },
            follow=True,
        )
        self.assertContains(response, '没有重复录入')

    def test_fresh_token_allows_resubmit(self):
        """重新打开录入页拿到新令牌后,可以再录一次(应用本身允许重复录入)。"""
        self._post_input('apple', submit_token=self._get_submit_token())
        self._post_input('apple', submit_token=self._get_submit_token())
        self.assertEqual(self._count_items(), 2)

    def test_submit_without_token_still_works(self):
        """没有令牌的提交照常处理(向后兼容,不阻塞正常录入)。"""
        self._post_input('apple')
        self.assertEqual(self._count_items(), 1)

    def test_invalid_form_does_not_consume_token(self):
        """校验失败不消耗令牌:修正后用同一令牌重提仍能录入。"""
        token = self._get_submit_token()
        bad = self.client.post(reverse('input-view'), {
            'input_date': 'not-a-date',
            'category': self.word_category.pk,
            'input': 'apple',
            'submit_token': token,
        })
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(self._count_items(), 0)

        self._post_input('apple', submit_token=token)
        self.assertEqual(self._count_items(), 1)

    def test_submit_creates_message_on_list(self):
        response = self.client.post(
            reverse('input-view'),
            {'input_date': '2026-01-01', 'category': self.word_category.pk, 'input': 'apple'},
            follow=True,
        )
        self.assertContains(response, '已录入 1 个条目')

    def test_blank_lines_are_skipped(self):
        """空行 / 只有冒号的行不产生空名条目。"""
        self._post_input('apple\r\n\r\n   \r\n: 只有内容\r\nbanana')
        self.assertEqual(self._count_items(), 2)
        self.assertFalse(Item.objects.filter(user=self.user, item='').exists())

    def test_blank_only_input_writes_nothing(self):
        """纯空白输入被表单必填校验拦下:原样重渲染,不写入任何条目。"""
        response = self._post_input('\r\n   \r\n')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count_items(), 0)

    def test_only_separator_lines_writes_nothing(self):
        """只有冒号(没有条目名)时:提示并跳转,不写入条目。"""
        response = self._post_input(':\r\n：')
        self.assertRedirects(response, reverse('item-list'))
        self.assertEqual(self._count_items(), 0)
