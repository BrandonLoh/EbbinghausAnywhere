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

from django.shortcuts import get_object_or_404
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