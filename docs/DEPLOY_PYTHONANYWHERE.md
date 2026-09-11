# PythonAnywhere 部署操作清单

> 适用:PA 生产实例(ebbinghaus.pythonanywhere.com)每次升级代码后的部署。
> 本文以 **M1 (2.1.0.0, REST API)** 为具体示例,通用步骤今后可复用。
>
> 前置:本地已完成开发与全量测试(125 个测试全绿),并已 `git push` 到 main。

## 变更影响范围(2.1.0.0)

| 项目 | 影响 |
|---|---|
| 数据库 | **仅新增表**(`authtoken_token` 等 4 张 + `api_wechatprofile`),现有表零改动 |
| 现有 Web UI | 零行为变化(模板、视图、静态文件均未改动) |
| 依赖 | 新增 `djangorestframework==3.17.2` |
| WSGI 配置 | **无需任何改动** |
| `.env` | **无需改动**(微信配置到 M3 再加) |
| 静态文件 | 本次无变化,`collectstatic` 可跳过 |

---

## Step 1. 备份数据库(不可跳过)

打开 PythonAnywhere → **Consoles → Bash**,执行:

```bash
# MySQL(本项目 PA 生产库):
mysqldump -u <PA用户名> -h <PA用户名>.mysql.pythonanywhere-services.com \
  '<PA用户名>$<库名>' -p > ~/backup_before_2.1.0.0.sql
# 提示 Enter password: 时输入数据库密码
ls -lh ~/backup_before_2.1.0.0.sql   # 确认文件非空

# 若 PA 上实际是 SQLite:
# cp ~/EbbinghausAnywhere/db.sqlite3 ~/backup_before_2.1.0.0.sqlite3
```

> 本次迁移只建新表、不动旧表,备份是保险措施;有了它,任何意外都可整库回退。

## Step 2. 拉取代码并安装依赖

```bash
cd ~/EbbinghausAnywhere          # 换成你的实际项目目录
git pull                         # 拉到包含本次修复的最新提交
pip install -r requirements.txt  # 主要新增 djangorestframework==3.17.2
pip show djangorestframework | head -2   # 确认安装成功
```

> **安装位置说明**:若控制台提示 `Defaulting to user installation`,说明当前没有
> 激活虚拟环境,包装进 `~/.local/lib/python3.x/site-packages`——PA 的 Web 应用
> 默认能读到该目录,直接可用(重新加载 Web 应用后生效)。
> 若你的 Web 标签页里配置了 virtualenv,则必须先 `workon <虚拟环境名>` 再执行
> `pip install`,否则包装的位置 Web 应用看不到。

> **版本兼容说明**:DRF 3.18+ 要求 Django≥5.2,与本项目的 Django 4.2 LTS 冲突
> (pip 报 `ResolutionImpossible: ... depends on django>=5.2`)。requirements.txt
> 已锁定 **DRF 3.17.2**——支持 Django 4.2 的最新版本。将来升级 Django 大版本时,
> 再一并评估 DRF 升级。

## Step 3. 执行迁移

```bash
python manage.py migrate
```

**预期输出(只应出现这 5 个):**
```
Applying api.0001_initial ... OK
Applying authtoken.0001_initial ... OK
Applying authtoken.0002_auto_20160226_1747 ... OK
Applying authtoken.0003_tokenproxy ... OK
Applying authtoken.0004_alter_tokenproxy_options ... OK
```
如果看到任何 `EAW.` 开头的迁移被应用,立刻停下检查(说明改动超出预期)。

```bash
python manage.py check    # 预期: System check identified no issues
```

## Step 4. 重载 Web 应用

PythonAnywhere → **Web** 标签页 → 点击绿色 **Reload** 按钮。
(不重载则旧进程继续运行,新端点不会生效。)

## Step 5. 验证

### 5.1 网站回归(浏览器)

- [ ] 打开 https://ebbinghaus.pythonanywhere.com/ 首页正常
- [ ] 登录 → 复习页 → 条目 Markdown/公式渲染正常

### 5.2 API 冒烟测试(Bash console 或本地终端均可)

```bash
BASE=https://ebbinghaus.pythonanywhere.com/api/v1

# 1) 登录换 token
curl -s -X POST $BASE/auth/login/ -H "Content-Type: application/json" \
  -d '{"username":"<你的用户名>","password":"<你的密码>"}'
# ✅ 预期: {"token":"...","user":{...}}

# 2) 带 token 访问(TOKEN 换成上面返回值)
curl -s $BASE/me/ -H "Authorization: Token <TOKEN>"
# ✅ 预期: {"user":{...},"stats":{"total_items":...,"today_due":...}}

# 3) 未认证访问应被拒
curl -s -o /dev/null -w "%{http_code}\n" $BASE/me/
# ✅ 预期: 401 或 403
```

> 微信登录端点现在返回错误是**预期行为**(PA 的 `.env` 尚未配置
> `WECHAT_APPID`/`WECHAT_SECRET`,到 M3 做小程序时再配),不影响其他 API。

## Step 6. 顺带检查:生产 DEBUG 状态

`DEBUG` 由 PA 上**不在 git 里**的 `local_settings.py` 控制。运行:

```bash
python manage.py shell -c "from django.conf import settings; print('DEBUG =', settings.DEBUG)"
```

若输出 `DEBUG = True`:生产环境开着调试模式会泄露配置与堆栈信息,建议改为 `False`。
**但改之前先确认**:PA → Web 标签页 → Static files 映射已把 `/static/` 指到
`staticfiles/` 目录(DEBUG=False 时 Django 自身不再提供静态文件)。确认后再改。

## Step 7(可选,M2 准备):创建同步专用账号

为 NAS 同步创建一个不用于登录网站的专用超级用户:

```bash
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

把该 token 存到密码管理器(M2 配 NAS 的 `.env` 时要用)。
该账号凭 token 仅能调用快照端点与普通 API,不会出现在你的日常使用中。

---

## 回滚预案

本次改动是纯增量,回滚简单:

```bash
git checkout 2.0.0.1     # 回到上一个已部署版本
# 到 Web 标签页点 Reload
```

**数据库无需回滚**:多出来的 authtoken/api 表不影响旧代码运行。
仅当数据本身出问题,才用 Step 1 的备份整库恢复。

## 常见问题

| 现象 | 处理 |
|---|---|
| 页面 500 | Web 标签页 → Error log 查看堆栈 |
| `/api/v1/...` 404 | 确认已 Reload;确认 `git log -1` 是 2.1.0.0 |
| API 全部 401/403 | 检查请求头格式:`Authorization: Token <key>`(注意 `Token` 前缀) |
| 微信登录返回 502 | 预期行为,尚未配置 `WECHAT_APPID`/`WECHAT_SECRET` |
