"""账号相关视图测试:注册、登录、个人资料。"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from EAW.models import Category, ReviewDay


class RegisterViewTests(TestCase):
    def test_register_creates_user_defaults_and_staff(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'correct-horse-battery',
            'password2': 'correct-horse-battery',
        })
        self.assertRedirects(response, reverse('login'))

        user = User.objects.get(username='newuser')
        # 注册即分配数据管理台(admin)权限
        self.assertTrue(user.is_staff)
        self.assertTrue(user.groups.filter(name='Public').exists())
        # 默认类别与默认复习计划
        self.assertTrue(
            Category.objects.filter(user=user, name='单词', is_default=True).exists()
        )
        self.assertEqual(
            set(ReviewDay.objects.filter(user=user).values_list('day', flat=True)),
            {1, 2, 4, 7, 15, 30, 90, 180, 365},
        )

    def test_register_duplicate_username_fails(self):
        User.objects.create_user('taken', 't@example.com', 'x-1234567890')
        response = self.client.post(reverse('register'), {
            'username': 'taken',
            'email': 'other@example.com',
            'password1': 'correct-horse-battery',
            'password2': 'correct-horse-battery',
        })
        self.assertEqual(response.status_code, 200)  # 停留在注册页
        self.assertFalse(User.objects.filter(email='other@example.com').exists())

    def test_register_password_mismatch_fails(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'correct-horse-battery',
            'password2': 'wrong-horse-battery',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'loginuser', 'l@example.com', 'pass-12345678'
        )

    def test_login_success_redirects_home(self):
        response = self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'pass-12345678',
        })
        self.assertRedirects(response, reverse('home'))

    def test_login_wrong_password_shows_error(self):
        response = self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'wrong-password',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '用户名或密码无效')

    def test_login_required_redirects_to_login(self):
        response = self.client.get(reverse('item-list'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('item-list')}")


class UserProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'profileuser', 'p@example.com', 'pass-12345678'
        )
        self.client.login(username='profileuser', password='pass-12345678')

    def test_profile_page_renders(self):
        response = self.client.get(reverse('user_profile'))
        self.assertEqual(response.status_code, 200)
        # 页面由三个表单区块构成
        self.assertContains(response, 'Change Email')
        self.assertContains(response, 'Update Profile')
        self.assertContains(response, 'Change Password')

    def test_update_first_last_name(self):
        response = self.client.post(reverse('user_profile'), {
            'update_profile': '1',
            'first_name': 'Ellie',
            'last_name': 'Loh',
        })
        self.assertRedirects(response, reverse('user_profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Ellie')
        self.assertEqual(self.user.last_name, 'Loh')
