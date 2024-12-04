from django.shortcuts import render
from django.core.paginator import Paginator
from django.views import generic
from django.db.models import Avg, Max, Min, Count, Sum
import datetime as dt
from datetime import timedelta
#from .forms import ReviewDateForm, InputForm, ImportForm
from django.contrib.auth.decorators import permission_required
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import Group

from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
#from .translate import createRequest, getChengyuRequest, baidu_translate
import json
import csv
from time import sleep
import logging
import re
logger = logging.getLogger(__name__)

# Create your views here.
from .models import Item, Proficiency, Category, ReviewDay

def custom_login(request):
    return render(request, 'registration/login.html')  # 指向自定义的模板文件

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            # 保存用户
            user = form.save()
            username = form.cleaned_data.get('username')

            # 将用户添加到 "Public" 组
            public_group, created = Group.objects.get_or_create(name='Public')
            user.groups.add(public_group)

            # 为用户赋予登录后台的权限
            user.is_staff = True
            user.save()

            # 创建默认 "单词" 分类
            Category.objects.create(user=user, name="单词", sort_order=1)

            # 创建默认的复习天数
            review_days = [1, 2, 4, 7, 15, 30, 90, 180, 365]
            ReviewDay.objects.bulk_create(
                [ReviewDay(user=user, day=day) for day in review_days]
            )

            # 提示用户注册成功
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def index(request):
    """
    Index view to show the total count of items and the count for each category.
    """
    # 获取当前登录用户
    user = request.user

    # 查询用户的所有条目和分类
    total_items = Item.objects.filter(user=user).count()  # 总条目数
    categories = Category.objects.filter(user=user)  # 当前用户的所有分类
    category_counts = {
        category.name: Item.objects.filter(user=user, category=category).count()
        for category in categories
    }

    # 渲染上下文
    context = {
        'total_items': total_items,
        'category_counts': category_counts,
    }

    return render(request, 'index.html', context)

