"""全量快照端点:供 NAS 每日单向同步拉取。

设计要点(见 docs/ARCHITECTURE_PLAN.md §3):
- 仅 superuser 可访问(绝不能是 is_staff ——本应用所有注册用户都是 is_staff);
- 保留主键,使 NAS 上的条目 id 与 PA 完全一致;
- 含密码哈希(副本可直接登录),但**不含 authtoken**(令牌是实例本地的);
- 不使用 dumpdata:避免 contenttypes/permissions 跨实例恢复的兼容问题。
"""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from EAW.models import Category, Item, ReviewDay

from ..models import WeChatProfile
from ..permissions import IsSuperUser

SNAPSHOT_FORMAT = 1


@api_view(['GET'])
@permission_classes([IsSuperUser])
def snapshot(request):
    users = [
        {
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'password': u.password,  # Django 密码哈希,原样保留
            'is_staff': u.is_staff,
            'is_active': u.is_active,
            'is_superuser': u.is_superuser,
        }
        for u in User.objects.order_by('id')
    ]

    categories = [
        {
            'id': c.id,
            'user_id': c.user_id,
            'name': c.name,
            'sort_order': c.sort_order,
            'is_default': c.is_default,
        }
        for c in Category.objects.order_by('id')
    ]

    review_days = [
        {'id': r.id, 'user_id': r.user_id, 'day': r.day}
        for r in ReviewDay.objects.order_by('id')
    ]

    items = [
        {
            'id': i.id,
            'user_id': i.user_id,
            'item': i.item,
            'content': i.content,
            'inputDate': i.inputDate.isoformat() if i.inputDate else None,
            'initDate': i.initDate.isoformat() if i.initDate else None,
            'proficiency': i.proficiency,
            'category_id': i.category_id,
            'src_tts': i.src_tts,
            'us_phonetic': i.us_phonetic,
            'uk_phonetic': i.uk_phonetic,
        }
        for i in Item.objects.order_by('id')
    ]

    wechat_profiles = [
        {
            'id': p.id,
            'user_id': p.user_id,
            'openid': p.openid,
            'created_at': p.created_at.isoformat(),
        }
        for p in WeChatProfile.objects.order_by('id')
    ]

    return Response({
        'meta': {
            'format': SNAPSHOT_FORMAT,
            'created_at': timezone.now().isoformat(),
            # 服务方主机名:便于确认快照确实来自 PA 而不是指向了 NAS 自身
            'source': request.get_host(),
        },
        'users': users,
        'categories': categories,
        'review_days': review_days,
        'items': items,
        'wechat_profiles': wechat_profiles,
    })
