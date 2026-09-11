"""全量快照端点:供 NAS 每日单向同步拉取。

设计要点(见 docs/ARCHITECTURE_PLAN.md §3):
- 仅 superuser 可访问(绝不能是 is_staff ——本应用所有注册用户都是 is_staff);
- 保留主键,使 NAS 上的条目 id 与 PA 完全一致;
- 含密码哈希(副本可直接登录),但**不含 authtoken**(令牌是实例本地的);
- 不使用 dumpdata:避免 contenttypes/permissions 跨实例恢复的兼容问题;
- 快照结构与恢复逻辑同源,见 api/snapshot.py。
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..permissions import IsSuperUser
from ..snapshot import build_snapshot


@api_view(['GET'])
@permission_classes([IsSuperUser])
def snapshot(request):
    # meta.source 记录服务方主机名:便于确认快照确实来自 PA,而不是误指向了 NAS 自身
    return Response(build_snapshot(source=request.get_host()))
