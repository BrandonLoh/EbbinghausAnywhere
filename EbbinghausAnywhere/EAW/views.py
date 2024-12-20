from django.shortcuts import render
from django.core.paginator import Paginator
from django.views import generic
from django.db.models import Avg, Max, Min, Count, Sum
from datetime import datetime
from datetime import timedelta
from django.utils.timezone import now
from django import forms
from .forms import InputForm, EmailUpdateForm
from django.utils.decorators import method_decorator
from django.views.generic.detail import DetailView
from django.contrib.auth.decorators import permission_required
from django.core.cache import cache
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, JsonResponse
from django.http import HttpResponse
from django.urls import reverse
import json
import csv
from time import sleep
import logging
import re
from django.views.decorators.csrf import csrf_exempt
import json
from django.template.loader import render_to_string
from .translate import baidu_translate, parse_json_to_string, check_api_keys
import openpyxl
from django.db import transaction
from .models import Item, Category, Proficiency
from .admin import ItemAdmin
import difflib

logger = logging.getLogger(__name__)

# Create your views here.
from .models import Item, Proficiency, Category, ReviewDay

def custom_login(request):
    return render(request, 'registration/login.html')  # 指向自定义的模板文件

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="请输入有效的邮箱地址")

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')

            # 加入 Public 组，设置默认值等
            public_group, created = Group.objects.get_or_create(name='Public')
            user.groups.add(public_group)
            user.is_staff = True
            user.save()

            Category.objects.create(user=user, name="单词", sort_order=1, is_default=True)

            review_days = [1, 2, 4, 7, 15, 30, 90, 180, 365]
            ReviewDay.objects.bulk_create(
                [ReviewDay(user=user, day=day) for day in review_days]
            )

            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'registration/register.html', {'form': form})

@login_required
def user_profile(request):
    if request.method == 'POST':
        email_form = EmailUpdateForm(request.POST, initial={'email': request.user.email})
        password_form = PasswordChangeForm(user=request.user, data=request.POST)

        if 'update_email' in request.POST and email_form.is_valid():
            # 修改邮箱
            new_email = email_form.cleaned_data.get('email')
            request.user.email = new_email
            request.user.save()
            messages.success(request, '邮箱更新成功！')

        elif password_form.is_valid():
            # 修改密码
            password_form.save()
            update_session_auth_hash(request, password_form.user)  # 防止登出
            messages.success(request, '密码更新成功！')

    else:
        email_form = EmailUpdateForm(initial={'email': request.user.email})
        password_form = PasswordChangeForm(user=request.user)

    context = {
        'email_form': email_form,
        'password_form': password_form,
    }
    return render(request, 'users/profile.html', context)


def home(request):
    # 检查用户是否登录
    if request.user.is_authenticated:
        # 用户已登录，返回登录后的首页
        return render(request, 'home_logged_in.html')
    else:
        # 用户未登录，返回未登录的首页
        return render(request, 'home_logged_out.html')

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
    print("Request routed to ReviewHomeView")  # 调试
    today = datetime.today().date()
    #print(today)
    return render(
        request,
        'review_home.html',
        context={'today': today}
    )

@login_required
def ReviewView(request, year, month, day):
    print(f"Request routed to ReviewView with date: {year}-{month}-{day}")  # 调试
    #print(f"Year: {year}, Month: {month}, Day: {day}")
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
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponse(render_to_string('review_day.html', {'output': output, 'reviewdate': reviewDate}, request))

    return render(request, 'review_day.html', {'output': output, 'reviewdate': reviewDate})


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
    

