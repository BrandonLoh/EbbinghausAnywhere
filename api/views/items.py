"""条目端点:列表(分页/搜索/筛选)、详情、批量新建。

新建时的冒号拆分规则与 Web 端 EAW.views.input 完全一致,
以"最先出现的英文或中文冒号"为界,前为条目名、后为内容。
"""

import re

from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from EAW.models import Item

from ..serializers import ItemCreateSerializer, ItemDetailSerializer, ItemListSerializer

PAGE_SIZE = 50  # 与 Web 端列表页一致


def _split_string(s):
    """按最先出现的冒号(英文/中文)拆分为 (名称, 内容)。"""
    pos = s.find(":")
    pos_cn = s.find("：")
    if pos == -1 or (pos_cn != -1 and pos_cn < pos):
        pos = pos_cn
    if pos == -1:
        return s, ""
    return s[:pos], s[pos + 1:]


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def items_collection(request):
    """GET: 分页列表(支持 ?q= 搜索、?category= 筛选);POST: 批量新建。"""
    if request.method == 'POST':
        return _create_items(request)

    queryset = (
        Item.objects.filter(user=request.user)
        .select_related('category')
        .order_by('-inputDate', '-id')
    )

    search = request.query_params.get('q', '').strip()
    if search:
        queryset = queryset.filter(item__icontains=search)

    category_id = request.query_params.get('category')
    if category_id:
        queryset = queryset.filter(category_id=category_id)

    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.query_params.get('page'))
    return Response({
        'count': paginator.count,
        'num_pages': paginator.num_pages,
        'page': page.number,
        'results': ItemListSerializer(page.object_list, many=True).data,
    })


def _create_items(request):
    serializer = ItemCreateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    # 支持多行文本一次提交(与 Web 端 textarea 行为一致)
    raw_text = serializer.validated_data['item_text']
    input_date = serializer.validated_data['input_date']
    category = serializer.validated_data['category_id']  # validate 后已是 Category 实例

    lines = [line for line in re.split(r'\r\n|\n', raw_text) if line.strip()]
    if not lines:
        return Response(
            {'detail': '没有任何有效条目。'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    created = []
    for line in lines:
        name, content = _split_string(line)
        name = name.strip()
        if not name:
            continue
        created.append(Item(
            user=request.user,
            item=name,
            content=content,
            inputDate=input_date,
            initDate=input_date,
            category=category,
        ))

    if not created:
        return Response(
            {'detail': '没有任何有效条目。'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    Item.objects.bulk_create(created)
    return Response(
        {'created': ItemDetailSerializer(created, many=True).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def item_detail(request, pk):
    try:
        item = Item.objects.select_related('category').get(user=request.user, pk=pk)
    except Item.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ItemDetailSerializer(item).data)
