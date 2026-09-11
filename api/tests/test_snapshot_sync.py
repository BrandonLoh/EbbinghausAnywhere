"""快照同步测试:构建 → 校验 → 恢复的完整语义。

重点覆盖(M2 验收标准):
- roundtrip:导出后恢复,数据(含主键、密码哈希、音标等)逐字段一致
- 幂等:重复恢复结果一致
- NAS 本地管理员不被删除,同名用户以主库为准
- 角色守卫:非 replica 实例拒绝恢复(防止旧快照覆盖主库)
- 快照校验:格式/外键完整性,非法快照在任何写操作前被拒绝
- 事务性:恢复中途失败则整体回滚,旧数据保留
- 主键保留:用户 id 与本地不同时,条目外键经映射正确重写
"""

import json
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from api.models import WeChatProfile
from api.snapshot import (
    SnapshotError,
    build_snapshot,
    download_snapshot,
    prune_snapshots,
    restore_snapshot,
    save_snapshot_file,
    validate_snapshot,
)
from EAW.models import Category, Item, ReviewDay, Proficiency


def _make_snapshot(**overrides):
    """一个最小但完整的快照(2 用户 / 2 类别 / 2 复习日 / 2 条目 / 1 绑定)。"""
    data = {
        'meta': {'format': 1, 'created_at': '2026-09-11T03:00:00+08:00', 'source': 'pa'},
        'users': [
            {'id': 1, 'username': 'ellie', 'email': 'e@x.com', 'first_name': 'Ellie',
             'last_name': 'L', 'password': 'pbkdf2_sha256$260000$aaa$bbb',
             'is_staff': True, 'is_active': True, 'is_superuser': False},
            {'id': 2, 'username': 'brandon', 'email': 'b@x.com', 'first_name': 'Brandon',
             'last_name': 'L', 'password': 'pbkdf2_sha256$260000$ccc$ddd',
             'is_staff': True, 'is_active': True, 'is_superuser': True},
        ],
        'categories': [
            {'id': 10, 'user_id': 1, 'name': '单词', 'sort_order': 1, 'is_default': True},
            {'id': 11, 'user_id': 1, 'name': '语法', 'sort_order': 2, 'is_default': False},
        ],
        'review_days': [
            {'id': 20, 'user_id': 1, 'day': 1},
            {'id': 21, 'user_id': 1, 'day': 7},
        ],
        'items': [
            {'id': 30, 'user_id': 1, 'item': 'apple', 'content': '苹果\nn.',
             'inputDate': '2026-01-01', 'initDate': '2026-01-01', 'proficiency': 1,
             'category_id': 10, 'src_tts': 'https://tsn.baidu.com/a.mp3',
             'us_phonetic': 'ˈæpəl', 'uk_phonetic': 'ˈæpl'},
            {'id': 31, 'user_id': 1, 'item': 'run', 'content': '跑',
             'inputDate': '2026-02-02', 'initDate': '2026-02-02', 'proficiency': 0,
             'category_id': 11, 'src_tts': None, 'us_phonetic': None, 'uk_phonetic': None},
        ],
        'wechat_profiles': [
            {'id': 40, 'user_id': 1, 'openid': 'openid-ellie',
             'created_at': '2026-03-01T10:00:00+08:00'},
        ],
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------- 构建与校验

class BuildSnapshotTests(TestCase):
    def test_build_matches_current_data(self):
        user = User.objects.create_user('ellie', 'e@x.com', 'x-12345678')
        category = Category.objects.create(user=user, name='单词', sort_order=1, is_default=True)
        Item.objects.create(user=user, item='apple', content='苹果', category=category,
                            inputDate=date(2026, 1, 1), initDate=date(2026, 1, 2),
                            proficiency=Proficiency.MASTERED, us_phonetic='x')
        WeChatProfile.objects.create(user=user, openid='oid')

        data = build_snapshot(source='test-host')

        self.assertEqual(data['meta']['format'], 1)
        self.assertEqual(data['meta']['source'], 'test-host')
        row = data['items'][0]
        self.assertEqual(row['item'], 'apple')
        self.assertEqual(row['inputDate'], '2026-01-01')
        self.assertEqual(row['initDate'], '2026-01-02')
        self.assertEqual(row['proficiency'], Proficiency.MASTERED)
        self.assertEqual(row['category_id'], category.pk)
        self.assertEqual(data['users'][0]['password'], user.password)  # 哈希原样
        self.assertEqual(data['wechat_profiles'][0]['openid'], 'oid')

    def test_built_snapshot_passes_validation(self):
        user = User.objects.create_user('ellie', 'e@x.com', 'x-12345678')
        Category.objects.create(user=user, name='单词', is_default=True)
        counts = validate_snapshot(build_snapshot())
        self.assertEqual(counts['users'], 1)


class ValidateSnapshotTests(TestCase):
    def test_valid_snapshot_returns_counts(self):
        counts = validate_snapshot(_make_snapshot())
        self.assertEqual(counts['users'], 2)
        self.assertEqual(counts['items'], 2)

    def test_wrong_format_rejected(self):
        data = _make_snapshot()
        data['meta']['format'] = 99
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_missing_section_rejected(self):
        data = _make_snapshot()
        del data['items']
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_dangling_user_reference_rejected(self):
        data = _make_snapshot()
        data['items'][0]['user_id'] = 999
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_dangling_category_reference_rejected(self):
        data = _make_snapshot()
        data['items'][0]['category_id'] = 999
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_bad_date_rejected(self):
        data = _make_snapshot()
        data['items'][0]['inputDate'] = 'not-a-date'
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_null_category_allowed(self):
        data = _make_snapshot()
        data['items'][0]['category_id'] = None
        counts = validate_snapshot(data)
        self.assertEqual(counts['items'], 2)

    def test_empty_string_fields_allowed(self):
        """回归测试: 主库存在条目名为空字符串的历史数据(真实案例 id=5466),
        校验只拦结构性损坏, 必须放行空字符串, 否则同步永久失败。"""
        data = _make_snapshot()
        data['items'][0]['item'] = ''
        data['items'][0]['content'] = ''
        data['categories'][0]['name'] = ''
        counts = validate_snapshot(data)
        self.assertEqual(counts['items'], 2)
        self.assertEqual(counts['categories'], 2)

    def test_missing_key_still_rejected(self):
        """字段整个缺失(不是空字符串)仍必须拦下。"""
        data = _make_snapshot()
        del data['items'][0]['item']
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)

    def test_none_value_still_rejected(self):
        """显式 null 仍必须拦下。"""
        data = _make_snapshot()
        data['items'][0]['item'] = None
        with self.assertRaises(SnapshotError):
            validate_snapshot(data)


