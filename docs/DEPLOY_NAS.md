# NAS 部署操作清单(数据副本 + 每日同步)

> 目标:在群晖/QNAP 上以 Docker 运行一个**只读副本**,每天 04:00 自动从
> PythonAnywhere 主库拉取全量数据。NAS 数据最多落后主库 24 小时。
>
> 前置:主库(PA)已部署 2.2.0 及以上版本(含 `/api/v1/backup/snapshot/` 端点与
> `sync_snapshot` 命令),见 [DEPLOY_PYTHONANYWHERE.md](DEPLOY_PYTHONANYWHERE.md)。

## 架构回顾

```
PA(PythonAnywhere, 主库)  ──每日全量快照(NAS 主动拉取)──►  NAS(Docker, 只读副本)
    唯一写入入口                                            数据被覆盖, 不要在此录入
```

- **NAS 不需要公网可达**、不需要开任何端口映射——同步是 NAS 主动发起的出站 HTTPS 请求。
- 副本上的**写入会在次日同步时被覆盖**,请只在主库录入数据。

---

## Step 0. 在 PA 上创建同步专用账号与令牌

在 PythonAnywhere 的 Bash 控制台执行(主库侧):

```bash
cd ~/EbbinghausAnywhere && workon <虚拟环境名>
python manage.py shell -c "
from django.contrib.auth.models import User
u, created = User.objects.get_or_create(username='syncbot')
u.is_staff = True; u.is_superuser = True
u.set_password('<生成一个随机强密码>')
u.save()
print('syncbot ready, created =', created)
"
python manage.py drf_create_token syncbot
# ✅ 输出: Generated token <40位字符串> for user syncbot
```

**把 token 记到密码管理器**,下一步要填进 NAS 的 `.env`。
(`syncbot` 只用于拉快照,不用于登录网站;如 token 泄露,在 PA 上删除该账号即可。)

## Step 1. NAS 上准备代码

在 NAS 上(以群晖为例,`/volume1/docker/ebbinghaus/` 为部署目录):

```bash
# 方式 A:git 克隆(推荐,便于日后 git pull 更新)
cd /volume1/docker
git clone <你的仓库地址> ebbinghaus
cd ebbinghaus/nas-deploy

# 方式 B:从本地电脑上传整个项目目录到 NAS
```

> 方式 B 上传时建议**排除** `venv/`(数百 MB)、`debug.log`、`db.sqlite3`、
> `staticfiles/`、`__pycache__/` 等本地运行产物;否则上传很慢且无意义。
> (不排除也**不影响运行**:构建镜像时 `.dockerignore` 会自动忽略这些文件,
> 且容器使用的数据库固定为 `data/db.sqlite3`——副本的数据一律来自同步,
> 上传的旧库文件不会被使用。排除只是为了省上传时间与 NAS 磁盘空间。)

### 关于目录与权限(常见疑问)

**代码目录本身不需要设置任何权限**:Docker 在群晖/QNAP 上以 root 运行,能直接读取
你上传的代码;放在 `/volume1/docker/` 这类标准位置即可,无需 chmod/chown。
需要留意的只有三处:

1. **`.env` 建议限制为仅自己可读** —— 它是唯一含敏感信息的文件(SECRET_KEY 与主库
   同步令牌)。有 SSH 时执行 `chmod 600 .env`;无 SSH 则在 File Station 中右键
   `.env` → 属性 → 权限,去掉其他用户/群组的读取权限。
2. **建议提前手动创建 `nas-deploy/data` 空目录**(File Station 新建文件夹即可)。
   容器会以 root 身份在其中写入数据库与快照:若目录由 Docker 自动创建,其归属为
   root,日后你在 File Station 中清理旧快照会提示权限不足;自己先建好则清理方便。
   容器生成的文件(`data/db.sqlite3`、`data/snapshots/`)显示属主为 root 属**正常现象**,
   不影响使用;需要整目录清空时用 SSH:`sudo rm -rf /volume1/docker/ebbinghaus/nas-deploy/data`。
