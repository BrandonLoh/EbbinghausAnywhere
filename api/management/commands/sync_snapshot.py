"""sync_snapshot:NAS 每日同步入口 —— 拉取主库快照并恢复。

用法:
    python manage.py sync_snapshot [--url URL] [--token TOKEN]
                                   [--snapshot-dir DIR] [--keep N]
                                   [--dry-run]

配置(环境变量, 见 .env):
    EAW_ROLE=replica            必须;角色守卫
    EAW_SYNC_URL                主库快照端点, 如
                                https://ebbinghaus.pythonanywhere.com/api/v1/backup/snapshot/
    EAW_SYNC_TOKEN              主库 syncbot 账号的 API token
    EAW_SNAPSHOT_DIR            快照保存目录(默认 BASE_DIR/snapshots)

流程:下载 → 校验 → 落盘(保留最近 N 份) → 事务内恢复。
任一步失败即中止, 当前数据库保持原样(旧数据不受影响)。
"""

import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...snapshot import (
    SnapshotError,
    download_snapshot,
    ensure_replica_role,
    prune_snapshots,
    restore_snapshot,
    save_snapshot_file,
    validate_snapshot,
)

logger = logging.getLogger(__name__)

DEFAULT_KEEP = 7


class Command(BaseCommand):
    help = '从主库拉取快照并恢复(仅 EAW_ROLE=replica 的副本实例可执行)'

    def add_arguments(self, parser):
        parser.add_argument('--url', default=None, help='覆盖 EAW_SYNC_URL')
        parser.add_argument('--token', default=None, help='覆盖 EAW_SYNC_TOKEN')
        parser.add_argument('--snapshot-dir', default=None, help='覆盖 EAW_SNAPSHOT_DIR')
        parser.add_argument('--keep', type=int, default=DEFAULT_KEEP,
                            help=f'保留最近几份快照(默认 {DEFAULT_KEEP})')
        parser.add_argument('--dry-run', action='store_true',
                            help='只下载并校验,不写数据库')

    def handle(self, *args, **options):
        # 0) 角色守卫: 在下载之前就拒绝非副本实例, 避免误连网络后才发现角色不符
        try:
            ensure_replica_role()
        except SnapshotError as exc:
            raise CommandError(str(exc))

        url = options['url'] or getattr(settings, 'EAW_SYNC_URL', '')
        token = options['token'] or getattr(settings, 'EAW_SYNC_TOKEN', '')
        snapshot_dir = Path(
            options['snapshot_dir']
            or getattr(settings, 'EAW_SNAPSHOT_DIR', settings.BASE_DIR / 'snapshots')
        )

        if not url:
            raise CommandError('未配置快照地址: 请设置 EAW_SYNC_URL 或传入 --url')
        if not token:
            raise CommandError('未配置同步令牌: 请设置 EAW_SYNC_TOKEN 或传入 --token')

        # 1) 下载
        self.stdout.write(f'拉取快照: {url}')
        try:
            data = download_snapshot(url, token)
        except SnapshotError as exc:
            raise CommandError(str(exc))
        meta = data.get('meta', {})
        self.stdout.write(f"  来源: {meta.get('source', '?')!r}, 生成时间: {meta.get('created_at', '?')}")

        # 2) 校验(先于任何写操作, 非法快照不落盘、不写库)
        try:
            counts = validate_snapshot(data)
        except SnapshotError as exc:
            raise CommandError(f'快照校验失败, 已中止(数据库未改动): {exc}')

        # 3) 落盘并轮换
        saved_path = save_snapshot_file(data, snapshot_dir)
        removed = prune_snapshots(snapshot_dir, keep=options['keep'])
        self.stdout.write(f'  已保存: {saved_path}')
        for old in removed:
            self.stdout.write(f'  已清理旧快照: {old.name}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('[dry-run] 校验通过,未写入数据库:'))
            for key in ('users', 'categories', 'review_days', 'items', 'wechat_profiles'):
                self.stdout.write(f'  {key}: {counts.get(key, 0)}')
            return

        # 4) 恢复(事务内; 失败自动回滚, 旧数据保留)
        try:
            result = restore_snapshot(data)
        except SnapshotError as exc:
            raise CommandError(f'恢复失败: {exc}')

        self.stdout.write(self.style.SUCCESS('同步完成:'))
        for key in ('users', 'categories', 'review_days', 'items', 'wechat_profiles'):
            self.stdout.write(f'  {key}: {result.get(key, 0)}')
        self.stdout.write(
            f"  用户: 新增 {result.get('users_created', 0)}, "
            f"更新 {result.get('users_updated', 0)}"
        )
