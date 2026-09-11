# Ebbinghaus Anywhere —— NAS 副本镜像
#
# 构建上下文为仓库根目录, 用 docker-compose 构建:
#   cd nas-deploy && docker compose build
#
# 镜像内容 = 应用代码 + 主依赖 + NAS 专属依赖(gunicorn / whitenoise)。
# 数据库与快照不打包进镜像, 由 compose 挂载卷提供。

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 主依赖(与 PA 完全一致的版本, 见 requirements.txt)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# NAS 专属依赖(仅副本容器需要; PA 上不安装这两个)
RUN pip install --no-cache-dir gunicorn==23.0.0 whitenoise==6.12.0

# 应用代码(不需要的文件已由 .dockerignore 排除)
COPY . .

# 入口脚本负责: 迁移 → 收集静态文件 → 启动 gunicorn
COPY nas-deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "EbbinghausAnywhere.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