3. **从 Windows 直接上传时注意脚本换行符** —— 若 `sync.sh` 等脚本被保存为 CRLF 换行,
   在 Linux 上执行会报 `$'\r': command not found`。上传后修正一次即可
   (注意按当前所在目录选择路径, 两种写法等价):
   ```bash
   # 在项目根目录:
   sed -i 's/\r$//' nas-deploy/*.sh
   # 或当前已在 nas-deploy 目录内:
   sed -i 's/\r$//' *.sh
   ```
   (用方式 A 的 git clone 不会有此问题——仓库已通过 `.gitattributes` 强制脚本使用 LF;
   容器入口脚本另有 Dockerfile 内兜底处理。)

## Step 2. 配置 .env

```bash
cd nas-deploy
cp .env.example .env
```

编辑 `.env`,填写两项:

```ini
SECRET_KEY=<在 NAS 上生成,见下>
EAW_SYNC_URL=https://ebbinghaus.pythonanywhere.com/api/v1/backup/snapshot/
EAW_SYNC_TOKEN=<Step 0 生成的主库 token>
```

生成 SECRET_KEY(**副本用独立的密钥,与 PA 的可以不同**;NAS 上无需安装任何依赖):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# 无 python3 时可用: openssl rand -base64 48(任何足够长的随机字符串均可)
```

> 不用 Django 生成(宿主机上没有 Django,且其默认字符集含 `$`、`#` 等,
> 在 .env 文件中易被误解析);`secrets.token_urlsafe` 的输出字符集对 .env 完全安全。

> `.env` 已被 git 忽略,切勿提交到仓库。

## Step 3. 构建并启动

```bash
cd nas-deploy
docker compose up -d --build     # 旧版环境用 docker-compose up -d --build
docker compose ps                # 确认 web 容器 Up
docker compose logs -f web       # 看到 gunicorn 启动日志即成功(Ctrl+C 退出)
```

> **群晖权限提示**:若报 `permission denied ... /var/run/docker.sock`,执行一次
> `sudo chown root:docker /var/run/docker.sock` 即可(docker 组与你的成员身份
> 通常已由 Container Manager 建好,唯一缺的是 socket 的属组)。
> 不想改系统配置的话,在命令前加 `sudo` 也能继续(定时任务以 root 运行,不受影响)。
> 详见「故障排查」末尾。

启动过程会自动执行:数据库迁移 → 收集静态文件 → gunicorn 监听 8000。
NAS 侧访问地址:**http://<NAS的IP>:8086/**(端口在 `docker-compose.yml` 中可改)。

## Step 4. 创建 NAS 本地应急管理员

副本首次启动后,数据库里还没有任何账号。先建一个**本地管理员**(它不会被同步删除):

```bash
docker compose exec web python manage.py createsuperuser
```

## Step 5. 首次同步(手动,先演练后正式)

```bash
# 5a. 演练:只下载+校验,不写数据库(确认能连上主库、快照合法)
docker compose exec -T web python manage.py sync_snapshot --dry-run

# 预期输出(数字与你的数据规模一致):
#   拉取快照: https://ebbinghaus.pythonanywhere.com/api/v1/backup/snapshot/
#     来源: 'ebbinghaus.pythonanywhere.com', 生成时间: ...
#     已保存: /data/snapshots/snapshot_YYYYmmdd_HHMMSS.json
#   [dry-run] 校验通过,未写入数据库:
#     users: N ...

# 5b. 正式同步
docker compose exec -T web python manage.py sync_snapshot --keep 7
```

> **数据量参考**:本地演练(19 用户 / 9218 条目)全程约 10 秒,快照约 4 MB。

## Step 6. 验证