@login_required
def InputView(request):
    if request.method == 'POST':
        form = InputForm(request.POST, user=request.user)  # 传递当前用户
        if form.is_valid():
            data = {
                'input_date': form.cleaned_data['input_date'],
                'category': form.cleaned_data['category'].name,
                'input': form.cleaned_data['input']
            }
            split = data['input'].split('\r\n')
            category_object = Category.objects.get(name=data['category'], user=request.user)  # 仅查找当前用户的类别

            # 获取是否勾选了翻译复选框，并且类别为"单词"
            translate = 'translate' in request.POST and data['category'] == '单词'

            for item in split:
                explain_txt = ''
                result_dict = None
                translated_content = ''
                simple_meaning = ''
                item_name = item
                item_name, explain_txt = split_string(item)  # 如果有拆分功能
                item_name = item_name.strip()
                # 初始化 phonetic_am 和 phonetic_en 为 None
                phonetic_am = phonetic_en = None
                src_tts = None

                # 如果勾选了 "获取释义" 复选框，则调用百度翻译函数
                if translate:
                    result_dict = baidu_translate(item_name)
                    if result_dict:  # 如果返回的字典非空
                        # 从 result_dict 中提取各个部分
                        phonetic = result_dict.get('phonetic', [])
                        phonetic_am = phonetic[1] if len(phonetic) > 1 else None  # 美式音标
                        phonetic_en = phonetic[0] if len(phonetic) > 0 else None  # 英式音标
                        src_tts = result_dict.get('src_tts', None)  # TTS URL
                        translated_content = result_dict.get('parts_and_means', [])  # 词性和释义
                        simple_meaning = result_dict.get('simple_meaning', [])  # 简明释义

                        # 拼接解释文本
                    # 确保是字符串并避免空行
                        if translated_content:
                            if explain_txt:  # 如果原来已有内容，才添加换行
                                explain_txt += "\n\n"
                            explain_txt += "\n".join([str(item) for item in translated_content])  # 拼接详细释义

                        # 如果有 translated_content 或音标，则不存储 simple_meaning
                        if not translated_content:
                            # 如果没有翻译内容才拼接简明释义
                            if simple_meaning:
                                if explain_txt:  # 如果原来已有内容，才添加换行
                                    explain_txt += "\n\n"
                                explain_txt += "\n".join([str(item) for item in simple_meaning])  # 拼接简明释义
                    else:
                        phonetic_am = phonetic_en = src_tts = None

                # 创建 Item 实例，并保存到数据库
                Item.objects.create(
                    user=request.user,
                    item=item_name,
                    inputDate=data['input_date'],
                    initDate=data['input_date'],
                    category=category_object,
                    content=explain_txt,
                    src_tts=src_tts if translate else None,  # 如果未勾选翻译，TTS 地址为 None
                    us_phonetic=phonetic_am,  # 存储美式音标
                    uk_phonetic=phonetic_en   # 存储英式音标
                )

            return redirect(reverse('item-list'))  # 重定向到项列表页面
    else:
        form = InputForm(user=request.user)  # 传递当前用户

    return render(request, 'input.html', {'form': form})



def split_string(s):
    # 查找第一个出现的英文冒号或中文冒号的位置
    pos = s.find(":")
    pos_cn = s.find("：")
    
    # 找到最先出现的冒号位置
    if pos == -1 or (pos_cn != -1 and pos_cn < pos):
        pos = pos_cn
    
    # 如果没有冒号，返回原字符串和空字符串
    if pos == -1:
        return s, ""
    
    # 根据位置分割字符串
    return s[:pos], s[pos + 1:]


@login_required
def export_user_data_to_excel(request):
    # 获取当前用户数据
    user = request.user
    items = Item.objects.filter(user=user)

    # 创建一个新的 Excel 工作簿
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "User Data"

    # 写入表头
    headers = ["Item", "Content", "Input Date", "Init Date", "Proficiency", "Category", "TTS URL", "US Phonetic", "UK Phonetic"]
    sheet.append(headers)

    # 写入用户数据
    for item in items:
        sheet.append([
            item.item,
            item.content,
            item.inputDate,
            item.initDate,
            item.get_proficiency_display(),
            item.category.name if item.category else "",
            item.src_tts,
            item.us_phonetic,
            item.uk_phonetic,
        ])

    # 创建 HTTP 响应
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="user_data.xlsx"'

    # 将工作簿保存到响应中
    workbook.save(response)

    return response
    


