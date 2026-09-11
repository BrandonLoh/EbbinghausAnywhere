"""模型层测试:唯一约束、默认类别保护、字符串表示。"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from EAW.models import Category, Item, Proficiency, ReviewDay

from .factories import create_item, create_user_with_defaults


class CategoryModelTests(TestCase):
    def test_unique_together_user_name(self):
        user = create_user_with_defaults()
        with self.assertRaises(IntegrityError):
            Category.objects.create(user=user, name="单词")  # 与注册时创建的默认类别重名

    def test_same_name_allowed_for_different_users(self):
        user1 = create_user_with_defaults('alice')
        user2 = create_user_with_defaults('bob')
        Category.objects.create(user=user1, name="语法")
        Category.objects.create(user=user2, name="语法")  # 不同用户可以同名
        self.assertEqual(Category.objects.filter(name="语法").count(), 2)

    def test_default_category_name_cannot_be_modified(self):
        user = create_user_with_defaults()
        category = Category.objects.get(user=user, is_default=True)
        category.name = "改名"
        with self.assertRaises(ValidationError):
            category.save()
        category.refresh_from_db()
        self.assertEqual(category.name, "单词")

    def test_default_category_cannot_be_deleted(self):
        user = create_user_with_defaults()
        category = Category.objects.get(user=user, is_default=True)
        with self.assertRaises(ValidationError):
            category.delete()

    def test_non_default_category_can_be_renamed_and_deleted(self):
        user = create_user_with_defaults()
        category = Category.objects.create(user=user, name="语法")
        category.name = "句法"
        category.save()
        category.refresh_from_db()
        self.assertEqual(category.name, "句法")
        category.delete()
        self.assertFalse(Category.objects.filter(user=user, name="句法").exists())


class ReviewDayModelTests(TestCase):
    def test_unique_together_user_day(self):
        user = create_user_with_defaults()
        with self.assertRaises(IntegrityError):
            ReviewDay.objects.create(user=user, day=1)  # 默认计划里已有 day=1

    def test_ordering(self):
        user = create_user_with_defaults()
        ReviewDay.objects.create(user=user, day=0)
        days = list(ReviewDay.objects.filter(user=user).values_list('day', flat=True))
        self.assertEqual(days, sorted(days))


class ItemModelTests(TestCase):
    def test_str_contains_item_and_category(self):
        user = create_user_with_defaults()
        item = create_item(user, item='apple', content='苹果')
        self.assertIn('apple', str(item))
        self.assertIn('单词', str(item))

    def test_proficiency_choices(self):
        self.assertEqual(Proficiency.UNFAMILIAR, 0)
        self.assertEqual(Proficiency.MASTERED, 1)

    def test_cascade_delete_with_user(self):
        user = create_user_with_defaults()
        create_item(user, item='apple')
        self.assertEqual(Item.objects.count(), 1)
        user.delete()
        self.assertEqual(Item.objects.count(), 0)