- [ ] 浏览器打开 `http://<NAS的IP>:8086/`,用**主库账号密码**登录(密码哈希随快照同步,直接可用)
- [ ] 条目列表/复习页/搜索正常,内容与主库一致
- [ ] 页面样式正常(静态文件由容器内 WhiteNoise 提供)
- [ ] 应急管理员仍可登录(确认同步不会删除本地账号)

## Step 7. 配置每日定时任务

### 群晖(Synology)

1. 控制面板 → 任务计划 → 新增 → 计划的任务 → **用户定义的脚本**
2. 常规:名称 `Ebbinghaus同步`,用户账户选 **root**
3. 计划:每天,时间 `04:00`
4. 任务设置 → 运行命令:
   ```bash
   bash /volume1/docker/ebbinghaus/nas-deploy/sync.sh
   ```
5. 勾选「任务失败时发送电子邮件」,同步失败当天即可收到告警

### QNAP

在 crontab 中添加(路径按实际调整):

```
0 4 * * * /bin/bash /share/Container/ebbinghaus/nas-deploy/sync.sh >> /share/Container/ebbinghaus/sync-cron.log 2>&1
```

## Step 8. 观察前三天

- [ ] `docker compose exec -T web ls -lt /data/snapshots/ | head`(应每天多一份,只保留 7 份)
- [ ] 群晖任务计划「操作 → 上次运行结果」应为成功
- [ ] 抽查一条 NAS 上的数据与主库一致

---

## 日常运维

| 场景 | 操作 |
|---|---|
| 主库升级后同步 NAS 代码 | `cd ebbinghaus && git pull && cd nas-deploy && docker compose up -d --build` |
| 查看同步日志 | 群晖任务计划的历史记录;或手动执行 `sync.sh` 观察输出 |
| 查看应用日志 | `docker compose logs web` |
| 手动触发一次同步 | `bash nas-deploy/sync.sh`(未配置免 sudo 时用 `sudo bash nas-deploy/sync.sh`) |
| 重启服务 | `docker compose restart` |

## 回滚:用旧快照恢复

每次同步都会在 `/data/snapshots/` 保留最近 7 份快照。若某天的数据异常,
可指定更早的快照恢复:

```bash
docker compose exec -T web python manage.py restore_snapshot \
    --file /data/snapshots/snapshot_20260910_040001.json
```

## 故障排查

| 现象 | 原因与处理 |
|---|---|
| `Failed to load .../.env: no such file or directory` | 尚未创建配置文件:执行 `cp .env.example .env` 并填入 SECRET_KEY / EAW_SYNC_TOKEN 后再运行 `docker compose up -d --build` |
| 同步报 `401` | `EAW_SYNC_TOKEN` 失效:在 PA 上 `python manage.py drf_create_token syncbot --reset` 重新生成并更新 `.env`,然后 `docker compose up -d` |
| 同步报 HTTP 5xx | 主库临时故障;保持原样,次日会自动重试 |
| 同步报「快照校验失败」 | 快照内容异常,数据库未被改动;查看输出中的具体行号信息 |
| 端口 8086 被占用 | 修改 `docker-compose.yml` 中的端口映射(如 `8087:8000`)后 `docker compose up -d` |
| 忘了本地管理员密码 | `docker compose exec web python manage.py changepassword <用户名>` |
| 想清空重来 | 停止容器 → 删除 `nas-deploy/data/` 目录 → 重新执行 Step 3-5。若 File Station 提示权限不足(目录归 root),用 SSH:`sudo rm -rf /volume1/docker/ebbinghaus/nas-deploy/data` |
| `$'\r': command not found` | 脚本被 Windows 保存成了 CRLF 换行;在 nas-deploy 目录内执行 `sed -i 's/\r$//' *.sh` 修正 |
| `permission denied ... /var/run/docker.sock` | socket 属组不是 docker:执行 `sudo chown root:docker /var/run/docker.sock`;或临时在命令前加 `sudo`。详见文末「免 sudo 使用 docker」 |
| 构建时 `pip install` 极慢(国内直连 PyPI 约 10 kB/s) | 属网络带宽问题,非故障。换镜像源重建,详见文末「构建极慢(国内网络)」 |

