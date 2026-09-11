"""复习端点:按日期取复习内容 + 单端点反馈(yes/no/reset)。

复习查询语义与 Web 端 EAW.views.review.ReviewView 完全一致:
按 initDate = 目标日期 - 间隔天数 匹配,组内按间隔天数升序。
"""

from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from EAW.models import Category, Item, Proficiency, ReviewDay

from ..serializers import FeedbackSerializer


def _parse_review_date(request):
    """从 ?date= 参数取目标日期,缺省为今天;非法格式返回 None。"""
    raw = request.query_params.get('date')
    if not raw:
        return timezone.localdate(), None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date(), None
    except ValueError:
        return None, Response(
            {'detail': '日期格式应为 YYYY-MM-DD。'},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def review_list(request):
    """按类别分组的复习列表。

    返回结构:
    {
      "review_date": "2026-09-11",
      "categories": [
        {"id": 1, "name": "单词", "items": [ {…, "review_day": 1}, … ]},  # 组内按天数升序
        …
      ]
    }
    """
    review_date, error = _parse_review_date(request)
    if error:
        return error

    user = request.user
    intervals = ReviewDay.objects.filter(user=user)
    checkdays = {review_date - timedelta(days=i.day): i.day for i in intervals}
    due_items = (
        Item.objects.filter(user=user, initDate__in=checkdays.keys())
        .select_related('category')
        .order_by('initDate')
    )

    # 一次取好类别元数据,供分组与排序使用(避免排序键里再查库)
    category_meta = {
        c.pk: (c.sort_order, c.name)
        for c in Category.objects.filter(user=user)
    }

    groups = {}  # category_id -> {id, name, items[]}
    for item in due_items:
        category_id = item.category_id
        category_name = item.category.name if item.category else '未分类'
        entry = {
            'id': item.pk,
            'item': item.item,
            'content': item.content or '',
            'review_day': checkdays[item.initDate],
            'proficiency': item.proficiency,
            'proficiency_label': item.get_proficiency_display(),
            'src_tts': item.src_tts,
            'us_phonetic': item.us_phonetic,
            'uk_phonetic': item.uk_phonetic,
        }
        groups.setdefault(
            category_id,
            {'id': category_id, 'name': category_name, 'items': []},
        )['items'].append(entry)

    # 组内按间隔天数升序(与 Web 端 review.py 的排序一致)
    for group in groups.values():
        group['items'].sort(key=lambda x: x['review_day'])

    # 类别按用户定义的 sort_order 排,未分类排最后
    def _category_sort_key(group):
        meta = category_meta.get(group['id'])
        if meta is None:
            return (1, 0, group['name'])
        return (0, meta[0], meta[1])

    categories = sorted(groups.values(), key=_category_sort_key)

    return Response({
        'review_date': review_date.isoformat(),
        'categories': categories,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def review_feedback(request):
    """复习反馈: {"id": 123, "action": "yes|no|reset"} 单端点替代 Web 的三个按钮。

    业务失败统一 200 + success:false(与 Web 端约定一致,便于前端统一弹窗)。
    """
    serializer = FeedbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    item_id = serializer.validated_data['id']
    action = serializer.validated_data['action']

    try:
        cur_item = Item.objects.get(user=request.user, id=item_id)
    except Item.DoesNotExist:
        return Response({'success': False, 'message': 'Item not found.'})

    if action == 'yes':
        cur_item.proficiency = Proficiency.MASTERED
        message = 'Proficiency updated to MASTERED.'
    elif action == 'no':
        cur_item.proficiency = Proficiency.UNFAMILIAR
        message = 'Proficiency updated to UNFAMILIAR.'
    else:  # reset: 复习周期重置为今天,熟练度归零
        cur_item.initDate = timezone.localdate()
        cur_item.proficiency = Proficiency.UNFAMILIAR
        message = 'initDate reset to today and proficiency set to UNFAMILIAR.'

    cur_item.save()
    return Response({
        'success': True,
        'message': message,
        'mastery': cur_item.get_proficiency_display(),
    })
