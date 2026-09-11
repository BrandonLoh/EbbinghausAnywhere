"""restore_snapshot:从本地快照文件恢复数据(仅副本实例)。

用法:
    python manage.py restore_snapshot --file snapshot.json [--dry-run]

角色守卫:必须设置 EAW_ROLE=replica 才允许执行,防止在 PA(主库)上误跑
旧快照反向覆盖生产数据。--dry-run 只校验不写库,可在正式恢复前安全检查。
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...snapshot import SnapshotError, restore_snapshot, validate_snapshot


class Command(BaseCommand):
    help = '从本地快照 JSON 文件恢复数据(仅 EAW_ROLE=replica 的副本实例可执行)'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='快照 JSON 文件路径')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只校验快照,不写数据库',
        )

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.is_file():
            raise CommandError(f'快照文件不存在: {path}')

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise CommandError(f'快照文件不是合法 JSON: {exc}')

        try:
            if options['dry_run']:
                counts = validate_snapshot(data)
                self.stdout.write(self.style.WARNING('[dry-run] 校验通过,未写入数据库:'))
            else:
                counts = restore_snapshot(data)
                self.stdout.write(self.style.SUCCESS('恢复完成:'))
        except SnapshotError as exc:
            raise CommandError(str(exc))

        for key in ('users', 'categories', 'review_days', 'items', 'wechat_profiles'):
            self.stdout.write(f'  {key}: {counts.get(key, 0)}')
        if not options['dry_run']:
            self.stdout.write(
                f"  用户: 新增 {counts.get('users_created', 0)}, "
                f"更新 {counts.get('users_updated', 0)}"
            )