### 群晖:免 sudo 使用 docker(可选)

**不配置完全没问题**:所有命令前加 `sudo` 即可;每日定时任务以 root 运行,不受影响。
只有想省去每次敲 `sudo` 时才需要下面的配置。

DSM 上 `/var/run/docker.sock` 的属主通常是 `root:root`,而 DSM 7.2 的 Container Manager
一般已预建好 `docker` 组(管理员账号可能已在组内,**核心步骤只是让 socket 属于 docker 组**):

```bash
# 1. 看当前属主(通常显示为 root root)
ls -l /var/run/docker.sock

# 2. 让 docker 组有权访问 socket(核心步骤)
sudo chown root:docker /var/run/docker.sock

# 3. 验证(不需要 sudo)
docker ps
```

若第 3 步仍报权限错误,按序检查:

- 你的账号是否在 docker 组内:`grep '^docker:' /etc/group`(组名后应列出你的用户名);
- 不在则加入:`sudo synogroup --memberadd docker <用户名>`;
- 已在组内但仍不生效:组权限在登录时加载,**退出 SSH 重新登录**,用 `id` 确认会话包含 docker。

注意:
- 对已存在的 docker 组执行 `synogroup --add docker` 会报
  `SYNOLocalAccountGroupSet failed, synoerr=0x1700`——这只是"组已存在"的提示,
  属正常现象,直接跳过创建步骤即可;
- 加入 docker 组等价于获得 root 权限,只对信任的账号操作;
- 重启 Container Manager 后 socket 属主可能被重置,届时重跑第 2 步 `chown` 即可。

### 构建极慢(国内网络):使用镜像源

首次构建需从 PyPI 下载约 15 MB 依赖,国内直连可能只有 ~10 kB/s(十几分钟)。改用国内镜像
可把依赖下载缩短到几十秒:

```bash
cd /volume1/docker/EbbinghausAnywhere

# 若构建仍在进行,先 Ctrl+C 中断;然后在两条 pip 命令中加入镜像参数
sed -i 's#pip install --no-cache-dir#pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple#g' nas-deploy/Dockerfile
grep -n 'pip install' nas-deploy/Dockerfile     # 确认两行均带 -i(应为 2 行)

# 重新构建(已完成的层会复用缓存)
cd nas-deploy && docker compose up -d --build
```

也可改用阿里云源 `https://mirrors.aliyun.com/pypi/simple/`。
Dockerfile 已支持构建参数 `PIP_INDEX_URL`,或取消 `docker-compose.yml` 中
`build.args` 注释后长期使用镜像。

> 更省事的替代(管理员账号适用,一条命令跳过组创建):
> `sudo chgrp administrators /var/run/docker.sock`,重新登录即可。

注意:
- 加入 docker 组等价于获得 root 权限,只对信任的账号操作;
- 有反馈称重启 Container Manager 后 socket 属主会被重置,届时重跑 `chown` 即可;
- 若 `--memberadd` 不被识别(旧版 DSM),改用 `--member`(此时组内成员很少,注意它会覆盖成员列表)。

## 设计要点(为什么这样部署)

- **单向下拉 + 全量快照**:NAS 无需公网可达,同步逻辑简单可靠、幂等可重放。
- **角色守卫**:`sync_snapshot` / `restore_snapshot` 仅在 `EAW_ROLE=replica` 的实例
  上允许执行。即使在 PA 上误跑这些命令也会被直接拒绝,旧快照永远无法反向覆盖主库。
- **事务化恢复**:恢复在单个数据库事务内完成,中途失败整体回滚,旧数据不受影响。
- **令牌不跨实例**:快照不含 API token 表,PA 的 token 在 NAS 上无效,反之亦然。
