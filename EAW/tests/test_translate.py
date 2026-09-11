"""翻译相关接口测试:全部 mock 百度 API,不发起真实网络请求。"""

import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from EAW.translate import (
    baidu_translate,
    check_api_keys,
    is_valid_tts_url,
    parse_json_to_string,
    standardize_input,
)

from .factories import create_user_with_defaults


class StandardizeInputTests(TestCase):
    def test_strips_and_collapses_whitespace(self):
        self.assertEqual(standardize_input('  hello   world  '), 'hello world')


class IsValidTtsUrlTests(TestCase):
    def test_accepts_https_baidu(self):
        self.assertTrue(is_valid_tts_url('https://tsn.baidu.com/voice.mp3'))

    def test_rejects_http(self):
        self.assertFalse(is_valid_tts_url('http://tsn.baidu.com/voice.mp3'))

    def test_rejects_foreign_domain(self):
        self.assertFalse(is_valid_tts_url('https://evil.example.com/voice.mp3'))


class ParseJsonToStringTests(TestCase):
    def _dict_json(self):
        means = {
            'word_result': {
                'simple_means': {
                    'symbols': [{
                        'ph_en': 'ˈæpl',
                        'ph_am': 'ˈæpəl',
                        'parts': [{'part': 'n.', 'means': ['苹果', '苹果树']}],
                    }],
                    'word_means': ['苹果'],
                }
            }
        }
        return json.dumps(means)

    def test_extract_phonetics_and_parts(self):
        result = parse_json_to_string(self._dict_json())
        self.assertEqual(result['phonetic'], ['ˈæpl', 'ˈæpəl'])
        self.assertEqual(len(result['parts_and_means']), 1)
        self.assertIn('n.', result['parts_and_means'][0])
        self.assertIn('苹果', result['parts_and_means'][0])

    def test_invalid_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_json_to_string('not-json')

    def test_missing_simple_means_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_json_to_string('{"word_result": {}}')

    def test_falls_back_to_simple_meaning(self):
        means = {
            'word_result': {'simple_means': {
                'symbols': [{'parts': []}],
                'word_means': ['苹果'],
            }}
        }
        result = parse_json_to_string(json.dumps(means))
        self.assertEqual(result['parts_and_means'], [])
        self.assertEqual(result['simple_meaning'], ['简明释义: 苹果'])


class BaiduTranslateTests(TestCase):
    def test_returns_empty_dict_when_keys_missing(self):
        """回归测试:密钥未配置时必须返回 {}(此前返回 JsonResponse 导致调用方崩溃)。"""
        with patch('EAW.translate.BAIDU_API_KEY', None), \
             patch('EAW.translate.BAIDU_SECRET_KEY', None):
            self.assertEqual(baidu_translate('apple'), {})


class CheckApiKeysViewTests(TestCase):
    def test_keys_configured(self):
        with patch('EAW.views.translate_api.check_api_keys', return_value=True):
            response = self.client.get(reverse('check-api-keys'))
        self.assertTrue(response.json()['success'])

    def test_keys_not_configured(self):
        with patch('EAW.views.translate_api.check_api_keys', return_value=False):
            response = self.client.get(reverse('check-api-keys'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])


class TranslateApiViewTests(TestCase):
    def setUp(self):
        create_user_with_defaults('alice')
        self.client.login(username='alice', password='pass-12345678')

    def _post(self, payload):
        return self.client.post(
            reverse('translate'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_translate_success(self):
        fake = {
            'phonetic': ['ˈæpl', 'ˈæpəl'],
            'parts_and_means': ['词性: n.\n释义: 苹果'],
            'simple_meaning': [],
            'src_tts': None,
        }
        with patch('EAW.views.translate_api.baidu_translate', return_value=fake):
            response = self._post({'query': 'apple'})
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['result'], fake)

    def test_translate_no_query(self):
        response = self._post({'query': ''})
        self.assertFalse(response.json()['success'])
        self.assertEqual(response.json()['message'], 'No query provided')

    def test_translate_invalid_json(self):
        response = self.client.post(
            reverse('translate'), data='not-json', content_type='application/json'
        )
        self.assertFalse(response.json()['success'])
        self.assertEqual(response.json()['message'], 'Invalid JSON')

    def test_translate_get_rejected(self):
        response = self.client.get(reverse('translate'))
        self.assertFalse(response.json()['success'])
        self.assertEqual(response.json()['message'], 'Invalid request method')

    def test_translate_failure_message(self):
        with patch('EAW.views.translate_api.baidu_translate', return_value={}):
            response = self._post({'query': 'zzz'})
        self.assertFalse(response.json()['success'])
        self.assertEqual(response.json()['message'], 'Translation failed')
