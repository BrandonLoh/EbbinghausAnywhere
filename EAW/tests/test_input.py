"""录入视图与 split_string 测试。"""

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
