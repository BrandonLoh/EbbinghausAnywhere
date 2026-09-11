"""首页、关于页、README 展示等杂项视图。"""

import logging
import os

import markdown
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from ..models import Item

logger = logging.getLogger(__name__)


def home(request):
    # 检查用户是否登录
    if request.user.is_authenticated:
        # 获取当前用户的所有 items
        items = Item.objects.filter(user=request.user)
        # 统计数据
        total_items = items.count()
        if total_items > 0:
            first_item_date = items.order_by('inputDate').first().inputDate
            days_since_first_item = (timezone.localdate() - first_item_date).days
        else:
            days_since_first_item = 0

        # 判断如何显示用户名
        if request.user.first_name and request.user.last_name:
            display_name = f"{request.user.first_name} {request.user.last_name}"  # 合并 first_name 和 last_name
        elif request.user.first_name:
            display_name = request.user.first_name  # 只有 first_name
        elif request.user.last_name:
            display_name = request.user.last_name  # 只有 last_name
        else:
            display_name = request.user.username  # 都没有，使用 username

        context = {
            'display_name': display_name,
            'total_items': total_items,
            'days_since_first_item': days_since_first_item,
        }
        # 用户已登录，返回登录后的首页
        return render(request, 'home_logged_in.html', context)
    else:
        # 用户未登录，返回未登录的首页
        return render(request, 'home_logged_out.html')


def about(request):
    return render(request, 'about.html')  # 渲染 about.html 页面


def readme_view(request):
    # 使用 BASE_DIR 获取 README.md 文件的路径
    readme_path = os.path.join(settings.BASE_DIR, 'README.md')

    # 读取文件内容
    with open(readme_path, 'r', encoding='utf-8') as f:
        readme_content = f.read()

    # 将 Markdown 转换为 HTML，并启用 fenced_code 扩展
    html_content = markdown.markdown(readme_content, extensions=['fenced_code'])

    # 渲染模板
    return render(request, 'readme.html', {'content': html_content})
