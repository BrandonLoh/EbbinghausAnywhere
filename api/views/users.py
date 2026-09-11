"""用户概览与类别端点。"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from EAW.models import Category, Item, ReviewDay

from ..serializers import CategorySerializer, UserSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """小程序首页:用户信息 + 统计(总数/坚持天数/今日待复习数)。"""
    user = request.user
    items = Item.objects.filter(user=user)

    total_items = items.count()
    if total_items > 0:
        first_item_date = items.order_by('inputDate').first().inputDate
        days_since_first_item = (timezone.localdate() - first_item_date).days
    else:
        days_since_first_item = 0

    today = timezone.localdate()
    intervals = ReviewDay.objects.filter(user=user).values_list('day', flat=True)
    due_dates = [today - timedelta(days=d) for d in intervals]
    today_due = items.filter(initDate__in=due_dates).count()

    return Response({
        'user': UserSerializer(user).data,
        'stats': {
            'total_items': total_items,
            'days_since_first_item': days_since_first_item,
            'today_due': today_due,
        },
    })


class CategoryListView(generics.ListAPIView):
    """类别列表(带条目计数),供录入页/筛选使用。"""

    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Category.objects.filter(user=self.request.user)
            .annotate_item_count()
        )