# ---------------------------------------------------------------- 恢复语义

@override_settings(EAW_ROLE='replica')
class RestoreSnapshotTests(TestCase):
    def test_restores_full_dataset(self):
        counts = restore_snapshot(_make_snapshot())

        self.assertEqual(counts['items'], 2)
        self.assertEqual(counts['users_created'], 2)
        self.assertEqual(User.objects.count(), 2)

        # 主键保留(NAS 上 id 与主库一致)
        item = Item.objects.get(pk=30)
        self.assertEqual(item.item, 'apple')
        self.assertEqual(item.us_phonetic, 'ˈæpəl')
        self.assertEqual(item.src_tts, 'https://tsn.baidu.com/a.mp3')
        self.assertEqual(item.inputDate, date(2026, 1, 1))
        self.assertEqual(item.proficiency, Proficiency.MASTERED)
        self.assertEqual(item.category.name, '单词')
        self.assertEqual(Item.objects.get(pk=30).user.username, 'ellie')

        # 密码哈希随快照恢复(登录行为与主库一致)
        self.assertEqual(User.objects.get(username='ellie').password,
                         'pbkdf2_sha256$260000$aaa$bbb')

        # 类别/复习日/绑定
        grammar = Category.objects.get(pk=11)
        self.assertEqual(grammar.name, '语法')
        self.assertFalse(grammar.is_default)
        self.assertEqual(ReviewDay.objects.filter(user__username='ellie').count(), 2)
        binding = WeChatProfile.objects.get(openid='openid-ellie')
        self.assertEqual(binding.user.username, 'ellie')
        # created_at 按快照值还原(不被 auto_now_add 覆盖)
        self.assertEqual(binding.created_at.year, 2026)
        self.assertEqual(binding.created_at.month, 3)

    def test_idempotent_repeated_restore(self):
        restore_snapshot(_make_snapshot())
        counts = restore_snapshot(_make_snapshot())  # 第二次

        self.assertEqual(Item.objects.count(), 2)
        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(ReviewDay.objects.count(), 2)
        self.assertEqual(WeChatProfile.objects.count(), 1)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(counts['users_created'], 0)  # 第二次全部为更新
        self.assertEqual(counts['users_updated'], 2)

    def test_preserves_local_admin_and_removes_local_business_data(self):
        """NAS 本地账号保留; 本地业务数据(不属于快照)被清理 —— 副本语义。"""
        local_admin = User.objects.create_superuser('nasadmin', 'n@x.com', 'nas-pass-123')
        local_category = Category.objects.create(user=local_admin, name='本地类别', is_default=True)
        Item.objects.create(user=local_admin, item='本地条目', category=local_category,
                            inputDate=date(2026, 1, 1), initDate=date(2026, 1, 1))

        restore_snapshot(_make_snapshot())

        # 本地管理员保留(且密码未被覆盖)
        nasadmin = User.objects.get(username='nasadmin')
        self.assertTrue(nasadmin.is_superuser)
        self.assertTrue(nasadmin.check_password('nas-pass-123'))
        # 本地业务数据被快照数据替换
        self.assertFalse(Item.objects.filter(item='本地条目').exists())
        self.assertEqual(Item.objects.count(), 2)

    def test_same_username_takes_snapshot_data(self):
        """NAS 上与主库同名(不同人)的账号:以主库为准。"""
        User.objects.create_user('ellie', 'local@x.com', 'local-pass-123')

        restore_snapshot(_make_snapshot())

        ellie = User.objects.get(username='ellie')
        self.assertEqual(ellie.email, 'e@x.com')
        self.assertEqual(User.objects.filter(username='ellie').count(), 1)

    def test_foreign_keys_remapped_when_local_ids_differ(self):
        """本地已存在用户占用 id=1 时, 快照用户获得新 id, 条目外键仍指向正确用户。"""
        User.objects.create_user('nasadmin', 'n@x.com', 'x-12345678')  # 占用 id=1

        restore_snapshot(_make_snapshot())

        ellie = User.objects.get(username='ellie')
        self.assertNotEqual(ellie.pk, 1)  # 本地 id 与快照 id 不同
        self.assertEqual(Item.objects.get(pk=30).user_id, ellie.pk)  # 但外键已重映射
        self.assertEqual(Category.objects.get(pk=10).user_id, ellie.pk)

    def test_rollback_on_failure_keeps_old_data(self):
        """恢复中途失败: 整体回滚, 旧数据保留。"""
        user = User.objects.create_user('old', 'o@x.com', 'x-12345678')
        old_category = Category.objects.create(user=user, name='旧类别', is_default=True)
        Item.objects.create(user=user, item='旧数据', category=old_category,
                            inputDate=date(2026, 1, 1), initDate=date(2026, 1, 1))

        data = _make_snapshot()
        data['items'][0]['proficiency'] = 'not-an-int'  # 触发 bulk_create 阶段失败

        with self.assertRaises(Exception):
            restore_snapshot(data)

        self.assertTrue(Item.objects.filter(item='旧数据').exists())
        self.assertTrue(Category.objects.filter(name='旧类别').exists())
        self.assertTrue(User.objects.filter(username='old').exists())

    def test_restores_empty_string_item_name(self):
        """端到端回归: 主库存在空名称条目(真实案例 id=5466)时, 恢复必须成功。"""
        data = _make_snapshot()
        data['items'][0]['item'] = ''
        data['items'][0]['content'] = ''

        restore_snapshot(data)

        restored = Item.objects.get(pk=30)
        self.assertEqual(restored.item, '')
        self.assertEqual(restored.content, '')
        # 其余字段不受影响
        self.assertEqual(restored.us_phonetic, 'ˈæpəl')


