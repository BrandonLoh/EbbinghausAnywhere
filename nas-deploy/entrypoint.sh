#!/bin/bash
# 容器入口:迁移 → 收集静态文件 → 启动传入的命令(默认 gunicorn)
set -e

echo "[entrypoint] 执行数据库迁移..."
python manage.py migrate --noinput

echo "[entrypoint] 收集静态文件..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] 启动: $*"
exec "$@"
