"""后台条目编辑与复习排期字段语义的回归测试。

背景:有反馈怀疑"在后台(admin)修改日期保存后会新建一条记录"。
这里锁定两个事实,防止以后被改坏:

1. admin 条目编辑页的三种保存按钮都在**原记录上更新**——记录数不变、主键不变;
2. 复习排期只由 `initDate`(周期起算)决定,`inputDate`(录入日期)不参与排期。

另锁定后台外观约束(见 AdminChromeTests):
3. 后台保持纯 admin 样式——不再注入前台 Bootstrap(其 border-box/字号全局规则
   曾把"保存 35px / 删除塌缩到 20px"的对齐规格打乱);
4. 每个后台页面右上角保留"View site"返回主页链接。
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from EAW.models import Category, Item

from .factories import create_item, create_user_with_defaults


class AdminItemSaveTests(TestCase):
    """admin 条目编辑页:保存必须原地更新,不得新增记录。"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            'admin_user', 'admin@example.com', 'pass-12345678'
        )
        self.category = Category.objects.create(user=self.user, name='单词')
        self.item = create_item(
            self.user,
            item='probe-word',
            category=self.category,
            input_date=date(2026, 1, 1),
            init_date=date(2026, 1, 1),
        )
        self.pk = self.item.pk
        self.client.force_login(self.user)
        self.url = f'/admin/EAW/item/{self.pk}/change/'
        self.post_data = {
            'item': 'probe-word',
            'content': '',
            'inputDate': '2026-01-01',
            'proficiency': 0,
            'category': self.category.id,
            'src_tts': '',
            'us_phonetic': '',
            'uk_phonetic': '',
        }

    def _post(self, **overrides):
        return self.client.post(self.url, {**self.post_data, **overrides})

    def _assert_in_place_update(self, expected_init_date):
        rows = Item.objects.filter(user=self.user)
        self.assertEqual(rows.count(), 1, '保存后不得新增记录')
        self.assertTrue(rows.filter(pk=self.pk).exists(), '原记录(主键)必须保留')
        self.item.refresh_from_db()
        self.assertEqual(self.item.initDate, expected_init_date)

    def test_save_updates_in_place(self):
        response = self._post(initDate='2026-03-03', _save='Save')
        self.assertEqual(response.status_code, 302)
        self._assert_in_place_update(date(2026, 3, 3))

    def test_save_and_continue_updates_in_place(self):
        response = self._post(initDate='2026-04-04', _continue='Save and continue')
        self.assertEqual(response.status_code, 302)
        self._assert_in_place_update(date(2026, 4, 4))

    def test_save_and_add_another_updates_in_place(self):
        response = self._post(initDate='2026-05-05', _addanother='Save and add another')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/add/', response['Location'])
        self._assert_in_place_update(date(2026, 5, 5))


class AdminChromeTests(TestCase):
    """后台外观:纯 admin 样式 + 返回主页链接 + 获取释义按钮用原生规格。"""

    def setUp(self):
        self.user = User.objects.create_superuser(
            'chrome_user', 'chrome@example.com', 'pass-12345678'
        )
        self.category = Category.objects.create(user=self.user, name='单词')
        self.item = create_item(
            self.user, item='chrome-word', category=self.category,
            input_date=date(2026, 1, 1), init_date=date(2026, 1, 1),
        )
        self.client.force_login(self.user)
        self.url = f'/admin/EAW/item/{self.item.pk}/change/'

    def _html(self):
        return self.client.get(self.url).content.decode()

    def test_no_frontend_bootstrap_in_admin(self):
        """后台页面不得再加载前台 Bootstrap / 自定义样式。"""
        html = self._html()
        self.assertNotIn('bootstrap.min.css', html)
        self.assertNotIn('css/styles.css', html)

    def test_view_site_link_present(self):
        """右上角保留返回主页的"View site"链接。"""
        self.assertIn('View site', self._html())

    def test_site_header_branding(self):
        """顶栏品牌为项目名,不再是 Django administration。"""
        self.assertIn('万物皆可艾宾浩斯 · 管理后台', self._html())

    @patch('EAW.admin.check_api_keys', return_value=True)
    def test_translate_button_native_sizing(self, _mock_keys):
        """获取释义按钮不带内联尺寸,与保存/删除同规格。"""
        html = self._html()
        self.assertIn(
            '<button type="button" id="translate-btn" class="button">获取释义</button>',
            html,
        )
        self.assertNotIn('height: auto', html)
        self.assertNotIn('padding: 5px 15px', html)
        self.assertNotIn('justify-content: flex-start', html)


class ReviewScheduleFieldTests(TestCase):
    """复习排期只跟随 initDate(周期起算);改 inputDate(录入日期)不影响安排。"""

    def setUp(self):
        self.user = create_user_with_defaults('sched')
        self.client.login(username='sched', password='pass-12345678')
        self.today = timezone.localdate()
        self.url = reverse(
            'review-view',
            args=[self.today.year, self.today.month, self.today.day],
        )

    def test_schedule_follows_init_date_only(self):
        # 起算=昨天 → 今天命中 Day 1
        item = create_item(
            self.user,
            item='sched-word',
            init_date=self.today - timedelta(days=1),
            input_date=self.today,
        )
        self.assertContains(self.client.get(self.url), 'sched-word')

        # 修改「录入日期」→ 复习安排不变
        item.inputDate = self.today - timedelta(days=30)
        item.save()
        self.assertContains(self.client.get(self.url), 'sched-word')

        # 修改「起算日期」→ 条目才从今天的清单移出
        item.initDate = self.today
        item.save()
        self.assertNotContains(self.client.get(self.url), 'sched-word')