# ---------------------------------------------------------------- 角色守卫

class RoleGuardTests(TestCase):
    @override_settings(EAW_ROLE='master')
    def test_restore_refused_on_master(self):
        with self.assertRaises(SnapshotError) as ctx:
            restore_snapshot(_make_snapshot())
        self.assertIn('replica', str(ctx.exception))
        self.assertEqual(User.objects.count(), 0)  # 未写入任何数据

    @override_settings(EAW_ROLE='master')
    def test_restore_command_refused_on_master(self):
        with TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / 's.json'
            snapshot_path.write_text(json.dumps(_make_snapshot()), encoding='utf-8')
            with self.assertRaises(CommandError) as ctx:
                call_command('restore_snapshot', '--file', str(snapshot_path))
        self.assertIn('replica', str(ctx.exception))
        self.assertEqual(User.objects.count(), 0)

    @override_settings(EAW_ROLE='replica')
    def test_restore_command_works_on_replica(self):
        with TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / 's.json'
            snapshot_path.write_text(json.dumps(_make_snapshot()), encoding='utf-8')
            out = StringIO()
            call_command('restore_snapshot', '--file', str(snapshot_path), stdout=out)
        self.assertEqual(Item.objects.count(), 2)
        self.assertIn('恢复完成', out.getvalue())

    @override_settings(EAW_ROLE='replica')
    def test_dry_run_writes_nothing(self):
        with TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / 's.json'
            snapshot_path.write_text(json.dumps(_make_snapshot()), encoding='utf-8')
            out = StringIO()
            call_command('restore_snapshot', '--file', str(snapshot_path),
                         '--dry-run', stdout=out)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Item.objects.count(), 0)
        self.assertIn('dry-run', out.getvalue())

    @override_settings(EAW_ROLE='replica')
    def test_missing_file_reports_error(self):
        with self.assertRaises(CommandError):
            call_command('restore_snapshot', '--file', 'no-such-file.json')


