"""测试数据构造辅助。"""

from datetime import date

from django.contrib.auth.models import User

from EAW.models import Category, Item, ReviewDay

DEFAULT_REVIEW_DAYS = [1, 2, 4, 7, 15, 30, 90, 180, 365]


def create_user_with_defaults(username='tester', password='pass-12345678'):
    """模拟 register 视图的行为:建用户 + 默认类别 + 默认复习计划。"""
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password=password,
    )
    user.is_staff = True
    user.save()
    Category.objects.create(user=user, name="单词", sort_order=1, is_default=True)
    ReviewDay.objects.bulk_create(
        [ReviewDay(user=user, day=day) for day in DEFAULT_REVIEW_DAYS]
    )
    return user


def create_item(user, item='apple', content='', category=None,
                input_date=None, init_date=None, proficiency=0):
    """快速构造一条 Item;默认用该用户的默认类别。"""
    if category is None:
        category = Category.objects.filter(user=user, is_default=True).first()
    return Item.objects.create(
        user=user,
        item=item,
        content=content,
        category=category,
        inputDate=input_date or date(2025, 1, 1),
        initDate=init_date or date(2025, 1, 1),
        proficiency=proficiency,
    )
