"""快照的导出、校验与恢复(NAS 单向同步的核心逻辑)。

- 主库(PythonAnywhere)通过 API 端点导出快照: build_snapshot()
- 副本(NAS)拉取快照后校验并恢复: validate_snapshot() / restore_snapshot()

恢复语义(单向副本, 主库为唯一写入方):
- 用户: 按 username upsert。本地独有账号(如 NAS 应急管理员)保留不动;
  同名用户以快照(主库)为准。
- 业务表(categories / review_days / items / wechat_profiles): 全量清空重建,
  条目等主键与主库保持一致;用户外键经"快照用户 id → 本地用户"映射重写。
- 整个过程在单个事务内, 任一环节失败自动回滚, 旧数据不受影响。
- 角色守卫: 仅 EAW_ROLE=replica 的实例允许执行恢复, 防止旧快照反向覆盖主库。
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from EAW.models import Category, Item, ReviewDay

from .models import WeChatProfile

logger = logging.getLogger(__name__)

SNAPSHOT_FORMAT = 1
REQUIRED_SECTIONS = ('users', 'categories', 'review_days', 'items')

DOWNLOAD_TIMEOUT = 120  # 秒


class SnapshotError(Exception):
    """快照不合法, 或恢复被拒绝(角色/格式/完整性)。"""


def build_snapshot(source=''):
    """导出全量快照字典(主库侧)。"""
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

    return {
        'meta': {
            'format': SNAPSHOT_FORMAT,
            'created_at': timezone.now().isoformat(),
            'source': source,
        },
        'users': users,
        'categories': categories,
        'review_days': review_days,
        'items': items,
        'wechat_profiles': wechat_profiles,
    }


def _parse_date(value, field, record_id):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise SnapshotError(f'条目 id={record_id} 的 {field} 不是合法日期: {value!r}')


def validate_snapshot(data):
    """校验快照结构与外键完整性。不合法时抛 SnapshotError。

    在任何写操作之前调用, 保证非法快照不会触碰数据库。
    返回各段行数统计。

    设计原则:**只拦结构性损坏, 不拦数据内容**。
    副本的职责是忠实镜像主库 —— 主库允许存在的数据(如条目名为空字符串、
    用户名为空等边缘数据)必须能原样恢复, 否则同步会因主库的历史数据
    永久失败。因此这里检查的是"字段是否缺失/为 None、外键能否解析、
    日期是否合法", 而不是"字段是否非空"。
    """
    if not isinstance(data, dict):
        raise SnapshotError('快照根节点必须是 JSON 对象')

    meta = data.get('meta')
    if not isinstance(meta, dict):
        raise SnapshotError('缺少 meta 段')
    if meta.get('format') != SNAPSHOT_FORMAT:
        raise SnapshotError(
            f"不支持的快照格式: {meta.get('format')!r}(需要 {SNAPSHOT_FORMAT})"
        )
    for section in REQUIRED_SECTIONS:
        if not isinstance(data.get(section), list):
            raise SnapshotError(f'缺少或非法段: {section}')

    # 用户: id 唯一且必须提供 username / password(哈希)
    user_ids = set()
    for row in data['users']:
        uid = row.get('id')
        if uid is None or row.get('username') is None or row.get('password') is None:
            raise SnapshotError(f'用户记录缺少 id/username/password: {row!r}')
        if uid in user_ids:
            raise SnapshotError(f'用户 id 重复: {uid}')
        user_ids.add(uid)

    # 类别: id 唯一, user_id 必须存在
    category_ids = set()
    for row in data['categories']:
        cid = row.get('id')
        if cid is None or row.get('name') is None:
            raise SnapshotError(f'类别记录缺少 id/name: {row!r}')
        if cid in category_ids:
            raise SnapshotError(f'类别 id 重复: {cid}')
        if row.get('user_id') not in user_ids:
            raise SnapshotError(f"类别 id={cid} 引用了不存在的用户 {row.get('user_id')!r}")
        category_ids.add(cid)

    # 复习计划: id 唯一, user_id 必须存在
    review_day_ids = set()
    for row in data['review_days']:
        rid = row.get('id')
        if rid is None or row.get('day') is None:
            raise SnapshotError(f'复习计划记录缺少 id/day: {row!r}')
        if rid in review_day_ids:
            raise SnapshotError(f'复习计划 id 重复: {rid}')
        if row.get('user_id') not in user_ids:
            raise SnapshotError(f"复习计划 id={rid} 引用了不存在的用户 {row.get('user_id')!r}")
        review_day_ids.add(rid)

    # 条目: id 唯一, user_id / category_id 必须可解析, 日期必须合法
    item_ids = set()
    for row in data['items']:
        iid = row.get('id')
        if iid is None or row.get('item') is None:
            raise SnapshotError(f'条目记录缺少 id/item: {row!r}')
        if iid in item_ids:
            raise SnapshotError(f'条目 id 重复: {iid}')
        if row.get('user_id') not in user_ids:
            raise SnapshotError(f"条目 id={iid} 引用了不存在的用户 {row.get('user_id')!r}")
        category_id = row.get('category_id')
        if category_id is not None and category_id not in category_ids:
            raise SnapshotError(f"条目 id={iid} 引用了不存在的类别 {category_id!r}")
        _parse_date(row.get('inputDate'), 'inputDate', iid)
        _parse_date(row.get('initDate'), 'initDate', iid)
        item_ids.add(iid)

    # 微信绑定: 可选段(老快照可能没有)
    wechat_profiles = data.get('wechat_profiles', [])
    if not isinstance(wechat_profiles, list):
        raise SnapshotError('wechat_profiles 段必须是列表')
    for row in wechat_profiles:
        if row.get('id') is None or row.get('openid') is None:
            raise SnapshotError(f'微信绑定记录缺少 id/openid: {row!r}')
        if row.get('user_id') not in user_ids:
            raise SnapshotError(f"微信绑定 id={row.get('id')} 引用了不存在的用户 {row.get('user_id')!r}")

    return {
        'users': len(data['users']),
        'categories': len(data['categories']),
        'review_days': len(data['review_days']),
        'items': len(data['items']),
        'wechat_profiles': len(wechat_profiles),
    }


def ensure_replica_role():
    """角色守卫: 非副本实例拒绝执行恢复类操作。"""
    role = getattr(settings, 'EAW_ROLE', 'master')
    if role != 'replica':
        raise SnapshotError(
            f"拒绝执行: 本实例角色为 {role!r}, 只有副本(EAW_ROLE=replica)允许恢复快照。"
            '该守卫用于防止旧快照反向覆盖主库数据。'
        )


def restore_snapshot(data):
    """把快照恢复进本地库(事务内)。仅副本实例可执行。

    返回统计信息: 各段行数 + 用户新增/更新数。
    """
    ensure_replica_role()
    counts = validate_snapshot(data)

    with transaction.atomic():
        # 1) 用户 upsert: 按 username 匹配, 本地独有账号(不在快照中)保持不变
        user_map = {}
        users_created = users_updated = 0
        for row in data['users']:
            user = User.objects.filter(username=row['username']).first()
            if user is None:
                user = User(username=row['username'])
                users_created += 1
            else:
                users_updated += 1
            user.email = row.get('email') or ''
            user.first_name = row.get('first_name') or ''
            user.last_name = row.get('last_name') or ''
            user.password = row['password']  # 已是哈希, 直接落库
            user.is_staff = bool(row.get('is_staff'))
            user.is_active = bool(row.get('is_active', True))
            user.is_superuser = bool(row.get('is_superuser'))
            user.save()
            user_map[row['id']] = user

        # 2) 业务表全量重建(用户表不动)
        #    QuerySet.delete() 不调用实例 delete(), 因此默认类别的删除保护不会阻挡副本重建
        Item.objects.all().delete()
        Category.objects.all().delete()
        ReviewDay.objects.all().delete()
        WeChatProfile.objects.all().delete()

        Category.objects.bulk_create([
            Category(
                id=row['id'],
                user=user_map[row['user_id']],
                name=row['name'],
                sort_order=row.get('sort_order') or 0,
                is_default=bool(row.get('is_default')),
            )
            for row in data['categories']
        ])

        ReviewDay.objects.bulk_create([
            ReviewDay(id=row['id'], user=user_map[row['user_id']], day=row['day'])
            for row in data['review_days']
        ])

        category_map = {c.id: c for c in Category.objects.all()}
        Item.objects.bulk_create([
            Item(
                id=row['id'],
                user=user_map[row['user_id']],
                item=row['item'],
                content=row.get('content'),
                inputDate=_parse_date(row.get('inputDate'), 'inputDate', row['id']),
                initDate=_parse_date(row.get('initDate'), 'initDate', row['id']),
                proficiency=row.get('proficiency') or 0,
                category=category_map.get(row.get('category_id')),
                src_tts=row.get('src_tts'),
                us_phonetic=row.get('us_phonetic'),
                uk_phonetic=row.get('uk_phonetic'),
            )
            for row in data['items']
        ])

        WeChatProfile.objects.bulk_create([
            WeChatProfile(
                id=row['id'],
                user=user_map[row['user_id']],
                openid=row['openid'],
            )
            for row in data.get('wechat_profiles', [])
        ])
        # bulk_create 会让 auto_now_add 覆盖 created_at,这里按快照值逐条还原
        for row in data.get('wechat_profiles', []):
            created_at = row.get('created_at')
            if not created_at:
                continue
            try:
                ts = datetime.fromisoformat(created_at)
            except (TypeError, ValueError):
                continue
            WeChatProfile.objects.filter(pk=row['id']).update(created_at=ts)

    counts['users_created'] = users_created
    counts['users_updated'] = users_updated
    return counts


def download_snapshot(url, token, timeout=DOWNLOAD_TIMEOUT):
    """从主库 API 拉取快照, 返回解析后的字典。"""
    try:
        response = requests.get(
            url,
            headers={'Authorization': f'Token {token}'},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise SnapshotError(f'拉取快照失败: {exc}')
    if response.status_code != 200:
        raise SnapshotError(f'拉取快照失败: HTTP {response.status_code}')
    try:
        return response.json()
    except ValueError as exc:
        raise SnapshotError(f'快照不是合法 JSON: {exc}')


def save_snapshot_file(data, directory, prefix='snapshot'):
    """将快照写入目录(先写临时文件再原子重命名, 避免留下半截文件)。

    同一秒内的重复保存会追加序号, 不会相互覆盖。
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    final_path = directory / f'{prefix}_{stamp}.json'
    seq = 1
    while final_path.exists():
        final_path = directory / f'{prefix}_{stamp}_{seq:02d}.json'
        seq += 1
    tmp_path = final_path.with_suffix('.json.tmp')
    tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp_path.replace(final_path)
    return final_path


def prune_snapshots(directory, keep=7):
    """只保留最近 keep 份快照, 删除更早的。返回被删除的文件列表。

    按文件名中的时间戳排序(与写入顺序一致), 同秒的序号保证顺序稳定。
    """
    files = sorted(Path(directory).glob('snapshot_*.json'))
    to_remove = files if keep <= 0 else files[:-keep]
    for path in to_remove:
        path.unlink()
    return to_remove
