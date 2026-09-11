"""复习相关视图:复习主页、按日期复习、复习反馈(Yes/No/Reset)。"""

import json
import logging
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse

from ..models import Category, Item, Proficiency, ReviewDay

logger = logging.getLogger(__name__)


@login_required
def ReviewHomeView(request):
    today = datetime.today().date()
    return render(
        request,
        'review_home.html',
        context={'today': today}
    )


@login_required
def ReviewView(request, year, month, day):
    # 创建选择的复习日期
    d1 = f"{year}-{month}-{day}"
    reviewDate = datetime.strptime(d1, '%Y-%m-%d').date()

    # 如果是POST请求，处理用户选择的日期
    if request.method == 'POST':
        review_date_str = request.POST.get('review_date')
        if review_date_str:
            reviewDate = datetime.strptime(review_date_str, '%Y-%m-%d').date()

    # 初始化每个类别的数据容器
    output = {}
    categories = Category.objects.filter(user=request.user)
    for category in categories:
        output[category.name] = []

    # 根据复习曲线匹配单词:一次性取出所有到期日的条目,避免逐个间隔查询
    intervals = ReviewDay.objects.filter(user=request.user)
    checkdays = {reviewDate - timedelta(days=interval.day): interval.day for interval in intervals}
    review_items = (
        Item.objects.filter(user=request.user, initDate__in=checkdays.keys())
        .select_related('category')
    )
    for item in review_items:
        # 生成 item 的详细页面 URL
        detail_url = reverse('item-detail', args=[item.pk])
        category_name = item.category.name if item.category else '未分类'
        output.setdefault(category_name, []).append([checkdays[item.initDate], item, detail_url])

    # ==================== 新增：按间隔天数（从小到大）排序 ====================
    for category_name in output:
        # x[0] 即 checkdays[item.initDate] (天数)，按照天数升序排序
        output[category_name].sort(key=lambda x: x[0])
    # ========================================================================

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # AJAX 场景:返回片段,由前端注入页面并触发 Markdown/MathJax 渲染
        return HttpResponse(render_to_string('review_day.html', {'output': output, 'reviewdate': reviewDate}, request))

    return render(request, 'review_day_page.html', {'output': output, 'reviewdate': reviewDate})


def _feedback_error(message):
    """业务失败统一返回 HTTP 200 + success:false,保持前端 alert 行为不变。"""
    return JsonResponse({'success': False, 'message': message})


@login_required
def ReviewFeedbackYes(request):
    """
    更新指定 Item 的 proficiency 为 MASTERED（熟练）。
    """
    if request.method != "POST":
        return _feedback_error('Invalid request method.')

    try:
        # 解析请求数据
        data = json.loads(request.body.decode("utf-8"))
        item_id = data.get('id')

        # 获取当前用户的 Item
        curword = Item.objects.get(user=request.user, id=item_id)

        # 更新 proficiency 为 MASTERED
        curword.proficiency = Proficiency.MASTERED
        curword.save()

        return JsonResponse({
            'success': True,
            'message': 'Proficiency updated to MASTERED.',
            'mastery': curword.get_proficiency_display()  # 返回最新的掌握程度
        })
    except Item.DoesNotExist:
        return _feedback_error('Item not found.')
    except (json.JSONDecodeError, AttributeError):
        return _feedback_error('Invalid JSON.')


@login_required
def ReviewFeedbackNo(request):
    """
    更新指定 Item 的 proficiency 为 UNFAMILIAR（不熟练）。
    """
    if request.method != "POST":
        return _feedback_error('Invalid request method.')

    try:
        # 解析请求数据
        data = json.loads(request.body.decode("utf-8"))
        item_id = data.get('id')

        # 获取当前用户的 Item
        curword = Item.objects.get(user=request.user, id=item_id)

        # 更新 proficiency 为 UNFAMILIAR
        curword.proficiency = Proficiency.UNFAMILIAR
        curword.save()

        return JsonResponse({
            'success': True,
            'message': 'Proficiency updated to UNFAMILIAR.',
            'mastery': curword.get_proficiency_display()  # 返回最新的掌握程度
        })
    except Item.DoesNotExist:
        return _feedback_error('Item not found.')
    except (json.JSONDecodeError, AttributeError):
        return _feedback_error('Invalid JSON.')


@login_required
def ReviewFeedbackReset(request):
    """
    重置指定 Item 的 initDate 为今天的日期，并将 proficiency 改为 UNFAMILIAR。
    """
    if request.method != "POST":
        return _feedback_error('Invalid request method.')

    try:
        # 解析请求数据
        data = json.loads(request.body.decode("utf-8"))
        item_id = data.get('id')

        # 获取当前用户的 Item
        curword = Item.objects.get(user=request.user, id=item_id)

        # 更新 initDate 为当前日期
        curword.initDate = date.today()

        # 更新 proficiency 为 UNFAMILIAR
        curword.proficiency = Proficiency.UNFAMILIAR
        curword.save()

        return JsonResponse({
            'success': True,
            'message': 'initDate reset to today and proficiency set to UNFAMILIAR.',
            'mastery': curword.get_proficiency_display()  # 返回最新的掌握程度
        })
    except Item.DoesNotExist:
        return _feedback_error('Item not found.')
    except (json.JSONDecodeError, AttributeError):
        return _feedback_error('Invalid JSON.')