# ---------------------------------------------------------------- 下载与轮换

class DownloadTests(TestCase):
    @patch('api.snapshot.requests.get')
    def test_download_returns_parsed_json(self, mock_get):
        payload = _make_snapshot()
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = payload

        data = download_snapshot('https://pa.example/api/v1/backup/snapshot/', 'tok')
        self.assertEqual(data['meta']['format'], 1)
        # 认证头正确
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs['headers']['Authorization'], 'Token tok')

    @patch('api.snapshot.requests.get')
    def test_download_http_error_raises(self, mock_get):
        mock_get.return_value.status_code = 401
        with self.assertRaises(SnapshotError):
            download_snapshot('https://pa.example/x', 'bad-token')


class SnapshotFileTests(TestCase):
    def test_save_and_prune(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for i in range(10):
                save_snapshot_file({'n': i}, directory)
            removed = prune_snapshots(directory, keep=7)
            self.assertEqual(len(removed), 3)
            self.assertEqual(len(list(directory.glob('snapshot_*.json'))), 7)


# ---------------------------------------------------------------- sync_snapshot 命令

@override_settings(EAW_ROLE='replica', EAW_SYNC_URL='https://pa.example/snap/',
                   EAW_SYNC_TOKEN='tok-123')
class SyncSnapshotCommandTests(TestCase):
    @patch('api.snapshot.requests.get')
    def test_sync_downloads_restores_and_keeps_file(self, mock_get):
        payload = _make_snapshot()
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = payload

        with TemporaryDirectory() as tmp:
            out = StringIO()
            call_command('sync_snapshot', '--snapshot-dir', tmp, stdout=out)

            self.assertEqual(Item.objects.count(), 2)
            self.assertEqual(len(list(Path(tmp).glob('snapshot_*.json'))), 1)
        self.assertIn('同步完成', out.getvalue())

    @patch('api.snapshot.requests.get')
    def test_sync_dry_run_does_not_restore(self, mock_get):
        payload = _make_snapshot()
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = payload

        with TemporaryDirectory() as tmp:
            out = StringIO()
            call_command('sync_snapshot', '--snapshot-dir', tmp, '--dry-run', stdout=out)
            self.assertEqual(Item.objects.count(), 0)
            self.assertEqual(len(list(Path(tmp).glob('snapshot_*.json'))), 1)
        self.assertIn('dry-run', out.getvalue())

    @patch('api.snapshot.requests.get')
    def test_sync_invalid_snapshot_aborts_everything(self, mock_get):
        bad = _make_snapshot()
        bad['meta']['format'] = 99
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = bad

        with TemporaryDirectory() as tmp:
            with self.assertRaises(CommandError):
                call_command('sync_snapshot', '--snapshot-dir', tmp)
            # 非法快照不落盘、不写库
            self.assertEqual(list(Path(tmp).glob('snapshot_*.json')), [])
        self.assertEqual(Item.objects.count(), 0)

    @override_settings(EAW_SYNC_URL='', EAW_SYNC_TOKEN='')
    def test_sync_requires_config(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('sync_snapshot')
        self.assertIn('EAW_SYNC_URL', str(ctx.exception))

    @override_settings(EAW_ROLE='master')
    def test_sync_refused_on_master(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(CommandError) as ctx:
                call_command('sync_snapshot', '--snapshot-dir', tmp,
                             '--url', 'https://x/y', '--token', 't', '--dry-run')
        self.assertIn('replica', str(ctx.exception))
