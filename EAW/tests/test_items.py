"""条目列表/详情/搜索测试:重点是用户数据隔离与 XSS 修复后的转义。"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .factories import create_item, create_user_with_defaults


class ItemListViewTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.client.login(username='alice', password='pass-12345678')

    def test_only_own_items_listed(self):
        other = create_user_with_defaults('bob')
        create_item(self.user, item='my-word')
        create_item(other, item='bobs-word')

        response = self.client.get(reverse('item-list'))
        self.assertContains(response, 'my-word')
        self.assertNotContains(response, 'bobs-word')

    def test_empty_list_renders(self):
        response = self.client.get(reverse('item-list'))
        self.assertEqual(response.status_code, 200)


class ItemDetailViewTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        self.other = create_user_with_defaults('bob')
        self.item = create_item(self.user, item='apple', content='苹果')
        self.client.login(username='alice', password='pass-12345678')

    def test_owner_can_view_detail(self):
        response = self.client.get(reverse('item-detail', args=[self.item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'apple')

    def test_cannot_view_others_item(self):
        bobs_item = create_item(self.other, item='secret')
        response = self.client.get(reverse('item-detail', args=[bobs_item.pk]))
        self.assertEqual(response.status_code, 404)

    def test_content_is_escaped_not_safe(self):
        """回归测试:XSS 修复后,<script> 必须被 HTML 转义,不得原样输出。"""
        create_item(self.user, item='xss', content='<script>alert(1)</script>')
        item = self.user.item_set.get(item='xss')
        response = self.client.get(reverse('item-detail', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        # 原样标签不得出现(base 模板自身的 <script> 引号闭合不同,不会误伤)
        self.assertNotContains(response, '<script>alert(1)</script>')
        # 必须以转义后的文本出现
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_content_marked_for_client_markdown_rendering(self):
        """内容容器应带 data-markdown 属性供前端渲染。"""
        response = self.client.get(reverse('item-detail', args=[self.item.pk]))
        self.assertContains(response, 'data-markdown')


class SearchViewTests(TestCase):
    def setUp(self):
        self.user = create_user_with_defaults('alice')
        other = create_user_with_defaults('bob')
        create_item(self.user, item='apple', content='苹果')
        create_item(self.user, item='application', content='应用')
        create_item(other, item='apple-of-bob')
        self.client.login(username='alice', password='pass-12345678')

    def test_search_matches_own_items_only(self):
        response = self.client.get(reverse('search'), {'q': 'apple'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'apple')
        self.assertNotContains(response, 'apple-of-bob')

    def test_search_no_query(self):
        response = self.client.get(reverse('search'))
        self.assertEqual(response.status_code, 200)

    def test_search_no_result(self):
        response = self.client.get(reverse('search'), {'q': 'zzz-not-exist'})
        self.assertContains(response, 'No search result.')