@login_required
def import_items_from_excel(request):
    if request.method == "POST" and request.FILES.get("file"):
        file = request.FILES["file"]
        user = request.user

        # 检查是否选择了“获取释义”选项
        fetch_definitions = "fetch_definitions" in request.POST

        try:
            workbook = openpyxl.load_workbook(file)
            sheet = workbook.active
        except Exception as e:
            messages.error(request, f"文件读取失败: {str(e)}")
            return render(request, "import_data.html")

        headers = [cell.value for cell in sheet[1]]
        required_columns = ["Item"]
        if not all(col in headers for col in required_columns):
            messages.error(request, "文件格式错误，缺少必要的列。")
            return render(request, "import_data.html")

        column_index = {header: headers.index(header) for header in headers}
        items_to_create = []
        errors = []

        # Proficiency 字段的映射
        proficiency_map = {
            "Unfamiliar": Proficiency.UNFAMILIAR,
            "Mastered": Proficiency.MASTERED,
        }

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            try:
                item_name = row[column_index["Item"]]
                if not item_name:
                    errors.append(f"第 {row_idx} 行缺少 Item 字段，已跳过。")
                    continue

                content = row[column_index.get("Content", None)] or ""
                input_date = row[column_index.get("Input Date", None)] or now().date()
                init_date = row[column_index.get("Init Date", None)] or now().date()

                # 处理 Proficiency 字段
                proficiency_name = row[column_index.get("Proficiency", None)] or "Unfamiliar"
                proficiency_degree = proficiency_map.get(proficiency_name, Proficiency.UNFAMILIAR)

                category_name = row[column_index.get("Category", None)]
                src_tts = row[column_index.get("TTS URL", None)] or ""
                us_phonetic = row[column_index.get("US Phonetic", None)] or ""
                uk_phonetic = row[column_index.get("UK Phonetic", None)] or ""

                category = None
                if category_name:
                    categories = Category.objects.filter(name=category_name, user=user)
                    if categories.exists():
                        category = categories.first()
                    else:
                        category = Category.objects.create(name=category_name, user=user)

                # 根据复选框的状态决定是否获取释义
                if fetch_definitions:
                    translation_result = baidu_translate(item_name)
                    if translation_result:
                        phonetic = translation_result.get("phonetic", [])
                        us_phonetic = phonetic[1] if len(phonetic) > 1 else us_phonetic
                        uk_phonetic = phonetic[0] if len(phonetic) > 0 else uk_phonetic
                        src_tts = translation_result.get("src_tts", src_tts)

                        simple_meaning = translation_result.get("simple_meaning", [])
                        parts_and_means = translation_result.get("parts_and_means", [])

                        new_definition = "\n".join([str(item) for item in parts_and_means]).strip() if parts_and_means else (simple_meaning[0] if simple_meaning else "")

                        existing_definition = " ".join(ItemAdmin.clean_definition(content))
                        content = compare_lines(existing_definition, new_definition)

                item = Item(
                    user=user,
                    item=item_name,
                    content=content,
                    inputDate=input_date,
                    initDate=init_date,
                    proficiency=proficiency_degree,
                    category=category,
                    src_tts=src_tts,
                    us_phonetic=us_phonetic,
                    uk_phonetic=uk_phonetic,
                )
                items_to_create.append(item)

            except Exception as e:
                errors.append(f"第 {row_idx} 行处理失败: {str(e)}")

        try:
            with transaction.atomic():
                Item.objects.bulk_create(items_to_create)
            success_message = f"导入完成。成功导入 {len(items_to_create)} 条记录，{len(errors)} 条记录跳过。"
            messages.success(request, success_message)
        except Exception as e:
            messages.error(request, f"保存失败: {str(e)}")

        return render(request, "import_data.html", {
            "import_results": {
                "success_count": len(items_to_create),
                "errors": errors,
            }
        })

    messages.error(request, "请求无效，请上传文件。")
    return render(request, "import_data.html")


@staticmethod
def compare_lines(existing_lines, new_lines):
    existing = [line.strip() for line in existing_lines.splitlines() if line.strip()]
    new = [line.strip() for line in new_lines.splitlines() if line.strip()]

    result = []
    existing_set = set(existing)

    # 逐行比较
    for line in existing:
        result.append(line)

    for new_line in new:
        if not any(difflib.SequenceMatcher(None, new_line, e_line).ratio() > 0.8 for e_line in existing_set):
            result.append(new_line)

    return "\n".join(result)



