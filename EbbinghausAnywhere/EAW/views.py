from django.shortcuts import render
from django.core.paginator import Paginator
from django.views import generic
from django.db.models import Avg, Max, Min, Count, Sum
from datetime import datetime
from datetime import timedelta
#from .forms import ReviewDateForm, InputForm, ImportForm


from django.utils.decorators import method_decorator
from django.views.generic.detail import DetailView
from django.contrib.auth.decorators import permission_required
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.models import Group

from django.shortcuts import get_object_or_404
from django.http import Http404
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
#from .translate import createRequest, getChengyuRequest, baidu_translate
import json
import csv
from time import sleep
import logging
import re
from django.views.decorators.csrf import csrf_exempt
import json
from .translate import baidu_translate, parse_json_to_string

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

@login_required
def item_list(request):
    # 获取当前登录用户的所有 Item
    item_list = Item.objects.filter(user=request.user).order_by('-inputDate')

    # 确保 item_list 不为空时才进行分页
    if item_list.exists():
        paginator = Paginator(item_list, 50)  # 每页 50 个
        page_number = request.GET.get('page')  # 获取当前页码
        page_obj = paginator.get_page(page_number)
    else:
        # 如果 item_list 为空，设置 page_obj 为一个空列表或自定义的对象
        page_obj = []

    # 渲染模板，传递分页对象
    return render(request, 'list.html', {'page_obj': page_obj})


@method_decorator(login_required, name='dispatch')  # 确保用户已登录
class ItemDetailView(DetailView):
    model = Item
    template_name = 'item_detail.html'  # 设置模板路径

    def get_queryset(self):
        # 只允许当前登录用户访问属于自己的 Item
        return Item.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # 验证是否属于当前用户
        if obj.user != self.request.user:
            # 返回自定义提示页面
            return render(self.request, 'EAW/item_not_found.html', status=404)
        return obj

@login_required
def SearchView(request):
    word = ''
    query = Item.objects.none()  # 初始化为空查询集

    # 获取搜索关键词
    search_input = request.GET.get('q', '').strip()

    if search_input == '':  # 如果没有输入关键词
        if request.method == 'GET' and 'q' in request.GET:
            word = 'No search input.'  # 用户提交了空表单
        # 初始访问，直接返回空页面或默认提示
        return render(
            request,
            'search.html',  # 渲染初始搜索页面
            context={
                'word': word,
            },
        )
    else:
        # 在当前用户的数据库中搜索 item 字段包含搜索关键词的条目
        query = Item.objects.filter(user=request.user, item__icontains=search_input)

        # 如果查询结果为空
        if not query.exists():
            word = 'No search result.'

    return render(
        request,
        'search_result.html',  # 渲染搜索结果模板
        context={
            'query': query,  # 查询结果
            'word': word,    # 提示信息
        },
    )


#复习单词的功能
@login_required
def ReviewHomeView(request):
    today = datetime.today().date()
    print(today)
    return render(
        request,
        'review_home.html',
        context={'today': today}
    )

@login_required
def ReviewView(request, year, month, day):
    print(f"Year: {year}, Month: {month}, Day: {day}")
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
    
    # 根据复习曲线匹配单词
    for interval in ReviewDay.objects.filter(user=request.user):
        checkday = reviewDate - timedelta(days=interval.day)
        review_items = Item.objects.filter(user=request.user, initDate=checkday)
        for item in review_items:
            # 生成 item 的详细页面 URL
            detail_url = reverse('item-detail', args=[item.pk])
            output[item.category.name].append([interval.day, item, detail_url])
    
    return render(
        request,
        'review_day.html',
        context={'output': output, 'reviewdate': reviewDate}
    )


@login_required
def ReviewFeedbackYes(request):
    """
    更新指定 Item 的 proficiency 为 MASTERED（熟练）。
    """
    try:
        if request.method == "POST":
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
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def ReviewFeedbackNo(request):
    """
    更新指定 Item 的 proficiency 为 UNFAMILIAR（不熟练）。
    """
    try:
        if request.method == "POST":
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
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def ReviewFeedbackReset(request):
    """
    重置指定 Item 的 initDate 为今天的日期，并将 proficiency 改为 UNFAMILIAR。
    """
    try:
        if request.method == "POST":
            # 解析请求数据
            data = json.loads(request.body.decode("utf-8"))
            item_id = data.get('id')

            # 获取当前用户的 Item
            curword = Item.objects.get(user=request.user, id=item_id)

            # 更新 initDate 为当前日期
            curword.initDate = datetime.today()

            # 更新 proficiency 为 UNFAMILIAR
            curword.proficiency = Proficiency.UNFAMILIAR
            curword.save()

            return JsonResponse({
                'success': True,
                'message': 'initDate reset to today and proficiency set to UNFAMILIAR.',
                'mastery': curword.get_proficiency_display()  # 返回最新的掌握程度
            })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

#BAIDU API调试页面
def translate_test(request):
    return render(request, 'translate.html')  # 渲染index.html页面
@csrf_exempt
def translate(request):
    if request.method == 'POST':
        try:
            # 获取前端传来的查询词
            data = json.loads(request.body)
            query = data.get('query', '')

            if not query:
                return JsonResponse({'success': False, 'message': 'No query provided'})

            # 调用百度翻译接口
            result = baidu_translate(query)
            
            if result:
                return JsonResponse({'success': True, 'result': result})
            else:
                return JsonResponse({'success': False, 'message': 'Translation failed'})
        
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})
def check_api_keys_view(request):
    """
    检查是否配置了百度 API 密钥
    :return: JsonResponse
    """
    if check_api_keys():
        return JsonResponse({"success": True, "message": "百度 API 密钥已配置"})
    else:
        return JsonResponse({"success": False, "message": "百度 API 密钥未配置"}, status=400)
    
    