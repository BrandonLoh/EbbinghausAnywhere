#!/bin/bash
# Ebbinghaus Anywhere —— NAS 每日同步脚本
#
# 由群晖「任务计划」(或 QNAP crontab)每天定时调用, 例如 04:00:
#   bash /volume1/docker/ebbinghaus/nas-deploy/sync.sh
#
# 流程: 拉取主库快照 → 校验 → 落盘(保留最近 7 份) → 事务内恢复。
# 任一步失败即中止, NAS 数据库保持原样; 退出码非 0, 任务计划可据此告警。

set -euo pipefail

# 定位到本脚本所在目录(nas-deploy/), 以便找到 .env 与 docker-compose.yml
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 兼容新旧两种命令: 群晖 Container Manager 为 `docker compose`,
# 部分 QNAP/旧版环境为 `docker-compose`
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "[sync] 错误: 未找到 docker compose / docker-compose"
    exit 1
fi

echo "===== 同步开始: $(date '+%Y-%m-%d %H:%M:%S') ====="

# 幂等启动(容器已在运行时为无操作; 刚开机时确保服务可用)
$DC up -d

# 在 web 容器内执行同步命令: 下载 → 校验 → 落盘 → 恢复
# 角色守卫(EAW_ROLE=replica)由容器环境提供
$DC exec -T web python manage.py sync_snapshot --keep 7

echo "===== 同步完成: $(date '+%Y-%m-%d %H:%M:%S') ====="
