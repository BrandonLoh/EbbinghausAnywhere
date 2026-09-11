"""条目列表、详情、搜索视图。"""

import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.generic.detail import DetailView

from ..models import Item

logger = logging.getLogger(__name__)


@login_required
def item_list(request):
    # 获取当前登录用户的所有 Item
    item_list = Item.objects.filter(user=request.user).order_by('-inputDate')

    # 统计每个类别下的条目数量
    category_stats = item_list.values('category__name').annotate(count=Count('category')).order_by('-count')

    # 确保 item_list 不为空时才进行分页
    if item_list.exists():
        paginator = Paginator(item_list, 50)  # 每页 50 个
        page_number = request.GET.get('page')  # 获取当前页码
        page_obj = paginator.get_page(page_number)
    else:
        # 如果 item_list 为空，设置 page_obj 为一个空列表或自定义的对象
        page_obj = []

    # 渲染模板，传递分页对象和类别统计信息
    return render(request, 'list.html', {'page_obj': page_obj, 'category_stats': category_stats})


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
    query = Item.objects.none()

    # 获取搜索关键词
    search_input = request.GET.get('q', '').strip()
    logger.debug(f"Search input received: {search_input}")

    if search_input == '':  # 如果没有输入关键词
        if 'q' in request.GET:
            word = 'No search input.'
        return render(
            request,
            'search.html',
            context={'word': word},
        )
    else:
        # 在当前用户的数据库中搜索 item 字段包含搜索关键词的条目
        try:
            query = Item.objects.filter(user=request.user, item__icontains=search_input)
            if not query.exists():
                word = 'No search result.'
        except Exception as e:
            logger.error(f"Error during search query: {e}")
            return JsonResponse({'error': 'Error processing your search query'}, status=500)

    # 如果是 AJAX 请求，返回 JSON 数据
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # 渲染搜索结果的 HTML
            html = render_to_string('search_results.html', {'query': query, 'word': word})
            logger.debug(f"Generated HTML for search results.")
            return JsonResponse({'html': html})
        except Exception as e:
            logger.error(f'Error during search result rendering: {e}')
            return JsonResponse({'error': 'Failed to generate results.'}, status=500)

    # 如果不是 AJAX 请求，返回正常的 HTML 页面
    return render(
        request,
        'search_results.html',
        context={'query': query, 'word': word},
    )
